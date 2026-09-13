"""One-time bootstrap: promote an existing registered user to super_admin.

There's no other way to create the first admin - /admin/* endpoints require an
admin already. Section 12's other roles are then granted from /admin/users.

Run with: docker compose exec api python -m app.db.seed.promote_admin <email-or-phone>
"""

import sys

from sqlalchemy import or_

from app.core.database import SessionLocal
from app.core.rbac import Role
from app.db.models.user import User


def promote(identifier: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(or_(User.email == identifier, User.phone == identifier)).first()
        if not user:
            print(f"No user found with email/phone '{identifier}'. Register the account first.")
            return

        user.role = Role.SUPER_ADMIN.value
        db.commit()
        print(f"Promoted '{identifier}' ({user.full_name}) to {Role.SUPER_ADMIN.value}.")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m app.db.seed.promote_admin <email-or-phone>")
        sys.exit(1)
    promote(sys.argv[1])
