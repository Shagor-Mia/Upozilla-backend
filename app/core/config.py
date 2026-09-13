from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "local"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@postgres:5432/upazila"
    REDIS_URL: str = "redis://redis:6379/0"
    # SQLAlchemy connection pool - tune per instance count so pool_size * worker_count
    # stays under the DB's max_connections as the deployment scales horizontally.
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 1800

    JWT_SECRET_KEY: str = "change-me-in-env"
    JWT_ALGORITHM: str = "HS256"
    # Encrypts `is_secret` platform_settings values at rest (app/core/secrets.py).
    # Optional - falls back to JWT_SECRET_KEY if unset, but set a distinct value
    # in production so rotating one secret doesn't affect the other.
    SETTINGS_ENCRYPTION_KEY: str | None = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # --- Phone OTP (Section 10 / 14.1) ---
    # "console" logs the code instead of sending SMS and echoes it back in the
    # API response (dev only). Switch to "http" once a real gateway is chosen.
    SMS_GATEWAY: str = "console"
    SMS_HTTP_URL: str | None = None
    SMS_HTTP_API_KEY: str | None = None
    SMS_SENDER_ID: str = "Upazila"
    OTP_EXPIRE_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 5
    OTP_REQUESTS_PER_PHONE_PER_HOUR: int = 5
    OTP_REQUESTS_PER_IP_PER_HOUR: int = 20
    # Cloudflare Turnstile on the OTP-request endpoint (Section 14.1). Empty = skip.
    TURNSTILE_SECRET_KEY: str | None = None

    # --- Facebook Login (Section 16.2) — verified server-side, never trusted as-is ---
    FACEBOOK_APP_ID: str | None = None
    FACEBOOK_APP_SECRET: str | None = None

    # --- Google Login (same pattern, added post-plan) — ID token verified server-side ---
    GOOGLE_CLIENT_ID: str | None = None

    # --- Marketplace / Exchange (Section 10) ---
    # Listings from sellers at/above this trust score skip the manual moderation queue.
    AUTO_APPROVE_TRUST_SCORE: int = 3
    EXCHANGE_LISTING_TTL_DAYS: int = 30
    LISTINGS_PER_USER_PER_DAY: int = 10
    SHOPS_PER_USER_PER_DAY: int = 5
    MESSAGES_PER_USER_PER_MINUTE: int = 20
    CONTACT_REVEALS_PER_USER_PER_HOUR: int = 30
    WS_TICKET_TTL_SECONDS: int = 60

    # --- Mobile app (Section 8.7) — overridable from admin settings ---
    # Clients below MIN_SUPPORTED_APP_VERSION are shown a force-update screen.
    MIN_SUPPORTED_APP_VERSION: str = "0.1.0"
    LATEST_APP_VERSION: str = "0.1.0"

    # --- Content translation (Section 5) — used only when translation_mode=automatic ---
    OPENAI_API_KEY: str | None = None

    # --- Media uploads (Section 6 free-hosting setup, added post-plan) ---
    # Client uploads straight to Cloudinary using a signature we mint here -
    # the file never transits our server. None of the three = uploads disabled.
    CLOUDINARY_CLOUD_NAME: str | None = None
    CLOUDINARY_API_KEY: str | None = None
    CLOUDINARY_API_SECRET: str | None = None
    UPLOAD_SIGNATURES_PER_USER_PER_MINUTE: int = 30

    # --- AI layer (Section 5.13/17 Phase 4) ---
    AI_CHAT_RATE_LIMIT_PER_HOUR: int = 20
    # Anonymous callers (the public floating widget) are limited per-IP,
    # tighter than the per-account limit since one IP can represent many
    # people behind carrier-grade NAT (Section 19.3).
    AI_CHAT_RATE_LIMIT_PER_HOUR_ANONYMOUS: int = 10
    AI_TIER: str = "standard"

    # --- Work Contracts (new scope beyond UPAZILA_SAAS_IMPLEMENTATION_PLAN.md) ---
    CONTRACTS_PER_USER_PER_MINUTE: int = 5
    CONTRACT_ENTRIES_PER_USER_PER_MINUTE: int = 10
    USER_LOOKUP_PER_USER_PER_MINUTE: int = 20

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

if settings.is_production and settings.JWT_SECRET_KEY == "change-me-in-env":
    raise RuntimeError("JWT_SECRET_KEY is still the default value - set a real secret before running in production")
