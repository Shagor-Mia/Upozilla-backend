import uuid

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser
from app.db.models.tenant import Tenant

# Section 13 Phase 5: the one place a request-supplied value is allowed to pick
# the tenant - only consulted for anonymous requests (an authenticated user's
# own tenant always wins, so a header can't be used to hop tenants).
TENANT_HEADER = "X-Tenant-Slug"


def resolve_tenant_id(
    db: Session, current_user: CurrentUser | None = None, *, request: Request | None = None
) -> uuid.UUID | None:
    """Tenant resolution order: (1) the authenticated user's own tenant, never
    client-suppliable; (2) for anonymous requests, an explicit X-Tenant-Slug
    header naming a real active tenant; (3) the single seeded/oldest active
    tenant, the fallback every call site relied on before per-request
    resolution existed - keeps today's single-tenant deployment and every
    caller that doesn't pass `request` behaving exactly as before."""
    if current_user and current_user.tenant_id:
        return uuid.UUID(current_user.tenant_id)
    if request is not None:
        slug = request.headers.get(TENANT_HEADER)
        if slug:
            tenant = db.query(Tenant).filter(Tenant.slug == slug, Tenant.status == "active").first()
            if tenant:
                return tenant.id
    tenant = db.query(Tenant).filter(Tenant.status == "active").order_by(Tenant.created_at).first()
    return tenant.id if tenant else None
