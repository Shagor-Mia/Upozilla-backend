import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.i18n import localized_value
from app.db.models.exchange import ListingType
from app.db.models.marketplace import ItemCondition, MarketplaceCategory, ProductStatus
from app.modules.exchange.schemas import ExchangeListingResponse, validate_images
from app.modules.sellers.schemas import SellerSummary


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    parent_id: uuid.UUID | None
    icon: str | None
    sort_order: int

    @classmethod
    def from_model(cls, category: MarketplaceCategory, locale: str) -> "CategoryResponse":
        return cls(
            id=category.id,
            name=localized_value(category.name_bn, category.name_en, category.name_ar, locale),
            slug=category.slug,
            parent_id=category.parent_id,
            icon=category.icon,
            sort_order=category.sort_order,
        )


class ProductCreate(BaseModel):
    category_id: uuid.UUID
    business_id: uuid.UUID | None = None
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    price: float = Field(ge=0, le=1_000_000_000)
    currency: str = Field(default="BDT", min_length=3, max_length=3)
    condition: ItemCondition = ItemCondition.NEW
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

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()


class ProductUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    business_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    price: float | None = Field(default=None, ge=0, le=1_000_000_000)
    condition: ItemCondition | None = None
    images: list[str] | None = None
    location_id: uuid.UUID | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    status: ProductStatus | None = None

    @field_validator("images")
    @classmethod
    def check_images(cls, v: list[str] | None) -> list[str] | None:
        return validate_images(v) if v is not None else None


class ProductResponse(BaseModel):
    id: uuid.UUID
    listing_type: ListingType = ListingType.MARKETPLACE
    business_id: uuid.UUID | None
    business_name: str | None
    business_slug: str | None
    seller_user_id: uuid.UUID | None
    category_id: uuid.UUID
    category_name: str
    title: str
    description: str | None
    price: float
    currency: str
    condition: str
    images: list[str]
    location_id: uuid.UUID
    location_name: str
    latitude: float | None
    longitude: float | None
    status: str
    moderation_status: str
    created_at: datetime
    updated_at: datetime
    seller: SellerSummary
    is_favorited: bool = False
    favorites_count: int = 0


class FavoritesResponse(BaseModel):
    """A user's saved listings across both kinds (Section 10: favorites)."""

    exchange: list[ExchangeListingResponse]
    marketplace: list[ProductResponse]
