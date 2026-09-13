import enum
import uuid

from sqlalchemy import ARRAY, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantMixin, TimestampMixin, UUIDPKMixin


class PlaceCategory(str, enum.Enum):
    TOURIST = "tourist"
    PARK = "park"
    HISTORICAL = "historical"
    RELIGIOUS = "religious"
    NATURAL = "natural"
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
