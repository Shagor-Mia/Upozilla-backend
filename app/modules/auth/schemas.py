import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.db.models.otp import OtpPurpose
from app.modules.auth.phone import normalize_bd_phone


def _validate_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("password must be at least 8 characters")
    return value


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr | None = None
    phone: str | None = None
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: str | None) -> str | None:
        return normalize_bd_phone(v) if v else None

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: EmailStr | None) -> EmailStr | None:
        return v.lower() if v else v


class LoginRequest(BaseModel):
    identifier: str  # email or phone
    password: str

    @field_validator("identifier")
    @classmethod
    def normalize_identifier(cls, v: str) -> str:
        """Accepts whatever a user actually types: an email in any case, or a
        BD mobile number in any of the formats registration/OTP already
        normalize (local `01...`, `880...`, `+880...`). Anything that isn't a
        valid phone shape is left as-is rather than raising here - `identifier`
        also legitimately fails to match anything for a wrong login, and this
        validator must never turn a bad-password case into a 422."""
        v = v.strip()
        if "@" in v:
            return v.lower()
        try:
            return normalize_bd_phone(v)
        except ValueError:
            return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    role: str
    roles: list[str] = []
    status: str
    phone_verified: bool
    oauth_provider: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OtpRequestBody(BaseModel):
    phone: str
    purpose: OtpPurpose
    turnstile_token: str | None = None

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: str) -> str:
        return normalize_bd_phone(v)


class OtpRequestResponse(BaseModel):
    sent: bool
    expires_in_seconds: int
    # Populated only by the console SMS gateway (local dev) - never in production.
    dev_code: str | None = None


class OtpVerifyBody(BaseModel):
    phone: str
    code: str
    purpose: OtpPurpose
    full_name: str | None = None  # required for purpose=register

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: str) -> str:
        return normalize_bd_phone(v)

    @field_validator("code")
    @classmethod
    def code_shape(cls, v: str) -> str:
        v = v.strip()
        if not (v.isdigit() and len(v) == 6):
            raise ValueError("code must be 6 digits")
        return v


class FacebookLoginRequest(BaseModel):
    access_token: str


class GoogleLoginRequest(BaseModel):
    id_token: str


class WsTicketResponse(BaseModel):
    ticket: str
    expires_in_seconds: int
