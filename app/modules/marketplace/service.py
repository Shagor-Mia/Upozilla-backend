import uuid
from collections.abc import Iterable

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.core import translation
from app.core.dependencies import CurrentUser
from app.core.i18n import localized_value
from app.core.pagination import PageParams
from app.core.rbac import Permission
from app.core.tenant import resolve_tenant_id
from app.db.models import (
    Business,
    ListingType,
    Location,
    MarketplaceCategory,
    MarketplaceProduct,
    ModerationEntityType,
    ModerationStatus,
    ProductStatus,
    User,
)
from app.modules.exchange import favorites
from app.modules.exchange.schemas import ListingSort
from app.modules.marketplace.schemas import ProductCreate, ProductResponse, ProductUpdate
from app.modules.moderation import service as moderation_service
from app.modules.sellers import service as sellers_service

# External API field names (unchanged for sellers) mapped to their `_bn` storage
# column — sellers write one language; readers can still get en/ar via
# automatic translation or a later admin correction (Section 5).
_LOCALIZED_INPUT_FIELDS = {"title": "title_bn", "description": "description_bn"}
CONTENT_FIELDS = {"title", "description", "images", "category_id", "price"}
SELLER_STATUS_TRANSITIONS = {ProductStatus.ACTIVE, ProductStatus.SOLD, ProductStatus.HIDDEN}


def _public_filter(query: Query) -> Query:
    return query.filter(
        MarketplaceProduct.status == ProductStatus.ACTIVE.value,
        MarketplaceProduct.moderation_status == ModerationStatus.APPROVED.value,
    )


# --- categories -------------------------------------------------------------------


def list_categories(db: Session) -> list[MarketplaceCategory]:
    return db.query(MarketplaceCategory).order_by(MarketplaceCategory.sort_order, MarketplaceCategory.name_bn).all()


# --- response building -------------------------------------------------------------


def to_responses(
    db: Session, products: Iterable[MarketplaceProduct], viewer: CurrentUser | None, locale: str
) -> list[ProductResponse]:
    rows = list(products)
    if not rows:
        return []
    ids = [r.id for r in rows]
    category_names = {
        c.id: localized_value(c.name_bn, c.name_en, c.name_ar, locale)
        for c in db.query(MarketplaceCategory)
        .filter(MarketplaceCategory.id.in_({r.category_id for r in rows}))
        .all()
    }
    location_names = {
        loc.id: localized_value(loc.name_bn, loc.name_en, loc.name_ar, locale)
        for loc in db.query(Location).filter(Location.id.in_({r.location_id for r in rows})).all()
    }
    business_ids = {r.business_id for r in rows if r.business_id}
    businesses = (
        {b.id: b for b in db.query(Business).filter(Business.id.in_(business_ids)).all()} if business_ids else {}
    )
    sellers = sellers_service.get_seller_summaries(db, {r.seller_user_id for r in rows})
    viewer_id = viewer.uuid if viewer else None
    favorited = favorites.favorited_ids(db, viewer_id, ListingType.MARKETPLACE, ids)
    counts = favorites.favorite_counts(db, ListingType.MARKETPLACE, ids)

    responses = []
    for r in rows:
        if r.seller_user_id not in sellers:
            continue
        business = businesses.get(r.business_id) if r.business_id else None
        responses.append(
            ProductResponse(
                id=r.id,
                business_id=r.business_id,
                business_name=localized_value(business.name_bn, business.name_en, business.name_ar, locale)
                if business
                else None,
                business_slug=business.slug if business else None,
                seller_user_id=r.seller_user_id,
                category_id=r.category_id,
                category_name=category_names.get(r.category_id, ""),
                title=localized_value(r.title_bn, r.title_en, r.title_ar, locale),
                description=localized_value(r.description_bn, r.description_en, r.description_ar, locale)
                if r.description_bn
                else None,
                price=float(r.price),
                currency=r.currency,
                condition=r.condition,
                images=r.images or [],
                location_id=r.location_id,
                location_name=location_names.get(r.location_id, ""),
                latitude=r.latitude,
                longitude=r.longitude,
                status=r.status,
                moderation_status=r.moderation_status,
                created_at=r.created_at,
                updated_at=r.updated_at,
                seller=sellers[r.seller_user_id],
                is_favorited=r.id in favorited,
                favorites_count=counts.get(r.id, 0),
            )
        )
    return responses


