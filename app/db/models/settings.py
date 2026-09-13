import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin, UUIDPKMixin


class PlatformSetting(Base, UUIDPKMixin, TimestampMixin):
    """Admin-editable integration settings (SMS gateway, Turnstile, Facebook,
    GTM, Mapbox, marketplace tuning). Env vars remain the fallback so a
    deployment can still be configured purely from the hosting secrets store
    (Section 14.5); a DB value, when present, wins."""

    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Set when a "Test Connection" check against the saved value succeeds
    # (currently only used for openai_api_key - Section 23 follow-up).
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
