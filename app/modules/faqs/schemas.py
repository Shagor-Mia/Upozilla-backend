import uuid
from typing import Literal

from pydantic import BaseModel

from app.core.i18n import localized_value
from app.db.models.faq import Faq

# Mirrors the DB CheckConstraint("status IN ('draft', 'published')") on
# faqs.status - validated here too so a bad value 422s instead of hitting
# that constraint as an unhandled IntegrityError.
FaqStatus = Literal["draft", "published"]


class FaqCreate(BaseModel):
    question_bn: str
    question_en: str | None = None
    question_ar: str | None = None
    answer_bn: str
    answer_en: str | None = None
    answer_ar: str | None = None
    status: FaqStatus = "published"


class FaqUpdate(BaseModel):
    question_bn: str | None = None
    question_en: str | None = None
    question_ar: str | None = None
    answer_bn: str | None = None
    answer_en: str | None = None
    answer_ar: str | None = None
    status: FaqStatus | None = None


class FaqAdminResponse(BaseModel):
    """Raw per-language fields, for the admin edit form to pre-fill (Section 22.2)."""

    id: uuid.UUID
    question_bn: str
    question_en: str | None
    question_ar: str | None
    answer_bn: str
    answer_en: str | None
    answer_ar: str | None
    status: str

    model_config = {"from_attributes": True}


class FaqResponse(BaseModel):
    id: uuid.UUID
    question: str
    answer: str
    status: str

    @classmethod
    def from_model(cls, faq: Faq, locale: str) -> "FaqResponse":
        return cls(
            id=faq.id,
            question=localized_value(faq.question_bn, faq.question_en, faq.question_ar, locale),
            answer=localized_value(faq.answer_bn, faq.answer_en, faq.answer_ar, locale),
            status=faq.status,
        )
