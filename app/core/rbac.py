"""Role/permission vocabulary for Section 5.12 / Section 12 RBAC.

The role -> permission mapping lives here in code (and is mirrored into the
`roles`/`permissions`/`role_permissions` tables by `seed_rbac.py`) so that a
permission check never needs a DB round-trip: the JWT carries the user's role
names, and `permissions_for()` resolves them against this table.
"""

import enum
from collections.abc import Iterable


class Role(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    UPAZILA_ADMIN = "upazila_admin"
    UNION_ADMIN = "union_admin"
    CONTENT_EDITOR = "content_editor"
    NEWS_EDITOR = "news_editor"
    MARKETPLACE_MODERATOR = "marketplace_moderator"
    BUSINESS_VERIFIER = "business_verifier"
    SUPPORT_STAFF = "support_staff"
    USER = "user"


class Permission(str, enum.Enum):
    DASHBOARD_VIEW = "dashboard.view"
    CONTENT_MANAGE = "content.manage"
    NEWS_MANAGE = "news.manage"
    MARKETPLACE_MODERATE = "marketplace.moderate"
    BUSINESS_VERIFY = "business.verify"
    USERS_MANAGE = "users.manage"
    ROLES_MANAGE = "roles.manage"
    SUPPORT_VIEW = "support.view"
    SETTINGS_MANAGE = "settings.manage"


_ALL_PERMISSIONS = frozenset(Permission)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.SUPER_ADMIN: _ALL_PERMISSIONS,
    Role.UPAZILA_ADMIN: _ALL_PERMISSIONS - {Permission.ROLES_MANAGE, Permission.SETTINGS_MANAGE},
    Role.UNION_ADMIN: frozenset(
        {
            Permission.DASHBOARD_VIEW,
            Permission.CONTENT_MANAGE,
            Permission.MARKETPLACE_MODERATE,
            Permission.BUSINESS_VERIFY,
            Permission.SUPPORT_VIEW,
        }
    ),
    Role.CONTENT_EDITOR: frozenset({Permission.DASHBOARD_VIEW, Permission.CONTENT_MANAGE}),
    Role.NEWS_EDITOR: frozenset({Permission.DASHBOARD_VIEW, Permission.NEWS_MANAGE}),
    Role.MARKETPLACE_MODERATOR: frozenset({Permission.DASHBOARD_VIEW, Permission.MARKETPLACE_MODERATE}),
    Role.BUSINESS_VERIFIER: frozenset({Permission.DASHBOARD_VIEW, Permission.BUSINESS_VERIFY}),
    Role.SUPPORT_STAFF: frozenset({Permission.DASHBOARD_VIEW, Permission.SUPPORT_VIEW}),
    Role.USER: frozenset(),
}

STAFF_ROLES: frozenset[Role] = frozenset(r for r in Role if r is not Role.USER)

# Phase 1 shipped with a two-value role column; these aliases let the JWT/role
# checks keep working for any token minted before the Phase 2 data migration.
LEGACY_ROLE_ALIASES: dict[str, Role] = {"admin": Role.SUPER_ADMIN, "editor": Role.CONTENT_EDITOR}


def normalize_role(name: str | None) -> Role | None:
    if name is None:
        return None
    if name in LEGACY_ROLE_ALIASES:
        return LEGACY_ROLE_ALIASES[name]
    try:
        return Role(name)
    except ValueError:
        return None


def permissions_for(role_names: Iterable[str | None]) -> set[Permission]:
    granted: set[Permission] = set()
    for name in role_names:
        role = normalize_role(name)
        if role is not None:
            granted |= ROLE_PERMISSIONS[role]
    return granted


def is_staff(role_names: Iterable[str | None]) -> bool:
    return any(normalize_role(name) in STAFF_ROLES for name in role_names)
