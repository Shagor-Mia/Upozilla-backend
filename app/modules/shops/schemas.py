import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.i18n import localized_value
from app.db.models.shop import Shop, ShopCategory, ShopStatus
from app.modules.exchange.schemas import validate_images
from app.modules.sellers.schemas import SellerSummary


class ShopCategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    icon: str | None
    sort_order: int

    @classmethod
    def from_model(cls, category: ShopCategory, locale: str) -> "ShopCategoryResponse":
        return cls(
            id=category.id,
            name=localized_value(category.name_bn, category.name_en, category.name_ar, locale),
            slug=category.slug,
            icon=category.icon,
            sort_order=category.sort_order,
        )


class ShopCreate(BaseModel):
    market_id: uuid.UUID
    category_id: uuid.UUID
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    contact_phone: str | None = Field(default=None, max_length=20)
    images: list[str] = []

    @field_validator("images")
    @classmethod
    def check_images(cls, v: list[str]) -> list[str]:
        return validate_images(v)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class ShopUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    contact_phone: str | None = Field(default=None, max_length=20)
    images: list[str] | None = None
    status: ShopStatus | None = None
    # Admin/moderator only - app/modules/shops/service.py:update rejects this
    # from a plain owner.
    is_featured: bool | None = None

    @field_validator("images")
    @classmethod
    def check_images(cls, v: list[str] | None) -> list[str] | None:
        return validate_images(v) if v is not None else None


class ShopAdminResponse(BaseModel):
    """Raw fields for the admin edit form to pre-fill (Section 22.2 pattern) -
    `name`/`description` here are the bn-only stored values, not locale-resolved."""

    id: uuid.UUID
    market_id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: str | None
    contact_phone: str | None
    images: list[str]
    is_featured: bool
    status: str
    moderation_status: str

    @classmethod
    def from_model(cls, shop: Shop) -> "ShopAdminResponse":
        return cls(
            id=shop.id,
            market_id=shop.market_id,
            category_id=shop.category_id,
            name=shop.name_bn,
            description=shop.description_bn,
            contact_phone=shop.contact_phone,
            images=shop.images or [],
            is_featured=shop.is_featured,
            status=shop.status,
            moderation_status=shop.moderation_status,
        )


class ShopResponse(BaseModel):
    id: uuid.UUID
    market_id: uuid.UUID
    market_name: str
    category_id: uuid.UUID
    category_name: str
    name: str
    description: str | None
    contact_phone: str | None
    images: list[str]
    is_featured: bool
    status: str
    moderation_status: str
    created_at: datetime
    updated_at: datetime
    seller: SellerSummary


def to_response(
    shop: Shop, *, market_name: str, category_name: str, locale: str, seller: SellerSummary
) -> ShopResponse:
    return ShopResponse(
        id=shop.id,
        market_id=shop.market_id,
        market_name=market_name,
        category_id=shop.category_id,
        category_name=category_name,
        name=localized_value(shop.name_bn, shop.name_en, shop.name_ar, locale),
        description=localized_value(shop.description_bn, shop.description_en, shop.description_ar, locale)
        if shop.description_bn
        else None,
        contact_phone=shop.contact_phone,
        images=shop.images or [],
        is_featured=shop.is_featured,
        status=shop.status,
        moderation_status=shop.moderation_status,
        created_at=shop.created_at,
        updated_at=shop.updated_at,
        seller=seller,
    )
