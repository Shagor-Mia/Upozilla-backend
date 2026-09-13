"""Section 17 Phase 4: LLM-assisted summary/category/tags for news articles
left blank by whoever created them (editor or the RSS ingestion worker,
Section 11). Same safe-no-op-without-a-key pattern as `translation.py` /
`embeddings.py` - never blocks or breaks article creation."""

import json
import logging

import httpx
from sqlalchemy.orm import Session

from app.core import ai_models, runtime_settings
from app.db.models.news import NewsArticle

logger = logging.getLogger(__name__)

_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


def is_configured() -> bool:
    return bool(runtime_settings.get("openai_api_key"))


def schedule_enrich(background_tasks, article_id) -> None:
    if not is_configured():
        return
    background_tasks.add_task(enrich, article_id)


def _existing_categories(db: Session) -> list[str]:
    rows = (
        db.query(NewsArticle.category)
        .filter(NewsArticle.category.isnot(None))
        .distinct()
        .limit(50)
        .all()
    )
    return [r[0] for r in rows]


def _suggest(body: str, existing_categories: list[str]) -> dict | None:
    api_key = runtime_settings.get("openai_api_key")
    if not api_key or not body.strip():
        return None

    category_hint = (
        f"Prefer one of these existing categories if it fits: {', '.join(existing_categories)}. "
        "Otherwise suggest a short new one."
        if existing_categories
        else "Suggest a short category name."
    )
    try:
        response = httpx.post(
            _CHAT_COMPLETIONS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": ai_models.chat_model(),
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Summarize the given Bengali news article body in 1-2 sentences (same "
                            f"language as the body), suggest a category, and 3-6 short tags. {category_hint} "
                            'Reply with ONLY a JSON object: {"summary": str, "category": str, "tags": [str, ...]}.'
                        ),
                    },
                    {"role": "user", "content": body},
                ],
                "temperature": 0,
            },
            timeout=20.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception:  # noqa: BLE001 - never let enrichment failure break article creation
        logger.warning("news enrichment failed", exc_info=True)
        return None


def enrich(article_id) -> None:
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        article = db.get(NewsArticle, article_id)
        if article is None or not article.body:
            return
        if article.summary and article.category and article.tags:
            return

        suggestion = _suggest(article.body, _existing_categories(db))
        if not suggestion:
            return

        changed = False
        if not article.summary and suggestion.get("summary"):
            article.summary = str(suggestion["summary"])
            changed = True
        if not article.category and suggestion.get("category"):
            article.category = str(suggestion["category"])
            changed = True
        if not article.tags and isinstance(suggestion.get("tags"), list):
            article.tags = [str(t) for t in suggestion["tags"]][:10]
            changed = True

        if changed:
            db.commit()
