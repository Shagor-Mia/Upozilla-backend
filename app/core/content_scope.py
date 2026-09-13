"""Shared tenant-scoping helpers for the public content modules (markets,
hospitals, places, government_services, faqs, businesses, news) that all
repeat the same two control-flow blocks around `resolve_tenant_id` - one for
filtering a list query, one for 404ing a single fetched row on a tenant
mismatch. Each module keeps its own field mapping, filters, and model-specific
logic; only the identical tenant-check plumbing lives here."""

from fastapi import HTTPException, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.core.dependencies import CurrentUser
from app.core.tenant import resolve_tenant_id


def tenant_scoped(query: Query, model, db: Session, *, actor: CurrentUser | None = None, request: Request | None = None) -> Query:
    """Filters `query` to the resolved tenant, permissively including
    untenanted (legacy) rows so an unbackfilled row is never hidden from
    everyone. Returns `query` unchanged if no tenant can be resolved at all."""
    tenant_id = resolve_tenant_id(db, actor, request=request)
    if tenant_id is None:
        return query
    return query.filter(or_(model.tenant_id == tenant_id, model.tenant_id.is_(None)))


def assert_tenant_match(
    obj, db: Session, *, actor: CurrentUser | None = None, request: Request | None = None, detail: str
) -> None:
    """Raises 404 if `obj` is None, or belongs to a different tenant than the
    one resolved for this request/actor. A `None` `obj.tenant_id` (legacy,
    unbackfilled row) is always treated as accessible."""
    tenant_id = resolve_tenant_id(db, actor, request=request)
    if obj is None or (tenant_id is not None and obj.tenant_id and obj.tenant_id != tenant_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
