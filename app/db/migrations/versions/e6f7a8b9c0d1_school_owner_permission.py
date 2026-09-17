"""Owner-managed schools: schools.owner_user_id and users.can_manage_school
(Section 17 dropdown follow-up, mirrors a2b3c4d5e6f7's hospital equivalent).

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-17 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('schools', sa.Column('owner_user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_schools_owner_user_id', 'schools', ['owner_user_id'])
    op.create_foreign_key(
        'fk_schools_owner_user_id_users', 'schools', 'users', ['owner_user_id'], ['id'], ondelete='SET NULL'
    )

    op.add_column('users', sa.Column('can_manage_school', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('users', 'can_manage_school', server_default=None)


def downgrade() -> None:
    op.drop_column('users', 'can_manage_school')

    op.drop_constraint('fk_schools_owner_user_id_users', 'schools', type_='foreignkey')
    op.drop_index('ix_schools_owner_user_id', table_name='schools')
    op.drop_column('schools', 'owner_user_id')
