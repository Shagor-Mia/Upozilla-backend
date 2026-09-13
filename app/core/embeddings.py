"""Phase 4 AI layer: keeps `knowledge_chunks` in sync with the content that
should be retrievable by the RAG chatbot (Section 5.13/17). Mirrors
`app/core/translation.py` exactly: uses `httpx` directly (no OpenAI SDK for a
single call), and every failure mode (no key, network error, bad response) is
a safe no-op - indexing is a convenience, never a hard dependency of content
creation."""

import logging
import uuid

import httpx

from app.core import runtime_settings
from app.db.models.ai import EMBEDDING_DIMENSIONS, KnowledgeChunk, KnowledgeSourceType

logger = logging.getLogger(__name__)

_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
_EMBEDDING_MODEL = "text-embedding-3-small"


def is_configured() -> bool:
    return bool(runtime_settings.get("openai_api_key"))


def embed(text: str) -> list[float] | None:
    """Returns a 1536-dim embedding for `text`, or `None` if unconfigured or
    the call fails. Never raises."""
    api_key = runtime_settings.get("openai_api_key")
    if not api_key or not text.strip():
        return None

    try:
        response = httpx.post(
            _EMBEDDINGS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": _EMBEDDING_MODEL, "input": text},
            timeout=15.0,
        )
        response.raise_for_status()
        vector = response.json()["data"][0]["embedding"]
        if len(vector) != EMBEDDING_DIMENSIONS:
            logger.warning("unexpected embedding size %d from %s", len(vector), _EMBEDDING_MODEL)
            return None
        return vector
    except Exception:  # noqa: BLE001 - never let an embedding failure break content creation
        logger.warning("embedding failed", exc_info=True)
        return None


async def embed_async(text: str) -> list[float] | None:
    """Async twin of `embed()`, for the request-time RAG chat path (`app/modules/ai/service.py`)
    - keeps it off the sync threadpool so a burst of chat traffic can't starve other endpoints."""
    api_key = runtime_settings.get("openai_api_key")
    if not api_key or not text.strip():
        return None

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                _EMBEDDINGS_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": _EMBEDDING_MODEL, "input": text},
                timeout=15.0,
            )
        response.raise_for_status()
        vector = response.json()["data"][0]["embedding"]
        if len(vector) != EMBEDDING_DIMENSIONS:
            logger.warning("unexpected embedding size %d from %s", len(vector), _EMBEDDING_MODEL)
            return None
        return vector
    except Exception:  # noqa: BLE001 - never let an embedding failure break content creation
        logger.warning("embedding failed", exc_info=True)
        return None


def schedule_reindex(
    background_tasks,
    source_type: KnowledgeSourceType,
    source_id: uuid.UUID,
    text: str,
    tenant_id: uuid.UUID | None = None,
) -> None:
    """Called from a module's `create_*`/`update_*` service function, same
    call-site pattern as `translation.schedule_translations`. No-op unless an
    OpenAI key is configured; runs after the response is sent."""
    if not is_configured():
        return
    background_tasks.add_task(reindex_now, source_type, source_id, text, tenant_id)


def schedule_delete(background_tasks, source_type: KnowledgeSourceType, source_id: uuid.UUID) -> None:
    """Called when content is unpublished/deleted so a stale embedding never
    outlives the content it was built from."""
    background_tasks.add_task(delete_from_index, source_type, source_id)


def schedule_publish_reindex(background_tasks, obj, source_type: KnowledgeSourceType, text: str) -> None:
    """Shared control flow for content with a draft/published `status` column
    (places, government services, faqs, news): delete any stale index entry
    while unpublished, else (re)index with `text`. Each module still builds
    its own `text` from its own fields - only the branch on `status` is
    identical across them."""
    if obj.status != "published":
        schedule_delete(background_tasks, source_type, obj.id)
        return
    schedule_reindex(background_tasks, source_type, obj.id, text, obj.tenant_id)


