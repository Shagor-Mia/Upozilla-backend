import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_locale, require_permission
from app.core.rbac import Permission
from app.modules.faqs import service
from app.modules.faqs.schemas import FaqAdminResponse, FaqCreate, FaqResponse, FaqUpdate

router = APIRouter(prefix="/faqs", tags=["faqs"])


@router.get("", response_model=list[FaqResponse])
def list_faqs(request: Request, locale: str = Depends(get_locale), db: Session = Depends(get_db)) -> list[FaqResponse]:
    return [FaqResponse.from_model(f, locale) for f in service.list_faqs(db, request=request)]


@router.post("", response_model=FaqResponse, status_code=201)
def create_faq(
    payload: FaqCreate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> FaqResponse:
    faq = service.create_faq(db, payload, background_tasks, actor)
    return FaqResponse.from_model(faq, locale)


@router.get("/all", response_model=list[FaqResponse])
def all_faqs_for_admin(
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> list[FaqResponse]:
    """Admin CMS list (every status, newest first)."""
    return [FaqResponse.from_model(f, locale) for f in service.list_all_for_admin(db, actor)]


@router.get("/admin/{faq_id}", response_model=FaqAdminResponse)
def get_faq_admin(
    faq_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> FaqAdminResponse:
    """Raw per-language fields for the admin edit form (Section 22.2)."""
    return FaqAdminResponse.model_validate(service.get_faq_by_id(db, faq_id, actor))


@router.patch("/{faq_id}", response_model=FaqResponse)
def update_faq(
    faq_id: uuid.UUID,
    payload: FaqUpdate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_permission(Permission.CONTENT_MANAGE)),
) -> FaqResponse:
    faq = service.update_faq(db, faq_id, payload, background_tasks, actor)
    return FaqResponse.from_model(faq, locale)
