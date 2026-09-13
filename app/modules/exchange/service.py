import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.core import runtime_settings, translation
from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.core.i18n import localized_value
from app.core.pagination import PageParams
from app.core.rbac import Permission
from app.core.tenant import resolve_tenant_id
from app.db.models import (
    ExchangeListing,
    ListingStatus,
    ListingType,
    Location,
    MarketplaceCategory,
    ModerationEntityType,
    ModerationStatus,
    User,
)
from app.modules.exchange import favorites
from app.modules.exchange.schemas import (
    ExchangeListingCreate,
    ExchangeListingResponse,
    ExchangeListingUpdate,
    ListingSort,
)
from app.modules.moderation import service as moderation_service
from app.modules.sellers import service as sellers_service

# External API field names (unchanged for sellers) mapped to their `_bn` storage column.
_LOCALIZED_INPUT_FIELDS = {"title": "title_bn", "description": "description_bn"}
# Fields whose edits send an approved listing back through moderation.
CONTENT_FIELDS = {"title", "description", "images", "category_id", "price"}
SELLER_STATUS_TRANSITIONS = {ListingStatus.ACTIVE, ListingStatus.SOLD, ListingStatus.REMOVED}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ttl_days() -> int:
    return runtime_settings.get_int("exchange_listing_ttl_days", settings.EXCHANGE_LISTING_TTL_DAYS)


def _public_filter(query: Query) -> Query:
    return query.filter(
        ExchangeListing.status == ListingStatus.ACTIVE.value,
        ExchangeListing.moderation_status == ModerationStatus.APPROVED.value,
    )


# --- response building -------------------------------------------------------------


def to_responses(
    db: Session, listings: Iterable[ExchangeListing], viewer: CurrentUser | None, locale: str
) -> list[ExchangeListingResponse]:
    rows = list(listings)
    if not rows:
        return []
    ids = [r.id for r in rows]
    category_names = {
        c.id: localized_value(c.name_bn, c.name_en, c.name_ar, locale) for c in db.query(MarketplaceCategory).all()
    }
    location_names = {
        loc.id: localized_value(loc.name_bn, loc.name_en, loc.name_ar, locale)
        for loc in db.query(Location).filter(Location.id.in_({r.location_id for r in rows})).all()
    }
    sellers = sellers_service.get_seller_summaries(db, {r.seller_user_id for r in rows})
    viewer_id = viewer.uuid if viewer else None
    favorited = favorites.favorited_ids(db, viewer_id, ListingType.EXCHANGE, ids)
    counts = favorites.favorite_counts(db, ListingType.EXCHANGE, ids)

    return [
        ExchangeListingResponse(
            id=r.id,
            seller_user_id=r.seller_user_id,
            category_id=r.category_id,
            category_name=category_names.get(r.category_id, ""),
            title=localized_value(r.title_bn, r.title_en, r.title_ar, locale),
            description=localized_value(r.description_bn, r.description_en, r.description_ar, locale)
            if r.description_bn
            else None,
            price=float(r.price),
            is_negotiable=r.is_negotiable,
            condition=r.condition,
            images=r.images or [],
            location_id=r.location_id,
            location_name=location_names.get(r.location_id, ""),
            latitude=r.latitude,
            longitude=r.longitude,
            status=r.status,
            moderation_status=r.moderation_status,
            expires_at=r.expires_at,
            created_at=r.created_at,
            updated_at=r.updated_at,
            seller=sellers[r.seller_user_id],
            is_favorited=r.id in favorited,
            favorites_count=counts.get(r.id, 0),
        )
        for r in rows
        if r.seller_user_id in sellers
    ]


# --- reads -------------------------------------------------------------------------


def list_public(
    db: Session,
    *,
    category_id: uuid.UUID | None,
    location_id: uuid.UUID | None,
    q: str | None,
    condition: str | None,
    min_price: float | None,
    max_price: float | None,
    sort: ListingSort,
    page: PageParams,
) -> tuple[list[ExchangeListing], int]:
    query = _public_filter(db.query(ExchangeListing))
    if category_id is not None:
        query = query.filter(ExchangeListing.category_id == category_id)
    if location_id is not None:
        query = query.filter(ExchangeListing.location_id == location_id)
    if condition:
        query = query.filter(ExchangeListing.condition == condition)
    if min_price is not None:
        query = query.filter(ExchangeListing.price >= min_price)
    if max_price is not None:
        query = query.filter(ExchangeListing.price <= max_price)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                ExchangeListing.title_bn.ilike(pattern),
                ExchangeListing.title_en.ilike(pattern),
                ExchangeListing.title_ar.ilike(pattern),
                ExchangeListing.description_bn.ilike(pattern),
                ExchangeListing.description_en.ilike(pattern),
                ExchangeListing.description_ar.ilike(pattern),
            )
        )

    total = query.count()
    if sort is ListingSort.PRICE_ASC:
        query = query.order_by(ExchangeListing.price.asc(), ExchangeListing.created_at.desc())
    elif sort is ListingSort.PRICE_DESC:
        query = query.order_by(ExchangeListing.price.desc(), ExchangeListing.created_at.desc())
    else:
        query = query.order_by(ExchangeListing.created_at.desc())
    return query.offset(page.offset).limit(page.page_size).all(), total


def get_by_ids_public(db: Session, ids: list[uuid.UUID]) -> list[ExchangeListing]:
    if not ids:
        return []
    rows = _public_filter(db.query(ExchangeListing)).filter(ExchangeListing.id.in_(ids)).all()
    order = {listing_id: index for index, listing_id in enumerate(ids)}
    return sorted(rows, key=lambda r: order[r.id])


