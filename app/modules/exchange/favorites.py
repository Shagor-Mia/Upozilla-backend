import uuid
from collections.abc import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import ListingFavorite, ListingType
from app.modules.exchange.lookup import get_public_listing


def set_favorite(db: Session, user_id: uuid.UUID, listing_type: ListingType, listing_id: uuid.UUID, on: bool) -> bool:
    get_public_listing(db, listing_type, listing_id)
    existing = (
        db.query(ListingFavorite)
        .filter(
            ListingFavorite.user_id == user_id,
            ListingFavorite.listing_type == listing_type.value,
            ListingFavorite.listing_id == listing_id,
        )
        .first()
    )
    if on and existing is None:
        db.add(ListingFavorite(user_id=user_id, listing_type=listing_type.value, listing_id=listing_id))
    elif not on and existing is not None:
        db.delete(existing)
    db.commit()
    return on


def favorited_ids(
    db: Session, user_id: uuid.UUID | None, listing_type: ListingType, listing_ids: Iterable[uuid.UUID]
) -> set[uuid.UUID]:
    ids = list(listing_ids)
    if user_id is None or not ids:
        return set()
    rows = (
        db.query(ListingFavorite.listing_id)
        .filter(
            ListingFavorite.user_id == user_id,
            ListingFavorite.listing_type == listing_type.value,
            ListingFavorite.listing_id.in_(ids),
        )
        .all()
    )
    return {r[0] for r in rows}


def favorite_counts(db: Session, listing_type: ListingType, listing_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, int]:
    ids = list(listing_ids)
    if not ids:
        return {}
    rows = (
        db.query(ListingFavorite.listing_id, func.count(ListingFavorite.id))
        .filter(ListingFavorite.listing_type == listing_type.value, ListingFavorite.listing_id.in_(ids))
        .group_by(ListingFavorite.listing_id)
        .all()
    )
    return {listing_id: int(count) for listing_id, count in rows}


def list_user_favorites(db: Session, user_id: uuid.UUID) -> dict[ListingType, list[uuid.UUID]]:
    rows = (
        db.query(ListingFavorite.listing_type, ListingFavorite.listing_id)
        .filter(ListingFavorite.user_id == user_id)
        .order_by(ListingFavorite.created_at.desc())
        .all()
    )
    grouped: dict[ListingType, list[uuid.UUID]] = {ListingType.EXCHANGE: [], ListingType.MARKETPLACE: []}
    for listing_type, listing_id in rows:
        grouped[ListingType(listing_type)].append(listing_id)
    return grouped
