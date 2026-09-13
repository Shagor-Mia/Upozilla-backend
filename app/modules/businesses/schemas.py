import uuid

from pydantic import BaseModel

from app.core.i18n import localized_value
from app.db.models.business import Business


class BusinessCreate(BaseModel):
    location_id: uuid.UUID
    name_bn: str
    name_en: str | None = None
    name_ar: str | None = None
    slug: str
    category: str
    description_bn: str | None = None
    description_en: str | None = None
    description_ar: str | None = None
    logo: str | None = None
    cover_image: str | None = None
    phone: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class BusinessUpdate(BaseModel):
    location_id: uuid.UUID | None = None
    name_bn: str | None = None
    name_en: str | None = None
    name_ar: str | None = None
    slug: str | None = None
    category: str | None = None
    description_bn: str | None = None
    description_en: str | None = None
    description_ar: str | None = None
    logo: str | None = None
    cover_image: str | None = None
    phone: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    status: str | None = None


class BusinessAdminResponse(BaseModel):
    """Raw per-language fields, for the admin edit form to pre-fill (Section 22.2)."""

    id: uuid.UUID
    location_id: uuid.UUID
    owner_user_id: uuid.UUID | None
    name_bn: str
    name_en: str | None
    name_ar: str | None
    slug: str
    category: str
    description_bn: str | None
    description_en: str | None
    description_ar: str | None
    logo: str | None
    cover_image: str | None
    phone: str | None
    address: str | None
    latitude: float | None
    longitude: float | None
    is_verified: bool
    status: str

    model_config = {"from_attributes": True}


class BusinessResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    owner_user_id: uuid.UUID | None
    name: str
    slug: str
    category: str
    description: str | None
    logo: str | None
    cover_image: str | None
    phone: str | None
    address: str | None
    latitude: float | None
    longitude: float | None
    is_verified: bool
    status: str
    # Section 17 Phase 3: only set when the list was queried with ?lat=&lng=
    distance_km: float | None = None

    @classmethod
    def from_model(cls, business: Business, locale: str, distance_km: float | None = None) -> "BusinessResponse":
        return cls(
            id=business.id,
            location_id=business.location_id,
            owner_user_id=business.owner_user_id,
            name=localized_value(business.name_bn, business.name_en, business.name_ar, locale),
            slug=business.slug,
            category=business.category,
            description=localized_value(
                business.description_bn, business.description_en, business.description_ar, locale
            )
            if business.description_bn
            else None,
            logo=business.logo,
            cover_image=business.cover_image,
            phone=business.phone,
            address=business.address,
            latitude=business.latitude,
            longitude=business.longitude,
            is_verified=business.is_verified,
            status=business.status,
            distance_km=distance_km,
        )
