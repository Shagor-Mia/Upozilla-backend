"""Generic marketplace/exchange category taxonomy (Section 5.7).

These are broad, upazila-agnostic categories - not Homna-specific facts - so
they are safe to seed. Admins can extend them later.
Run with: docker compose exec api python -m app.db.seed.seed_marketplace_categories
"""

from app.core.database import SessionLocal
from app.db.models.marketplace import MarketplaceCategory

# (name, slug, lucide icon name)
CATEGORIES = [
    ("Mobile Phones", "mobile-phones", "smartphone"),
    ("Electronics", "electronics", "tv"),
    ("Vehicles", "vehicles", "car"),
    ("Property & Land", "property-land", "home"),
    ("Furniture & Home", "furniture-home", "sofa"),
    ("Fashion & Clothing", "fashion-clothing", "shirt"),
    ("Agriculture & Livestock", "agriculture-livestock", "wheat"),
    ("Books & Education", "books-education", "book-open"),
    ("Groceries & Food", "groceries-food", "shopping-basket"),
    ("Services", "services", "wrench"),
    ("Others", "others", "package"),
]


def seed() -> None:
    db = SessionLocal()
    try:
        existing = {c.slug for c in db.query(MarketplaceCategory).all()}
        created = 0
        for order, (name, slug, icon) in enumerate(CATEGORIES):
            if slug in existing:
                continue
            db.add(MarketplaceCategory(name_bn=name, name_en=name, slug=slug, icon=icon, sort_order=order))
            created += 1
        db.commit()
        print(f"Seeded {created} marketplace categories ({len(CATEGORIES)} total).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
