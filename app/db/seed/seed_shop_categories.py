"""Common village/bazaar shop category taxonomy (new "shops inside markets"
feature). Upazila-agnostic, safe to seed everywhere; admins can extend later.

Run with: docker compose exec api python -m app.db.seed.seed_shop_categories
"""

from app.core.database import SessionLocal
from app.db.models.shop import ShopCategory

# (name_bn, name_en, slug, lucide icon name)
CATEGORIES = [
    ("ফার্মেসী", "Pharmacy", "pharmacy", "pill"),
    ("পশু ফার্মেসী (ভেটেরিনারি)", "Veterinary Pharmacy", "veterinary-pharmacy", "syringe"),
    ("স্টেশনারী ও বই", "Stationery & Books", "stationery-books", "pencil"),
    ("মুদি দোকান", "Grocery", "grocery", "shopping-basket"),
    ("কাপড় ও টেইলার্স", "Cloth & Tailor", "cloth-tailor", "shirt"),
    ("ইলেকট্রনিক্স ও মোবাইল", "Electronics & Mobile", "electronics-mobile", "smartphone"),
    ("হোটেল ও চা স্টল", "Hotel & Tea Stall", "hotel-tea-stall", "coffee"),
    ("হার্ডওয়্যার", "Hardware", "hardware", "hammer"),
    ("স্বর্ণকার", "Jewelry", "jewelry", "gem"),
    ("আড়ত (পাইকারি ব্যবসা)", "Wholesale Trader (Arot)", "wholesale-arot", "warehouse"),
    ("ব্যাংক শাখা", "Bank Branch", "bank-branch", "landmark"),
    ("মোবাইল ব্যাংকিং এজেন্ট", "Mobile Banking Agent", "mobile-banking-agent", "smartphone-nfc"),
    ("প্রিন্টিং প্রেস", "Printing Press", "printing-press", "printer"),
    ("অন্যান্য", "Other", "other-shop", "package"),
]


def seed() -> None:
    db = SessionLocal()
    try:
        existing = {c.slug for c in db.query(ShopCategory).all()}
        created = 0
        for order, (name_bn, name_en, slug, icon) in enumerate(CATEGORIES):
            if slug in existing:
                continue
            db.add(ShopCategory(name_bn=name_bn, name_en=name_en, slug=slug, icon=icon, sort_order=order))
            created += 1
        db.commit()
        print(f"Seeded {created} shop categories ({len(CATEGORIES)} total).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
