"""Let regular users submit a place for admin approval

Adds `places.moderation_status` (denormalised moderation_queue outcome, same
pattern as marketplace_products.moderation_status) and `places.seller_user_id`
(the submitter - nullable/SET NULL since admin-created places have none and a
submitter's account can be deleted without losing the place). Existing rows
were all admin-created via CONTENT_MANAGE, so they backfill as already
'approved'.

Also recognizes 'place' in `check_moderation_entity_ref()` (see b4e48b7be522
for the same fix when contract_dispute was added) - without this, any
moderation_queue insert with entity_type='place' is rejected by the trigger.

Revision ID: b6c7d8e9f0a1
Revises: a3b4c5d6e7f8
Create Date: 2026-09-17 06:26:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b6c7d8e9f0a1'
down_revision: Union[str, None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'places',
        sa.Column('moderation_status', sa.String(length=20), nullable=False, server_default='approved'),
    )
    op.alter_column('places', 'moderation_status', server_default=None)
    op.add_column('places', sa.Column('seller_user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_places_moderation_status', 'places', ['moderation_status'])
    op.create_index('ix_places_seller_user_id', 'places', ['seller_user_id'])
    op.create_foreign_key(
        'places_seller_user_id_fkey', 'places', 'users', ['seller_user_id'], ['id'], ondelete='SET NULL'
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_moderation_entity_ref() RETURNS trigger AS $$
        BEGIN
            IF NEW.entity_type = 'exchange_listing' THEN
                IF NOT EXISTS (SELECT 1 FROM exchange_listings WHERE id = NEW.entity_id) THEN
                    RAISE EXCEPTION 'entity_id % does not exist in exchange_listings', NEW.entity_id;
                END IF;
            ELSIF NEW.entity_type = 'marketplace_product' THEN
                IF NOT EXISTS (SELECT 1 FROM marketplace_products WHERE id = NEW.entity_id) THEN
                    RAISE EXCEPTION 'entity_id % does not exist in marketplace_products', NEW.entity_id;
                END IF;
            ELSIF NEW.entity_type = 'shop' THEN
                IF NOT EXISTS (SELECT 1 FROM shops WHERE id = NEW.entity_id) THEN
                    RAISE EXCEPTION 'entity_id % does not exist in shops', NEW.entity_id;
                END IF;
            ELSIF NEW.entity_type = 'listing_report' THEN
                IF NOT EXISTS (SELECT 1 FROM listing_reports WHERE id = NEW.entity_id) THEN
                    RAISE EXCEPTION 'entity_id % does not exist in listing_reports', NEW.entity_id;
                END IF;
            ELSIF NEW.entity_type = 'contract_dispute' THEN
                IF NOT EXISTS (SELECT 1 FROM contract_problems WHERE id = NEW.entity_id) THEN
                    RAISE EXCEPTION 'entity_id % does not exist in contract_problems', NEW.entity_id;
                END IF;
            ELSIF NEW.entity_type = 'place' THEN
                IF NOT EXISTS (SELECT 1 FROM places WHERE id = NEW.entity_id) THEN
                    RAISE EXCEPTION 'entity_id % does not exist in places', NEW.entity_id;
                END IF;
            ELSE
                RAISE EXCEPTION 'unknown entity_type %', NEW.entity_type;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_moderation_entity_ref() RETURNS trigger AS $$
        BEGIN
            IF NEW.entity_type = 'exchange_listing' THEN
                IF NOT EXISTS (SELECT 1 FROM exchange_listings WHERE id = NEW.entity_id) THEN
                    RAISE EXCEPTION 'entity_id % does not exist in exchange_listings', NEW.entity_id;
                END IF;
            ELSIF NEW.entity_type = 'marketplace_product' THEN
                IF NOT EXISTS (SELECT 1 FROM marketplace_products WHERE id = NEW.entity_id) THEN
                    RAISE EXCEPTION 'entity_id % does not exist in marketplace_products', NEW.entity_id;
                END IF;
            ELSIF NEW.entity_type = 'shop' THEN
                IF NOT EXISTS (SELECT 1 FROM shops WHERE id = NEW.entity_id) THEN
                    RAISE EXCEPTION 'entity_id % does not exist in shops', NEW.entity_id;
                END IF;
            ELSIF NEW.entity_type = 'listing_report' THEN
                IF NOT EXISTS (SELECT 1 FROM listing_reports WHERE id = NEW.entity_id) THEN
                    RAISE EXCEPTION 'entity_id % does not exist in listing_reports', NEW.entity_id;
                END IF;
            ELSIF NEW.entity_type = 'contract_dispute' THEN
                IF NOT EXISTS (SELECT 1 FROM contract_problems WHERE id = NEW.entity_id) THEN
                    RAISE EXCEPTION 'entity_id % does not exist in contract_problems', NEW.entity_id;
                END IF;
            ELSE
                RAISE EXCEPTION 'unknown entity_type %', NEW.entity_type;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.drop_constraint('places_seller_user_id_fkey', 'places', type_='foreignkey')
    op.drop_index('ix_places_seller_user_id', table_name='places')
    op.drop_index('ix_places_moderation_status', table_name='places')
    op.drop_column('places', 'seller_user_id')
    op.drop_column('places', 'moderation_status')
