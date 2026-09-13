import enum
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.db.models.moderation import ModerationEntityType, ModerationQueueStatus


class ModerationDecision(str, enum.Enum):
    APPROVE = "approve"
    REJECT = "reject"


class ModerationReviewBody(BaseModel):
    decision: ModerationDecision
    note: str | None = Field(default=None, max_length=1000)
    # Only meaningful (and required) for a CONTRACT_DISPUTE approval - the
    # router validates it against the queue row's entity_type since that
    # isn't known to this body in isolation (Section 2 of the plan).
    favored_party: Literal["employer", "worker"] | None = None


class QueueListingSnapshot(BaseModel):
    listing_type: str
    title: str
    price: float
    currency: str
    status: str
    moderation_status: str
    seller_user_id: uuid.UUID | None
    seller_name: str
    cover_image: str | None
    description: str | None


class QueueReportSnapshot(BaseModel):
    reason: str
    details: str | None
    status: str
    reporter_name: str
    listing_type: str
    listing_id: uuid.UUID
    listing_title: str | None
    listing_status: str | None


class ModerationQueueItem(BaseModel):
    id: uuid.UUID
    entity_type: ModerationEntityType
    entity_id: uuid.UUID
    location_id: uuid.UUID | None
    location_name: str | None
    reason: str | None
    status: ModerationQueueStatus
    created_at: datetime
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    review_note: str | None
    listing: QueueListingSnapshot | None = None
    report: QueueReportSnapshot | None = None


class ModerationStats(BaseModel):
    pending: int
    approved: int
    rejected: int
