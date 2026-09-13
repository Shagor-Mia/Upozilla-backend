import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantMixin, TimestampMixin, UUIDPKMixin


class ServiceCategory(Base, UUIDPKMixin):
    __tablename__ = "service_categories"

    name_bn: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_categories.id"), nullable=True
    )


class Service(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    __tablename__ = "services"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_categories.id"), nullable=False, index=True
    )
    name_bn: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_bn: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    eligibility: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_documents: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    fee: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    official_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    office_name_bn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    office_name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    office_name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    office_contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="published", nullable=False)


class LicenseApplication(Base, UUIDPKMixin, TimestampMixin):
    """Self-reported / manually-updated tracker until a real government API exists (Section 5.3, Phase 5)."""

    __tablename__ = "license_applications"

    # Nullable: SET NULL on the applicant's account deletion so the application record survives.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id"), nullable=False, index=True
    )
    application_ref_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="submitted", nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