# --- reads -------------------------------------------------------------------------


def list_public(
    db: Session,
    *,
    category_id: uuid.UUID | None,
    location_id: uuid.UUID | None,
    business_id: uuid.UUID | None,
    q: str | None,
    condition: str | None,
    min_price: float | None,
    max_price: float | None,
    sort: ListingSort,
    page: PageParams,
) -> tuple[list[MarketplaceProduct], int]:
    query = _public_filter(db.query(MarketplaceProduct))
    if category_id is not None:
        query = query.filter(MarketplaceProduct.category_id == category_id)
    if location_id is not None:
        query = query.filter(MarketplaceProduct.location_id == location_id)
    if business_id is not None:
        query = query.filter(MarketplaceProduct.business_id == business_id)
    if condition:
        query = query.filter(MarketplaceProduct.condition == condition)
    if min_price is not None:
        query = query.filter(MarketplaceProduct.price >= min_price)
    if max_price is not None:
        query = query.filter(MarketplaceProduct.price <= max_price)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                MarketplaceProduct.title_bn.ilike(pattern),
                MarketplaceProduct.title_en.ilike(pattern),
                MarketplaceProduct.title_ar.ilike(pattern),
                MarketplaceProduct.description_bn.ilike(pattern),
                MarketplaceProduct.description_en.ilike(pattern),
                MarketplaceProduct.description_ar.ilike(pattern),
            )
        )

    total = query.count()
    if sort is ListingSort.PRICE_ASC:
        query = query.order_by(MarketplaceProduct.price.asc(), MarketplaceProduct.created_at.desc())
    elif sort is ListingSort.PRICE_DESC:
        query = query.order_by(MarketplaceProduct.price.desc(), MarketplaceProduct.created_at.desc())
    else:
        query = query.order_by(MarketplaceProduct.created_at.desc())
    return query.offset(page.offset).limit(page.page_size).all(), total


def get_by_ids_public(db: Session, ids: list[uuid.UUID]) -> list[MarketplaceProduct]:
    if not ids:
        return []
    rows = _public_filter(db.query(MarketplaceProduct)).filter(MarketplaceProduct.id.in_(ids)).all()
    order = {product_id: index for index, product_id in enumerate(ids)}
    return sorted(rows, key=lambda r: order[r.id])


