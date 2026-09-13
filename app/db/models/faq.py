from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantMixin, TimestampMixin, UUIDPKMixin


class Faq(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    """Minimal admin-managed FAQ content type, added in Phase 4 (Section
    5.13 lists `faq` as a knowledge-base source type but no FAQ content
    model existed yet). Same bn/en/ar shape as every other Section 22.2
    localized content table."""

    __tablename__ = "faqs"
    __table_args__ = (CheckConstraint("status IN ('draft', 'published')", name="ck_faqs_status"),)

    question_bn: Mapped[str] = mapped_column(String(500), nullable=False)
    question_en: Mapped[str | None] = mapped_column(String(500), nullable=True)
    question_ar: Mapped[str | None] = mapped_column(String(500), nullable=True)
    answer_bn: Mapped[str] = mapped_column(Text, nullable=False)
    answer_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="published", nullable=False)
