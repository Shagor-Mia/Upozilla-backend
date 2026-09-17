import uuid

from pydantic import BaseModel

from app.core.i18n import localized_value
from app.db.models.school import School, SchoolType


class SchoolCreate(BaseModel):
    location_id: uuid.UUID
    name_bn: str
    name_en: str | None = None
    name_ar: str | None = None
    type: SchoolType
    address: str | None = None
    contact: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class SchoolResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    name: str
    type: SchoolType
    address: str | None
    contact: str | None
    latitude: float | None
    longitude: float | None
    distance_km: float | None = None

    @classmethod
    def from_model(cls, school: School, locale: str, distance_km: float | None = None) -> "SchoolResponse":
        return cls(
            id=school.id,
            location_id=school.location_id,
            name=localized_value(school.name_bn, school.name_en, school.name_ar, locale),
            type=school.type,
            address=school.address,
            contact=school.contact,
            latitude=school.latitude,
            longitude=school.longitude,
            distance_km=distance_km,
        )


class SchoolUpdate(BaseModel):
    location_id: uuid.UUID | None = None
    name_bn: str | None = None
    name_en: str | None = None
    name_ar: str | None = None
    type: SchoolType | None = None
    address: str | None = None
    contact: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class SchoolAdminResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    name_bn: str
    name_en: str | None
    name_ar: str | None
    type: SchoolType
    address: str | None
    contact: str | None
    latitude: float | None
    longitude: float | None
    owner_user_id: uuid.UUID | None

    model_config = {"from_attributes": True}
