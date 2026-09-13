"""tenants.upazila_id: add FK to locations + unique constraint

"One tenant per upazila" is the platform's core invariant (Section 1) but
upazila_id was a plain nullable UUID with no FK and no uniqueness - nothing
stopped it referencing a deleted location or two tenants claiming the same
upazila.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-06 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint('uq_tenants_upazila_id', 'tenants', ['upazila_id'])
    op.create_foreign_key(
        'fk_tenants_upazila_id_locations', 'tenants', 'locations', ['upazila_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_tenants_upazila_id_locations', 'tenants', type_='foreignkey')
    op.drop_constraint('uq_tenants_upazila_id', 'tenants', type_='unique')
