"""Union Parishad representative directory - a citizen-services contact list,
not an RBAC/permissions concern (Section: new civic directory feature). Each
row links an existing user account to a location + elected position; the
person authenticates the same way as any citizen (phone OTP) and self-edits
only their own bio/photo through the ownership check in the service layer."""

import enum
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantMixin, TimestampMixin, UUIDPKMixin


class RepresentativePosition(str, enum.Enum):
    CHAIRMAN = "chairman"
    WOMEN_MEMBER = "women_member"
    WARD_MEMBER = "ward_member"


class RepresentativeStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Representative(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    __tablename__ = "representatives"

    # Nullable: SET NULL on the linked account's deletion so the civic record survives.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Union for chairman/women_member; a village (or union, if wards aren't
    # mapped to individual villages yet) for ward_member.
    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=False, index=True
    )
    position: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    bio_bn: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    bio_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=RepresentativeStatus.ACTIVE.value, nullable=False, index=True
    )
