import uuid

from pydantic import BaseModel

from app.core.i18n import localized_value
from app.db.models.location import Location, LocationType


class LocationResponse(BaseModel):
    id: uuid.UUID
    type: LocationType
    name: str
    parent_id: uuid.UUID | None

    @classmethod
    def from_model(cls, location: Location, locale: str) -> "LocationResponse":
        return cls(
            id=location.id,
            type=location.type,
            name=localized_value(location.name_bn, location.name_en, location.name_ar, locale),
            parent_id=location.parent_id,
        )
