import uuid
from collections.abc import Iterable

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Query, Session

from app.core import translation
from app.core.dependencies import CurrentUser
from app.core.i18n import localized_value
from app.core.pagination import PageParams
from app.core.rbac import Permission
from app.core.tenant import resolve_tenant_id
from app.db.models import Market, ModerationEntityType, ModerationStatus, Shop, ShopCategory, ShopStatus
from app.modules.moderation import service as moderation_service
from app.modules.sellers import service as sellers_service
from app.modules.shops.schemas import ShopCreate, ShopResponse, ShopUpdate, to_response

CONTENT_FIELDS = {"name", "description", "images", "category_id"}


def _public_filter(query: Query) -> Query:
    return query.filter(
        Shop.status == ShopStatus.ACTIVE.value,
        Shop.moderation_status == ModerationStatus.APPROVED.value,
    )


# --- categories ---------------------------------------------------------------------


def list_categories(db: Session) -> list[ShopCategory]:
    return db.query(ShopCategory).order_by(ShopCategory.sort_order, ShopCategory.name_bn).all()


# --- response building ---------------------------------------------------------------


def to_responses(db: Session, shops: Iterable[Shop], locale: str) -> list[ShopResponse]:
    rows = list(shops)
    if not rows:
        return []
    market_names = {
        m.id: localized_value(m.name_bn, m.name_en, m.name_ar, locale)
        for m in db.query(Market).filter(Market.id.in_({r.market_id for r in rows})).all()
    }
    category_names = {
        c.id: localized_value(c.name_bn, c.name_en, c.name_ar, locale) for c in db.query(ShopCategory).all()
    }
    sellers = sellers_service.get_seller_summaries(db, {r.seller_user_id for r in rows})

    responses = []
    for r in rows:
        if r.seller_user_id not in sellers:
            continue
        responses.append(
            to_response(
                r,
                market_name=market_names.get(r.market_id, ""),
                category_name=category_names.get(r.category_id, ""),
                locale=locale,
                seller=sellers[r.seller_user_id],
            )
        )
    return responses


# --- reads -----------------------------------------------------------------------------


def list_public(
    db: Session,
    *,
    market_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    featured_only: bool,
    page: PageParams,
) -> tuple[list[Shop], int]:
    query = _public_filter(db.query(Shop))
    if market_id is not None:
        query = query.filter(Shop.market_id == market_id)
    if category_id is not None:
        query = query.filter(Shop.category_id == category_id)
    if featured_only:
        query = query.filter(Shop.is_featured.is_(True))
    total = query.count()
    rows = (
        query.order_by(Shop.is_featured.desc(), Shop.created_at.desc())
        .offset(page.offset)
        .limit(page.page_size)
        .all()
    )
    return rows, total


def get_for_admin(db: Session, shop_id: uuid.UUID) -> Shop:
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="shop not found")
    return shop


def get_one(db: Session, shop_id: uuid.UUID, viewer: CurrentUser | None) -> Shop:
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if shop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="shop not found")
    is_owner = viewer is not None and shop.seller_user_id == viewer.uuid
    can_moderate = viewer is not None and viewer.has_permission(Permission.MARKETPLACE_MODERATE)
    visible = shop.status == ShopStatus.ACTIVE.value and shop.moderation_status == ModerationStatus.APPROVED.value
    if not (visible or is_owner or can_moderate):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="shop not found")
    return shop


def list_mine(db: Session, seller: CurrentUser) -> list[Shop]:
    return db.query(Shop).filter(Shop.seller_user_id == seller.uuid).order_by(Shop.created_at.desc()).all()


def list_all_for_admin(db: Session, moderator: CurrentUser) -> list[Shop]:
    tenant_id = resolve_tenant_id(db, moderator)
    query = db.query(Shop)
    if tenant_id:
        query = query.filter(Shop.tenant_id == tenant_id)
    return query.order_by(Shop.created_at.desc()).limit(200).all()


# --- writes -----------------------------------------------------------------------------


def _get_market(db: Session, market_id: uuid.UUID) -> Market:
    market = db.query(Market).filter(Market.id == market_id).first()
    if market is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown market")
    return market


def _assert_category(db: Session, category_id: uuid.UUID) -> None:
    if db.query(ShopCategory.id).filter(ShopCategory.id == category_id).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown category")


def create(db: Session, seller: CurrentUser, payload: ShopCreate, background_tasks: BackgroundTasks) -> Shop:
    market = _get_market(db, payload.market_id)
    _assert_category(db, payload.category_id)
    tenant_id = resolve_tenant_id(db, seller)

    shop = Shop(
        tenant_id=tenant_id,
        seller_user_id=seller.uuid,
        market_id=market.id,
        location_id=market.location_id,
        category_id=payload.category_id,
        name_bn=payload.name,
        description_bn=payload.description,
        contact_phone=payload.contact_phone,
        images=payload.images,
    )
    db.add(shop)
    db.flush()
    moderation_service.enqueue_listing(db, entity_type=ModerationEntityType.SHOP, listing=shop, tenant_id=tenant_id)
    db.commit()
    db.refresh(shop)
    translation.schedule_translations(background_tasks, Shop, shop.id, ["name", "description"])
    return shop


def _get_editable(db: Session, shop_id: uuid.UUID, actor: CurrentUser) -> tuple[Shop, bool]:
    shop = db.query(Shop).filter(Shop.id == shop_id).first()
    if shop is None or (shop.tenant_id and shop.tenant_id != resolve_tenant_id(db, actor)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="shop not found")
    is_owner = shop.seller_user_id == actor.uuid
    if not is_owner:
        if not actor.has_permission(Permission.MARKETPLACE_MODERATE):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your shop")
        moderation_service.assert_can_moderate_location(db, actor, shop.location_id)
    return shop, is_owner


def update(db: Session, actor: CurrentUser, shop_id: uuid.UUID, payload: ShopUpdate) -> Shop:
    shop, is_owner = _get_editable(db, shop_id, actor)
    changes = payload.model_dump(exclude_unset=True)

    if "category_id" in changes:
        _assert_category(db, changes["category_id"])
    if "status" in changes and changes["status"] is not None:
        changes["status"] = changes["status"].value
    if "is_featured" in changes and not actor.has_permission(Permission.MARKETPLACE_MODERATE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="only a moderator can feature a shop")

    field_map = {"name": "name_bn", "description": "description_bn"}
    for field, value in changes.items():
        setattr(shop, field_map.get(field, field), value)

    if is_owner and CONTENT_FIELDS & changes.keys() and shop.moderation_status == ModerationStatus.APPROVED.value:
        moderation_service.reenqueue_after_edit(
            db, entity_type=ModerationEntityType.SHOP, listing=shop, tenant_id=shop.tenant_id
        )

    db.commit()
    db.refresh(shop)
    return shop
