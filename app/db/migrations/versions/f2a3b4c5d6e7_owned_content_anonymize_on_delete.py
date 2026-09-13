"""anonymize (SET NULL) genuinely-owned content on user deletion

Product decision (user-confirmed 2026-09-07): for content a deleted user
authored/owned, anonymize rather than cascade or block - preserves
buyer-visible history, moderation history, and civic/audit records even
after the account is gone. Still no delete-user feature anywhere in the
app today; this is schema-only hardening for whenever one is built, same
as e1f2a3b4c5d6.

Columns changed (nullable=True + FK ondelete=SET NULL):
- businesses.owner_user_id
- shops.seller_user_id
- marketplace_products.seller_user_id
- exchange_listings.seller_user_id
- listing_reports.reporter_user_id
- seller_reviews.seller_user_id / seller_reviews.reviewer_user_id
- representatives.user_id
- conversations.buyer_id / conversations.seller_id
- messages.sender_id
- license_applications.user_id
- place_reviews.user_id (model-only feature, no service/router wired up yet)

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = [
    ('businesses_owner_user_id_fkey', 'businesses', 'owner_user_id'),
    ('shops_seller_user_id_fkey', 'shops', 'seller_user_id'),
    ('marketplace_products_seller_user_id_fkey', 'marketplace_products', 'seller_user_id'),
    ('exchange_listings_seller_user_id_fkey', 'exchange_listings', 'seller_user_id'),
    ('listing_reports_reporter_user_id_fkey', 'listing_reports', 'reporter_user_id'),
    ('seller_reviews_seller_user_id_fkey', 'seller_reviews', 'seller_user_id'),
    ('seller_reviews_reviewer_user_id_fkey', 'seller_reviews', 'reviewer_user_id'),
    ('representatives_user_id_fkey', 'representatives', 'user_id'),
    ('conversations_buyer_id_fkey', 'conversations', 'buyer_id'),
    ('conversations_seller_id_fkey', 'conversations', 'seller_id'),
    ('messages_sender_id_fkey', 'messages', 'sender_id'),
    ('license_applications_user_id_fkey', 'license_applications', 'user_id'),
    ('place_reviews_user_id_fkey', 'place_reviews', 'user_id'),
]


def upgrade() -> None:
    for name, table, column in _TABLES:
        op.alter_column(table, column, nullable=True)
        op.drop_constraint(name, table, type_='foreignkey')
        op.create_foreign_key(name, table, 'users', [column], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    for name, table, column in _TABLES:
        op.drop_constraint(name, table, type_='foreignkey')
        op.create_foreign_key(name, table, 'users', [column], ['id'])
        op.alter_column(table, column, nullable=False)
