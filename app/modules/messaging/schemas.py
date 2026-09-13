import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.db.models.exchange import ListingType


class ConversationCreate(BaseModel):
    listing_type: ListingType
    listing_id: uuid.UUID


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def strip_body(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message cannot be empty")
        return v


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID | None
    body: str
    created_at: datetime
    read_at: datetime | None


class ConversationParticipant(BaseModel):
    id: uuid.UUID
    full_name: str


class UnreadCountResponse(BaseModel):
    unread: int


class ConversationResponse(BaseModel):
    id: uuid.UUID
    listing_type: ListingType
    listing_id: uuid.UUID
    listing_title: str | None
    listing_image: str | None
    buyer: ConversationParticipant
    seller: ConversationParticipant
    other_party: ConversationParticipant
    last_message: MessageResponse | None
    unread_count: int
    created_at: datetime
