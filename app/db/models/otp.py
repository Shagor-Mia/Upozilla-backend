import enum
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class OtpPurpose(str, enum.Enum):
    LOGIN = "login"
    REGISTER = "register"
    VERIFY_PHONE = "verify_phone"


class OtpCode(Base, UUIDPKMixin, TimestampMixin):
    """Section 5.1: code hashed at rest, short expiry, attempt-counted.
    Consumed/expired rows are hard-deleted by the cleanup task (Section 14.4)."""

    __tablename__ = "otp_codes"

    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
