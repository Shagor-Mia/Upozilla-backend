import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_locale,
    get_optional_user,
    require_permission,
    require_phone_verified,
)
from app.core.pagination import PageParams, Paginated
from app.core.rate_limit import rate_limit_by_user
from app.core.rbac import Permission
from app.modules.shops import service
from app.modules.shops.schemas import ShopAdminResponse, ShopCategoryResponse, ShopCreate, ShopResponse, ShopUpdate

router = APIRouter(prefix="/shops", tags=["shops"])


@router.get("/categories", response_model=list[ShopCategoryResponse])
def list_categories(locale: str = Depends(get_locale), db: Session = Depends(get_db)) -> list[ShopCategoryResponse]:
    return [ShopCategoryResponse.from_model(c, locale) for c in service.list_categories(db)]


@router.get("", response_model=Paginated[ShopResponse])
def list_shops(
    market_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    featured_only: bool = False,
    page: PageParams = Depends(),
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
) -> Paginated[ShopResponse]:
    rows, total = service.list_public(
        db, market_id=market_id, category_id=category_id, featured_only=featured_only, page=page
    )
    return Paginated(
        items=service.to_responses(db, rows, locale), total=total, page=page.page, page_size=page.page_size
    )


@router.get("/mine", response_model=list[ShopResponse])
def my_shops(
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ShopResponse]:
    return service.to_responses(db, service.list_mine(db, current_user), locale)


@router.get("/all", response_model=list[ShopResponse])
def all_shops_for_admin(
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    moderator: CurrentUser = Depends(require_permission(Permission.MARKETPLACE_MODERATE)),
) -> list[ShopResponse]:
    """Admin CMS list (every status, newest first)."""
    return service.to_responses(db, service.list_all_for_admin(db, moderator), locale)


@router.get("/admin/{shop_id}", response_model=ShopAdminResponse)
def get_shop_admin(
    shop_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_permission(Permission.MARKETPLACE_MODERATE)),
) -> ShopAdminResponse:
    """Raw fields for the admin edit form (Section 22.2)."""
    return ShopAdminResponse.from_model(service.get_for_admin(db, shop_id))


@router.get("/{shop_id}", response_model=ShopResponse)
def get_shop(
    shop_id: uuid.UUID,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    viewer: CurrentUser | None = Depends(get_optional_user),
) -> ShopResponse:
    return service.to_responses(db, [service.get_one(db, shop_id, viewer)], locale)[0]


@router.post(
    "",
    response_model=ShopResponse,
    status_code=201,
    dependencies=[Depends(rate_limit_by_user("shop-create", settings.SHOPS_PER_USER_PER_DAY, 86400))],
)
def create_shop(
    payload: ShopCreate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    seller: CurrentUser = Depends(require_phone_verified),
) -> ShopResponse:
    return service.to_responses(db, [service.create(db, seller, payload, background_tasks)], locale)[0]


@router.patch("/{shop_id}", response_model=ShopResponse)
def update_shop(
    shop_id: uuid.UUID,
    payload: ShopUpdate,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(get_current_user),
) -> ShopResponse:
    """Phone verification is enforced inside `service.update` only for the
    owner-editing path - a moderator/admin (gated there by MARKETPLACE_MODERATE
    instead) shouldn't need their own phone verified to approve/feature a shop."""
    return service.to_responses(db, [service.update(db, actor, shop_id, payload)], locale)[0]
