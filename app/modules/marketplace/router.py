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
from app.db.models import ListingType
from app.modules.exchange.lookup import get_public_listing
from app.modules.exchange.schemas import ListingSort
from app.modules.marketplace import service
from app.modules.marketplace.schemas import CategoryResponse, ProductCreate, ProductResponse, ProductUpdate
from app.modules.sellers.schemas import ContactRevealResponse

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(locale: str = Depends(get_locale), db: Session = Depends(get_db)) -> list[CategoryResponse]:
    return [CategoryResponse.from_model(c, locale) for c in service.list_categories(db)]


@router.get("/products", response_model=Paginated[ProductResponse])
def list_products(
    category_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    business_id: uuid.UUID | None = None,
    q: str | None = None,
    condition: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    sort: ListingSort = ListingSort.NEWEST,
    page: PageParams = Depends(),
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    viewer: CurrentUser | None = Depends(get_optional_user),
) -> Paginated[ProductResponse]:
    rows, total = service.list_public(
        db,
        category_id=category_id,
        location_id=location_id,
        business_id=business_id,
        q=q,
        condition=condition,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        page=page,
    )
    return Paginated(
        items=service.to_responses(db, rows, viewer, locale), total=total, page=page.page, page_size=page.page_size
    )


@router.get("/products/mine", response_model=list[ProductResponse])
def my_products(
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ProductResponse]:
    return service.to_responses(db, service.list_mine(db, current_user), current_user, locale)


@router.get("/products/all", response_model=list[ProductResponse])
def all_products_for_admin(
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    moderator: CurrentUser = Depends(require_permission(Permission.MARKETPLACE_MODERATE)),
) -> list[ProductResponse]:
    """Admin CMS list (every status, newest first)."""
    return service.to_responses(db, service.list_all_for_admin(db, moderator), moderator, locale)


@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: uuid.UUID,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    viewer: CurrentUser | None = Depends(get_optional_user),
) -> ProductResponse:
    return service.to_responses(db, [service.get_one(db, product_id, viewer)], viewer, locale)[0]


@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=201,
    dependencies=[Depends(rate_limit_by_user("listing-create", settings.LISTINGS_PER_USER_PER_DAY, 86400))],
)
def create_product(
    payload: ProductCreate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    seller: CurrentUser = Depends(require_phone_verified),
) -> ProductResponse:
    return service.to_responses(db, [service.create(db, seller, payload, background_tasks)], seller, locale)[0]


@router.patch("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_phone_verified),
) -> ProductResponse:
    return service.to_responses(db, [service.update(db, actor, product_id, payload)], actor, locale)[0]


@router.delete("/products/{product_id}", status_code=204)
def delete_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_phone_verified),
) -> None:
    service.remove(db, actor, product_id)


@router.post(
    "/products/{product_id}/contact",
    response_model=ContactRevealResponse,
    dependencies=[Depends(rate_limit_by_user("contact-reveal", settings.CONTACT_REVEALS_PER_USER_PER_HOUR, 3600))],
)
def reveal_contact(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: CurrentUser = Depends(require_phone_verified),
) -> ContactRevealResponse:
    product = get_public_listing(db, ListingType.MARKETPLACE, product_id)
    name, phone = service.reveal_seller_phone(db, product)
    return ContactRevealResponse(seller_name=name, phone=phone)
