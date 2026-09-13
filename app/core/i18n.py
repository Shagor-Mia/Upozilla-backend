"""Content locale resolution (bn/en/ar). Section 5: every content table stores
`<field>_bn`/`_en`/`_ar`; `bn` is always populated and is the fallback for any
locale the admin hasn't translated into yet."""

SUPPORTED_LOCALES: tuple[str, ...] = ("bn", "en", "ar")
DEFAULT_LOCALE = "bn"


def resolve_locale(raw: str | None) -> str:
    """Normalizes a raw `?lang=` value or an `Accept-Language` primary tag
    (e.g. `en-US` -> `en`) to a supported locale, defaulting to bn."""
    if not raw:
        return DEFAULT_LOCALE
    candidate = raw.strip().lower()[:2]
    return candidate if candidate in SUPPORTED_LOCALES else DEFAULT_LOCALE


def localized_value(bn: str, en: str | None, ar: str | None, locale: str) -> str:
    values = {"bn": bn, "en": en, "ar": ar}
    return values.get(locale) or bn
