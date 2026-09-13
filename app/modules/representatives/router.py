import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, get_locale, require_permission
from app.core.pagination import PageParams, Paginated
from app.core.rbac import Permission
from app.db.models.representative import RepresentativePosition
from app.modules.representatives import service
from app.modules.representatives.schemas import (
    RepresentativeAdminResponse,
    RepresentativeAdminUpdate,
    RepresentativeCreate,
    RepresentativeResponse,
)

router = APIRouter(prefix="/representatives", tags=["representatives"])


@router.get("", response_model=Paginated[RepresentativeResponse])
def list_representatives(
    location_id: uuid.UUID | None = None,
    position: RepresentativePosition | None = None,
    page: PageParams = Depends(),
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
) -> Paginated[RepresentativeResponse]:
    rows, total = service.list_public(
        db, location_id=location_id, position=position.value if position else None, page=page
    )
    return Paginated(
        items=service.to_responses(db, rows, locale), total=total, page=page.page, page_size=page.page_size
    )


@router.get("/mine", response_model=list[RepresentativeResponse])
def list_my_representative_profiles(
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> list[RepresentativeResponse]:
    return service.to_responses(db, service.list_mine(db, actor.uuid), locale)


@router.get("/admin/{rep_id}", response_model=RepresentativeAdminResponse)
def get_representative_admin(
    rep_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> RepresentativeAdminResponse:
    """Raw fields for the admin edit form (Section 22.2)."""
    return RepresentativeAdminResponse.from_model(service.get_one(db, rep_id))


@router.get("/{rep_id}", response_model=RepresentativeResponse)
def get_representative(
    rep_id: uuid.UUID, locale: str = Depends(get_locale), db: Session = Depends(get_db)
) -> RepresentativeResponse:
    return service.to_responses(db, [service.get_public(db, rep_id)], locale)[0]


@router.post("", response_model=RepresentativeResponse, status_code=201)
def create_representative(
    payload: RepresentativeCreate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> RepresentativeResponse:
    rep = service.create(db, actor, payload, background_tasks)
    return service.to_responses(db, [rep], locale)[0]


@router.patch("/{rep_id}", response_model=RepresentativeResponse)
def update_representative(
    rep_id: uuid.UUID,
    payload: RepresentativeAdminUpdate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> RepresentativeResponse:
    """The linked account's owner may update their own bio/photo; a
    CONTENT_MANAGE actor may additionally reassign location/position/status
    (app/modules/representatives/service.py:update)."""
    is_admin = actor.has_permission(Permission.CONTENT_MANAGE)
    rep = service.update(db, actor, rep_id, payload, background_tasks, is_admin=is_admin)
    return service.to_responses(db, [rep], locale)[0]
