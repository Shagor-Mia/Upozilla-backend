"""Shared lookups over both listing kinds (favorites, reports, messaging and
reviews all take a `(listing_type, listing_id)` pair)."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import (
    ExchangeListing,
    ListingStatus,
    ListingType,
    MarketplaceProduct,
    ModerationStatus,
    ProductStatus,
)

Listing = ExchangeListing | MarketplaceProduct


def find_listing(db: Session, listing_type: ListingType, listing_id: uuid.UUID) -> Listing | None:
    if listing_type is ListingType.EXCHANGE:
        return db.query(ExchangeListing).filter(ExchangeListing.id == listing_id).first()
    return db.query(MarketplaceProduct).filter(MarketplaceProduct.id == listing_id).first()


def is_publicly_visible(listing: Listing) -> bool:
    active = ListingStatus.ACTIVE.value if isinstance(listing, ExchangeListing) else ProductStatus.ACTIVE.value
    return listing.status == active and listing.moderation_status == ModerationStatus.APPROVED.value


def get_public_listing(db: Session, listing_type: ListingType, listing_id: uuid.UUID) -> Listing:
    listing = find_listing(db, listing_type, listing_id)
    if listing is None or not is_publicly_visible(listing):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing not found")
    return listing
