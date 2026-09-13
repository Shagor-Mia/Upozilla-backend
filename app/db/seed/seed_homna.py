"""Seeds Homna Upazila (Cumilla district), its 9 unions, and the Phase 1 tenant row.

Run with: docker compose exec api python -m app.db.seed.seed_homna
Requires seed_locations.py (divisions/districts) to have run first.
"""

from app.core.database import SessionLocal
from app.db.models.location import Location, LocationType
from app.db.models.tenant import Tenant
from app.db.seed.homna_upazila import DISTRICT_NAME, UNIONS, UPAZILA_NAME
from app.db.seed.utils import get_or_create_location

TENANT_SLUG = "homna"


def seed() -> None:
    db = SessionLocal()
    try:
        district = db.query(Location).filter(
            Location.type == LocationType.DISTRICT, Location.name_bn == DISTRICT_NAME
        ).first()
        if not district:
            raise RuntimeError(f"District '{DISTRICT_NAME}' not found — run seed_locations.py first")

        upazila = get_or_create_location(db, LocationType.UPAZILA, UPAZILA_NAME, district.id)

        union_count = 0
        for union_name in UNIONS:
            get_or_create_location(db, LocationType.UNION, union_name, upazila.id)
            union_count += 1

        tenant = db.query(Tenant).filter(Tenant.slug == TENANT_SLUG).first()
        if not tenant:
            tenant = Tenant(
                name=f"{UPAZILA_NAME} Upazila",
                slug=TENANT_SLUG,
                upazila_id=upazila.id,
                status="active",
            )
            db.add(tenant)
        else:
            tenant.upazila_id = upazila.id

        db.commit()
    finally:
        db.close()

    print(f"Seeded upazila '{UPAZILA_NAME}' under '{DISTRICT_NAME}' with {union_count} unions, tenant slug '{TENANT_SLUG}'.")


if __name__ == "__main__":
    seed()
