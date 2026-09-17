"""Owner-managed hospitals: hospitals.owner_user_id/images/services/ambulance_contact
and users.can_manage_hospital (Section 17 dropdown + ambulance page follow-up).

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-09-17 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('hospitals', sa.Column('owner_user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('hospitals', sa.Column('images', sa.ARRAY(sa.String()), nullable=True))
    op.add_column('hospitals', sa.Column('services', sa.ARRAY(sa.String()), nullable=True))
    op.add_column('hospitals', sa.Column('ambulance_contact', sa.String(length=100), nullable=True))
    op.create_index('ix_hospitals_owner_user_id', 'hospitals', ['owner_user_id'])
    op.create_foreign_key(
        'fk_hospitals_owner_user_id_users', 'hospitals', 'users', ['owner_user_id'], ['id'], ondelete='SET NULL'
    )

    op.add_column('users', sa.Column('can_manage_hospital', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('users', 'can_manage_hospital', server_default=None)


def downgrade() -> None:
    op.drop_column('users', 'can_manage_hospital')

    op.drop_constraint('fk_hospitals_owner_user_id_users', 'hospitals', type_='foreignkey')
    op.drop_index('ix_hospitals_owner_user_id', table_name='hospitals')
    op.drop_column('hospitals', 'ambulance_contact')
    op.drop_column('hospitals', 'services')
    op.drop_column('hospitals', 'images')
    op.drop_column('hospitals', 'owner_user_id')
