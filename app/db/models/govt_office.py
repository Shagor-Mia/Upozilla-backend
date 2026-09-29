"""Government/union office contact directory - UNO office, Upazila Parishad,
Union Parishad, police station, etc. Admin-managed only, same convention as
Hospital (no self-submission, no moderation queue)."""

import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantMixin, TimestampMixin, UUIDPKMixin


class GovtOfficeCategory(str, enum.Enum):
    UNO_OFFICE = "uno_office"
    UPAZILA_PARISHAD = "upazila_parishad"
    UNION_PARISHAD = "union_parishad"
    POLICE_STATION = "police_station"
    OTHER = "other"


class GovtOffice(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    __tablename__ = "govt_offices"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False, index=True
    )
    # values_callable: the DB enum's labels are lowercase ("other", not
    # "OTHER") - without it SQLAlchemy binds on the Python member NAME by
    # default and every insert 500s with "invalid input value for enum
    # govt_office_category".
    category: Mapped[GovtOfficeCategory] = mapped_column(
        Enum(
            GovtOfficeCategory,
            name="govt_office_category",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        index=True,
    )
    name_bn: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
