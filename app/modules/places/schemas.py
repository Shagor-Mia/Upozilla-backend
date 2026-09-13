import uuid

from pydantic import BaseModel

from app.core.i18n import localized_value
from app.db.models.place import Place, PlaceCategory


class PlaceCreate(BaseModel):
    location_id: uuid.UUID
    name_bn: str
    name_en: str | None = None
    name_ar: str | None = None
    slug: str
    category: PlaceCategory
    description_bn: str | None = None
    description_en: str | None = None
    description_ar: str | None = None
    cover_image: str | None = None
    gallery: list[str] | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_featured: bool = False


class PlaceUpdate(BaseModel):
    location_id: uuid.UUID | None = None
    name_bn: str | None = None
    name_en: str | None = None
    name_ar: str | None = None
    slug: str | None = None
    category: PlaceCategory | None = None
    description_bn: str | None = None
    description_en: str | None = None
    description_ar: str | None = None
    cover_image: str | None = None
    gallery: list[str] | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_featured: bool | None = None
    status: str | None = None


class PlaceAdminResponse(BaseModel):
    """Raw per-language fields, for the admin edit form to pre-fill (Section 22.2)."""

    id: uuid.UUID
    location_id: uuid.UUID
    name_bn: str
    name_en: str | None
    name_ar: str | None
    slug: str
    category: PlaceCategory
    description_bn: str | None
    description_en: str | None
    description_ar: str | None
    cover_image: str | None
    gallery: list[str] | None
    latitude: float | None
    longitude: float | None
    is_featured: bool
    status: str

    model_config = {"from_attributes": True}


class PlaceResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    name: str
    slug: str
    category: PlaceCategory
    description: str | None
    cover_image: str | None
    gallery: list[str] | None
    latitude: float | None
    longitude: float | None
    is_featured: bool
    status: str
    # Section 17 Phase 3: only set when the list was queried with ?lat=&lng=
    distance_km: float | None = None

    @classmethod
    def from_model(cls, place: Place, locale: str, distance_km: float | None = None) -> "PlaceResponse":
        return cls(
            id=place.id,
            location_id=place.location_id,
            name=localized_value(place.name_bn, place.name_en, place.name_ar, locale),
            slug=place.slug,
            category=place.category,
            description=localized_value(place.description_bn, place.description_en, place.description_ar, locale)
            if place.description_bn
            else None,
            cover_image=place.cover_image,
            gallery=place.gallery,
            latitude=place.latitude,
            longitude=place.longitude,
            is_featured=place.is_featured,
            status=place.status,
            distance_km=distance_km,
        )
