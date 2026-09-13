import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.core.i18n import localized_value
from app.db.models.contract import (
    ContractPaymentMethod,
    ContractPaymentType,
    ContractProblemCategory,
    WorkContract,
)

MAX_REFERENCE_IMAGES = 5
MAX_PROGRESS_IMAGES = 6
MAX_PROOF_IMAGES = 4
MAX_PROBLEM_IMAGES = 6


def _validate_images(images: list[str], cap: int) -> list[str]:
    """Same pasted-URL validator pattern as `exchange/schemas.py::validate_images`,
    parametrised by cap since each image list here has its own limit (Section 1)."""
    if len(images) > cap:
        raise ValueError(f"at most {cap} images")
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


# --- contract -----------------------------------------------------------------------


class ContractCreate(BaseModel):
    worker_user_id: uuid.UUID
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3, max_length=5000)
    payment_amount: float = Field(gt=0, le=1_000_000_000)
    payment_type: ContractPaymentType
    currency: str = Field(default="BDT", min_length=3, max_length=3)
    start_date: date | None = None
    end_date: date | None = None
    reference_images: list[str] = []

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return v.strip()

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: str) -> str:
        return v.strip()

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str) -> str:
        return v.upper()

    @field_validator("reference_images")
    @classmethod
    def check_reference_images(cls, v: list[str]) -> list[str]:
        return _validate_images(v, MAX_REFERENCE_IMAGES)


class ContractRejectBody(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class ContractCancelBody(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class ContractResponse(BaseModel):
    id: uuid.UUID
    employer_user_id: uuid.UUID | None
    employer_name: str | None
    worker_user_id: uuid.UUID | None
    worker_name: str | None
    title: str
    description: str
    payment_amount: float
    payment_type: str
    currency: str
    start_date: date | None
    end_date: date | None
    status: str
    employer_accepted_at: datetime
    worker_accepted_at: datetime | None
    employer_completion_confirmed_at: datetime | None
    worker_completion_confirmed_at: datetime | None
    cancelled_by_user_id: uuid.UUID | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    reference_images: list[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(
        cls,
        contract: WorkContract,
        locale: str,
        employer_name: str | None,
        worker_name: str | None,
    ) -> "ContractResponse":
        return cls(
            id=contract.id,
            employer_user_id=contract.employer_user_id,
            employer_name=employer_name,
            worker_user_id=contract.worker_user_id,
            worker_name=worker_name,
            title=localized_value(contract.title_bn, contract.title_en, contract.title_ar, locale),
            description=localized_value(
                contract.description_bn, contract.description_en, contract.description_ar, locale
            ),
            payment_amount=float(contract.payment_amount),
            payment_type=contract.payment_type,
            currency=contract.currency,
            start_date=contract.start_date,
            end_date=contract.end_date,
            status=contract.status,
            employer_accepted_at=contract.employer_accepted_at,
            worker_accepted_at=contract.worker_accepted_at,
            employer_completion_confirmed_at=contract.employer_completion_confirmed_at,
            worker_completion_confirmed_at=contract.worker_completion_confirmed_at,
            cancelled_by_user_id=contract.cancelled_by_user_id,
            cancelled_at=contract.cancelled_at,
            cancellation_reason=contract.cancellation_reason,
            reference_images=contract.reference_images or [],
            created_at=contract.created_at,
            updated_at=contract.updated_at,
        )


# --- progress -------------------------------------------------------------------------


class ContractProgressCreate(BaseModel):
    note: str = Field(min_length=1, max_length=2000)
    percent_complete: int | None = Field(default=None, ge=0, le=100)
    images: list[str] = []

    @field_validator("note")
    @classmethod
    def strip_note(cls, v: str) -> str:
        return v.strip()

    @field_validator("images")
    @classmethod
    def check_images(cls, v: list[str]) -> list[str]:
        return _validate_images(v, MAX_PROGRESS_IMAGES)


class ContractProgressResponse(BaseModel):
    id: uuid.UUID
    contract_id: uuid.UUID
    created_by_user_id: uuid.UUID | None
    created_by_name: str | None
    note: str
    percent_complete: int | None
    images: list[str]
    created_at: datetime


# --- payments ---------------------------------------------------------------------------


class ContractPaymentCreate(BaseModel):
    amount: float = Field(gt=0, le=1_000_000_000)
    method: ContractPaymentMethod
    note: str | None = Field(default=None, max_length=2000)
    proof_images: list[str] = []
    paid_at: datetime | None = None

    @field_validator("proof_images")
    @classmethod
    def check_images(cls, v: list[str]) -> list[str]:
        return _validate_images(v, MAX_PROOF_IMAGES)


class ContractPaymentResponse(BaseModel):
    id: uuid.UUID
    contract_id: uuid.UUID
    logged_by_user_id: uuid.UUID | None
    logged_by_name: str | None
    amount: float
    method: str
    note: str | None
    proof_images: list[str]
    paid_at: datetime
    status: str
    confirmed_by_user_id: uuid.UUID | None
    confirmed_by_name: str | None
    confirmed_at: datetime | None
    created_at: datetime


# --- problems / disputes -----------------------------------------------------------------


class ContractProblemCreate(BaseModel):
    category: ContractProblemCategory
    description: str = Field(min_length=3, max_length=2000)
    images: list[str] = []

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: str) -> str:
        return v.strip()

    @field_validator("images")
    @classmethod
    def check_images(cls, v: list[str]) -> list[str]:
        return _validate_images(v, MAX_PROBLEM_IMAGES)


class ContractProblemResponse(BaseModel):
    id: uuid.UUID
    contract_id: uuid.UUID
    raised_by_user_id: uuid.UUID | None
    raised_by_name: str | None
    category: str
    description: str
    images: list[str]
    status: str
    escalated_at: datetime | None
    resolution: str | None
    resolution_note: str | None
    resolved_by_user_id: uuid.UUID | None
    resolved_by_name: str | None
    resolved_at: datetime | None
    created_at: datetime
