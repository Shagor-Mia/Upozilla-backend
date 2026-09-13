"""Shops inside a Market (bazaar) - shopkeeper self-submitted, moderated the
same way marketplace/exchange listings are (Section 5.7 pattern reused)."""

import enum
import uuid

from sqlalchemy import ARRAY, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantMixin, TimestampMixin, UUIDPKMixin
from app.db.models.marketplace import ModerationStatus


class ShopStatus(str, enum.Enum):
    ACTIVE = "active"
    HIDDEN = "hidden"  # soft-delete, same convention as ProductStatus


class ShopCategory(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "shop_categories"

    name_bn: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name_ar: Mapped[str | None] = mapped_column(String(100), nullable=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Shop(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    __tablename__ = "shops"

    market_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("markets.id"), nullable=False, index=True
    )
    # Named to match ExchangeListing/MarketplaceProduct's "listing owner" convention
    # (app/modules/moderation/service.py's generic enqueue_listing()/reenqueue_after_edit()
    # duck-type on `.seller_user_id`) - the shopkeeper, not necessarily a "seller".
    # Nullable: SET NULL on the shopkeeper's account deletion so the shop listing survives.
    seller_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shop_categories.id"), nullable=False, index=True
    )
    # Denormalised copy of the market's location_id at creation time (same convention as
    # MarketplaceProduct.location_id) so moderation queue location-scoping doesn't need a join.
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False, index=True
    )
    name_bn: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name_ar: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description_bn: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    images: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    # Admin/moderator-set only (app/modules/shops/service.py:update) - highlighted
    # above the regular grid on the market detail page.
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default=ShopStatus.ACTIVE.value, nullable=False, index=True)
    # Denormalised copy of the moderation_queue outcome, same convention as
    # MarketplaceProduct/ExchangeListing (moderation/service.py).
    moderation_status: Mapped[str] = mapped_column(
        String(20), default=ModerationStatus.PENDING.value, nullable=False, index=True
    )
