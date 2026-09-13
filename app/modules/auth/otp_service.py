"""Phone OTP issue/verify (Section 10, Section 5.1 `otp_codes`).

Codes are HMAC-hashed at rest, expire in minutes, are attempt-counted, and
issuing is rate-limited per phone first and per IP second (Section 19.3).
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import runtime_settings
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit
from app.core.sms import get_sms_gateway, sender_name
from app.db.models.otp import OtpCode, OtpPurpose
from app.db.models.user import User

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def _hash_code(phone: str, code: str) -> str:
    return hmac.new(settings.JWT_SECRET_KEY.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def _verify_turnstile(token: str | None, client_ip: str) -> None:
    secret = runtime_settings.get("turnstile_secret_key")
    if not secret:
        return
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="captcha challenge required")
    response = httpx.post(
        TURNSTILE_VERIFY_URL,
        data={"secret": secret, "response": token, "remoteip": client_ip},
        timeout=10,
    )
    if not response.is_success or not response.json().get("success"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="captcha verification failed")


def _check_purpose_preconditions(db: Session, phone: str, purpose: OtpPurpose, requesting_user_id) -> None:
    owner = db.query(User).filter(User.phone == phone).first()
    if purpose is OtpPurpose.LOGIN and owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no account uses this phone number - register first")
    if purpose is OtpPurpose.REGISTER and owner is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="an account with this phone already exists - sign in instead")
    if purpose is OtpPurpose.VERIFY_PHONE and owner is not None and owner.id != requesting_user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="this phone number is already verified on another account")


def request_otp(
    db: Session,
    phone: str,
    purpose: OtpPurpose,
    client_ip: str,
    turnstile_token: str | None = None,
    requesting_user_id=None,
) -> tuple[int, str | None]:
    """Returns (expires_in_seconds, dev_code). `dev_code` is only populated by the
    console gateway so local/browser tests can complete the flow without SMS."""
    _verify_turnstile(turnstile_token, client_ip)
    enforce_rate_limit(f"otp:req:phone:{phone}", settings.OTP_REQUESTS_PER_PHONE_PER_HOUR, 3600)
    enforce_rate_limit(f"otp:req:ip:{client_ip}", settings.OTP_REQUESTS_PER_IP_PER_HOUR, 3600)
    _check_purpose_preconditions(db, phone, purpose, requesting_user_id)

    now = datetime.now(timezone.utc)
    # Only the newest code per (phone, purpose) is valid - retire earlier ones.
    db.query(OtpCode).filter(
        OtpCode.phone == phone, OtpCode.purpose == purpose.value, OtpCode.consumed_at.is_(None)
    ).update({OtpCode.consumed_at: now})

    code = f"{secrets.randbelow(10**6):06d}"
    expires_in = settings.OTP_EXPIRE_MINUTES * 60
    db.add(
        OtpCode(
            phone=phone,
            code_hash=_hash_code(phone, code),
            purpose=purpose.value,
            expires_at=now + timedelta(seconds=expires_in),
        )
    )
    db.commit()

    gateway = get_sms_gateway()
    gateway.send(
        phone,
        f"{sender_name()}: your verification code is {code}. "
        f"It expires in {settings.OTP_EXPIRE_MINUTES} minutes. Never share it.",
    )
    dev_code = code if gateway.name == "console" else None
    return expires_in, dev_code


def verify_otp(db: Session, phone: str, code: str, purpose: OtpPurpose) -> None:
    now = datetime.now(timezone.utc)
    row = (
        db.query(OtpCode)
        .filter(OtpCode.phone == phone, OtpCode.purpose == purpose.value, OtpCode.consumed_at.is_(None))
        .order_by(OtpCode.created_at.desc())
        .first()
    )
    if row is None or row.expires_at < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="code expired or not requested - request a new one")
    if row.attempt_count >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="too many attempts - request a new code")

    if not hmac.compare_digest(row.code_hash, _hash_code(phone, code)):
        row.attempt_count += 1
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid code")

    row.consumed_at = now
    db.commit()


def purge_stale_codes(db: Session) -> int:
    """Section 14.4 retention: consumed or expired rows older than a day are hard-deleted."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    deleted = (
        db.query(OtpCode)
        .filter((OtpCode.consumed_at.isnot(None)) | (OtpCode.expires_at < cutoff))
        .filter(OtpCode.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted
