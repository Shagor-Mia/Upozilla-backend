from datetime import datetime

from pydantic import BaseModel


class PublicSettings(BaseModel):
    """Unauthenticated config for web/app clients - public keys only, never secrets."""

    site_name: str
    site_url: str
    site_description: str | None
    sms_demo_mode: bool
    turnstile_site_key: str | None
    facebook_app_id: str | None
    google_client_id: str | None
    gtm_id: str | None
    mapbox_token: str | None


class AdminSettingItem(BaseModel):
    key: str
    label: str
    group: str
    kind: str
    options: list[str]
    help: str
    is_secret: bool
    is_public: bool
    # Effective value for non-secrets; secrets only report whether one is set.
    value: str | None
    is_configured: bool
    source: str  # "database" | "environment" | "none"


class SettingsUpdate(BaseModel):
    """`{key: value}`; an empty string clears the DB value (env fallback resumes)."""

    values: dict[str, str | None]


class AiSettingsResponse(BaseModel):
    """Dedicated shape for the AI settings panel (Section 23 follow-up) -
    the generic `AdminSettingItem` has no masked-preview/last-verified
    concept, so this doesn't try to reuse it."""

    tier: str
    translation_mode: str
    is_configured: bool
    masked_key: str | None
    last_verified_at: datetime | None


class TestConnectionRequest(BaseModel):
    # When omitted, tests the currently saved key instead of an unsaved draft.
    api_key: str | None = None


class TestConnectionResponse(BaseModel):
    valid: bool
    message: str


class QueuedResponse(BaseModel):
    status: str
