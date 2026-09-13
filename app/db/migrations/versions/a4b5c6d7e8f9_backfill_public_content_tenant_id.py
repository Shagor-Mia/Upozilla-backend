"""backfill tenant_id on pre-existing markets/hospitals/services/places/faqs/businesses rows

These six tables already had a tenant_id column, but only *new* rows created
after the session-2 tenant-isolation fix got it stamped - every row that
existed before that fix is still NULL (confirmed live: 2 markets, 1 hospital,
5 services, 5 places, 2 faqs, 2 businesses, all NULL). That's fine while every
public list/get endpoint is unscoped, but the new per-request tenant
resolution (X-Tenant-Slug header, app/core/tenant.py) filters public reads by
tenant_id - so today's only seeded content needs the same one-time backfill
NewsArticle already got in c9d0e1f2a3b4, or it would vanish from public
listings the moment a request actually resolves a tenant.

Revision ID: a4b5c6d7e8f9
Revises: f2a3b4c5d6e7
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a4b5c6d7e8f9'
down_revision: Union[str, None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ['markets', 'hospitals', 'services', 'places', 'faqs', 'businesses']


def upgrade() -> None:
    for table in _TABLES:
        op.execute(
            f"UPDATE {table} SET tenant_id = "
            "(SELECT id FROM tenants WHERE status = 'active' ORDER BY created_at LIMIT 1) "
            "WHERE tenant_id IS NULL"
        )


def downgrade() -> None:
    # Backfill is one-directional - there is no record of which rows were
    # NULL before upgrade, so downgrade is a deliberate no-op (same
    # convention as data-only migrations elsewhere in this history).
    pass