def get_one(db: Session, product_id: uuid.UUID, viewer: CurrentUser | None) -> MarketplaceProduct:
    product = db.query(MarketplaceProduct).filter(MarketplaceProduct.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    is_owner = viewer is not None and product.seller_user_id == viewer.uuid
    can_moderate = viewer is not None and viewer.has_permission(Permission.MARKETPLACE_MODERATE)
    visible = (
        product.status == ProductStatus.ACTIVE.value
        and product.moderation_status == ModerationStatus.APPROVED.value
    )
    if not (visible or is_owner or can_moderate):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    return product


def list_mine(db: Session, seller: CurrentUser) -> list[MarketplaceProduct]:
    return (
        db.query(MarketplaceProduct)
        .filter(MarketplaceProduct.seller_user_id == seller.uuid)
        .order_by(MarketplaceProduct.created_at.desc())
        .all()
    )


def list_all_for_admin(db: Session, moderator: CurrentUser) -> list[MarketplaceProduct]:
    tenant_id = resolve_tenant_id(db, moderator)
    query = db.query(MarketplaceProduct)
    if tenant_id:
        query = query.filter(MarketplaceProduct.tenant_id == tenant_id)
    return query.order_by(MarketplaceProduct.created_at.desc()).limit(200).all()


# --- writes ------------------------------------------------------------------------


def _assert_category(db: Session, category_id: uuid.UUID) -> None:
    if db.query(MarketplaceCategory.id).filter(MarketplaceCategory.id == category_id).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown category")


def _assert_location(db: Session, location_id: uuid.UUID) -> None:
    if db.query(Location.id).filter(Location.id == location_id).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown location")


def _assert_business_owned(db: Session, business_id: uuid.UUID | None, seller: CurrentUser) -> None:
    if business_id is None:
        return
    business = db.query(Business).filter(Business.id == business_id).first()
    if business is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown business")
    if business.owner_user_id != seller.uuid and not seller.has_permission(Permission.MARKETPLACE_MODERATE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="you do not own this business")


def create(
    db: Session, seller: CurrentUser, payload: ProductCreate, background_tasks: BackgroundTasks
) -> MarketplaceProduct:
    _assert_category(db, payload.category_id)
    _assert_location(db, payload.location_id)
    _assert_business_owned(db, payload.business_id, seller)
    tenant_id = resolve_tenant_id(db, seller)

    product = MarketplaceProduct(
        tenant_id=tenant_id,
        seller_user_id=seller.uuid,
        title_bn=payload.title,
        description_bn=payload.description,
        **payload.model_dump(exclude={"condition", "title", "description"}),
        condition=payload.condition.value,
    )
    db.add(product)
    db.flush()
    moderation_service.enqueue_listing(
        db, entity_type=ModerationEntityType.MARKETPLACE_PRODUCT, listing=product, tenant_id=tenant_id
    )
    db.commit()
    db.refresh(product)
    translation.schedule_translations(background_tasks, MarketplaceProduct, product.id, ["title", "description"])
    return product


def _get_editable(db: Session, product_id: uuid.UUID, actor: CurrentUser) -> tuple[MarketplaceProduct, bool]:
    product = db.query(MarketplaceProduct).filter(MarketplaceProduct.id == product_id).first()
    if product is None or (product.tenant_id and product.tenant_id != resolve_tenant_id(db, actor)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product not found")
    is_owner = product.seller_user_id == actor.uuid
    if not is_owner:
        if not actor.has_permission(Permission.MARKETPLACE_MODERATE):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your listing")
        moderation_service.assert_can_moderate_location(db, actor, product.location_id)
    return product, is_owner


def update(db: Session, actor: CurrentUser, product_id: uuid.UUID, payload: ProductUpdate) -> MarketplaceProduct:
    product, is_owner = _get_editable(db, product_id, actor)
    changes = payload.model_dump(exclude_unset=True)

    if "category_id" in changes:
        _assert_category(db, changes["category_id"])
    if "location_id" in changes:
        _assert_location(db, changes["location_id"])
    if "business_id" in changes:
        _assert_business_owned(db, changes["business_id"], actor)
    if "status" in changes:
        new_status = ProductStatus(changes["status"])
        if is_owner and new_status not in SELLER_STATUS_TRANSITIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid status")
        changes["status"] = new_status.value
    if "condition" in changes and changes["condition"] is not None:
        changes["condition"] = changes["condition"].value

    for field, value in changes.items():
        setattr(product, _LOCALIZED_INPUT_FIELDS.get(field, field), value)

    if is_owner and CONTENT_FIELDS & changes.keys() and product.moderation_status == ModerationStatus.APPROVED.value:
        moderation_service.reenqueue_after_edit(
            db, entity_type=ModerationEntityType.MARKETPLACE_PRODUCT, listing=product, tenant_id=product.tenant_id
        )

    db.commit()
    db.refresh(product)
    return product


def remove(db: Session, actor: CurrentUser, product_id: uuid.UUID) -> None:
    product, _ = _get_editable(db, product_id, actor)
    product.status = ProductStatus.HIDDEN.value
    db.commit()


def reveal_seller_phone(db: Session, product: MarketplaceProduct) -> tuple[str, str]:
    seller = db.query(User).filter(User.id == product.seller_user_id).first()
    if seller is None or not seller.phone or seller.phone_verified_at is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="seller has no verified phone")
    return seller.full_name, seller.phone
