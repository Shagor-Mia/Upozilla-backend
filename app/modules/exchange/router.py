import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
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
from app.modules.exchange import favorites, reports, service
from app.modules.exchange.lookup import get_public_listing
from app.modules.exchange.schemas import (
    ExchangeListingCreate,
    ExchangeListingResponse,
    ExchangeListingUpdate,
    FavoriteResponse,
    ListingReportCreate,
    ListingReportResponse,
    ListingSort,
)
from app.modules.marketplace import service as marketplace_service
from app.modules.marketplace.schemas import FavoritesResponse
from app.modules.sellers.schemas import ContactRevealResponse

router = APIRouter(prefix="/exchange", tags=["exchange"])


@router.get("/listings", response_model=Paginated[ExchangeListingResponse])
def list_listings(
    category_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    q: str | None = None,
    condition: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    sort: ListingSort = ListingSort.NEWEST,
    page: PageParams = Depends(),
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    viewer: CurrentUser | None = Depends(get_optional_user),
) -> Paginated[ExchangeListingResponse]:
    rows, total = service.list_public(
        db,
        category_id=category_id,
        location_id=location_id,
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


@router.get("/listings/mine", response_model=list[ExchangeListingResponse])
def my_listings(
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[ExchangeListingResponse]:
    return service.to_responses(db, service.list_mine(db, current_user), current_user, locale)


@router.get("/listings/all", response_model=list[ExchangeListingResponse])
def all_listings_for_admin(
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    moderator: CurrentUser = Depends(require_permission(Permission.MARKETPLACE_MODERATE)),
) -> list[ExchangeListingResponse]:
    """Admin CMS list (every status, newest first)."""
    return service.to_responses(db, service.list_all_for_admin(db, moderator), moderator, locale)


@router.get("/listings/{listing_id}", response_model=ExchangeListingResponse)
def get_listing(
    listing_id: uuid.UUID,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    viewer: CurrentUser | None = Depends(get_optional_user),
) -> ExchangeListingResponse:
    return service.to_responses(db, [service.get_one(db, listing_id, viewer)], viewer, locale)[0]


@router.post(
    "/listings",
    response_model=ExchangeListingResponse,
    status_code=201,
    dependencies=[Depends(rate_limit_by_user("listing-create", settings.LISTINGS_PER_USER_PER_DAY, 86400))],
)
def create_listing(
    payload: ExchangeListingCreate,
    background_tasks: BackgroundTasks,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    seller: CurrentUser = Depends(require_phone_verified),
) -> ExchangeListingResponse:
    return service.to_responses(db, [service.create(db, seller, payload, background_tasks)], seller, locale)[0]


@router.patch("/listings/{listing_id}", response_model=ExchangeListingResponse)
def update_listing(
    listing_id: uuid.UUID,
    payload: ExchangeListingUpdate,
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_phone_verified),
) -> ExchangeListingResponse:
    return service.to_responses(db, [service.update(db, actor, listing_id, payload)], actor, locale)[0]


@router.delete("/listings/{listing_id}", status_code=204)
def delete_listing(
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_phone_verified),
) -> None:
    service.remove(db, actor, listing_id)


# --- contact reveal (Section 14.4: gated + rate limited) ---------------------------


@router.post(
    "/listings/{listing_id}/contact",
    response_model=ContactRevealResponse,
    dependencies=[Depends(rate_limit_by_user("contact-reveal", settings.CONTACT_REVEALS_PER_USER_PER_HOUR, 3600))],
)
def reveal_contact(
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_phone_verified),
) -> ContactRevealResponse:
    listing = get_public_listing(db, ListingType.EXCHANGE, listing_id)
    if listing.seller_user_id == actor.uuid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="you cannot reveal contact info on your own listing")
    name, phone = service.reveal_seller_phone(db, listing)
    return ContactRevealResponse(seller_name=name, phone=phone)


# --- favorites (both listing kinds) -------------------------------------------------


@router.put("/favorites/{listing_type}/{listing_id}", response_model=FavoriteResponse)
def add_favorite(
    listing_type: ListingType,
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> FavoriteResponse:
    favorites.set_favorite(db, current_user.uuid, listing_type, listing_id, on=True)
    return FavoriteResponse(listing_type=listing_type, listing_id=listing_id, is_favorited=True)


@router.delete("/favorites/{listing_type}/{listing_id}", response_model=FavoriteResponse)
def remove_favorite(
    listing_type: ListingType,
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> FavoriteResponse:
    favorites.set_favorite(db, current_user.uuid, listing_type, listing_id, on=False)
    return FavoriteResponse(listing_type=listing_type, listing_id=listing_id, is_favorited=False)


@router.get("/favorites", response_model=FavoritesResponse)
def list_favorites(
    locale: str = Depends(get_locale),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> FavoritesResponse:
    grouped = favorites.list_user_favorites(db, current_user.uuid)
    exchange_rows = service.get_by_ids_public(db, grouped[ListingType.EXCHANGE])
    product_rows = marketplace_service.get_by_ids_public(db, grouped[ListingType.MARKETPLACE])
    return FavoritesResponse(
        exchange=service.to_responses(db, exchange_rows, current_user, locale),
        marketplace=marketplace_service.to_responses(db, product_rows, current_user, locale),
    )


# --- reports (both listing kinds) ---------------------------------------------------


@router.post(
    "/reports/{listing_type}/{listing_id}",
    response_model=ListingReportResponse,
    status_code=201,
    dependencies=[Depends(rate_limit_by_user("reports", limit=20, window_seconds=86400))],
)
def report_listing(
    listing_type: ListingType,
    listing_id: uuid.UUID,
    payload: ListingReportCreate,
    db: Session = Depends(get_db),
    reporter: CurrentUser = Depends(get_current_user),
) -> ListingReportResponse:
    return reports.create_report(db, reporter, listing_type, listing_id, payload)
