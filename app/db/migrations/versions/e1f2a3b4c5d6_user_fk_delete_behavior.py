"""sensible ON DELETE behavior for a safe subset of FKs to users.id

There is no delete-user feature anywhere in the app today, so this is
schema-only hardening for whenever one is eventually built - deliberately
narrow in scope. Only the unambiguous cases are touched here:

- audit_logs.actor_user_id / moderation_queue.reviewed_by /
  platform_settings.updated_by -> SET NULL: these are historical/audit
  records that should outlive the actor, not disappear or block deletion.
- refresh_tokens.user_id -> CASCADE: sessions are meaningless without the
  user; this is pure technical housekeeping, not a product decision.

Every FK on genuinely owned content (businesses, shops, listings, reviews,
reports, conversations/messages, representatives, license_applications,
place_reviews) is deliberately left as NO ACTION - what should happen to a
user's own content on account deletion (cascade vs. anonymize vs. keep) is
a product decision, not something to guess at in a schema migration.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-07 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SET_NULL = [
    ('audit_logs_actor_user_id_fkey', 'audit_logs', 'actor_user_id'),
    ('moderation_queue_reviewed_by_fkey', 'moderation_queue', 'reviewed_by'),
    ('platform_settings_updated_by_fkey', 'platform_settings', 'updated_by'),
]
_CASCADE = [
    ('refresh_tokens_user_id_fkey', 'refresh_tokens', 'user_id'),
]


def upgrade() -> None:
    op.alter_column('audit_logs', 'actor_user_id', nullable=True)
    for name, table, column in _SET_NULL:
        op.drop_constraint(name, table, type_='foreignkey')
        op.create_foreign_key(name, table, 'users', [column], ['id'], ondelete='SET NULL')
    for name, table, column in _CASCADE:
        op.drop_constraint(name, table, type_='foreignkey')
        op.create_foreign_key(name, table, 'users', [column], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    for name, table, column in _CASCADE:
        op.drop_constraint(name, table, type_='foreignkey')
        op.create_foreign_key(name, table, 'users', [column], ['id'])
    for name, table, column in _SET_NULL:
        op.drop_constraint(name, table, type_='foreignkey')
        op.create_foreign_key(name, table, 'users', [column], ['id'])
    op.alter_column('audit_logs', 'actor_user_id', nullable=False)
