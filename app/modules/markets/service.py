import uuid

from fastapi import BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.core import embeddings, translation
from app.core.content_scope import assert_tenant_match, tenant_scoped
from app.core.dependencies import CurrentUser
from app.core.geo import NearParams, apply_near_paginated
from app.core.pagination import PageParams
from app.core.tenant import resolve_tenant_id
from app.db.models.ai import KnowledgeSourceType

from app.db.models.market import Market
from app.modules.markets.schemas import MarketCreate, MarketUpdate


def _schedule_reindex(background_tasks: BackgroundTasks, market: Market) -> None:
    # Markets have no status column (Section 17 Phase 1) - always public.
    days = ", ".join(market.market_day or [])
    text = f"{market.name_bn} {market.name_en or ''} {days} {market.description_bn or ''}".strip()
    embeddings.schedule_reindex(background_tasks, KnowledgeSourceType.MARKET, market.id, text, market.tenant_id)


def update_market(
    db: Session, market_id, payload: MarketUpdate, background_tasks: BackgroundTasks, actor: CurrentUser
) -> Market:
    market = get_market(db, market_id, actor)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(market, field, value)
    db.commit()
    db.refresh(market)
    translation.schedule_translations(background_tasks, Market, market.id, ["name"])
    _schedule_reindex(background_tasks, market)
    return market


def list_markets(
    db: Session,
    page: PageParams,
    location_id: uuid.UUID | None = None,
    near: NearParams | None = None,
    *,
    request: Request | None = None,
) -> tuple[list[tuple[Market, float | None]], int]:
    query = tenant_scoped(db.query(Market), Market, db, request=request)
    if location_id is not None:
        query = query.filter(Market.location_id == location_id)
    return apply_near_paginated(query.order_by(Market.name_bn), Market, near or NearParams(), page)


def get_market(
    db: Session, market_id: uuid.UUID, actor: CurrentUser | None = None, *, request: Request | None = None
) -> Market:
    """Tenant match is enforced either way: `actor` for authenticated admin
    call sites (edit, admin raw-fields view), `request`'s X-Tenant-Slug header
    for the public GET (Section 13 Phase 5 per-request tenant resolution)."""
    market = db.query(Market).filter(Market.id == market_id).first()
    assert_tenant_match(market, db, actor=actor, request=request, detail="market not found")
    return market


def create_market(
    db: Session, payload: MarketCreate, background_tasks: BackgroundTasks, actor: CurrentUser
) -> Market:
    market = Market(tenant_id=resolve_tenant_id(db, actor), **payload.model_dump())
    db.add(market)
    db.commit()
    db.refresh(market)
    translation.schedule_translations(background_tasks, Market, market.id, ["name"])
    _schedule_reindex(background_tasks, market)
    return market
