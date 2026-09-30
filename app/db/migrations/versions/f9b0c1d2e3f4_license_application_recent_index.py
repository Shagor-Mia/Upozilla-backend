"""add recent lookup index for user license applications

Revision ID: f9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-09-30 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "f9b0c1d2e3f4"
down_revision: Union[str, None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_license_applications_user_recent",
        "license_applications",
        ["user_id", "submitted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_license_applications_user_recent", table_name="license_applications")
