import uuid
from datetime import time

from pydantic import BaseModel

from app.core.i18n import localized_value
from app.db.models.market import Market, MarketType


class MarketCreate(BaseModel):
    location_id: uuid.UUID
    name_bn: str
    name_en: str | None = None
    name_ar: str | None = None
    description_bn: str | None = None
    description_en: str | None = None
    description_ar: str | None = None
    market_day: list[str] | None = None
    start_time: time | None = None
    end_time: time | None = None
    type: MarketType
    latitude: float | None = None
    longitude: float | None = None


class MarketUpdate(BaseModel):
    location_id: uuid.UUID | None = None
    name_bn: str | None = None
    name_en: str | None = None
    name_ar: str | None = None
    description_bn: str | None = None
    description_en: str | None = None
    description_ar: str | None = None
    market_day: list[str] | None = None
    start_time: time | None = None
    end_time: time | None = None
    type: MarketType | None = None
    latitude: float | None = None
    longitude: float | None = None


class MarketAdminResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    name_bn: str
    name_en: str | None
    name_ar: str | None
    description_bn: str | None
    description_en: str | None
    description_ar: str | None
    market_day: list[str] | None
    start_time: time | None
    end_time: time | None
    type: MarketType
    latitude: float | None
    longitude: float | None

    model_config = {"from_attributes": True}


class MarketResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    name: str
    description: str | None
    market_day: list[str] | None
    start_time: time | None
    end_time: time | None
    type: MarketType
    latitude: float | None
    longitude: float | None
    # Section 17 Phase 3: only set when the list was queried with ?lat=&lng=
    distance_km: float | None = None

    @classmethod
    def from_model(cls, market: Market, locale: str, distance_km: float | None = None) -> "MarketResponse":
        return cls(
            id=market.id,
            location_id=market.location_id,
            name=localized_value(market.name_bn, market.name_en, market.name_ar, locale),
            description=localized_value(market.description_bn, market.description_en, market.description_ar, locale)
            if market.description_bn
            else None,
            market_day=market.market_day,
            start_time=market.start_time,
            end_time=market.end_time,
            type=market.type,
            latitude=market.latitude,
            longitude=market.longitude,
            distance_km=distance_km,
        )
