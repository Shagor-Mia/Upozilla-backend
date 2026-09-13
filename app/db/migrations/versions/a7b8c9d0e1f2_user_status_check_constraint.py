"""CHECK constraint on users.status

users.status was a plain unconstrained VARCHAR even though the app's own
admin/service.py declares the complete authoritative set
(USER_STATUSES = {"active", "suspended"}) - nothing at the DB layer stopped
an invalid string landing in the column. Other ad-hoc status columns
(Business/Place/Service/NewsArticle/Faq) are intentionally left alone here:
their update schemas accept an unrestricted `status: str`, so the complete
write-side value set can't be confirmed from the backend code alone.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-06 00:50:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint('ck_users_status', 'users', "status IN ('active', 'suspended')")


def downgrade() -> None:
    op.drop_constraint('ck_users_status', 'users', type_='check')
