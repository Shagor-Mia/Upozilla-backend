"""fix license_applications.updated_at to use standard TimestampMixin behaviour

license_applications.updated_at was declared as a plain nullable column with no
default, shadowing the app.db.base_class.TimestampMixin column of the same name
and defeating its auto-managed created_at/updated_at guarantee (Section 20.3).
This backfills existing NULLs from created_at, then applies the same
server_default + NOT NULL shape every other table's updated_at column has.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE license_applications SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column(
        'license_applications',
        'updated_at',
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text('now()'),
    )


def downgrade() -> None:
    op.alter_column(
        'license_applications',
        'updated_at',
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        server_default=None,
    )
