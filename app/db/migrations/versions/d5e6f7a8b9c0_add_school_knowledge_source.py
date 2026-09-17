"""Add 'school' to the knowledge_source_type enum, for AI chatbot indexing
parity with hospitals/markets/places (see hospital.py's _schedule_reindex).

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-17 16:05:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # knowledge_source_type uses values_callable=lowercase .value (see ai.py) -
    # unlike place_category, which persists the uppercase Python .name.
    op.execute("ALTER TYPE knowledge_source_type ADD VALUE IF NOT EXISTS 'school'")


def downgrade() -> None:
    """Postgres has no ALTER TYPE ... DROP VALUE - left as a no-op."""
    pass
