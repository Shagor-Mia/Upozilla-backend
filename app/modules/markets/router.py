import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_locale, require_permission
from app.core.geo import NearParams, with_distance
from app.core.pagination import PageParams, Paginated
from app.core.rbac import Permission
from app.modules.markets import service
from app.modules.markets.schemas import MarketAdminResponse, MarketCreate, MarketResponse, MarketUpdate

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("", response_model=Paginated[MarketResponse])
def list_markets(
    request: Request,
    location_id: uuid.UUID | None = None,
    near: NearParams = Depends(),
    page: PageParams = Depends(),
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
) -> Paginated[MarketResponse]:
    rows, total = service.list_markets(db, page, location_id=location_id, near=near, request=request)
    return Paginated(
        items=[with_distance(MarketResponse.from_model(m, locale), d) for m, d in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/{market_id}", response_model=MarketResponse)
def get_market(
    market_id: uuid.UUID, request: Request, locale: str = Depends(get_locale), db: Session = Depends(get_db)
) -> MarketResponse:
    return MarketResponse.from_model(service.get_market(db, market_id, request=request), locale)


@router.post("", response_model=MarketResponse, status_code=201)
def create_market(
    payload: MarketCreate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> MarketResponse:
    market = service.create_market(db, payload, background_tasks, actor)
    return MarketResponse.from_model(market, locale)


@router.get("/admin/{market_id}", response_model=MarketAdminResponse)
def get_market_admin(
    market_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> MarketAdminResponse:
    return MarketAdminResponse.model_validate(service.get_market(db, market_id, actor))


@router.patch("/{market_id}", response_model=MarketResponse)
def update_market(
    market_id: uuid.UUID,
    payload: MarketUpdate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> MarketResponse:
    market = service.update_market(db, market_id, payload, background_tasks, actor)
    return MarketResponse.from_model(market, locale)
