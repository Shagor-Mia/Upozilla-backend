import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, get_locale, require_permission
from app.core.pagination import PageParams, Paginated
from app.core.rbac import Permission
from app.modules.government_services import service
from app.modules.government_services.schemas import (
    LicenseApplicationCreate,
    LicenseApplicationResponse,
    ServiceAdminResponse,
    ServiceCategoryResponse,
    ServiceCreate,
    ServiceResponse,
    ServiceUpdate,
)

router = APIRouter(prefix="/services", tags=["government-services"])


@router.get("/categories", response_model=list[ServiceCategoryResponse])
def list_categories(locale: str = Depends(get_locale), db: Session = Depends(get_db)) -> list[ServiceCategoryResponse]:
    return [ServiceCategoryResponse.from_model(c, locale) for c in service.list_categories(db)]


@router.get("", response_model=Paginated[ServiceResponse])
def list_services(
    request: Request,
    location_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    page: PageParams = Depends(),
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
) -> Paginated[ServiceResponse]:
    services, total = service.list_services(
        db, page, location_id=location_id, category_id=category_id, request=request
    )
    return Paginated(
        items=[ServiceResponse.from_model(s, locale) for s in services],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/{service_id}", response_model=ServiceResponse)
def get_service(
    service_id: uuid.UUID, request: Request, locale: str = Depends(get_locale), db: Session = Depends(get_db)
) -> ServiceResponse:
    return ServiceResponse.from_model(service.get_service(db, service_id, request=request), locale)


@router.post("", response_model=ServiceResponse, status_code=201)
def create_service(
    payload: ServiceCreate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> ServiceResponse:
    svc = service.create_service(db, payload, background_tasks, actor)
    return ServiceResponse.from_model(svc, locale)


@router.get("/admin/{service_id}", response_model=ServiceAdminResponse)
def get_service_admin(
    service_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> ServiceAdminResponse:
    return ServiceAdminResponse.model_validate(service.get_service_by_id(db, service_id, actor))


@router.patch("/{service_id}", response_model=ServiceResponse)
def update_service(
    service_id: uuid.UUID,
    payload: ServiceUpdate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> ServiceResponse:
    svc = service.update_service(db, service_id, payload, background_tasks, actor)
    return ServiceResponse.from_model(svc, locale)


@router.post("/applications", response_model=LicenseApplicationResponse, status_code=201)
def create_application(
    payload: LicenseApplicationCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> LicenseApplicationResponse:
    application = service.create_license_application(db, uuid.UUID(current_user.user_id), payload)
    return LicenseApplicationResponse.model_validate(application)


@router.get("/applications/me", response_model=list[LicenseApplicationResponse])
def list_my_applications(
    db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)
) -> list[LicenseApplicationResponse]:
    applications = service.list_my_applications(db, uuid.UUID(current_user.user_id))
    return [LicenseApplicationResponse.model_validate(a) for a in applications]
