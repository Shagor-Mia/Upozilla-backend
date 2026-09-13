"""DB-level integrity check for polymorphic listing_id/entity_id references

listing_favorites/listing_reports/seller_reviews/conversations.listing_id and
moderation_queue.entity_id have no real FK - the type discriminator column
(listing_type / entity_type) picks which table listing_id actually points
into, which a plain FK can't express. Every current write path already
validates existence at the application layer (app/modules/exchange/lookup.py's
get_public_listing, sellers/service.py's _listing_belongs_to_seller) before
insert, so this isn't fixing a live bug - it's a DB-level backstop for
whatever bypasses those helpers next (a future endpoint, a script, a bug).

Chose a trigger over normalizing into per-target nullable FK columns: it adds
zero columns and touches zero existing queries, at the cost of being the
first stored procedure in this codebase (previously TenantScope/CHECK
constraints/app-layer checks were used everywhere - see the QA audit memory
for why this over that).

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b5c6d7e8f9a0'
down_revision: Union[str, None] = 'a4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LISTING_REF_TABLES = ['listing_favorites', 'listing_reports', 'seller_reviews', 'conversations']


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION check_listing_ref() RETURNS trigger AS $$
        BEGIN
            IF NEW.listing_id IS NULL THEN
                RETURN NEW;
            END IF;
            IF NEW.listing_type = 'exchange' THEN
                IF NOT EXISTS (SELECT 1 FROM exchange_listings WHERE id = NEW.listing_id) THEN
                    RAISE EXCEPTION 'listing_id % does not exist in exchange_listings', NEW.listing_id;
                END IF;
            ELSIF NEW.listing_type = 'marketplace' THEN
                IF NOT EXISTS (SELECT 1 FROM marketplace_products WHERE id = NEW.listing_id) THEN
                    RAISE EXCEPTION 'listing_id % does not exist in marketplace_products', NEW.listing_id;
                END IF;
            ELSE
                RAISE EXCEPTION 'unknown listing_type %', NEW.listing_type;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in _LISTING_REF_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_check_listing_ref
            BEFORE INSERT OR UPDATE OF listing_type, listing_id ON {table}
            FOR EACH ROW EXECUTE FUNCTION check_listing_ref();
            """
        )

    op.execute(
        """
        CREATE FUNCTION check_moderation_entity_ref() RETURNS trigger AS $$
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
    op.execute(
        """
        CREATE TRIGGER trg_check_moderation_entity_ref
        BEFORE INSERT OR UPDATE OF entity_type, entity_id ON moderation_queue
        FOR EACH ROW EXECUTE FUNCTION check_moderation_entity_ref();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_check_moderation_entity_ref ON moderation_queue")
    op.execute("DROP FUNCTION IF EXISTS check_moderation_entity_ref()")
    for table in _LISTING_REF_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_check_listing_ref ON {table}")
    op.execute("DROP FUNCTION IF EXISTS check_listing_ref()")
