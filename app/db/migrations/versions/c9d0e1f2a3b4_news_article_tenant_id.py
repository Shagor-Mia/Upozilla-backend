"""add tenant_id to news_articles

NewsArticle was the only content-ish model with no tenant_id column at all
(not even unused plumbing, unlike markets/hospitals/places/services/faqs
which at least had the column). Backfills existing rows to the single active
tenant so ingested articles don't leak across the RAG chatbot's tenant
boundary via a NULL-matches-everyone tenant_id.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('news_articles', sa.Column('tenant_id', sa.UUID(), nullable=True))
    op.create_index('ix_news_articles_tenant_id', 'news_articles', ['tenant_id'])
    op.execute(
        "UPDATE news_articles SET tenant_id = "
        "(SELECT id FROM tenants WHERE status = 'active' ORDER BY created_at LIMIT 1)"
    )


def downgrade() -> None:
    op.drop_index('ix_news_articles_tenant_id', table_name='news_articles')
    op.drop_column('news_articles', 'tenant_id')