def reindex_now(
    source_type: KnowledgeSourceType,
    source_id: uuid.UUID,
    text: str,
    tenant_id: uuid.UUID | None = None,
) -> None:
    from app.core.database import SessionLocal

    vector = embed(text)
    with SessionLocal() as db:
        db.query(KnowledgeChunk).filter(
            KnowledgeChunk.source_type == source_type, KnowledgeChunk.source_id == source_id
        ).delete()
        if vector is not None:
            db.add(
                KnowledgeChunk(
                    tenant_id=tenant_id,
                    source_type=source_type,
                    source_id=source_id,
                    content=text,
                    embedding=vector,
                )
            )
        db.commit()


def delete_from_index(source_type: KnowledgeSourceType, source_id: uuid.UUID) -> None:
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        db.query(KnowledgeChunk).filter(
            KnowledgeChunk.source_type == source_type, KnowledgeChunk.source_id == source_id
        ).delete()
        db.commit()


def _place_text(row) -> str:
    return f"{row.name_bn} {row.name_en or ''} {row.description_bn or ''} {row.description_en or ''}".strip()


def _service_text(row) -> str:
    return (
        f"{row.name_bn} {row.name_en or ''} {row.description_bn or ''} {row.description_en or ''} "
        f"{row.office_name_bn or ''}"
    ).strip()


def _hospital_text(row) -> str:
    return f"{row.name_bn} {row.name_en or ''} {row.address or ''}".strip()


def _market_text(row) -> str:
    days = ", ".join(row.market_day or [])
    return f"{row.name_bn} {row.name_en or ''} {days}".strip()


def _news_text(row) -> str:
    return f"{row.title} {row.summary or ''} {row.body or ''}".strip()


def _faq_text(row) -> str:
    return f"{row.question_bn} {row.question_en or ''} {row.answer_bn} {row.answer_en or ''}".strip()


def _registry():
    from app.db.models.faq import Faq
    from app.db.models.hospital import Hospital
    from app.db.models.market import Market
    from app.db.models.news import NewsArticle
    from app.db.models.place import Place
    from app.db.models.service import Service

    # (source_type, model, text_fn, is_indexable_fn) - "is_indexable" mirrors
    # each module's own public-content gate; hospitals/markets have no status
    # column (Section 22.2/17 Phase 1) so they're always indexable.
    return [
        (KnowledgeSourceType.PLACE, Place, _place_text, lambda r: r.status == "published"),
        (KnowledgeSourceType.SERVICE, Service, _service_text, lambda r: r.status == "published"),
        (KnowledgeSourceType.HOSPITAL, Hospital, _hospital_text, lambda _r: True),
        (KnowledgeSourceType.MARKET, Market, _market_text, lambda _r: True),
        (KnowledgeSourceType.NEWS, NewsArticle, _news_text, lambda r: r.status == "published"),
        (KnowledgeSourceType.FAQ, Faq, _faq_text, lambda r: r.status == "published"),
    ]


def queue_reindex_all(background_tasks, limit_per_model: int = 1000) -> None:
    """Admin-triggered one-off backfill: queues one background task per
    existing indexable row across every content type. No-op unless an OpenAI
    key is configured - same safety guard as `translation.py`'s backlog
    sweep (`POST /admin/settings/reindex-knowledge-base`)."""
    if not is_configured():
        return
    for source_type, model, text_fn, is_indexable in _registry():
        background_tasks.add_task(_reindex_model, source_type, model, text_fn, is_indexable, limit_per_model)


def _reindex_model(source_type: KnowledgeSourceType, model: type, text_fn, is_indexable, limit: int) -> None:
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        rows = db.query(model).limit(limit).all()
        for row in rows:
            tenant_id = getattr(row, "tenant_id", None)
            if is_indexable(row):
                reindex_now(source_type, row.id, text_fn(row), tenant_id)
            else:
                delete_from_index(source_type, row.id)
