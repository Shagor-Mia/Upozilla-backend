"""Placeholder content so every Phase 1 section has something to show locally.

Run with: docker compose exec api python -m app.db.seed.seed_placeholder_content
Requires seed_locations.py, seed_homna.py, and seed_content_taxonomies.py to
have run first (locations, service categories, news source).

This is intentionally GENERIC, not researched Homna-specific fact — unlike the
places/hospital rows added by hand during testing (Homna Kali Mandir, Karakandi
Balagazi Mosque, Homna Upazila Health Complex), the entries here are meant to
be replaced with real content via /admin once available. Names/descriptions
are written so they're obviously placeholders, not passable as verified facts.
"""

from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.db.models.business import Business
from app.db.models.hospital import Doctor, Hospital
from app.db.models.location import Location, LocationType
from app.db.models.market import Market, MarketType
from app.db.models.news import NewsArticle, NewsSource
from app.db.models.service import Service, ServiceCategory
from app.db.models.user import User

PLACEHOLDER_MARKER = "[Placeholder — replace via /admin]"

# Approximate points around Homna town (Cumilla) so the Phase 3 "near me" query
# has something to rank locally. Placeholder rows only - real places/hospitals
# get their exact position from /admin.
HOMNA_CENTRE = (23.6833, 90.7833)
PLACEHOLDER_COORDS = {
    "Homna Sadar Bazar": (23.6841, 90.7822),
    "Homna Weekly Cattle Haat": (23.6950, 90.7700),
    "sample-general-store": (23.6820, 90.7860),
    "sample-tailoring-shop": (23.6875, 90.7790),
}


def _get_homna_upazila_id(db) -> "str":
    upazila = db.query(Location).filter(Location.type == LocationType.UPAZILA).first()
    if not upazila:
        raise RuntimeError("No upazila found — run seed_homna.py first")
    return upazila.id


def _seed_services(db, location_id) -> int:
    categories = {c.name_bn: c for c in db.query(ServiceCategory).all()}
    if not categories:
        raise RuntimeError("No service categories found — run seed_content_taxonomies.py first")

    templates = [
        ("Land & Records (ভূমি ও রেকর্ড)", "Certified Copy of Land Record (Khatian)"),
        ("Health & Family Welfare", "Outpatient Consultation"),
        ("Education", "Secondary School Admission Information"),
        ("Trade License", "New Trade License Application"),
        ("Birth & Death Registration", "Birth Registration Certificate"),
    ]

    created = 0
    for category_name, service_name in templates:
        category = categories.get(category_name)
        if not category:
            continue
        exists = db.query(Service).filter(Service.name_bn == service_name).first()
        if exists:
            continue
        db.add(
            Service(
                location_id=location_id,
                category_id=category.id,
                name_bn=service_name,
                name_en=service_name,
                description_bn=f"{PLACEHOLDER_MARKER} General description of this service — replace with the actual eligibility, process, and office details for Homna.",
                description_en=f"{PLACEHOLDER_MARKER} General description of this service — replace with the actual eligibility, process, and office details for Homna.",
                office_name_bn="Homna Upazila Parishad",
                office_name_en="Homna Upazila Parishad",
                status="published",
            )
        )
        created += 1
    return created


def _seed_markets(db, location_id) -> int:
    templates = [
        ("Homna Sadar Bazar", ["Saturday", "Tuesday"], MarketType.GENERAL),
        ("Homna Weekly Cattle Haat", ["Friday"], MarketType.CATTLE),
    ]
    created = 0
    for name, days, market_type in templates:
        if db.query(Market).filter(Market.name_bn == name).first():
            continue
        db.add(
            Market(
                location_id=location_id,
                name_bn=name,
                name_en=name,
                market_day=days,
                type=market_type,
                latitude=PLACEHOLDER_COORDS[name][0],
                longitude=PLACEHOLDER_COORDS[name][1],
            )
        )
        created += 1
    return created


