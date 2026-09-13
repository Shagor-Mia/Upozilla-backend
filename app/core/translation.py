"""Optional automatic translation for content fields left blank by the admin
(Section 5, `translation_mode=automatic`). Uses `httpx` directly rather than
pulling in the `openai` SDK for a single call. Every failure mode (no key,
network error, bad response) is a safe no-op — automatic translation is a
convenience, never a hard dependency of content creation."""

import logging

import httpx

from app.core import ai_models, runtime_settings

logger = logging.getLogger(__name__)

_LANGUAGE_NAMES = {"bn": "Bengali", "en": "English", "ar": "Arabic"}
_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


def is_automatic() -> bool:
    return runtime_settings.get("translation_mode") == "automatic"


def translate(text: str, target_locale: str) -> str | None:
    """Translates `text` (assumed Bengali) into `target_locale` via the
    OpenAI API. Returns `None` if unconfigured or the call fails."""
    api_key = runtime_settings.get("openai_api_key")
    target_language = _LANGUAGE_NAMES.get(target_locale)
    if not api_key or not target_language or not text.strip():
        return None

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
                            f"Translate the given text from Bengali to {target_language}. "
                            "Reply with only the translation, no quotes or extra commentary."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                "temperature": 0,
            },
            timeout=15.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return content.strip() or None
    except Exception:  # noqa: BLE001 - never let a translation failure break content creation
        logger.warning("translation failed for target_locale=%s", target_locale, exc_info=True)
        return None


# Registered for the "translate missing content" admin action (Section 5) -
# every localized content model/field pair, kept in one place so the bulk
# action and any future audit tooling don't have to duplicate the list.
def _localized_registry() -> list[tuple[type, list[str]]]:
    from app.db.models.business import Business
    from app.db.models.exchange import ExchangeListing
    from app.db.models.hospital import Hospital
    from app.db.models.location import Location
    from app.db.models.market import Market
    from app.db.models.marketplace import MarketplaceCategory, MarketplaceProduct
    from app.db.models.place import Place
    from app.db.models.representative import Representative
    from app.db.models.service import Service, ServiceCategory
    from app.db.models.shop import Shop, ShopCategory

    return [
        (Location, ["name"]),
        (Place, ["name", "description"]),
        (Business, ["name", "description"]),
        (Hospital, ["name"]),
        (Market, ["name", "description"]),
        (MarketplaceCategory, ["name"]),
        (MarketplaceProduct, ["title", "description"]),
        (ExchangeListing, ["title", "description"]),
        (ServiceCategory, ["name"]),
        (Service, ["name", "description", "office_name"]),
        (ShopCategory, ["name"]),
        (Shop, ["name", "description"]),
        (Representative, ["bio"]),
    ]


def queue_missing_content_translations(background_tasks, limit_per_model: int = 500) -> None:
    """Admin-triggered backlog sweep: queues one background task per content
    model that walks up to `limit_per_model` rows and fills in whatever
    `_en`/`_ar` values are still missing. No-op unless translation_mode is
    automatic - same safety guard as the per-create path."""
    if not is_automatic():
        return
    for model, fields in _localized_registry():
        background_tasks.add_task(_translate_missing_for_model, model, fields, limit_per_model)


def _translate_missing_for_model(model: type, fields: list[str], limit: int) -> None:
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        rows = db.query(model).limit(limit).all()
        for row in rows:
            _translate_missing_fields(model, row.id, fields)


def schedule_translations(background_tasks, model: type, obj_id, fields: list[str]) -> None:
    """Called from a module's `create_*`/backlog service function right after
    insert. No-op unless `translation_mode=automatic`; runs after the response
    is sent so content creation itself is never slowed down by the OpenAI call."""
    if not is_automatic():
        return
    background_tasks.add_task(_translate_missing_fields, model, obj_id, fields)


def _translate_missing_fields(model: type, obj_id, fields: list[str]) -> None:
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        obj = db.get(model, obj_id)
        if obj is None:
            return
        changed = False
        for field in fields:
            base_value = getattr(obj, f"{field}_bn", None)
            if not base_value:
                continue
            for locale in ("en", "ar"):
                column = f"{field}_{locale}"
                if getattr(obj, column, None):
                    continue
                translated = translate(base_value, locale)
                if translated:
                    setattr(obj, column, translated)
                    changed = True
        if changed:
            db.commit()
