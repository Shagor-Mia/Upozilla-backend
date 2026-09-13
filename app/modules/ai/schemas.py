import uuid

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class SourceRef(BaseModel):
    source_type: str
    source_id: uuid.UUID


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceRef]
