"""shops.market_id: make nullable so a shop can be listed independently of
any market/bazaar, not just as a stall inside one.

Revision ID: f0a1b2c3d4e5
Revises: d3e4f5a6b7c8
Create Date: 2026-09-17 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f0a1b2c3d4e5'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('shops', 'market_id', existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column('shops', 'market_id', existing_type=sa.UUID(), nullable=False)
