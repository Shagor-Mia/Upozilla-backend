"""Section 17 Phase 4 "personalized recommendations" = location + trending
fallback (per the project owner - no browsing history/home-location field
exists yet to build favorites-based similarity on). Pure SQL, no LLM/vector
involved - reuses the same `to_responses`/`get_by_ids_public` helpers the
marketplace/exchange list endpoints already use."""

import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser
from app.db.models import (
    ExchangeListing,
    Hospital,
    ListingFavorite,
    ListingStatus,
    ListingType,
    Market,
    MarketplaceProduct,
    ModerationStatus,
    NewsArticle,
    Place,
    ProductStatus,
    Service,
)
from app.modules.exchange import service as exchange_service
from app.modules.government_services.schemas import ServiceResponse
from app.modules.hospitals.schemas import HospitalResponse
from app.modules.marketplace import service as marketplace_service
from app.modules.markets.schemas import MarketResponse
from app.modules.news.schemas import NewsArticleResponse
from app.modules.places.schemas import PlaceResponse
from app.modules.recommendations.schemas import RecommendationsResponse

PER_SECTION_LIMIT = 5
# Section 19.6: never leave the viewer looking at an all-but-empty page just
# because their exact location has little content yet.
MIN_ITEMS_BEFORE_WIDENING = 5


def _trending_ids(db: Session, model, status_filters: list, listing_type: ListingType, location_id, limit: int):
    query = (
        db.query(ListingFavorite.listing_id, func.count(ListingFavorite.id))
        .join(model, model.id == ListingFavorite.listing_id)
        .filter(ListingFavorite.listing_type == listing_type.value)
    )
    for condition in status_filters:
        query = query.filter(condition)
    if location_id is not None:
        query = query.filter(model.location_id == location_id)
    rows = (
        query.group_by(ListingFavorite.listing_id)
        .order_by(func.count(ListingFavorite.id).desc())
        .limit(limit)
        .all()
    )
    return [row[0] for row in rows]


def _fetch_bundle(db: Session, viewer: CurrentUser | None, locale: str, location_id, limit: int):
    product_ids = _trending_ids(
        db,
        MarketplaceProduct,
        [
            MarketplaceProduct.status == ProductStatus.ACTIVE.value,
            MarketplaceProduct.moderation_status == ModerationStatus.APPROVED.value,
        ],
        ListingType.MARKETPLACE,
        location_id,
        limit,
    )
    products = marketplace_service.to_responses(
        db, marketplace_service.get_by_ids_public(db, product_ids), viewer, locale
    )

    exchange_ids = _trending_ids(
        db,
        ExchangeListing,
        [
            ExchangeListing.status == ListingStatus.ACTIVE.value,
            ExchangeListing.moderation_status == ModerationStatus.APPROVED.value,
        ],
        ListingType.EXCHANGE,
        location_id,
        limit,
    )
    exchange_listings = exchange_service.to_responses(
        db, exchange_service.get_by_ids_public(db, exchange_ids), viewer, locale
    )

    places_query = db.query(Place).filter(Place.status == "published")
    if location_id is not None:
        places_query = places_query.filter(Place.location_id == location_id)
    places = [
        PlaceResponse.from_model(p, locale)
        for p in places_query.order_by(Place.created_at.desc()).limit(limit).all()
    ]

    hospitals_query = db.query(Hospital)  # no status column (Section 17 Phase 1) - always public
    if location_id is not None:
        hospitals_query = hospitals_query.filter(Hospital.location_id == location_id)
    hospitals = [
        HospitalResponse.from_model(h, locale)
        for h in hospitals_query.order_by(Hospital.created_at.desc()).limit(limit).all()
    ]

    markets_query = db.query(Market)
    if location_id is not None:
        markets_query = markets_query.filter(Market.location_id == location_id)
    markets = [
        MarketResponse.from_model(m, locale)
        for m in markets_query.order_by(Market.created_at.desc()).limit(limit).all()
    ]

    services_query = db.query(Service).filter(Service.status == "published")
    if location_id is not None:
        services_query = services_query.filter(Service.location_id == location_id)
    services = [
        ServiceResponse.from_model(s, locale)
        for s in services_query.order_by(Service.created_at.desc()).limit(limit).all()
    ]

    news_query = db.query(NewsArticle).filter(NewsArticle.status == "published")
    if location_id is not None:
        news_query = news_query.filter(NewsArticle.location_id == location_id)
    news = [
        NewsArticleResponse.model_validate(n)
        for n in news_query.order_by(NewsArticle.published_at.desc()).limit(limit).all()
    ]

    total = len(products) + len(exchange_listings) + len(places) + len(hospitals) + len(markets) + len(services) + len(
        news
    )
    return total, (products, exchange_listings, places, hospitals, markets, services, news)


def get_recommendations(
    db: Session, viewer: CurrentUser | None, locale: str, location_id: uuid.UUID | None
) -> RecommendationsResponse:
    total, bundle = _fetch_bundle(db, viewer, locale, location_id, PER_SECTION_LIMIT)
    widened = False
    if location_id is not None and total < MIN_ITEMS_BEFORE_WIDENING:
        total, bundle = _fetch_bundle(db, viewer, locale, None, PER_SECTION_LIMIT)
        widened = True

    products, exchange_listings, places, hospitals, markets, services, news = bundle
    return RecommendationsResponse(
        location_id=location_id,
        widened_to_upazila=widened,
        trending_products=products,
        trending_exchange=exchange_listings,
        places=places,
        hospitals=hospitals,
        markets=markets,
        services=services,
        news=news,
    )
