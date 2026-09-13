import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.core.rbac import Role


class UserRoleUpdate(BaseModel):
    role: Role


class UserStatusUpdate(BaseModel):
    status: str  # "active" | "suspended"


class BusinessVerificationUpdate(BaseModel):
    is_verified: bool


class ScopedRoleCreate(BaseModel):
    role: Role
    scope_location_id: uuid.UUID | None = None


class ScopedRoleResponse(BaseModel):
    id: uuid.UUID
    role: str
    scope_location_id: uuid.UUID | None
    scope_location_name: str | None


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    role: str
    status: str
    phone_verified: bool
    scoped_roles: list[ScopedRoleResponse]
    created_at: datetime


class RoleDefinition(BaseModel):
    name: str
    permissions: list[str]


class DashboardCounts(BaseModel):
    users: int
    places: int
    services: int
    hospitals: int
    markets: int
    businesses: int
    news_articles: int
    marketplace_products: int
    exchange_listings: int
    pending_moderation: int


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_name: str | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    meta: dict[str, Any]
    created_at: datetime
