import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_locale, require_permission
from app.core.geo import NearParams, with_distance
from app.core.pagination import PageParams, Paginated
from app.core.rbac import Permission
from app.modules.hospitals import service
from app.modules.hospitals.schemas import (
    DoctorCreate,
    DoctorResponse,
    HospitalAdminResponse,
    HospitalCreate,
    HospitalResponse,
    HospitalUpdate,
)

router = APIRouter(prefix="/hospitals", tags=["hospitals"])


@router.get("", response_model=Paginated[HospitalResponse])
def list_hospitals(
    request: Request,
    location_id: uuid.UUID | None = None,
    near: NearParams = Depends(),
    page: PageParams = Depends(),
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
) -> Paginated[HospitalResponse]:
    rows, total = service.list_hospitals(db, page, location_id=location_id, near=near, request=request)
    return Paginated(
        items=[with_distance(HospitalResponse.from_model(h, locale), d) for h, d in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/{hospital_id}", response_model=HospitalResponse)
def get_hospital(
    hospital_id: uuid.UUID, request: Request, locale: str = Depends(get_locale), db: Session = Depends(get_db)
) -> HospitalResponse:
    return HospitalResponse.from_model(service.get_hospital(db, hospital_id, request=request), locale)


@router.post("", response_model=HospitalResponse, status_code=201)
def create_hospital(
    payload: HospitalCreate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> HospitalResponse:
    hospital = service.create_hospital(db, payload, background_tasks, actor)
    return HospitalResponse.from_model(hospital, locale)


@router.get("/admin/{hospital_id}", response_model=HospitalAdminResponse)
def get_hospital_admin(
    hospital_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> HospitalAdminResponse:
    return HospitalAdminResponse.model_validate(service.get_hospital(db, hospital_id, actor))


@router.patch("/{hospital_id}", response_model=HospitalResponse)
def update_hospital(
    hospital_id: uuid.UUID,
    payload: HospitalUpdate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> HospitalResponse:
    hospital = service.update_hospital(db, hospital_id, payload, background_tasks, actor)
    return HospitalResponse.from_model(hospital, locale)


@router.get("/{hospital_id}/doctors", response_model=list[DoctorResponse])
def list_doctors(hospital_id: uuid.UUID, request: Request, db: Session = Depends(get_db)) -> list[DoctorResponse]:
    doctors = service.list_doctors(db, hospital_id, request=request)
    return [DoctorResponse.model_validate(d) for d in doctors]


@router.post("/{hospital_id}/doctors", response_model=DoctorResponse, status_code=201)
def create_doctor(
    hospital_id: uuid.UUID,
    payload: DoctorCreate,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> DoctorResponse:
    payload.hospital_id = hospital_id
    return DoctorResponse.model_validate(service.create_doctor(db, payload, actor))
