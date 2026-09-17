import enum
import uuid

from sqlalchemy import ARRAY, Enum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantMixin, TimestampMixin, UUIDPKMixin


class HospitalType(str, enum.Enum):
    GOVT = "govt"
    PRIVATE = "private"
    CLINIC = "clinic"


class Hospital(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    __tablename__ = "hospitals"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False, index=True
    )
    name_bn: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[HospitalType] = mapped_column(Enum(HospitalType, name="hospital_type"), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    images: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    services: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    # Separate from `contact` (the hospital's general hotline) so the ambulance
    # directory page can list only hospitals that actually offer the service.
    ambulance_contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Nullable: NULL for admin-created hospitals (no owner). SET NULL on the
    # owner's account deletion so the listing survives - same convention as
    # Business.owner_user_id / Shop.seller_user_id. An owner is granted this
    # by an admin (off-platform vetting, Section 17 follow-up) and may manage
    # only the one hospital they own - see hospitals/router.py.
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )


class Doctor(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "doctors"

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    specialty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chamber_days: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    chamber_hours: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
