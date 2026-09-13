import enum
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.db.models.exchange import ListingStatus, ListingType
from app.db.models.marketplace import ItemCondition
from app.modules.sellers.schemas import SellerSummary

MAX_IMAGES = 8


class ListingSort(str, enum.Enum):
    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"


def validate_images(images: list[str]) -> list[str]:
    if len(images) > MAX_IMAGES:
        raise ValueError(f"at most {MAX_IMAGES} images")
    cleaned = []
    for url in images:
        url = url.strip()
        if not url:
            continue
        HttpUrl(url)  # raises on a malformed URL
        if len(url) > 500:
            raise ValueError("image URL too long")
        cleaned.append(url)
    return cleaned


class ExchangeListingCreate(BaseModel):
    category_id: uuid.UUID
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    price: float = Field(ge=0, le=1_000_000_000)
    is_negotiable: bool = False
    condition: ItemCondition = ItemCondition.USED
    images: list[str] = []
    location_id: uuid.UUID
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("images")
    @classmethod
    def check_images(cls, v: list[str]) -> list[str]:
        return validate_images(v)

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return v.strip()


class ExchangeListingUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    price: float | None = Field(default=None, ge=0, le=1_000_000_000)
    is_negotiable: bool | None = None
    condition: ItemCondition | None = None
    images: list[str] | None = None
    location_id: uuid.UUID | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    status: ListingStatus | None = None

    @field_validator("images")
    @classmethod
    def check_images(cls, v: list[str] | None) -> list[str] | None:
        return validate_images(v) if v is not None else None


class ExchangeListingResponse(BaseModel):
    id: uuid.UUID
    listing_type: ListingType = ListingType.EXCHANGE
    seller_user_id: uuid.UUID | None
    category_id: uuid.UUID
    category_name: str
    title: str
    description: str | None
    price: float
    currency: str = "BDT"
    is_negotiable: bool
    condition: str
    images: list[str]
    location_id: uuid.UUID
    location_name: str
    latitude: float | None
    longitude: float | None
    status: str
    moderation_status: str
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    seller: SellerSummary
    is_favorited: bool = False
    favorites_count: int = 0


class ReportReason(str, enum.Enum):
    SPAM = "spam"
    SCAM = "scam"
    PROHIBITED_ITEM = "prohibited_item"
    WRONG_CATEGORY = "wrong_category"
    OFFENSIVE = "offensive"
    DUPLICATE = "duplicate"
    OTHER = "other"


class ListingReportCreate(BaseModel):
    reason: ReportReason
    details: str | None = Field(default=None, max_length=1000)


class ListingReportResponse(BaseModel):
    id: uuid.UUID
    listing_type: str
    listing_id: uuid.UUID
    reason: str
    status: str
    created_at: datetime


class FavoriteResponse(BaseModel):
    listing_type: ListingType
    listing_id: uuid.UUID
    is_favorited: bool
