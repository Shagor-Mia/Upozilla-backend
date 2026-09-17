import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_locale, require_permission
from app.core.rbac import Permission
from app.modules.govt_offices import service
from app.modules.govt_offices.schemas import (
    GovtOfficeAdminResponse,
    GovtOfficeCreate,
    GovtOfficeResponse,
    GovtOfficeUpdate,
)

router = APIRouter(prefix="/govt-offices", tags=["govt-offices"])


@router.get("", response_model=list[GovtOfficeResponse])
def list_offices(
    request: Request,
    location_id: uuid.UUID | None = None,
    category: str | None = None,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
) -> list[GovtOfficeResponse]:
    rows = service.list_offices(db, location_id=location_id, category=category, request=request)
    return [GovtOfficeResponse.from_model(o, locale) for o in rows]


@router.get("/{office_id}", response_model=GovtOfficeResponse)
def get_office(
    office_id: uuid.UUID, request: Request, locale: str = Depends(get_locale), db: Session = Depends(get_db)
) -> GovtOfficeResponse:
    return GovtOfficeResponse.from_model(service.get_office(db, office_id, request=request), locale)


@router.post("", response_model=GovtOfficeResponse, status_code=201)
def create_office(
    payload: GovtOfficeCreate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> GovtOfficeResponse:
    office = service.create_office(db, payload, background_tasks, actor)
    return GovtOfficeResponse.from_model(office, locale)


@router.get("/admin/{office_id}", response_model=GovtOfficeAdminResponse)
def get_office_admin(
    office_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> GovtOfficeAdminResponse:
    return GovtOfficeAdminResponse.model_validate(service.get_office(db, office_id, actor))


@router.patch("/{office_id}", response_model=GovtOfficeResponse)
def update_office(
    office_id: uuid.UUID,
    payload: GovtOfficeUpdate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> GovtOfficeResponse:
    office = service.update_office(db, office_id, payload, background_tasks, actor)
    return GovtOfficeResponse.from_model(office, locale)
