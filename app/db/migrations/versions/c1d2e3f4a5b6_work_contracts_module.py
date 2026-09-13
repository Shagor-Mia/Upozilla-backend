"""work contracts module

New scope beyond `UPAZILA_SAAS_IMPLEMENTATION_PLAN.md` - the standalone Work
Contract feature (see `purrfect-sprouting-candy.md`): `work_contracts`,
`contract_progress_entries`, `contract_payments`, and `contract_problems`.
`contract_problems` doubles as the dispute record fed into the existing
`moderation_queue` (via `ModerationEntityType.CONTRACT_DISPUTE`, a plain
string value - no DDL needed there).

Revision ID: c1d2e3f4a5b6
Revises: b5c6d7e8f9a0
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'b5c6d7e8f9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'work_contracts',
        sa.Column('employer_user_id', sa.UUID(), nullable=True),
        sa.Column('worker_user_id', sa.UUID(), nullable=True),
        sa.Column('title_bn', sa.String(length=200), nullable=False),
        sa.Column('title_en', sa.String(length=200), nullable=True),
        sa.Column('title_ar', sa.String(length=200), nullable=True),
        sa.Column('description_bn', sa.Text(), nullable=False),
        sa.Column('description_en', sa.Text(), nullable=True),
        sa.Column('description_ar', sa.Text(), nullable=True),
        sa.Column('payment_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('payment_type', sa.String(length=20), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('employer_accepted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('worker_accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('employer_completion_confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('worker_completion_confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_by_user_id', sa.UUID(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('reference_images', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['employer_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['worker_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['cancelled_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_work_contracts_employer_user_id'), 'work_contracts', ['employer_user_id'], unique=False)
    op.create_index(op.f('ix_work_contracts_worker_user_id'), 'work_contracts', ['worker_user_id'], unique=False)
    op.create_index(op.f('ix_work_contracts_status'), 'work_contracts', ['status'], unique=False)
    op.create_index(op.f('ix_work_contracts_tenant_id'), 'work_contracts', ['tenant_id'], unique=False)

    op.create_table(
        'contract_progress_entries',
        sa.Column('contract_id', sa.UUID(), nullable=False),
        sa.Column('created_by_user_id', sa.UUID(), nullable=True),
        sa.Column('note_bn', sa.Text(), nullable=False),
        sa.Column('note_en', sa.Text(), nullable=True),
        sa.Column('note_ar', sa.Text(), nullable=True),
        sa.Column('percent_complete', sa.Integer(), nullable=True),
        sa.Column('images', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['contract_id'], ['work_contracts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_contract_progress_entries_contract_id'), 'contract_progress_entries', ['contract_id'], unique=False
    )
    op.create_index(
        op.f('ix_contract_progress_entries_tenant_id'), 'contract_progress_entries', ['tenant_id'], unique=False
    )

    op.create_table(
        'contract_payments',
        sa.Column('contract_id', sa.UUID(), nullable=False),
        sa.Column('logged_by_user_id', sa.UUID(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('method', sa.String(length=20), nullable=False),
        sa.Column('note_bn', sa.Text(), nullable=True),
        sa.Column('note_en', sa.Text(), nullable=True),
        sa.Column('note_ar', sa.Text(), nullable=True),
        sa.Column('proof_images', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('confirmed_by_user_id', sa.UUID(), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['contract_id'], ['work_contracts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['logged_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['confirmed_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_contract_payments_contract_id'), 'contract_payments', ['contract_id'], unique=False)
    op.create_index(op.f('ix_contract_payments_status'), 'contract_payments', ['status'], unique=False)
    op.create_index(op.f('ix_contract_payments_tenant_id'), 'contract_payments', ['tenant_id'], unique=False)

    op.create_table(
        'contract_problems',
        sa.Column('contract_id', sa.UUID(), nullable=False),
        sa.Column('raised_by_user_id', sa.UUID(), nullable=True),
        sa.Column('category', sa.String(length=30), nullable=False),
        sa.Column('description_bn', sa.Text(), nullable=False),
        sa.Column('description_en', sa.Text(), nullable=True),
        sa.Column('description_ar', sa.Text(), nullable=True),
        sa.Column('images', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('escalated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution', sa.String(length=20), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('resolved_by', sa.UUID(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['contract_id'], ['work_contracts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['raised_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_contract_problems_contract_id'), 'contract_problems', ['contract_id'], unique=False)
    op.create_index(op.f('ix_contract_problems_status'), 'contract_problems', ['status'], unique=False)
    op.create_index(op.f('ix_contract_problems_tenant_id'), 'contract_problems', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_contract_problems_tenant_id'), table_name='contract_problems')
    op.drop_index(op.f('ix_contract_problems_status'), table_name='contract_problems')
    op.drop_index(op.f('ix_contract_problems_contract_id'), table_name='contract_problems')
    op.drop_table('contract_problems')

    op.drop_index(op.f('ix_contract_payments_tenant_id'), table_name='contract_payments')
    op.drop_index(op.f('ix_contract_payments_status'), table_name='contract_payments')
    op.drop_index(op.f('ix_contract_payments_contract_id'), table_name='contract_payments')
    op.drop_table('contract_payments')

    op.drop_index(op.f('ix_contract_progress_entries_tenant_id'), table_name='contract_progress_entries')
    op.drop_index(op.f('ix_contract_progress_entries_contract_id'), table_name='contract_progress_entries')
    op.drop_table('contract_progress_entries')

    op.drop_index(op.f('ix_work_contracts_tenant_id'), table_name='work_contracts')
    op.drop_index(op.f('ix_work_contracts_status'), table_name='work_contracts')
    op.drop_index(op.f('ix_work_contracts_worker_user_id'), table_name='work_contracts')
    op.drop_index(op.f('ix_work_contracts_employer_user_id'), table_name='work_contracts')
    op.drop_table('work_contracts')
