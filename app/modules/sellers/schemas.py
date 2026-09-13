import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models.exchange import ListingType


class SellerSummary(BaseModel):
    """Public seller identity embedded in listing responses. Phone is masked
    (Section 14.4) - the full number comes from the rate-limited contact endpoint."""

    id: uuid.UUID
    full_name: str
    phone_masked: str | None
    phone_verified: bool
    member_since: datetime
    trust_score: int
    avg_rating: float | None
    review_count: int


class SellerReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)
    listing_type: ListingType | None = None
    listing_id: uuid.UUID | None = None


class SellerReviewResponse(BaseModel):
    id: uuid.UUID
    seller_user_id: uuid.UUID | None
    reviewer_user_id: uuid.UUID | None
    reviewer_name: str
    listing_type: str | None
    listing_id: uuid.UUID | None
    rating: int
    comment: str | None
    created_at: datetime


class SellerProfileResponse(SellerSummary):
    active_listings: int
    total_listings: int
    reviews: list[SellerReviewResponse]


class ContactRevealResponse(BaseModel):
    seller_name: str
    phone: str
