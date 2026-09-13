"""add created_at/updated_at to markets, hospitals, doctors

markets/hospitals/doctors were created without TimestampMixin, the only
tables in the schema missing it, contradicting Section 20.3's "every table
gets created_at/updated_at, no exceptions" rule. Backfills existing rows to
now() since there is no earlier timestamp to recover.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-06 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ('markets', 'hospitals', 'doctors')


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        )
        op.add_column(
            table,
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        )


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, 'updated_at')
        op.drop_column(table, 'created_at')
