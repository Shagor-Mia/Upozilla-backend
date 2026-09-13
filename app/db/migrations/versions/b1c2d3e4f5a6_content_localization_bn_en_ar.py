"""content localization (bn/en/ar)

Revision ID: b1c2d3e4f5a6
Revises: 382a8487fc00
Create Date: 2026-09-01 00:00:00.000000

Splits every admin/seller-authored content field into `<field>_bn` (required),
`<field>_en`/`<field>_ar` (optional) so the API can serve the viewer's chosen
locale, falling back to `bn`. Existing values are backfilled into both `_bn`
and `_en` (the two locales the app already served before this migration) so
current content keeps displaying unchanged; `_ar` starts empty until an admin
(or automatic translation, Section 5) supplies it.

Person names (`doctors.name`) and third-party/source names
(`news_sources.name`, `news_articles.title`) are intentionally left alone —
see UPAZILA_SAAS_IMPLEMENTATION_PLAN.md Section 5 for the scope note.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = '382a8487fc00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, field, sql_type, length, required) - required=True fields were
# NOT NULL before and become NOT NULL again (on `_bn`) after backfill.
_FIELDS: list[tuple[str, str, str, int | None, bool]] = [
    ("locations", "name", "string", 255, True),
    ("places", "name", "string", 255, True),
    ("places", "description", "text", None, False),
    ("businesses", "name", "string", 255, True),
    ("businesses", "description", "text", None, False),
    ("hospitals", "name", "string", 255, True),
    ("markets", "name", "string", 255, True),
    ("marketplace_categories", "name", "string", 100, True),
    ("marketplace_products", "title", "string", 200, True),
    ("marketplace_products", "description", "text", None, False),
    ("exchange_listings", "title", "string", 200, True),
    ("exchange_listings", "description", "text", None, False),
    ("service_categories", "name", "string", 255, True),
    ("services", "name", "string", 255, True),
    ("services", "description", "text", None, False),
    ("services", "office_name", "string", 255, False),
]


def _column(sql_type: str, length: int | None) -> sa.types.TypeEngine:
    return sa.String(length=length) if sql_type == "string" else sa.Text()


def upgrade() -> None:
    for table, field, sql_type, length, required in _FIELDS:
        for suffix in ("bn", "en", "ar"):
            op.add_column(table, sa.Column(f"{field}_{suffix}", _column(sql_type, length), nullable=True))
        op.execute(f"UPDATE {table} SET {field}_bn = {field}, {field}_en = {field}")
        if required:
            op.alter_column(table, f"{field}_bn", nullable=False)

    # marketplace_categories.name carried a UNIQUE constraint - move it to name_bn.
    op.execute("ALTER TABLE marketplace_categories DROP CONSTRAINT IF EXISTS marketplace_categories_name_key")
    op.create_unique_constraint("uq_marketplace_categories_name_bn", "marketplace_categories", ["name_bn"])

    for table, field, _sql_type, _length, _required in _FIELDS:
        op.drop_column(table, field)


def downgrade() -> None:
    for table, field, sql_type, length, required in _FIELDS:
        op.add_column(table, sa.Column(field, _column(sql_type, length), nullable=True))
        op.execute(f"UPDATE {table} SET {field} = COALESCE({field}_bn, {field}_en, {field}_ar)")
        if required:
            op.alter_column(table, field, nullable=False)

    op.drop_constraint("uq_marketplace_categories_name_bn", "marketplace_categories", type_="unique")
    op.create_unique_constraint("marketplace_categories_name_key", "marketplace_categories", ["name"])

    for table, field, _sql_type, _length, _required in _FIELDS:
        for suffix in ("bn", "en", "ar"):
            op.drop_column(table, f"{field}_{suffix}")
