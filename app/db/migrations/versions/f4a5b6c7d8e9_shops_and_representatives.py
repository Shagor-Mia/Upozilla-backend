"""shops and representatives

Revision ID: f4a5b6c7d8e9
Revises: d1e2f3a4b5c6
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f4a5b6c7d8e9'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'shop_categories',
        sa.Column('name_bn', sa.String(length=100), nullable=False),
        sa.Column('name_en', sa.String(length=100), nullable=True),
        sa.Column('name_ar', sa.String(length=100), nullable=True),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )

    op.create_table(
        'shops',
        sa.Column('market_id', sa.UUID(), nullable=False),
        sa.Column('seller_user_id', sa.UUID(), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=False),
        sa.Column('location_id', sa.UUID(), nullable=False),
        sa.Column('name_bn', sa.String(length=200), nullable=False),
        sa.Column('name_en', sa.String(length=200), nullable=True),
        sa.Column('name_ar', sa.String(length=200), nullable=True),
        sa.Column('description_bn', sa.Text(), nullable=True),
        sa.Column('description_en', sa.Text(), nullable=True),
        sa.Column('description_ar', sa.Text(), nullable=True),
        sa.Column('contact_phone', sa.String(length=20), nullable=True),
        sa.Column('images', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('moderation_status', sa.String(length=20), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['shop_categories.id']),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id']),
        sa.ForeignKeyConstraint(['market_id'], ['markets.id']),
        sa.ForeignKeyConstraint(['seller_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_shops_category_id'), 'shops', ['category_id'], unique=False)
    op.create_index(op.f('ix_shops_location_id'), 'shops', ['location_id'], unique=False)
    op.create_index(op.f('ix_shops_market_id'), 'shops', ['market_id'], unique=False)
    op.create_index(op.f('ix_shops_moderation_status'), 'shops', ['moderation_status'], unique=False)
    op.create_index(op.f('ix_shops_seller_user_id'), 'shops', ['seller_user_id'], unique=False)
    op.create_index(op.f('ix_shops_status'), 'shops', ['status'], unique=False)
    op.create_index(op.f('ix_shops_tenant_id'), 'shops', ['tenant_id'], unique=False)

    op.create_table(
        'representatives',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('location_id', sa.UUID(), nullable=False),
        sa.Column('position', sa.String(length=20), nullable=False),
        sa.Column('bio_bn', sa.Text(), nullable=True),
        sa.Column('bio_en', sa.Text(), nullable=True),
        sa.Column('bio_ar', sa.Text(), nullable=True),
        sa.Column('photo_url', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_representatives_location_id'), 'representatives', ['location_id'], unique=False)
    op.create_index(op.f('ix_representatives_position'), 'representatives', ['position'], unique=False)
    op.create_index(op.f('ix_representatives_status'), 'representatives', ['status'], unique=False)
    op.create_index(op.f('ix_representatives_tenant_id'), 'representatives', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_representatives_user_id'), 'representatives', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_representatives_user_id'), table_name='representatives')
    op.drop_index(op.f('ix_representatives_tenant_id'), table_name='representatives')
    op.drop_index(op.f('ix_representatives_status'), table_name='representatives')
    op.drop_index(op.f('ix_representatives_position'), table_name='representatives')
    op.drop_index(op.f('ix_representatives_location_id'), table_name='representatives')
    op.drop_table('representatives')

    op.drop_index(op.f('ix_shops_tenant_id'), table_name='shops')
    op.drop_index(op.f('ix_shops_status'), table_name='shops')
    op.drop_index(op.f('ix_shops_seller_user_id'), table_name='shops')
    op.drop_index(op.f('ix_shops_moderation_status'), table_name='shops')
    op.drop_index(op.f('ix_shops_market_id'), table_name='shops')
    op.drop_index(op.f('ix_shops_location_id'), table_name='shops')
    op.drop_index(op.f('ix_shops_category_id'), table_name='shops')
    op.drop_table('shops')

    op.drop_table('shop_categories')
