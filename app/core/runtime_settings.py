"""Runtime (admin-editable) integration settings with env-var fallback.

Resolution order for a key: `platform_settings` row (set from the admin CMS)
-> the matching `Settings` env attribute -> None. Values are cached in-process
for a short TTL and invalidated on write, so hot paths (OTP, listing create)
don't hit the DB for config on every request.
"""

import threading
import time
from dataclasses import dataclass, field

from app.core import secrets
from app.core.config import settings
from app.core.database import SessionLocal
from app.db.models.settings import PlatformSetting

CACHE_TTL_SECONDS = 30


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    label: str
    group: str
    env_attr: str | None = None
    is_secret: bool = False
    # Public settings are exposed unauthenticated to the web/app clients
    # (analytics ids, map token, site keys) - never mark a secret public.
    is_public: bool = False
    kind: str = "text"  # text | select | int
    options: tuple[str, ...] = field(default_factory=tuple)
    help: str = ""


DEFINITIONS: tuple[SettingDefinition, ...] = (
    SettingDefinition(
        "sms_gateway", "SMS gateway", "sms", env_attr="SMS_GATEWAY", kind="select", options=("console", "http"),
        help="console = no SMS is sent, the OTP code is shown on screen (demo mode). http = real gateway below.",
    ),
    SettingDefinition("sms_http_url", "Gateway URL", "sms", env_attr="SMS_HTTP_URL", help="JSON POST endpoint of the SMS provider."),
    SettingDefinition("sms_http_api_key", "Gateway API key", "sms", env_attr="SMS_HTTP_API_KEY", is_secret=True),
    SettingDefinition("sms_sender_id", "Sender ID", "sms", env_attr="SMS_SENDER_ID", help="Name shown as the SMS sender."),
    SettingDefinition(
        "turnstile_site_key", "Turnstile site key", "captcha", is_public=True,
        help="Cloudflare Turnstile. Leave both empty to skip the challenge on OTP requests.",
    ),
    SettingDefinition("turnstile_secret_key", "Turnstile secret key", "captcha", env_attr="TURNSTILE_SECRET_KEY", is_secret=True),
    SettingDefinition("facebook_app_id", "Facebook App ID", "facebook", env_attr="FACEBOOK_APP_ID", is_public=True,
                      help="Enables the 'Continue with Facebook' button once both values are set."),
    SettingDefinition("facebook_app_secret", "Facebook App secret", "facebook", env_attr="FACEBOOK_APP_SECRET", is_secret=True),
    SettingDefinition("google_client_id", "Google Client ID", "google", env_attr="GOOGLE_CLIENT_ID", is_public=True,
                      help="Enables the 'Continue with Google' button once set (Google Cloud Console > Credentials > OAuth client ID > Web application)."),
    SettingDefinition("gtm_id", "Google Tag Manager container ID", "analytics", is_public=True,
                      help="GTM-XXXXXXX. GA4 and Meta Pixel are configured inside the container."),
    SettingDefinition("mapbox_token", "Mapbox public token", "maps", is_public=True,
                      help="pk.… token restricted by HTTP referrer. Without it maps show a coordinates line."),
    SettingDefinition("auto_approve_trust_score", "Auto-approve trust score", "marketplace",
                      env_attr="AUTO_APPROVE_TRUST_SCORE", kind="int",
                      help="Sellers at or above this trust score skip the manual moderation queue."),
    SettingDefinition("exchange_listing_ttl_days", "Exchange listing lifetime (days)", "marketplace",
                      env_attr="EXCHANGE_LISTING_TTL_DAYS", kind="int"),
    SettingDefinition("min_supported_app_version", "Minimum supported app version", "mobile_app",
                      env_attr="MIN_SUPPORTED_APP_VERSION", is_public=True,
                      help="Semver. Installed apps below this version are forced to update (Section 8.7)."),
    SettingDefinition("latest_app_version", "Latest app version", "mobile_app",
                      env_attr="LATEST_APP_VERSION", is_public=True,
                      help="Semver of the build currently in the stores; shown in the update prompt."),
    SettingDefinition(
        "translation_mode", "Content translation", "ai", kind="select", options=("manual", "automatic"),
        help="manual = admins type each language themselves. automatic = blank en/ar content fields are "
             "filled in the background using the AI settings below.",
    ),
    SettingDefinition("openai_api_key", "OpenAI API key", "ai", env_attr="OPENAI_API_KEY", is_secret=True,
                      help="Powers the AI chatbot, content translation, embeddings, and news enrichment."),
    SettingDefinition(
        "ai_tier", "AI quality tier", "ai", env_attr="AI_TIER", kind="select",
        options=("economy", "standard", "premium"),
        help="Economy = fastest/cheapest, Standard = balanced (recommended), Premium = highest quality/cost.",
    ),
)

DEFINITIONS_BY_KEY: dict[str, SettingDefinition] = {d.key: d for d in DEFINITIONS}

_lock = threading.Lock()
_cache: dict[str, str | None] = {}
_cache_loaded_at = 0.0


def _load_rows() -> dict[str, str | None]:
    with SessionLocal() as db:
        return {row.key: row.value for row in db.query(PlatformSetting).all()}


def _db_values() -> dict[str, str | None]:
    global _cache, _cache_loaded_at
    now = time.monotonic()
    if now - _cache_loaded_at > CACHE_TTL_SECONDS:
        with _lock:
            if now - _cache_loaded_at > CACHE_TTL_SECONDS:
                try:
                    _cache = _load_rows()
                except Exception:  # noqa: BLE001 - config must never take the API down
                    _cache = {}
                _cache_loaded_at = now
    return _cache


def invalidate() -> None:
    global _cache_loaded_at
    _cache_loaded_at = 0.0


def get(key: str) -> str | None:
    definition = DEFINITIONS_BY_KEY[key]
    value = _db_values().get(key)
    if value not in (None, ""):
        return secrets.decrypt_or_plain(value) if definition.is_secret else value
    if definition.env_attr:
        env_value = getattr(settings, definition.env_attr, None)
        if env_value not in (None, ""):
            return str(env_value)
    return None


def get_int(key: str, default: int) -> int:
    raw = get(key)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


def public_values() -> dict[str, str | None]:
    return {d.key: get(d.key) for d in DEFINITIONS if d.is_public}
