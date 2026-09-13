import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.dependencies import CurrentUser
from app.core.rbac import ROLE_PERMISSIONS, Role
from app.core.tenant import resolve_tenant_id
from app.db.models import (
    AuditLog,
    Business,
    ExchangeListing,
    Hospital,
    Location,
    Market,
    MarketplaceProduct,
    ModerationQueue,
    ModerationQueueStatus,
    NewsArticle,
    Place,
    RoleRow,
    Service,
    User,
    UserRole,
)
from app.modules.admin.schemas import (
    AdminUserResponse,
    AuditLogResponse,
    DashboardCounts,
    RoleDefinition,
    ScopedRoleResponse,
)
from app.modules.auth import service as auth_service

USER_STATUSES = {"active", "suspended"}


def _scoped_roles_by_user(db: Session, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[ScopedRoleResponse]]:
    if not user_ids:
        return {}
    rows = (
        db.query(UserRole, RoleRow.name, Location.name_bn)
        .join(RoleRow, RoleRow.id == UserRole.role_id)
        .outerjoin(Location, Location.id == UserRole.scope_location_id)
        .filter(UserRole.user_id.in_(user_ids))
        .all()
    )
    grouped: dict[uuid.UUID, list[ScopedRoleResponse]] = {}
    for user_role, role_name, location_name in rows:
        grouped.setdefault(user_role.user_id, []).append(
            ScopedRoleResponse(
                id=user_role.id,
                role=role_name,
                scope_location_id=user_role.scope_location_id,
                scope_location_name=location_name,
            )
        )
    return grouped


def _to_admin_user(user: User, scoped: list[ScopedRoleResponse]) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        status=user.status,
        phone_verified=user.phone_verified_at is not None,
        scoped_roles=scoped,
        created_at=user.created_at,
    )


def list_users(db: Session) -> list[AdminUserResponse]:
    users = db.query(User).order_by(User.created_at.desc()).limit(500).all()
    scoped = _scoped_roles_by_user(db, [u.id for u in users])
    return [_to_admin_user(u, scoped.get(u.id, [])) for u in users]


def _get_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return user


def _serialize(db: Session, user: User) -> AdminUserResponse:
    return _to_admin_user(user, _scoped_roles_by_user(db, [user.id]).get(user.id, []))


def update_user_role(db: Session, actor: CurrentUser, user_id: uuid.UUID, role: Role) -> AdminUserResponse:
    user = _get_user(db, user_id)
    if user.id == actor.uuid and role is not Role.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="you cannot demote yourself")
    previous = user.role
    user.role = role.value
    record_audit(db, actor.uuid, "user.role_changed", "user", user.id, {"from": previous, "to": role.value})
    db.commit()
    # Role claims live in the JWT; force re-login so the change takes effect.
    auth_service.revoke_all_refresh_tokens(db, user.id)
    db.refresh(user)
    return _serialize(db, user)


def update_user_status(db: Session, actor: CurrentUser, user_id: uuid.UUID, new_status: str) -> AdminUserResponse:
    if new_status not in USER_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"status must be one of {sorted(USER_STATUSES)}")
    user = _get_user(db, user_id)
    if user.id == actor.uuid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="you cannot suspend yourself")
    previous = user.status
    user.status = new_status
    record_audit(db, actor.uuid, "user.status_changed", "user", user.id, {"from": previous, "to": new_status})
    db.commit()
    if new_status != "active":
        auth_service.revoke_all_refresh_tokens(db, user.id)
    db.refresh(user)
    return _serialize(db, user)


def add_scoped_role(
    db: Session, actor: CurrentUser, user_id: uuid.UUID, role: Role, scope_location_id: uuid.UUID | None
) -> AdminUserResponse:
    user = _get_user(db, user_id)
    role_row = db.query(RoleRow).filter(RoleRow.name == role.value).first()
    if role_row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="roles not seeded - run seed_rbac")
    if scope_location_id is not None and db.query(Location.id).filter(Location.id == scope_location_id).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown scope location")

    existing = (
        db.query(UserRole)
        .filter(
            UserRole.user_id == user.id,
            UserRole.role_id == role_row.id,
            UserRole.scope_location_id == scope_location_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="that role/scope is already assigned")

    db.add(UserRole(user_id=user.id, role_id=role_row.id, scope_location_id=scope_location_id))
    record_audit(
        db,
        actor.uuid,
        "user.scoped_role_added",
        "user",
        user.id,
        {"role": role.value, "scope_location_id": str(scope_location_id) if scope_location_id else None},
    )
    db.commit()
    auth_service.revoke_all_refresh_tokens(db, user.id)
    return _serialize(db, user)


def remove_scoped_role(db: Session, actor: CurrentUser, user_id: uuid.UUID, user_role_id: uuid.UUID) -> AdminUserResponse:
    user = _get_user(db, user_id)
    row = db.query(UserRole).filter(UserRole.id == user_role_id, UserRole.user_id == user.id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="role assignment not found")
    db.delete(row)
    record_audit(db, actor.uuid, "user.scoped_role_removed", "user", user.id, {"user_role_id": str(user_role_id)})
    db.commit()
    auth_service.revoke_all_refresh_tokens(db, user.id)
    return _serialize(db, user)


def list_role_definitions() -> list[RoleDefinition]:
    return [
        RoleDefinition(name=role.value, permissions=sorted(p.value for p in permissions))
        for role, permissions in ROLE_PERMISSIONS.items()
    ]


def get_dashboard_counts(db: Session) -> DashboardCounts:
    return DashboardCounts(
        users=db.query(User).count(),
        places=db.query(Place).count(),
        services=db.query(Service).count(),
        hospitals=db.query(Hospital).count(),
        markets=db.query(Market).count(),
        businesses=db.query(Business).count(),
        news_articles=db.query(NewsArticle).count(),
        marketplace_products=db.query(MarketplaceProduct).count(),
        exchange_listings=db.query(ExchangeListing).count(),
        pending_moderation=db.query(ModerationQueue)
        .filter(ModerationQueue.status == ModerationQueueStatus.PENDING.value)
        .count(),
    )


def list_businesses_for_verification(db: Session, actor: CurrentUser) -> list[Business]:
    """Every business regardless of status - verifiers need to see inactive ones too."""
    tenant_id = resolve_tenant_id(db, actor)
    query = db.query(Business)
    if tenant_id:
        query = query.filter(Business.tenant_id == tenant_id)
    return query.order_by(Business.is_verified, Business.name_bn).limit(500).all()


def set_business_verification(db: Session, actor: CurrentUser, business_id: uuid.UUID, is_verified: bool) -> Business:
    business = db.query(Business).filter(Business.id == business_id).first()
    if not business or (business.tenant_id and business.tenant_id != resolve_tenant_id(db, actor)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="business not found")
    if business.is_verified != is_verified:
        business.is_verified = is_verified
        record_audit(
            db,
            actor.uuid,
            "business.verified" if is_verified else "business.unverified",
            "business",
            business.id,
            {"name": business.name_bn},
        )
        db.commit()
        db.refresh(business)
    return business


def list_audit_logs(db: Session, limit: int = 100) -> list[AuditLogResponse]:
    # Outer join - a deleted actor's audit rows must still show up (with a
    # null actor_name), not silently vanish from this list.
    rows = (
        db.query(AuditLog, User.full_name)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        AuditLogResponse(
            id=log.id,
            actor_user_id=log.actor_user_id,
            actor_name=name,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            meta=log.meta,
            created_at=log.created_at,
        )
        for log, name in rows
    ]
