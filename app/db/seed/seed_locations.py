"""Idempotent seed for the Division -> District levels of the location hierarchy.

Run with: docker compose exec api python -m app.db.seed.seed_locations

Upazila/Union/Village rows are added later, per-upazila, as each one launches
(Section 4 of UPAZILA_SAAS_IMPLEMENTATION_PLAN.md).
"""

from app.core.database import SessionLocal
from app.db.models.location import LocationType
from app.db.seed.bd_divisions_districts import DIVISIONS_WITH_DISTRICTS
from app.db.seed.utils import get_or_create_location


def seed() -> None:
    db = SessionLocal()
    division_count = 0
    district_count = 0
    try:
        for division_name, districts in DIVISIONS_WITH_DISTRICTS.items():
            division = get_or_create_location(db, LocationType.DIVISION, division_name, None)
            division_count += 1

            for district_name in districts:
                get_or_create_location(db, LocationType.DISTRICT, district_name, division.id)
                district_count += 1

        db.commit()
    finally:
        db.close()

    print(f"Seeded {division_count} divisions and {district_count} districts.")


if __name__ == "__main__":
    seed()
