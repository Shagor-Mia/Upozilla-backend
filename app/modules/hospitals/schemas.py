import uuid

from pydantic import BaseModel

from app.core.i18n import localized_value
from app.db.models.hospital import Hospital, HospitalType


class HospitalCreate(BaseModel):
    location_id: uuid.UUID
    name_bn: str
    name_en: str | None = None
    name_ar: str | None = None
    type: HospitalType
    address: str | None = None
    contact: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    images: list[str] | None = None
    services: list[str] | None = None
    ambulance_contact: str | None = None


class HospitalResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    name: str
    type: HospitalType
    address: str | None
    contact: str | None
    latitude: float | None
    longitude: float | None
    images: list[str] | None
    services: list[str] | None
    ambulance_contact: str | None
    # Section 17 Phase 3: only set when the list was queried with ?lat=&lng=
    distance_km: float | None = None

    @classmethod
    def from_model(cls, hospital: Hospital, locale: str, distance_km: float | None = None) -> "HospitalResponse":
        return cls(
            id=hospital.id,
            location_id=hospital.location_id,
            name=localized_value(hospital.name_bn, hospital.name_en, hospital.name_ar, locale),
            type=hospital.type,
            address=hospital.address,
            contact=hospital.contact,
            latitude=hospital.latitude,
            longitude=hospital.longitude,
            images=hospital.images,
            services=hospital.services,
            ambulance_contact=hospital.ambulance_contact,
            distance_km=distance_km,
        )


class HospitalUpdate(BaseModel):
    location_id: uuid.UUID | None = None
    name_bn: str | None = None
    name_en: str | None = None
    name_ar: str | None = None
    type: HospitalType | None = None
    address: str | None = None
    contact: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    images: list[str] | None = None
    services: list[str] | None = None
    ambulance_contact: str | None = None


class HospitalAdminResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    name_bn: str
    name_en: str | None
    name_ar: str | None
    type: HospitalType
    address: str | None
    contact: str | None
    latitude: float | None
    longitude: float | None
    images: list[str] | None
    services: list[str] | None
    ambulance_contact: str | None
    owner_user_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class AmbulanceHospitalResponse(BaseModel):
    id: uuid.UUID
    name: str
    ambulance_contact: str
    address: str | None

    @classmethod
    def from_model(cls, hospital: Hospital, locale: str) -> "AmbulanceHospitalResponse":
        return cls(
            id=hospital.id,
            name=localized_value(hospital.name_bn, hospital.name_en, hospital.name_ar, locale),
            ambulance_contact=hospital.ambulance_contact,
            address=hospital.address,
        )


class DoctorCreate(BaseModel):
    hospital_id: uuid.UUID
    name: str
    specialty: str | None = None
    chamber_days: list[str] | None = None
    chamber_hours: str | None = None
    contact: str | None = None


class DoctorResponse(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    name: str
    specialty: str | None
    chamber_days: list[str] | None
    chamber_hours: str | None
    contact: str | None

    model_config = {"from_attributes": True}
