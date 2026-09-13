"""Section 5.8 - Exchange / classifieds (OLX-style C2C) plus the favorites,
reports and seller-review tables shared with the marketplace module.

`listing_type` on favorites/reports/conversations lets one table serve both
listing kinds (Section 10 splits them into two modules that share UI)."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantMixin, TimestampMixin, UUIDPKMixin
from app.db.models.marketplace import ItemCondition, ModerationStatus


class ListingType(str, enum.Enum):
    EXCHANGE = "exchange"
    MARKETPLACE = "marketplace"


class ListingStatus(str, enum.Enum):
    ACTIVE = "active"
    SOLD = "sold"
    EXPIRED = "expired"
    REPORTED = "reported"  # hidden after a report was upheld by moderation
    REMOVED = "removed"  # seller soft-delete


class ReportStatus(str, enum.Enum):
    OPEN = "open"
    UPHELD = "upheld"
    DISMISSED = "dismissed"


class ExchangeListing(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    __tablename__ = "exchange_listings"

    # Nullable: SET NULL on the seller's account deletion so buyer-visible history survives.
    seller_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_categories.id"), nullable=False, index=True
    )
    title_bn: Mapped[str] = mapped_column(String(200), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(200), nullable=True)
    title_ar: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description_bn: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_negotiable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    condition: Mapped[str] = mapped_column(String(10), default=ItemCondition.USED.value, nullable=False)
    images: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False, index=True
    )
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=ListingStatus.ACTIVE.value, nullable=False, index=True)
    moderation_status: Mapped[str] = mapped_column(
        String(20), default=ModerationStatus.PENDING.value, nullable=False, index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class ListingFavorite(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "listing_favorites"
    __table_args__ = (UniqueConstraint("user_id", "listing_type", "listing_id", name="uq_favorite_user_listing"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    listing_type: Mapped[str] = mapped_column(String(20), nullable=False)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)


class ListingReport(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    __tablename__ = "listing_reports"

    listing_type: Mapped[str] = mapped_column(String(20), nullable=False)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # Nullable: SET NULL on the reporter's account deletion so the report survives for moderation history.
    reporter_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=ReportStatus.OPEN.value, nullable=False, index=True)


class SellerReview(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    """Buyer -> seller rating after a transaction (Section 10 trust progression:
    "Ratings/Reviews"). Feeds `user_trust_scores.avg_rating`."""

    __tablename__ = "seller_reviews"
    __table_args__ = (
        UniqueConstraint("seller_user_id", "reviewer_user_id", "listing_type", "listing_id", name="uq_review_per_listing"),
        # The constraint above is a no-op for general reviews (listing_type/listing_id
        # both NULL) - Postgres treats NULL as distinct in unique constraints, so a
        # buyer could otherwise submit unlimited duplicate general reviews. This partial
        # index closes that gap: at most one general review per (seller, reviewer).
        Index(
            "uq_seller_reviews_general",
            "seller_user_id",
            "reviewer_user_id",
            unique=True,
            postgresql_where=text("listing_id IS NULL"),
        ),
    )

    # Nullable: SET NULL on either party's account deletion so the review survives (anonymized).
    seller_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    listing_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    listing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
