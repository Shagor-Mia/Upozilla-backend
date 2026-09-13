import uuid
from datetime import datetime

from pydantic import BaseModel

from app.core.i18n import localized_value
from app.db.models.service import Service, ServiceCategory


class ServiceCategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None

    @classmethod
    def from_model(cls, category: ServiceCategory, locale: str) -> "ServiceCategoryResponse":
        return cls(
            id=category.id,
            name=localized_value(category.name_bn, category.name_en, category.name_ar, locale),
            parent_id=category.parent_id,
        )


class ServiceCreate(BaseModel):
    location_id: uuid.UUID
    category_id: uuid.UUID
    name_bn: str
    name_en: str | None = None
    name_ar: str | None = None
    description_bn: str | None = None
    description_en: str | None = None
    description_ar: str | None = None
    eligibility: str | None = None
    required_documents: list[str] | None = None
    fee: float | None = None
    official_link: str | None = None
    office_name_bn: str | None = None
    office_name_en: str | None = None
    office_name_ar: str | None = None
    office_contact: str | None = None


class ServiceResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: str | None
    eligibility: str | None
    required_documents: list[str] | None
    fee: float | None
    official_link: str | None
    office_name: str | None
    office_contact: str | None
    status: str

    @classmethod
    def from_model(cls, svc: Service, locale: str) -> "ServiceResponse":
        return cls(
            id=svc.id,
            location_id=svc.location_id,
            category_id=svc.category_id,
            name=localized_value(svc.name_bn, svc.name_en, svc.name_ar, locale),
            description=localized_value(svc.description_bn, svc.description_en, svc.description_ar, locale)
            if svc.description_bn
            else None,
            eligibility=svc.eligibility,
            required_documents=svc.required_documents,
            fee=svc.fee,
            official_link=svc.official_link,
            office_name=localized_value(svc.office_name_bn, svc.office_name_en, svc.office_name_ar, locale)
            if svc.office_name_bn
            else None,
            office_contact=svc.office_contact,
            status=svc.status,
        )


class ServiceUpdate(BaseModel):
    location_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    name_bn: str | None = None
    name_en: str | None = None
    name_ar: str | None = None
    description_bn: str | None = None
    description_en: str | None = None
    description_ar: str | None = None
    eligibility: str | None = None
    required_documents: list[str] | None = None
    fee: float | None = None
    official_link: str | None = None
    office_name_bn: str | None = None
    office_name_en: str | None = None
    office_name_ar: str | None = None
    office_contact: str | None = None
    status: str | None = None


class ServiceAdminResponse(BaseModel):
    id: uuid.UUID
    location_id: uuid.UUID
    category_id: uuid.UUID
    name_bn: str
    name_en: str | None
    name_ar: str | None
    description_bn: str | None
    description_en: str | None
    description_ar: str | None
    eligibility: str | None
    required_documents: list[str] | None
    fee: float | None
    official_link: str | None
    office_name_bn: str | None
    office_name_en: str | None
    office_name_ar: str | None
    office_contact: str | None
    status: str

    model_config = {"from_attributes": True}


class LicenseApplicationCreate(BaseModel):
    service_id: uuid.UUID
    application_ref_no: str | None = None
    notes: str | None = None


class LicenseApplicationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    service_id: uuid.UUID
    application_ref_no: str | None
    status: str
    submitted_at: datetime | None
    updated_at: datetime | None
    notes: str | None

    model_config = {"from_attributes": True}
