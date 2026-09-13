import uuid

from pydantic import BaseModel

from app.modules.exchange.schemas import ExchangeListingResponse
from app.modules.government_services.schemas import ServiceResponse
from app.modules.hospitals.schemas import HospitalResponse
from app.modules.marketplace.schemas import ProductResponse
from app.modules.markets.schemas import MarketResponse
from app.modules.news.schemas import NewsArticleResponse
from app.modules.places.schemas import PlaceResponse


class RecommendationsResponse(BaseModel):
    """Section 17 Phase 4 "personalized recommendations": content scoped to
    the requested location (falls back to upazila-wide - Section 19.6 - when
    that's too sparse) plus platform-wide trending marketplace/exchange
    listings. No LLM/embedding involved."""

    location_id: uuid.UUID | None
    widened_to_upazila: bool
    trending_products: list[ProductResponse]
    trending_exchange: list[ExchangeListingResponse]
    places: list[PlaceResponse]
    hospitals: list[HospitalResponse]
    markets: list[MarketResponse]
    services: list[ServiceResponse]
    news: list[NewsArticleResponse]
