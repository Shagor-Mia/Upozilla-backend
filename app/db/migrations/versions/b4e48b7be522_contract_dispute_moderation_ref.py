"""Recognize contract_dispute in the moderation polymorphic-ref trigger

`check_moderation_entity_ref()` (b5c6d7e8f9a0) is a DB-level backstop that
rejects any moderation_queue insert/update whose entity_type isn't one of a
fixed, hardcoded list - it predates the work-contracts module, so escalating
a contract dispute (entity_type='contract_dispute') was rejected outright by
the trigger with "unknown entity_type contract_dispute", even though the
Python-level enqueue_contract_dispute() call looked correct. Caught by an
actual end-to-end run against a live Postgres, not by code review, since
nothing in the Python/ORM layer references this trigger.

Revision ID: b4e48b7be522
Revises: c1d2e3f4a5b6
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b4e48b7be522'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
            ELSE
                RAISE EXCEPTION 'unknown entity_type %', NEW.entity_type;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
