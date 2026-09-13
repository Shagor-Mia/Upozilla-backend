"""Mirrors `app.core.rbac` (roles, permissions, role_permissions) into the DB.

Idempotent - re-run after changing the mapping in code.
Run with: docker compose exec api python -m app.db.seed.seed_rbac
"""

from app.core.database import SessionLocal
from app.core.rbac import ROLE_PERMISSIONS, Permission, Role
from app.db.models.rbac import PermissionRow, RolePermission, RoleRow


def seed() -> None:
    db = SessionLocal()
    try:
        roles = {r.name: r for r in db.query(RoleRow).all()}
        for role in Role:
            if role.value not in roles:
                row = RoleRow(name=role.value)
                db.add(row)
                roles[role.value] = row

        permissions = {p.name: p for p in db.query(PermissionRow).all()}
        for permission in Permission:
            if permission.value not in permissions:
                row = PermissionRow(name=permission.value)
                db.add(row)
                permissions[permission.value] = row
        db.flush()

        db.query(RolePermission).delete()
        for role, granted in ROLE_PERMISSIONS.items():
            for permission in granted:
                db.add(
                    RolePermission(
                        role_id=roles[role.value].id,
                        permission_id=permissions[permission.value].id,
                    )
                )
        db.commit()
        print(f"Seeded {len(roles)} roles, {len(permissions)} permissions.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
