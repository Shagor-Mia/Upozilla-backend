"""Add 'shop' to the place_category enum

Union/village detail pages need a "popular shop" section, modeled as a Place
with category=shop (not the separate market-scoped Shop entity) - product
decision to keep "shop" a lightweight Place category rather than requiring a
market_id.

Revision ID: c2d3e4f5a6b7
Revises: b6c7d8e9f0a1
Create Date: 2026-09-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b6c7d8e9f0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLAlchemy's `Enum` type persists the Python enum's uppercase *name*
    # (see a3b4c5d6e7f8 for the same convention when 'restaurant' was added).
    op.execute("ALTER TYPE place_category ADD VALUE IF NOT EXISTS 'SHOP'")


def downgrade() -> None:
    """Postgres has no ALTER TYPE ... DROP VALUE - left as a no-op."""
    pass
