"""Creates (or resets) a demo super_admin login for local development.

    email:    demo.admin@example.com
    password: Demo@12345

Refuses to run in production. Run with:
    docker compose exec api python -m app.db.seed.seed_demo_admin
"""

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.rbac import Role
from app.core.security import hash_password
from app.core.tenant import resolve_tenant_id
from app.db.models.user import User

DEMO_EMAIL = "demo.admin@example.com"
DEMO_PASSWORD = "Demo@12345"


def seed() -> None:
    if settings.is_production:
        raise SystemExit("Refusing to seed a demo admin in production.")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if user is None:
            user = User(
                tenant_id=resolve_tenant_id(db),
                full_name="Demo Admin",
                email=DEMO_EMAIL,
                role=Role.SUPER_ADMIN.value,
            )
            db.add(user)
        user.password_hash = hash_password(DEMO_PASSWORD)
        user.role = Role.SUPER_ADMIN.value
        user.status = "active"
        db.commit()
        print(f"Demo super_admin ready: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