def _seed_businesses(db, location_id, owner_user_id) -> int:
    templates = [
        ("Sample General Store", "grocery", "sample-general-store"),
        ("Sample Tailoring Shop", "tailoring", "sample-tailoring-shop"),
    ]
    created = 0
    for name, category, slug in templates:
        if db.query(Business).filter(Business.slug == slug).first():
            continue
        db.add(
            Business(
                location_id=location_id,
                owner_user_id=owner_user_id,
                name_bn=name,
                name_en=name,
                slug=slug,
                category=category,
                description_bn=f"{PLACEHOLDER_MARKER} Example business listing — replace with a real, owner-submitted or admin-verified listing.",
                description_en=f"{PLACEHOLDER_MARKER} Example business listing — replace with a real, owner-submitted or admin-verified listing.",
                latitude=PLACEHOLDER_COORDS[slug][0],
                longitude=PLACEHOLDER_COORDS[slug][1],
                status="active",
            )
        )
        created += 1
    return created


def _backfill_placeholder_coordinates(db) -> int:
    """Phase 3: placeholder rows seeded before near-me existed have no position."""
    updated = 0
    for market in db.query(Market).filter(Market.latitude.is_(None), Market.name_bn.in_(PLACEHOLDER_COORDS)):
        market.latitude, market.longitude = PLACEHOLDER_COORDS[market.name_bn]
        updated += 1
    for business in db.query(Business).filter(Business.latitude.is_(None), Business.slug.in_(PLACEHOLDER_COORDS)):
        business.latitude, business.longitude = PLACEHOLDER_COORDS[business.slug]
        updated += 1
    return updated


def _seed_news(db) -> int:
    source = db.query(NewsSource).filter(NewsSource.name == "Editorial Desk").first()
    if not source:
        raise RuntimeError("No 'Editorial Desk' news source — run seed_content_taxonomies.py first")

    templates = [
        ("welcome-to-the-homna-upazila-portal", "Welcome to the Homna Upazila Digital Portal"),
        ("sample-local-news-placeholder", "Sample Local News Item — Replace via Admin"),
    ]
    created = 0
    for slug, title in templates:
        if db.query(NewsArticle).filter(NewsArticle.slug == slug).first():
            continue
        db.add(
            NewsArticle(
                source_id=source.id,
                title=title,
                slug=slug,
                summary=f"{PLACEHOLDER_MARKER} This is example content so the News section isn't empty during development.",
                status="published",
                published_at=datetime.now(timezone.utc),
            )
        )
        created += 1
    return created


def _seed_doctors(db) -> int:
    hospital = db.query(Hospital).filter(Hospital.name_bn == "Homna Upazila Health Complex").first()
    if not hospital:
        return 0

    templates = [
        ("Dr. (Sample) Medical Officer", "General Medicine", ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]),
    ]
    created = 0
    for name, specialty, days in templates:
        if db.query(Doctor).filter(Doctor.hospital_id == hospital.id, Doctor.name == name).first():
            continue
        db.add(Doctor(hospital_id=hospital.id, name=name, specialty=specialty, chamber_days=days))
        created += 1
    return created


def seed() -> None:
    db = SessionLocal()
    try:
        location_id = _get_homna_upazila_id(db)
        # Phase 2 renamed admin -> super_admin; accept both so old DBs still seed.
        owner = db.query(User).filter(User.role.in_(["super_admin", "admin"])).first()
        if not owner:
            raise RuntimeError("No admin user found — run promote_admin.py first")

        counts = {
            "services": _seed_services(db, location_id),
            "markets": _seed_markets(db, location_id),
            "businesses": _seed_businesses(db, location_id, owner.id),
            "coordinates_backfilled": _backfill_placeholder_coordinates(db),
            "news": _seed_news(db),
            "doctors": _seed_doctors(db),
        }
        db.commit()
    finally:
        db.close()

    print("Seeded placeholder content:", counts)


if __name__ == "__main__":
    seed()
