import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Mirrors the DB CheckConstraint("status IN ('draft', 'published')") on
# news_articles.status - validated here too so a bad value 422s instead of
# hitting that constraint as an unhandled IntegrityError.
NewsArticleStatus = Literal["draft", "published"]


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
    status: NewsArticleStatus = "draft"
    tags: list[str] | None = None


class NewsArticleUpdate(BaseModel):
    """Lets an admin publish a draft (or otherwise edit an article) - there
    was previously no way to change an article after creation at all, even
    though `list_all_for_admin`'s own docstring says a draft should be
    "found and published again"."""

    source_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    category: str | None = None
    title: str | None = None
    slug: str | None = None
    summary: str | None = None
    body: str | None = None
    original_url: str | None = None
    image: str | None = None
    published_at: datetime | None = None
    status: NewsArticleStatus | None = None
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
