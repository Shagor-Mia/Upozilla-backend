import uuid

from pydantic import BaseModel

from app.core.i18n import localized_value
from app.db.models.govt_office import GovtOffice, GovtOfficeCategory


class GovtOfficeCreate(BaseModel):
    location_id: uuid.UUID
    category: GovtOfficeCategory
    name_bn: str
    name_en: str | None = None
    name_ar: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    sort_order: int = 0


class GovtOfficeUpdate(BaseModel):
    location_id: uuid.UUID | None = None
    category: GovtOfficeCategory | None = None
    name_bn: str | None = None
    name_en: str | None = None
    name_ar: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    sort_order: int | None = None


class GovtOfficeAdminResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    category: GovtOfficeCategory
    name_bn: str
    name_en: str | None
    name_ar: str | None
    address: str | None
    phone: str | None
    email: str | None
    latitude: float | None
    longitude: float | None
    sort_order: int

    model_config = {"from_attributes": True}


class GovtOfficeResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    category: GovtOfficeCategory
    name: str
    address: str | None
    phone: str | None
    email: str | None
    latitude: float | None
    longitude: float | None

    @classmethod
    def from_model(cls, office: GovtOffice, locale: str) -> "GovtOfficeResponse":
        return cls(
            id=office.id,
            location_id=office.location_id,
            category=office.category,
            name=localized_value(office.name_bn, office.name_en, office.name_ar, locale),
            address=office.address,
            phone=office.phone,
            email=office.email,
            latitude=office.latitude,
            longitude=office.longitude,
        )
