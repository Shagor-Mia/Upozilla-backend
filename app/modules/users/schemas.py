import uuid

from pydantic import BaseModel, EmailStr, field_validator

from app.modules.auth.phone import normalize_bd_phone


class UserProfileUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: str | None) -> str | None:
        return normalize_bd_phone(v) if v else None


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    role: str
    status: str
    phone_verified: bool

    model_config = {"from_attributes": True}


class UserLookupResponse(BaseModel):
    id: uuid.UUID
    full_name: str
