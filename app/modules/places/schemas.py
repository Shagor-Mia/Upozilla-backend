import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.core.i18n import localized_value
from app.db.models.place import Place, PlaceCategory

MAX_SUBMIT_IMAGES = 3


def validate_gallery(images: list[str]) -> list[str]:
    if len(images) > MAX_SUBMIT_IMAGES:
        raise ValueError(f"at most {MAX_SUBMIT_IMAGES} images")
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

# `places.status` has no DB CheckConstraint (unlike faqs/news), so an
# unvalidated string here doesn't 500 - it silently persists garbage and the
# place vanishes from every public listing (which only shows "published")
# with no way back except guessing the right string again. Validate at the
# same draft/published convention the rest of the codebase uses.
PlaceStatus = Literal["draft", "published"]


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


class PlaceSubmit(BaseModel):
    """Public submission (POST /places/submit) - a regular logged-in user, not
    an admin, so no `slug` (server-generated), `is_featured`, or `status`, and
    `name`/`description` are a single field in the submitter's own language
    rather than the admin form's separate bn/en/ar columns (same convention
    as ProductCreate.title -> title_bn in marketplace)."""

    location_id: uuid.UUID
    name: str = Field(min_length=2, max_length=255)
    category: PlaceCategory
    description: str | None = Field(default=None, max_length=5000)
    gallery: list[str] = []
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("gallery")
    @classmethod
    def check_gallery(cls, v: list[str]) -> list[str]:
        return validate_gallery(v)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


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
    status: PlaceStatus | None = None


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
    moderation_status: str
    seller_user_id: uuid.UUID | None

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
    moderation_status: str
    seller_user_id: uuid.UUID | None
    created_at: datetime
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
            moderation_status=place.moderation_status,
            seller_user_id=place.seller_user_id,
            created_at=place.created_at,
            distance_km=distance_km,
        )
