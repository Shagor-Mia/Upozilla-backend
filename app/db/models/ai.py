"""Section 5.13 AI / Vector (Phase 4) - pgvector knowledge base over existing
content (places, government services, hospitals, markets, news, FAQs)."""

import enum
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantMixin, TimestampMixin, UUIDPKMixin

EMBEDDING_DIMENSIONS = 1536  # matches OpenAI text-embedding-3-small


class KnowledgeSourceType(str, enum.Enum):
    PLACE = "place"
    SERVICE = "service"
    HOSPITAL = "hospital"
    MARKET = "market"
    NEWS = "news"
    FAQ = "faq"


class KnowledgeChunk(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    """One embedded row per source item. `tenant_id`/`updated_at` added
    beyond Section 5.13's schema sketch per Section 20.3/21 rule 4 (every
    new table keeps tenant_id + created_at/updated_at)."""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index("ix_knowledge_chunks_source_lookup", "source_type", "source_id"),
        Index(
            "ix_knowledge_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    source_type: Mapped[KnowledgeSourceType] = mapped_column(
        # values_callable: the native `knowledge_source_type` Postgres enum's labels are
        # the lowercase .value strings, not the uppercase Python member .name SQLAlchemy
        # binds by default - without this, comparing/inserting a KnowledgeSourceType member
        # (e.g. KnowledgeSourceType.FAQ) binds 'FAQ', which the DB enum rejects.
        Enum(KnowledgeSourceType, name="knowledge_source_type", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
        index=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