def get_one(db: Session, listing_id: uuid.UUID, viewer: CurrentUser | None) -> ExchangeListing:
    """Public visibility unless the viewer owns it or can moderate (they see drafts/pending)."""
    listing = db.query(ExchangeListing).filter(ExchangeListing.id == listing_id).first()
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing not found")
    is_owner = viewer is not None and listing.seller_user_id == viewer.uuid
    can_moderate = viewer is not None and viewer.has_permission(Permission.MARKETPLACE_MODERATE)
    visible = (
        listing.status == ListingStatus.ACTIVE.value
        and listing.moderation_status == ModerationStatus.APPROVED.value
    )
    if not (visible or is_owner or can_moderate):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing not found")
    return listing


def list_all_for_admin(db: Session, moderator: CurrentUser) -> list[ExchangeListing]:
    tenant_id = resolve_tenant_id(db, moderator)
    query = db.query(ExchangeListing)
    if tenant_id:
        query = query.filter(ExchangeListing.tenant_id == tenant_id)
    return query.order_by(ExchangeListing.created_at.desc()).limit(200).all()


def list_mine(db: Session, seller: CurrentUser) -> list[ExchangeListing]:
    return (
        db.query(ExchangeListing)
        .filter(ExchangeListing.seller_user_id == seller.uuid, ExchangeListing.status != ListingStatus.REMOVED.value)
        .order_by(ExchangeListing.created_at.desc())
        .all()
    )


# --- writes (phone-verified sellers only, enforced by the router dependency) -------


def _assert_category(db: Session, category_id: uuid.UUID) -> None:
    if db.query(MarketplaceCategory.id).filter(MarketplaceCategory.id == category_id).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown category")


def _assert_location(db: Session, location_id: uuid.UUID) -> None:
    if db.query(Location.id).filter(Location.id == location_id).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown location")


def create(
    db: Session, seller: CurrentUser, payload: ExchangeListingCreate, background_tasks: BackgroundTasks
) -> ExchangeListing:
    _assert_category(db, payload.category_id)
    _assert_location(db, payload.location_id)
    tenant_id = resolve_tenant_id(db, seller)

    listing = ExchangeListing(
        tenant_id=tenant_id,
        seller_user_id=seller.uuid,
        expires_at=_now() + timedelta(days=_ttl_days()),
        title_bn=payload.title,
        description_bn=payload.description,
        **payload.model_dump(exclude={"condition", "title", "description"}),
        condition=payload.condition.value,
    )
    db.add(listing)
    db.flush()
    moderation_service.enqueue_listing(
        db, entity_type=ModerationEntityType.EXCHANGE_LISTING, listing=listing, tenant_id=tenant_id
    )
    db.commit()
    db.refresh(listing)
    translation.schedule_translations(background_tasks, ExchangeListing, listing.id, ["title", "description"])
    return listing


def _get_editable(db: Session, listing_id: uuid.UUID, actor: CurrentUser) -> tuple[ExchangeListing, bool]:
    """Section 14.1 object-level authorization: owner or a moderator, within the actor's tenant."""
    listing = db.query(ExchangeListing).filter(ExchangeListing.id == listing_id).first()
    if listing is None or (listing.tenant_id and listing.tenant_id != resolve_tenant_id(db, actor)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing not found")
    is_owner = listing.seller_user_id == actor.uuid
    if not is_owner:
        if not actor.has_permission(Permission.MARKETPLACE_MODERATE):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your listing")
        moderation_service.assert_can_moderate_location(db, actor, listing.location_id)
    return listing, is_owner


def update(db: Session, actor: CurrentUser, listing_id: uuid.UUID, payload: ExchangeListingUpdate) -> ExchangeListing:
    listing, is_owner = _get_editable(db, listing_id, actor)
    changes = payload.model_dump(exclude_unset=True)

    if "category_id" in changes:
        _assert_category(db, changes["category_id"])
    if "location_id" in changes:
        _assert_location(db, changes["location_id"])
    if "status" in changes:
        new_status = ListingStatus(changes["status"])
        if is_owner and new_status not in SELLER_STATUS_TRANSITIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="sellers can only mark active, sold or removed")
        changes["status"] = new_status.value
        if new_status is ListingStatus.ACTIVE and listing.status == ListingStatus.EXPIRED.value:
            listing.expires_at = _now() + timedelta(days=_ttl_days())
    if "condition" in changes and changes["condition"] is not None:
        changes["condition"] = changes["condition"].value

    for field, value in changes.items():
        setattr(listing, _LOCALIZED_INPUT_FIELDS.get(field, field), value)

    if is_owner and CONTENT_FIELDS & changes.keys() and listing.moderation_status == ModerationStatus.APPROVED.value:
        moderation_service.reenqueue_after_edit(
            db, entity_type=ModerationEntityType.EXCHANGE_LISTING, listing=listing, tenant_id=listing.tenant_id
        )

    db.commit()
    db.refresh(listing)
    return listing


def remove(db: Session, actor: CurrentUser, listing_id: uuid.UUID) -> None:
    listing, _ = _get_editable(db, listing_id, actor)
    listing.status = ListingStatus.REMOVED.value
    db.commit()


def reveal_seller_phone(db: Session, listing: ExchangeListing) -> tuple[str, str]:
    seller = db.query(User).filter(User.id == listing.seller_user_id).first()
    if seller is None or not seller.phone or seller.phone_verified_at is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="seller has no verified phone")
    return seller.full_name, seller.phone


def expire_stale(db: Session) -> int:
    """Celery beat: active listings past `expires_at` become `expired`."""
    count = (
        db.query(ExchangeListing)
        .filter(ExchangeListing.status == ListingStatus.ACTIVE.value, ExchangeListing.expires_at < _now())
        .update({ExchangeListing.status: ListingStatus.EXPIRED.value}, synchronize_session=False)
    )
    db.commit()
    return count
