import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantMixin, TimestampMixin, UUIDPKMixin


class SchoolType(str, enum.Enum):
    GOVT = "govt"
    PRIVATE = "private"
    MADRASA = "madrasa"
    COLLEGE = "college"
    OTHER = "other"


class School(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    __tablename__ = "schools"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False, index=True
    )
    name_bn: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[SchoolType] = mapped_column(Enum(SchoolType, name="school_type"), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Nullable: NULL for admin-created schools (no owner). SET NULL on the
    # owner's account deletion so the listing survives - same convention as
    # Hospital.owner_user_id. An owner is granted this by an admin (off-platform
    # vetting, Section 17 follow-up) and may manage only the one school they
    # own - see schools/router.py.
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
