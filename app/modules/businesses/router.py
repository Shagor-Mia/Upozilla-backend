import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, get_locale, require_permission
from app.core.geo import NearParams, with_distance
from app.core.rbac import Permission
from app.modules.businesses import service
from app.modules.businesses.schemas import BusinessAdminResponse, BusinessCreate, BusinessResponse, BusinessUpdate

router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.get("", response_model=list[BusinessResponse])
def list_businesses(
    request: Request,
    location_id: uuid.UUID | None = None,
    near: NearParams = Depends(),
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
) -> list[BusinessResponse]:
    rows = service.list_businesses(db, location_id=location_id, near=near, request=request)
    return [with_distance(BusinessResponse.from_model(b, locale), d) for b, d in rows]


@router.get("/{slug}", response_model=BusinessResponse)
def get_business(
    slug: str, request: Request, locale: str = Depends(get_locale), db: Session = Depends(get_db)
) -> BusinessResponse:
    return BusinessResponse.from_model(service.get_business_by_slug(db, slug, request=request), locale)


@router.post("", response_model=BusinessResponse, status_code=201)
def create_business(
    payload: BusinessCreate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BusinessResponse:
    business = service.create_business(db, uuid.UUID(current_user.user_id), payload, background_tasks, current_user)
    return BusinessResponse.from_model(business, locale)


@router.get("/admin/{business_id}", response_model=BusinessAdminResponse)
def get_business_admin(
    business_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE, Permission.BUSINESS_VERIFY)),
) -> BusinessAdminResponse:
    """Raw per-language fields for the admin edit form (Section 22.2)."""
    return BusinessAdminResponse.model_validate(service.get_business_by_id(db, business_id, actor))


@router.patch("/{business_id}", response_model=BusinessResponse)
def update_business(
    business_id: uuid.UUID,
    payload: BusinessUpdate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE, Permission.BUSINESS_VERIFY)),
) -> BusinessResponse:
    business = service.update_business(db, business_id, payload, background_tasks, actor)
    return BusinessResponse.from_model(business, locale)
