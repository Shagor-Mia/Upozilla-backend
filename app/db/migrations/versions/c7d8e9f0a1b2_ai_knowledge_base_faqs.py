"""AI layer: pgvector knowledge base, faqs, news tags

Revision ID: c7d8e9f0a1b2
Revises: b1c2d3e4f5a6
Create Date: 2026-09-02 00:00:00.000000

Section 17 Phase 4 / Section 5.13. Requires the `pgvector/pgvector:pg16`
Postgres image (docker-compose.yml) - the plain `postgres:16-alpine` image
has no `vector` extension binary to install.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIMENSIONS = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "faqs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("question_bn", sa.String(length=500), nullable=False),
        sa.Column("question_en", sa.String(length=500), nullable=True),
        sa.Column("question_ar", sa.String(length=500), nullable=True),
        sa.Column("answer_bn", sa.Text(), nullable=False),
        sa.Column("answer_en", sa.Text(), nullable=True),
        sa.Column("answer_ar", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="published"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_faqs_tenant_id", "faqs", ["tenant_id"])

    postgresql.ENUM(
        "place", "service", "hospital", "market", "news", "faq", name="knowledge_source_type"
    ).create(op.get_bind(), checkfirst=True)
    # Already created above - the Column below must not try to CREATE TYPE again
    # (generic sa.Enum re-issues CREATE TYPE on table create; the PG-specific
    # ENUM honours create_type=False).
    knowledge_source_type = postgresql.ENUM(
        "place", "service", "hospital", "market", "news", "faq",
        name="knowledge_source_type", create_type=False,
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", knowledge_source_type, nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_knowledge_chunks_tenant_id", "knowledge_chunks", ["tenant_id"])
    op.create_index("ix_knowledge_chunks_source_type", "knowledge_chunks", ["source_type"])
    op.create_index("ix_knowledge_chunks_source_id", "knowledge_chunks", ["source_id"])
    op.create_index("ix_knowledge_chunks_source_lookup", "knowledge_chunks", ["source_type", "source_id"])
    # HNSW over ivfflat: no "train on existing data" step needed, a better fit
    # for a single-upazila dataset that starts empty and grows gradually.
    op.execute(
        "CREATE INDEX ix_knowledge_chunks_embedding ON knowledge_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.add_column("news_articles", sa.Column("tags", sa.ARRAY(sa.String()), nullable=True))


def downgrade() -> None:
    op.drop_column("news_articles", "tags")

    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding")
    op.drop_index("ix_knowledge_chunks_source_lookup", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_source_id", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_source_type", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_tenant_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    sa.Enum(name="knowledge_source_type").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_faqs_tenant_id", table_name="faqs")
    op.drop_table("faqs")

    op.execute("DROP EXTENSION IF EXISTS vector")
