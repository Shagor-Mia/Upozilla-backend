from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import ai_models, runtime_settings, secrets
from app.core.audit import record_audit
from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.core.runtime_settings import DEFINITIONS, DEFINITIONS_BY_KEY
from app.db.models.settings import PlatformSetting
from app.modules.settings.schemas import (
    AdminSettingItem,
    AiSettingsResponse,
    PublicSettings,
    SettingsUpdate,
    TestConnectionRequest,
    TestConnectionResponse,
)


DEFAULT_SITE_NAME = "Upazila Digital Ecosystem"


def get_public_settings() -> PublicSettings:
    """`site_name`/`site_url`/`site_description` used to be hardcoded (an
    unused `site_name` default param here, and a frontend-only env var for
    the URL) - now real admin-editable settings (Section 16 SEO follow-up),
    same database-row-with-env-fallback pattern as gtm_id/mapbox_token."""
    values = runtime_settings.public_values()
    return PublicSettings(
        site_name=values.get("site_name") or DEFAULT_SITE_NAME,
        site_url=values.get("site_url") or "",
        site_description=values.get("site_description"),
        sms_demo_mode=(runtime_settings.get("sms_gateway") or "console") == "console",
        turnstile_site_key=values.get("turnstile_site_key"),
        facebook_app_id=values.get("facebook_app_id"),
        google_client_id=values.get("google_client_id"),
        gtm_id=values.get("gtm_id"),
        mapbox_token=values.get("mapbox_token"),
    )


def list_admin_settings(db: Session) -> list[AdminSettingItem]:
    db_rows = {row.key: row.value for row in db.query(PlatformSetting).all()}
    items = []
    for definition in DEFINITIONS:
        effective = runtime_settings.get(definition.key)
        db_value = db_rows.get(definition.key)
        if db_value not in (None, ""):
            source = "database"
        elif effective is not None:
            source = "environment"
        else:
            source = "none"
        items.append(
            AdminSettingItem(
                key=definition.key,
                label=definition.label,
                group=definition.group,
                kind=definition.kind,
                options=list(definition.options),
                help=definition.help,
                is_secret=definition.is_secret,
                is_public=definition.is_public,
                value=None if definition.is_secret else effective,
                is_configured=effective is not None,
                source=source,
            )
        )
    return items


def _validate(key: str, value: str | None) -> str | None:
    definition = DEFINITIONS_BY_KEY.get(key)
    if definition is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unknown setting '{key}'")
    if value is None or value.strip() == "":
        return None
    value = value.strip()
    if definition.kind == "select" and value not in definition.options:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{key}' must be one of {list(definition.options)}")
    if definition.kind == "int":
        try:
            int(value)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{key}' must be a whole number") from exc
    if key == "sms_gateway" and value == "console" and settings.is_production:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="console SMS mode is not allowed in production")
    return value


def update_settings(db: Session, actor: CurrentUser, payload: SettingsUpdate) -> list[AdminSettingItem]:
    changed: list[str] = []
    for key, raw in payload.values.items():
        value = _validate(key, raw)
        row = db.query(PlatformSetting).filter(PlatformSetting.key == key).first()
        if row is None:
            if value is None:
                continue
            row = PlatformSetting(key=key, is_secret=DEFINITIONS_BY_KEY[key].is_secret)
            db.add(row)
        row.value = secrets.encrypt(value) if (value is not None and DEFINITIONS_BY_KEY[key].is_secret) else value
        row.updated_by = actor.uuid
        changed.append(key)

    if changed:
        # Keys only - secret values never go into the audit log.
        record_audit(db, actor.uuid, "settings.updated", "platform_settings", None, {"keys": changed})
        db.commit()
        runtime_settings.invalidate()
    return list_admin_settings(db)


# --- AI settings panel (Section 23 follow-up) ---------------------------------------


def get_ai_settings(db: Session) -> AiSettingsResponse:
    current_key = runtime_settings.get("openai_api_key")
    row = db.query(PlatformSetting).filter(PlatformSetting.key == "openai_api_key").first()
    return AiSettingsResponse(
        tier=runtime_settings.get("ai_tier") or ai_models.DEFAULT_TIER,
        translation_mode=runtime_settings.get("translation_mode") or "manual",
        is_configured=bool(current_key),
        masked_key=secrets.mask(current_key) if current_key else None,
        last_verified_at=row.last_verified_at if row else None,
    )


def test_ai_connection(db: Session, payload: TestConnectionRequest) -> TestConnectionResponse:
    """Makes one cheap real call (`GET /v1/models`, no completion cost) to
    confirm a key is accepted by OpenAI. With `payload.api_key` set, tests an
    unsaved draft value without persisting anything; with it omitted, tests
    the currently saved key and stamps `last_verified_at` on success."""
    api_key = payload.api_key or runtime_settings.get("openai_api_key")
    if not api_key:
        return TestConnectionResponse(valid=False, message="No API key configured.")

    try:
        response = httpx.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
    except httpx.HTTPError:
        return TestConnectionResponse(valid=False, message="Could not reach OpenAI - check your network.")

    if response.status_code in (401, 403):
        return TestConnectionResponse(valid=False, message="OpenAI rejected this key.")

    # Any other status (200, 429, 5xx) proves the credential itself was
    # accepted, even if rate-limited/quota-exhausted right now.
    if payload.api_key is None:
        row = db.query(PlatformSetting).filter(PlatformSetting.key == "openai_api_key").first()
        if row is not None:
            row.last_verified_at = datetime.now(timezone.utc)
            db.commit()
    return TestConnectionResponse(valid=True, message="Connection looks good.")


def disconnect_ai(db: Session, actor: CurrentUser) -> AiSettingsResponse:
    row = db.query(PlatformSetting).filter(PlatformSetting.key == "openai_api_key").first()
    if row is not None and row.value is not None:
        row.value = None
        row.last_verified_at = None
        row.updated_by = actor.uuid
        record_audit(db, actor.uuid, "settings.ai_disconnected", "platform_settings", None, {"key": "openai_api_key"})
        db.commit()
        runtime_settings.invalidate()
    return get_ai_settings(db)
