"""market highlights and shop featured flag

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('markets', sa.Column('description_bn', sa.Text(), nullable=True))
    op.add_column('markets', sa.Column('description_en', sa.Text(), nullable=True))
    op.add_column('markets', sa.Column('description_ar', sa.Text(), nullable=True))

    op.add_column('shops', sa.Column('is_featured', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.create_index(op.f('ix_shops_is_featured'), 'shops', ['is_featured'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_shops_is_featured'), table_name='shops')
    op.drop_column('shops', 'is_featured')

    op.drop_column('markets', 'description_ar')
    op.drop_column('markets', 'description_en')
    op.drop_column('markets', 'description_bn')
