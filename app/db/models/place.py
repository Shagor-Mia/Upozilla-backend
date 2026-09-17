import enum
import uuid

from sqlalchemy import ARRAY, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantMixin, TimestampMixin, UUIDPKMixin


class PlaceCategory(str, enum.Enum):
    TOURIST = "tourist"
    RESTAURANT = "restaurant"
    PARK = "park"
    HISTORICAL = "historical"
    RELIGIOUS = "religious"
    NATURAL = "natural"
    SHOP = "shop"
    OTHER = "other"


class Place(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    __tablename__ = "places"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False, index=True
    )
    name_bn: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    category: Mapped[PlaceCategory] = mapped_column(Enum(PlaceCategory, name="place_category"), nullable=False)
    description_bn: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    gallery: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_featured: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="published", nullable=False)
    # Denormalised copy of the moderation_queue outcome, same pattern as
    # MarketplaceProduct.moderation_status - public queries filter on this
    # directly instead of joining moderation_queue. Admin-created places
    # (POST /places, CONTENT_MANAGE) are approved immediately; user-submitted
    # places (POST /places/submit) always start pending - no trust-score
    # auto-approve for this entity type, per product decision.
    moderation_status: Mapped[str] = mapped_column(String(20), default="approved", nullable=False, index=True)
    # Nullable: NULL for admin-created places (no submitter) and SET NULL on
    # the submitter's account deletion so the place survives. Named
    # `seller_user_id` (not `submitted_by`) to match the attribute name the
    # shared moderation service (app/modules/moderation/service.py) already
    # expects on every moderatable entity - see Shop for the same convention
    # on a non-"seller" entity.
    seller_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )


class PlaceReview(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "place_reviews"

    place_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("places.id"), nullable=False, index=True
    )
    # Nullable: SET NULL on the reviewer's account deletion so the review survives (anonymized).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
