import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_locale, require_permission
from app.core.rbac import Permission
from app.modules.admin import service
from app.modules.admin.schemas import (
    AdminUserResponse,
    AuditLogResponse,
    BusinessVerificationUpdate,
    DashboardCounts,
    RoleDefinition,
    ScopedRoleCreate,
    UserRoleUpdate,
    UserStatusUpdate,
)
from app.modules.businesses.schemas import BusinessResponse

router = APIRouter(prefix="/admin", tags=["admin"])

users_manage = require_permission(Permission.USERS_MANAGE)
roles_manage = require_permission(Permission.ROLES_MANAGE)
business_verify = require_permission(Permission.BUSINESS_VERIFY)


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(db: Session = Depends(get_db), _: CurrentUser = Depends(users_manage)) -> list[AdminUserResponse]:
    return service.list_users(db)


@router.patch("/users/{user_id}/role", response_model=AdminUserResponse)
def update_user_role(
    user_id: uuid.UUID,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(roles_manage),
) -> AdminUserResponse:
    return service.update_user_role(db, actor, user_id, payload.role)


@router.patch("/users/{user_id}/status", response_model=AdminUserResponse)
def update_user_status(
    user_id: uuid.UUID,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(users_manage),
) -> AdminUserResponse:
    return service.update_user_status(db, actor, user_id, payload.status)


@router.post("/users/{user_id}/roles", response_model=AdminUserResponse, status_code=201)
def add_scoped_role(
    user_id: uuid.UUID,
    payload: ScopedRoleCreate,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(roles_manage),
) -> AdminUserResponse:
    return service.add_scoped_role(db, actor, user_id, payload.role, payload.scope_location_id)


@router.delete("/users/{user_id}/roles/{user_role_id}", response_model=AdminUserResponse)
def remove_scoped_role(
    user_id: uuid.UUID,
    user_role_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(roles_manage),
) -> AdminUserResponse:
    return service.remove_scoped_role(db, actor, user_id, user_role_id)


@router.get("/roles", response_model=list[RoleDefinition])
def list_roles(_: CurrentUser = Depends(users_manage)) -> list[RoleDefinition]:
    return service.list_role_definitions()


@router.get("/dashboard", response_model=DashboardCounts)
def dashboard(
    db: Session = Depends(get_db), _: CurrentUser = Depends(require_permission(Permission.DASHBOARD_VIEW))
) -> DashboardCounts:
    return service.get_dashboard_counts(db)


@router.get("/businesses", response_model=list[BusinessResponse])
def list_businesses(
    locale: str = Depends(get_locale), db: Session = Depends(get_db), actor: CurrentUser = Depends(business_verify)
) -> list[BusinessResponse]:
    return [BusinessResponse.from_model(b, locale) for b in service.list_businesses_for_verification(db, actor)]


@router.patch("/businesses/{business_id}/verification", response_model=BusinessResponse)
def update_business_verification(
    business_id: uuid.UUID,
    payload: BusinessVerificationUpdate,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(business_verify),
) -> BusinessResponse:
    return BusinessResponse.from_model(
        service.set_business_verification(db, actor, business_id, payload.is_verified), locale
    )


@router.get("/audit-logs", response_model=list[AuditLogResponse])
def audit_logs(db: Session = Depends(get_db), _: CurrentUser = Depends(users_manage)) -> list[AuditLogResponse]:
    return service.list_audit_logs(db)
