import uuid
from datetime import datetime

from pydantic import BaseModel


class NewsArticleCreate(BaseModel):
    source_id: uuid.UUID
    location_id: uuid.UUID | None = None
    category: str | None = None
    title: str
    slug: str
    summary: str | None = None
    body: str | None = None
    original_url: str | None = None
    image: str | None = None
    published_at: datetime | None = None
    status: str = "draft"
    tags: list[str] | None = None


class NewsArticleResponse(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    location_id: uuid.UUID | None
    category: str | None
    title: str
    slug: str
    summary: str | None
    image: str | None
    published_at: datetime | None
    status: str
    tags: list[str] | None

    model_config = {"from_attributes": True}


class NewsArticleDetailResponse(NewsArticleResponse):
    body: str | None
    original_url: str | None


class NewsSourceResponse(BaseModel):
    id: uuid.UUID
    name: str
    feed_url: str
    type: str
    is_licensed: bool
    active: bool

    model_config = {"from_attributes": True}
