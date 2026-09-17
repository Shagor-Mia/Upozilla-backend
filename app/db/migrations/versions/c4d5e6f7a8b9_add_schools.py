"""Add schools table - govt/private/madrasa/college directory (admin-managed,
no moderation queue, same convention as hospitals/govt_offices).

Revision ID: c4d5e6f7a8b9
Revises: a2b3c4d5e6f7
Create Date: 2026-09-17 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'schools',
        sa.Column('location_id', sa.UUID(), nullable=False),
        sa.Column(
            'type',
            sa.Enum('govt', 'private', 'madrasa', 'college', 'other', name='school_type'),
            nullable=False,
        ),
        sa.Column('name_bn', sa.String(length=255), nullable=False),
        sa.Column('name_en', sa.String(length=255), nullable=True),
        sa.Column('name_ar', sa.String(length=255), nullable=True),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('contact', sa.String(length=100), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_schools_location_id', 'schools', ['location_id'])
    op.create_index('ix_schools_tenant_id', 'schools', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('ix_schools_tenant_id', table_name='schools')
    op.drop_index('ix_schools_location_id', table_name='schools')
    op.drop_table('schools')
    op.execute('DROP TYPE IF EXISTS school_type')
