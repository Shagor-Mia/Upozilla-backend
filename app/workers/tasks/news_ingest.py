import hashlib
import logging
import re
from datetime import datetime, timezone

import feedparser
import httpx

from app.core.database import SessionLocal
from app.core.tenant import resolve_tenant_id
from app.db.models.news import NewsArticle, NewsSource
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_FEED_FETCH_TIMEOUT_SECONDS = 15.0


def _strip_html(raw: str) -> str:
    return _HTML_TAG_RE.sub("", raw or "").strip()


def _dedupe_slug(title: str, source_id: str) -> str:
    digest = hashlib.sha256(f"{source_id}:{title}".encode()).hexdigest()[:16]
    return f"{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:80]}-{digest}"


@celery_app.task(name="app.workers.tasks.news_ingest.ingest_all_active_sources")
def ingest_all_active_sources() -> int:
    """Pull RSS feeds, normalize, dedupe by (source, title) hash, publish licensed sources.

    See Section 11 of UPAZILA_SAAS_IMPLEMENTATION_PLAN.md — unlicensed sources land as
    drafts for manual moderation instead of auto-publishing.
    """
    db = SessionLocal()
    ingested_count = 0
    try:
        sources = db.query(NewsSource).filter(NewsSource.active.is_(True)).all()
        for source in sources:
            try:
                ingested_count += _ingest_source(db, source)
            except Exception:  # noqa: BLE001 - one bad feed must not skip every other source
                db.rollback()
                logger.warning("news ingestion failed for source %s (%s)", source.id, source.feed_url, exc_info=True)
    finally:
        db.close()
    return ingested_count


def _ingest_source(db, source: NewsSource) -> int:
    response = httpx.get(source.feed_url, timeout=_FEED_FETCH_TIMEOUT_SECONDS, follow_redirects=True)
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    new_count = 0

    for entry in feed.entries:
        title = getattr(entry, "title", None)
        if not title:
            continue

        slug = _dedupe_slug(title, str(source.id))
        exists = db.query(NewsArticle).filter(NewsArticle.slug == slug).first()
        if exists:
            continue

        summary = _strip_html(getattr(entry, "summary", ""))[:500]
        published_at = datetime.now(timezone.utc)
        if getattr(entry, "published_parsed", None):
            published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

        image = None
        media = getattr(entry, "media_content", None) or getattr(entry, "media_thumbnail", None)
        if media:
            image = media[0].get("url")

        article = NewsArticle(
            tenant_id=resolve_tenant_id(db, None),
            source_id=source.id,
            title=title,
            slug=slug,
            summary=summary,
            original_url=getattr(entry, "link", None),
            image=image,
            published_at=published_at,
            status="published" if source.is_licensed else "draft",
        )
        db.add(article)
        new_count += 1

    db.commit()
    return new_count
