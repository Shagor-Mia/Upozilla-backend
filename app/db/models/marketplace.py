"""Section 5.7 - Local Market (business/B2C leaning). Shares
`marketplace_categories` with the exchange module."""

import enum
import uuid
from decimal import Decimal

from sqlalchemy import ARRAY, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantMixin, TimestampMixin, UUIDPKMixin


class ItemCondition(str, enum.Enum):
    NEW = "new"
    USED = "used"


class ProductStatus(str, enum.Enum):
    ACTIVE = "active"
    SOLD = "sold"
    HIDDEN = "hidden"  # soft-delete (Section 20.3: listings soft-delete via status)


class ModerationStatus(str, enum.Enum):
    """Denormalised copy of the listing's `moderation_queue` outcome so public
    list queries don't need a join."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MarketplaceCategory(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "marketplace_categories"

    name_bn: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name_en: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name_ar: Mapped[str | None] = mapped_column(String(100), nullable=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_categories.id"), nullable=True
    )
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class MarketplaceProduct(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    __tablename__ = "marketplace_products"

    business_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=True, index=True
    )
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
    currency: Mapped[str] = mapped_column(String(3), default="BDT", nullable=False)
    condition: Mapped[str] = mapped_column(String(10), default=ItemCondition.NEW.value, nullable=False)
    images: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False, index=True
    )
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=ProductStatus.ACTIVE.value, nullable=False, index=True)
    moderation_status: Mapped[str] = mapped_column(
        String(20), default=ModerationStatus.PENDING.value, nullable=False, index=True
    )
