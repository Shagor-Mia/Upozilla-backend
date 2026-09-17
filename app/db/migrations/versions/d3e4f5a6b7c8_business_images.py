"""Add businesses.images for the up-to-3-photo gallery on business listings
(banks, bKash/Robi service points, etc. - Section 22.2 admin form).

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-09-17 08:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('businesses', sa.Column('images', sa.ARRAY(sa.String()), nullable=True))


def downgrade() -> None:
    op.drop_column('businesses', 'images')
