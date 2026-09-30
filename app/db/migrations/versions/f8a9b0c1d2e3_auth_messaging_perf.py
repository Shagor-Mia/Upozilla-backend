"""add indexes for auth and messaging hot paths

Revision ID: f8a9b0c1d2e3
Revises: f7a8b9c0d1e2
Create Date: 2026-09-30 13:35:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEXES = [
    ("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"]),
    ("ix_messages_unread_lookup", "messages", ["conversation_id", "read_at", "sender_id"]),
    ("ix_conversations_buyer_recent", "conversations", ["buyer_id", "last_message_at", "created_at"]),
    ("ix_conversations_seller_recent", "conversations", ["seller_id", "last_message_at", "created_at"]),
    ("ix_conversations_listing_buyer", "conversations", ["listing_type", "listing_id", "buyer_id"]),
    ("ix_user_roles_user_role", "user_roles", ["user_id", "role_id"]),
]


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in reversed(INDEXES):
        op.drop_index(name, table_name=table)
