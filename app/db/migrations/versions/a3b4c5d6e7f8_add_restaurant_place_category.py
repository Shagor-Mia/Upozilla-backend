"""Add 'restaurant' to the place_category enum

The header's Places nav dropdown needs a Restaurant category, which didn't
exist in `PlaceCategory` (tourist/park/historical/religious/natural/other).
Postgres enum values can only be added, never removed in place, so
`downgrade()` can't drop the value again - it's a no-op, matching the
standard tradeoff for additive enum migrations.

Revision ID: a3b4c5d6e7f8
Revises: b4e48b7be522
Create Date: 2026-09-17 06:06:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, None] = 'b4e48b7be522'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The existing labels are the Python enum's uppercase *names*
    # (TOURIST/PARK/...), not lowercase values - SQLAlchemy's `Enum` type
    # persists `.name`. Match that convention so `PlaceCategory.RESTAURANT`
    # round-trips correctly; a lowercase 'restaurant' label would raise
    # "invalid input value for enum place_category" on first use.
    op.execute("ALTER TYPE place_category ADD VALUE IF NOT EXISTS 'RESTAURANT'")


def downgrade() -> None:
    """Postgres has no ALTER TYPE ... DROP VALUE - left as a no-op."""
    pass
