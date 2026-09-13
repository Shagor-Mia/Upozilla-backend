"""CHECK constraints on faqs.status and news_articles.status

Both are the only two ad-hoc status columns where the admin UI itself
enumerates a complete, closed set of options (frontend/lib/admin-entities.ts)
- draft/published for each, no third value anywhere in the actual write
path. Business/Place/Service status columns are deliberately left alone:
they have no editable status field in the admin UI at all, so there's no
equivalent confirmation of a complete value set.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-07 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint('ck_faqs_status', 'faqs', "status IN ('draft', 'published')")
    op.create_check_constraint('ck_news_articles_status', 'news_articles', "status IN ('draft', 'published')")


def downgrade() -> None:
    op.drop_constraint('ck_news_articles_status', 'news_articles', type_='check')
    op.drop_constraint('ck_faqs_status', 'faqs', type_='check')
