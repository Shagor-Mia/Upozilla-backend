"""Encryption at rest for `platform_settings` secret values (Section 5 /
`is_secret` settings). Uses `cryptography.fernet` - already an installed
transitive dependency of `python-jose[cryptography]`, no new requirement.

Key material is `SETTINGS_ENCRYPTION_KEY` if set, else `JWT_SECRET_KEY` (so
existing deployments keep working with zero new config); either way it's
hashed into a valid Fernet key so any plain string works, not just a
pre-formatted one.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    key_material = settings.SETTINGS_ENCRYPTION_KEY or settings.JWT_SECRET_KEY
    derived_key = base64.urlsafe_b64encode(hashlib.sha256(key_material.encode()).digest())
    return Fernet(derived_key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_or_plain(value: str) -> str:
    """Decrypts a value encrypted by `encrypt()`. Falls back to returning the
    raw value unchanged if it isn't a valid Fernet token - safe for any
    secret row written before this encryption layer existed, no data
    migration script needed."""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return value


def mask(value: str, visible: int = 4) -> str:
    tail = value[-visible:] if len(value) > visible else value
    return "*" * 16 + tail
