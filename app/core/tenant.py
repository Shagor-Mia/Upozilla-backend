import uuid
import time
from threading import Lock

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser
from app.db.models.tenant import Tenant

# Section 13 Phase 5: the one place a request-supplied value is allowed to pick
# the tenant - only consulted for anonymous requests (an authenticated user's
# own tenant always wins, so a header can't be used to hop tenants).
TENANT_HEADER = "X-Tenant-Slug"
TENANT_CACHE_TTL_SECONDS = 30.0

_cache_lock = Lock()
_slug_cache: dict[str, tuple[uuid.UUID, float]] = {}
_fallback_cache: tuple[uuid.UUID | None, float] = (None, 0.0)


def _cached_slug(slug: str) -> uuid.UUID | None:
    now = time.monotonic()
    with _cache_lock:
        cached = _slug_cache.get(slug)
        if cached and cached[1] > now:
            return cached[0]
    return None


def _remember_slug(slug: str, tenant_id: uuid.UUID) -> None:
    with _cache_lock:
        _slug_cache[slug] = (tenant_id, time.monotonic() + TENANT_CACHE_TTL_SECONDS)


def _cached_fallback() -> uuid.UUID | None:
    tenant_id, expires_at = _fallback_cache
    if expires_at > time.monotonic():
        return tenant_id
    return None


def _remember_fallback(tenant_id: uuid.UUID | None) -> None:
    global _fallback_cache
    _fallback_cache = (tenant_id, time.monotonic() + TENANT_CACHE_TTL_SECONDS)


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
            cached = _cached_slug(slug)
            if cached is not None:
                return cached
            tenant = db.query(Tenant).filter(Tenant.slug == slug, Tenant.status == "active").first()
            if tenant:
                _remember_slug(slug, tenant.id)
                return tenant.id
    cached = _cached_fallback()
    if cached is not None:
        return cached
    tenant = db.query(Tenant).filter(Tenant.status == "active").order_by(Tenant.created_at).first()
    tenant_id = tenant.id if tenant else None
    _remember_fallback(tenant_id)
    return tenant_id
