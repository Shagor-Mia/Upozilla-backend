"""Work Contract module (new scope, not in UPAZILA_SAAS_IMPLEMENTATION_PLAN.md).

A digital "চুক্তিপত্র" between an employer and a worker (both existing
registered users - Section 1's ownership constraint): scope of work, duration,
and pay, with in-app dual acceptance, progress/payment/problem tracking during
the work, and dispute escalation into the existing moderation queue. Standalone
module, not tied to any marketplace/services listing - see `ContractProblem`
below for why disputes reuse a single-table lifecycle rather than a 5th table.

All status/category fields are plain `String` columns holding a Python
`str, enum.Enum` member's `.value` (never a native Postgres `Enum` - that
caused the real bug fixed in `e8a33ec`)."""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ARRAY, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TenantMixin, TimestampMixin, UUIDPKMixin


class ContractStatus(str, enum.Enum):
    PENDING = "pending"  # created, worker hasn't accepted
    ACTIVE = "active"  # both accepted
    REJECTED = "rejected"  # worker declined while PENDING
    CANCELLED = "cancelled"  # party cancelled, or dispute ruling ended it
    DISPUTED = "disputed"  # an escalated problem is open
    COMPLETED = "completed"  # both parties confirmed completion


class ContractPaymentType(str, enum.Enum):
    FIXED = "fixed"
    HOURLY = "hourly"
    DAILY = "daily"
    MILESTONE = "milestone"


class ContractPaymentMethod(str, enum.Enum):
    CASH = "cash"
    BKASH = "bkash"
    NAGAD = "nagad"
    BANK = "bank"
    OTHER = "other"


class ContractPaymentStatus(str, enum.Enum):
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"


class ContractProblemCategory(str, enum.Enum):
    SCOPE_DISAGREEMENT = "scope_disagreement"
    PAYMENT_ISSUE = "payment_issue"
    QUALITY_ISSUE = "quality_issue"
    NO_SHOW = "no_show"
    OTHER = "other"


class ContractProblemStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"  # peer-resolved
    ESCALATED = "escalated"
    DISPUTE_RESOLVED = "dispute_resolved"  # admin ruled


class ContractDisputeResolution(str, enum.Enum):
    FAVOR_EMPLOYER = "favor_employer"
    FAVOR_WORKER = "favor_worker"
    DISMISSED = "dismissed"


class WorkContract(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    __tablename__ = "work_contracts"

    # Nullable + SET NULL on account deletion: matches `ExchangeListing.seller_user_id`
    # precedent so the contract's history survives either party deleting their account.
    employer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    worker_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title_bn: Mapped[str] = mapped_column(String(200), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(200), nullable=True)
    title_ar: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Bn is what a dispute gets judged against - always required, unlike the
    # optional en/ar translations.
    description_bn: Mapped[str] = mapped_column(Text, nullable=False)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="BDT", nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=ContractStatus.PENDING.value, nullable=False, index=True)
    # Set at creation time (the employer implicitly "accepts" by creating it).
    employer_accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    worker_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Dual-confirm completion: both must confirm before status flips to COMPLETED.
    employer_completion_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    worker_completion_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Admin/operational only - plain text, not shown as a formal legal record.
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Capped at 5 by the Pydantic validator (schemas.py), same convention as
    # marketplace/exchange - pasted URLs, no upload infra.
    reference_images: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)


class ContractProgressEntry(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    __tablename__ = "contract_progress_entries"

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note_bn: Mapped[str] = mapped_column(Text, nullable=False)
    note_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    percent_complete: Mapped[int | None] = mapped_column(Integer, nullable=True)
    images: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)


class ContractPayment(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    __tablename__ = "contract_payments"

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    logged_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    note_bn: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_images: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    # Defaults to submit time; the payload may override with an earlier `paid_at`.
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default=ContractPaymentStatus.PENDING_CONFIRMATION.value, nullable=False, index=True
    )
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ContractProblem(Base, UUIDPKMixin, TenantMixin, TimestampMixin):
    """Doubles as the dispute record - one row per problem, `status` carries it
    through `OPEN -> ESCALATED -> DISPUTE_RESOLVED`, mirroring `ListingReport`'s
    single-table lifecycle rather than adding a 5th table."""

    __tablename__ = "contract_problems"

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raised_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    description_bn: Mapped[str] = mapped_column(Text, nullable=False)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    images: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=ContractProblemStatus.OPEN.value, nullable=False, index=True
    )
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set only on an admin ruling - never by the peer-resolve path.
    resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Admin's note, plain text like `ModerationQueue.review_note`.
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
