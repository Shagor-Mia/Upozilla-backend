"""add composite indexes for public read hot paths

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-30 12:45:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEXES = [
    (
        "ix_places_public_list",
        "places",
        ["tenant_id", "status", "moderation_status", "is_featured", "name_bn"],
    ),
    (
        "ix_places_public_location",
        "places",
        ["tenant_id", "status", "moderation_status", "location_id", "name_bn"],
    ),
    (
        "ix_marketplace_products_public_newest",
        "marketplace_products",
        ["tenant_id", "status", "moderation_status", "created_at"],
    ),
    (
        "ix_marketplace_products_public_category",
        "marketplace_products",
        ["tenant_id", "status", "moderation_status", "category_id", "created_at"],
    ),
    (
        "ix_marketplace_products_public_location",
        "marketplace_products",
        ["tenant_id", "status", "moderation_status", "location_id", "created_at"],
    ),
    (
        "ix_exchange_listings_public_newest",
        "exchange_listings",
        ["tenant_id", "status", "moderation_status", "created_at"],
    ),
    (
        "ix_exchange_listings_public_category",
        "exchange_listings",
        ["tenant_id", "status", "moderation_status", "category_id", "created_at"],
    ),
    (
        "ix_exchange_listings_public_location",
        "exchange_listings",
        ["tenant_id", "status", "moderation_status", "location_id", "created_at"],
    ),
    (
        "ix_listing_favorites_type_listing",
        "listing_favorites",
        ["listing_type", "listing_id"],
    ),
]


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table)
