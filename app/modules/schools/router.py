import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, get_locale, require_permission
from app.core.geo import NearParams, with_distance
from app.core.pagination import PageParams, Paginated
from app.core.rbac import Permission
from app.modules.schools import service
from app.modules.schools.schemas import SchoolAdminResponse, SchoolCreate, SchoolResponse, SchoolUpdate

router = APIRouter(prefix="/schools", tags=["schools"])


@router.get("", response_model=Paginated[SchoolResponse])
def list_schools(
    request: Request,
    location_id: uuid.UUID | None = None,
    near: NearParams = Depends(),
    page: PageParams = Depends(),
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
) -> Paginated[SchoolResponse]:
    rows, total = service.list_schools(db, page, location_id=location_id, near=near, request=request)
    return Paginated(
        items=[with_distance(SchoolResponse.from_model(s, locale), d) for s, d in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get("/mine", response_model=SchoolAdminResponse | None)
def get_my_school(
    db: Session = Depends(get_db), actor: CurrentUser = Depends(get_current_user)
) -> SchoolAdminResponse | None:
    school = service.get_my_school(db, actor)
    return SchoolAdminResponse.model_validate(school) if school else None


@router.get("/{school_id}", response_model=SchoolResponse)
def get_school(
    school_id: uuid.UUID, request: Request, locale: str = Depends(get_locale), db: Session = Depends(get_db)
) -> SchoolResponse:
    return SchoolResponse.from_model(service.get_school(db, school_id, request=request), locale)


@router.post("", response_model=SchoolResponse, status_code=201)
def create_school(
    payload: SchoolCreate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> SchoolResponse:
    # Staff (CONTENT_MANAGE) may create any school; a plain user needs the
    # admin-granted can_manage_school flag and is capped at one - both
    # enforced in service.create_school, not here, so the 403/400 detail
    # stays in one place.
    school = service.create_school(db, payload, background_tasks, actor)
    return SchoolResponse.from_model(school, locale)


@router.get("/admin/{school_id}", response_model=SchoolAdminResponse)
def get_school_admin(
    school_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> SchoolAdminResponse:
    return SchoolAdminResponse.model_validate(service.get_school(db, school_id, actor))


@router.patch("/{school_id}", response_model=SchoolResponse)
def update_school(
    school_id: uuid.UUID,
    payload: SchoolUpdate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> SchoolResponse:
    # Ownership check (staff vs. the school's own owner_user_id) lives in
    # service.update_school / _assert_can_manage.
    school = service.update_school(db, school_id, payload, background_tasks, actor)
    return SchoolResponse.from_model(school, locale)
