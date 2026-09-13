import enum
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantMixin, TimestampMixin, UUIDPKMixin


class NewsSourceType(str, enum.Enum):
    RSS = "rss"
    API = "api"
    FACEBOOK_PAGE = "facebook_page"  # Phase 3+, see Section 5.10


class NewsSource(Base, UUIDPKMixin):
    __tablename__ = "news_sources"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    feed_url: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[NewsSourceType] = mapped_column(Enum(NewsSourceType, name="news_source_type"), nullable=False)
    is_licensed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class NewsArticle(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    __tablename__ = "news_articles"
    __table_args__ = (CheckConstraint("status IN ('draft', 'published')", name="ck_news_articles_status"),)

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("news_sources.id"), nullable=False, index=True
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("locations.id"), nullable=True, index=True
    )
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    # Phase 4 AI layer: filled by an editor or, if left blank, by news_ai.enrich()
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
