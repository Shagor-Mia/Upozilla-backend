"""Seeds standard service categories and a manual-publish news source.

Run with: docker compose exec api python -m app.db.seed.seed_content_taxonomies

These are generic administrative categories used across Bangladeshi upazilas
(not specific to Homna), plus one NewsSource row so admins have somewhere to
attribute manually-published articles to (Section 5.10 requires source_id).
"""

from app.core.database import SessionLocal
from app.db.models.service import ServiceCategory
from app.db.models.news import NewsSource, NewsSourceType

SERVICE_CATEGORIES = [
    "Land & Records (ভূমি ও রেকর্ড)",
    "Health & Family Welfare",
    "Education",
    "Trade License",
    "Birth & Death Registration",
    "Social Safety Net",
]

EDITORIAL_SOURCE_NAME = "Editorial Desk"


def seed() -> None:
    db = SessionLocal()
    try:
        category_count = 0
        for name in SERVICE_CATEGORIES:
            existing = db.query(ServiceCategory).filter(ServiceCategory.name_bn == name).first()
            if not existing:
                db.add(ServiceCategory(name_bn=name, name_en=name, parent_id=None))
                category_count += 1

        source = db.query(NewsSource).filter(NewsSource.name == EDITORIAL_SOURCE_NAME).first()
        if not source:
            db.add(
                NewsSource(
                    name=EDITORIAL_SOURCE_NAME,
                    feed_url="internal://manual-publish",
                    type=NewsSourceType.API,
                    is_licensed=True,
                    active=True,
                )
            )

        db.commit()
    finally:
        db.close()

    print(f"Seeded {category_count} service categories and ensured '{EDITORIAL_SOURCE_NAME}' news source exists.")


if __name__ == "__main__":
    seed()
