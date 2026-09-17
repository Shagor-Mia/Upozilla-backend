"""Add govt_offices table - UNO office / Upazila Parishad / Union Parishad /
police station contact directory (admin-managed, no moderation queue, same
convention as hospitals).

Revision ID: f1a2b3c4d5e6
Revises: f0a1b2c3d4e5
Create Date: 2026-09-17 09:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'f0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'govt_offices',
        sa.Column('location_id', sa.UUID(), nullable=False),
        sa.Column(
            'category',
            sa.Enum('uno_office', 'upazila_parishad', 'union_parishad', 'police_station', 'other', name='govt_office_category'),
            nullable=False,
        ),
        sa.Column('name_bn', sa.String(length=255), nullable=False),
        sa.Column('name_en', sa.String(length=255), nullable=True),
        sa.Column('name_ar', sa.String(length=255), nullable=True),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('phone', sa.String(length=100), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_govt_offices_category', 'govt_offices', ['category'])
    op.create_index('ix_govt_offices_location_id', 'govt_offices', ['location_id'])
    op.create_index('ix_govt_offices_tenant_id', 'govt_offices', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('ix_govt_offices_tenant_id', table_name='govt_offices')
    op.drop_index('ix_govt_offices_location_id', table_name='govt_offices')
    op.drop_index('ix_govt_offices_category', table_name='govt_offices')
    op.drop_table('govt_offices')
    op.execute('DROP TYPE IF EXISTS govt_office_category')
