"""add indexes on FK columns that are actually filtered on in query code

These columns are joined/filtered by app/modules/*/service.py but were never
indexed, forcing full table scans as data grows (businesses, places,
place_reviews, news_articles, refresh_tokens, hospitals, doctors, markets,
services, license_applications).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-06 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEXES = [
    ('ix_businesses_location_id', 'businesses', ['location_id']),
    ('ix_businesses_owner_user_id', 'businesses', ['owner_user_id']),
    ('ix_places_location_id', 'places', ['location_id']),
    ('ix_place_reviews_place_id', 'place_reviews', ['place_id']),
    ('ix_place_reviews_user_id', 'place_reviews', ['user_id']),
    ('ix_news_articles_source_id', 'news_articles', ['source_id']),
    ('ix_news_articles_location_id', 'news_articles', ['location_id']),
    ('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id']),
    ('ix_hospitals_location_id', 'hospitals', ['location_id']),
    ('ix_doctors_hospital_id', 'doctors', ['hospital_id']),
    ('ix_markets_location_id', 'markets', ['location_id']),
    ('ix_services_location_id', 'services', ['location_id']),
    ('ix_services_category_id', 'services', ['category_id']),
    ('ix_license_applications_user_id', 'license_applications', ['user_id']),
    ('ix_license_applications_service_id', 'license_applications', ['service_id']),
]


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in INDEXES:
        op.drop_index(name, table_name=table)
