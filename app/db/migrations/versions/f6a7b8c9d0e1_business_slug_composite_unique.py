"""businesses.slug: scope uniqueness to (tenant_id, slug) instead of globally

Business is tenant-scoped but slug had a bare global unique constraint, so
two different tenants wanting the same slug would collide even though they
have nothing to do with each other.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-06 00:40:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('businesses_slug_key', 'businesses', type_='unique')
    op.create_index('ix_businesses_slug', 'businesses', ['slug'])
    op.create_unique_constraint('uq_businesses_tenant_id_slug', 'businesses', ['tenant_id', 'slug'])


def downgrade() -> None:
    op.drop_constraint('uq_businesses_tenant_id_slug', 'businesses', type_='unique')
    op.drop_index('ix_businesses_slug', table_name='businesses')
    op.create_unique_constraint('businesses_slug_key', 'businesses', ['slug'])
