import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, get_locale, require_permission
from app.core.geo import NearParams, with_distance
from app.core.pagination import PageParams, Paginated
from app.core.rate_limit import rate_limit_by_user
from app.core.rbac import Permission
from app.core.config import settings
from app.db.models.place import PlaceCategory
from app.modules.places import service
from app.modules.places.schemas import PlaceAdminResponse, PlaceCreate, PlaceResponse, PlaceSubmit, PlaceUpdate

router = APIRouter(prefix="/places", tags=["places"])


@router.get("", response_model=Paginated[PlaceResponse])
def list_places(
    request: Request,
    location_id: uuid.UUID | None = None,
    featured_only: bool = False,
    category: PlaceCategory | None = None,
    near: NearParams = Depends(),
    page: PageParams = Depends(),
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
) -> Paginated[PlaceResponse]:
    rows, total = service.list_places(
        db, page, location_id=location_id, featured_only=featured_only, category=category, near=near, request=request
    )
    return Paginated(
        items=[with_distance(PlaceResponse.from_model(p, locale), d) for p, d in rows],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


# Must come before GET /{slug} - otherwise FastAPI matches "mine" as a slug
# (see the same ordering note on GET /marketplace/products/mine).
@router.get("/mine", response_model=list[PlaceResponse])
def my_places(
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> list[PlaceResponse]:
    return [PlaceResponse.from_model(p, locale) for p in service.list_mine(db, actor)]


@router.post(
    "/submit",
    response_model=PlaceResponse,
    status_code=201,
    dependencies=[Depends(rate_limit_by_user("place-submit", settings.LISTINGS_PER_USER_PER_DAY, 86400))],
)
def submit_place(
    payload: PlaceSubmit,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> PlaceResponse:
    """Public submission - any logged-in user (no phone verification, no
    CONTENT_MANAGE), always pending until an admin reviews it."""
    place = service.submit_place(db, payload, background_tasks, actor)
    return PlaceResponse.from_model(place, locale)


@router.get("/{slug}", response_model=PlaceResponse)
def get_place(
    slug: str, request: Request, locale: str = Depends(get_locale), db: Session = Depends(get_db)
) -> PlaceResponse:
    place = service.get_place_by_slug(db, slug, request=request)
    return PlaceResponse.from_model(place, locale)


@router.post("", response_model=PlaceResponse, status_code=201)
def create_place(
    payload: PlaceCreate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> PlaceResponse:
    place = service.create_place(db, payload, background_tasks, actor)
    return PlaceResponse.from_model(place, locale)


@router.get("/admin/{place_id}", response_model=PlaceAdminResponse)
def get_place_admin(
    place_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> PlaceAdminResponse:
    """Raw per-language fields for the admin edit form (Section 22.2)."""
    return PlaceAdminResponse.model_validate(service.get_place_by_id(db, place_id, actor))


@router.patch("/{place_id}", response_model=PlaceResponse)
def update_place(
    place_id: uuid.UUID,
    payload: PlaceUpdate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> PlaceResponse:
    place = service.update_place(db, place_id, payload, background_tasks, actor)
    return PlaceResponse.from_model(place, locale)
