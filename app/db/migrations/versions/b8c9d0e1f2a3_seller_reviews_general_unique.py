"""partial unique index closing the NULL-bypass gap on seller_reviews

uq_review_per_listing (seller_user_id, reviewer_user_id, listing_type,
listing_id) is a no-op for general reviews since Postgres treats NULL as
distinct in unique constraints - a buyer could submit unlimited duplicate
general (non-listing) reviews for the same seller. This adds a partial
unique index scoped to listing_id IS NULL to close that gap.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-06 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'uq_seller_reviews_general',
        'seller_reviews',
        ['seller_user_id', 'reviewer_user_id'],
        unique=True,
        postgresql_where=sa.text('listing_id IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_seller_reviews_general', table_name='seller_reviews')
