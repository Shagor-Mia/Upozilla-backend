import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class LocationType(str, enum.Enum):
    DIVISION = "division"
    DISTRICT = "district"
    UPAZILA = "upazila"
    UNION = "union"
    VILLAGE = "village"


class Location(Base, UUIDPKMixin, TimestampMixin):
    """Division -> District -> Upazila -> Union -> Village/Ward, self-referential."""

    __tablename__ = "locations"

    type: Mapped[LocationType] = mapped_column(Enum(LocationType, name="location_type"), nullable=False)
    name_bn: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True
    )
