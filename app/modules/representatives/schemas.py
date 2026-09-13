import uuid

from pydantic import BaseModel, Field

from app.core.i18n import localized_value
from app.db.models.representative import Representative, RepresentativePosition, RepresentativeStatus


class RepresentativeCreate(BaseModel):
    user_id: uuid.UUID
    location_id: uuid.UUID
    position: RepresentativePosition
    bio: str | None = Field(default=None, max_length=2000)
    photo_url: str | None = Field(default=None, max_length=500)


class RepresentativeUpdate(BaseModel):
    """Self-service fields only - `location_id`/`position`/`status` need
    CONTENT_MANAGE (app/modules/representatives/service.py:update)."""

    bio: str | None = Field(default=None, max_length=2000)
    photo_url: str | None = Field(default=None, max_length=500)


class RepresentativeAdminUpdate(RepresentativeUpdate):
    location_id: uuid.UUID | None = None
    position: RepresentativePosition | None = None
    status: RepresentativeStatus | None = None


class RepresentativeAdminResponse(BaseModel):
    """Raw fields for the admin edit form to pre-fill (Section 22.2 pattern) -
    `bio` here is the bn-only stored value, not locale-resolved."""

    id: uuid.UUID
    user_id: uuid.UUID | None
    location_id: uuid.UUID
    position: RepresentativePosition
    bio: str | None
    photo_url: str | None
    status: RepresentativeStatus

    @classmethod
    def from_model(cls, rep: Representative) -> "RepresentativeAdminResponse":
        return cls(
            id=rep.id,
            user_id=rep.user_id,
            location_id=rep.location_id,
            position=RepresentativePosition(rep.position),
            bio=rep.bio_bn,
            photo_url=rep.photo_url,
            status=RepresentativeStatus(rep.status),
        )


class RepresentativeResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    full_name: str
    # Deliberately unmasked, unlike SellerSummary.phone_masked - this is a public
    # citizen-contact directory for elected officials, not a marketplace privacy context.
    phone: str | None
    location_id: uuid.UUID
    location_name: str
    position: RepresentativePosition
    bio: str | None
    photo_url: str | None
    status: RepresentativeStatus


def to_response(
    rep: Representative, *, full_name: str, phone: str | None, location_name: str, locale: str
) -> RepresentativeResponse:
    return RepresentativeResponse(
        id=rep.id,
        user_id=rep.user_id,
        full_name=full_name,
        phone=phone,
        location_id=rep.location_id,
        location_name=location_name,
        position=RepresentativePosition(rep.position),
        bio=localized_value(rep.bio_bn, rep.bio_en, rep.bio_ar, locale) if rep.bio_bn else None,
        photo_url=rep.photo_url,
        status=RepresentativeStatus(rep.status),
    )
