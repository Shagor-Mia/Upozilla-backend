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


def get_public_listing(
    db: Session, listing_type: ListingType, listing_id: uuid.UUID, *, tenant_id: uuid.UUID | None = None
) -> Listing:
    """`tenant_id` (normally the caller's own resolved tenant) is enforced the
    same permissive way as `content_scope.assert_tenant_match`: a listing with
    no `tenant_id` of its own (legacy/unbackfilled) is never hidden, but a
    listing that belongs to a *different* tenant 404s instead of letting one
    tenant's user favorite, report or contact-reveal another tenant's listing."""
    listing = find_listing(db, listing_type, listing_id)
    if (
        listing is None
        or not is_publicly_visible(listing)
        or (tenant_id is not None and listing.tenant_id and listing.tenant_id != tenant_id)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="listing not found")
    return listing
