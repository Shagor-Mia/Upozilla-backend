import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core import runtime_settings
from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.core.rbac import Role
from app.core.redis_client import get_redis
from app.core.security import create_access_token, hash_password, verify_password
from app.core.tenant import resolve_tenant_id
from app.db.models import RefreshToken, RoleRow, User, UserRole
from app.modules.auth.schemas import LoginRequest, RegisterRequest, UserResponse

FACEBOOK_GRAPH_URL = "https://graph.facebook.com/v19.0"
OAUTH_PROVIDER_FACEBOOK = "facebook"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
OAUTH_PROVIDER_GOOGLE = "google"


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- user lookup / serialisation -------------------------------------------------


def get_user_by_id(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return user


def get_role_names(db: Session, user: User) -> list[str]:
    """Primary role first, then any scoped `user_roles` assignments (Section 5.12)."""
    names = [user.role]
    extra = (
        db.query(RoleRow.name)
        .join(UserRole, UserRole.role_id == RoleRow.id)
        .filter(UserRole.user_id == user.id)
        .all()
    )
    for (name,) in extra:
        if name not in names:
            names.append(name)
    return names


def to_user_response(db: Session, user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        roles=get_role_names(db, user),
        status=user.status,
        phone_verified=user.phone_verified_at is not None,
        oauth_provider=user.oauth_provider,
        created_at=user.created_at,
    )


# --- password auth ---------------------------------------------------------------


def register_user(db: Session, payload: RegisterRequest) -> User:
    if not payload.email and not payload.phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email or phone is required")

    existing = db.query(User).filter(
        or_(
            func.lower(User.email) == payload.email.lower() if payload.email else False,
            User.phone == payload.phone if payload.phone else False,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="account already exists")

    user = User(
        tenant_id=resolve_tenant_id(db),
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=Role.USER.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, payload: LoginRequest) -> User:
    # `identifier` is already normalized by LoginRequest (lowercased email or
    # E.164 phone), but comparing case-insensitively too protects any account
    # whose email was stored with different casing before that validator existed.
    user = db.query(User).filter(
        or_(func.lower(User.email) == payload.identifier.lower(), User.phone == payload.identifier)
    ).first()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    _ensure_active(user)
    return user


def _ensure_active(user: User) -> None:
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account is suspended")


# --- token lifecycle -------------------------------------------------------------


def issue_token_pair(db: Session, user: User) -> tuple[str, str]:
    access_token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id) if user.tenant_id else None,
        role=user.role,
        roles=get_role_names(db, user),
        phone_verified=user.phone_verified_at is not None,
    )
    raw_refresh_token = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_hash_token(raw_refresh_token),
            expires_at=_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()
    return access_token, raw_refresh_token


def rotate_refresh_token(db: Session, raw_refresh_token: str) -> tuple[str, str]:
    token_hash = _hash_token(raw_refresh_token)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    now = _now()

    if not row or row.expires_at < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired refresh token")
    if row.revoked_at is not None:
        # Section 14.2 reuse detection: a revoked token being replayed means the
        # family is compromised - revoke every live token for that user.
        revoke_all_refresh_tokens(db, row.user_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh token reuse detected - please sign in again")

    row.revoked_at = now
    user = db.query(User).filter(User.id == row.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token")
    _ensure_active(user)

    db.commit()
    return issue_token_pair(db, user)


def revoke_refresh_token(db: Session, raw_refresh_token: str) -> None:
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == _hash_token(raw_refresh_token)).first()
    if row and row.revoked_at is None:
        row.revoked_at = _now()
        db.commit()


def revoke_all_refresh_tokens(db: Session, user_id: uuid.UUID) -> int:
    count = (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .update({RefreshToken.revoked_at: _now()})
    )
    db.commit()
    return count


# --- phone OTP identities --------------------------------------------------------


def login_with_verified_phone(db: Session, phone: str) -> User:
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no account uses this phone number")
    _ensure_active(user)
    if user.phone_verified_at is None:
        # Completing an OTP login proves possession of the number.
        user.phone_verified_at = _now()
        db.commit()
    return user


def register_with_verified_phone(db: Session, phone: str, full_name: str) -> User:
    if db.query(User).filter(User.phone == phone).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="an account with this phone already exists")
    user = User(
        tenant_id=resolve_tenant_id(db),
        full_name=full_name,
        phone=phone,
        phone_verified_at=_now(),
        role=Role.USER.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def attach_verified_phone(db: Session, user_id: uuid.UUID, phone: str) -> User:
    owner = db.query(User).filter(User.phone == phone).first()
    if owner and owner.id != user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="this phone number belongs to another account")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    user.phone = phone
    user.phone_verified_at = _now()
    db.commit()
    db.refresh(user)
    return user


# --- Facebook Login (Section 16.2) ----------------------------------------------


def _facebook_graph_get(path: str, params: dict[str, str]) -> dict:
    try:
        response = httpx.get(f"{FACEBOOK_GRAPH_URL}{path}", params=params, timeout=10)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="could not reach Facebook") from exc
    if not response.is_success:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="facebook token rejected")
    return response.json()


def login_with_facebook(db: Session, access_token: str) -> User:
    """Client token is verified server-side against Graph API before any account
    is linked - a client-supplied Facebook user id is never trusted on its own."""
    app_id = runtime_settings.get("facebook_app_id")
    app_secret = runtime_settings.get("facebook_app_secret")
    if not app_id or not app_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="facebook login is not configured")

    debug = _facebook_graph_get(
        "/debug_token",
        {"input_token": access_token, "access_token": f"{app_id}|{app_secret}"},
    ).get("data", {})
    if not debug.get("is_valid") or debug.get("app_id") != app_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="facebook token is not valid for this app")

    profile = _facebook_graph_get("/me", {"fields": "id,name,email", "access_token": access_token})
    facebook_id = str(profile.get("id") or debug.get("user_id") or "")
    if not facebook_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="facebook profile unavailable")

    user = (
        db.query(User)
        .filter(User.oauth_provider == OAUTH_PROVIDER_FACEBOOK, User.oauth_id == facebook_id)
        .first()
    )
    email = profile.get("email")
    if user is None and email:
        user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
        if user is not None and user.oauth_provider is None:
            user.oauth_provider = OAUTH_PROVIDER_FACEBOOK
            user.oauth_id = facebook_id
    if user is None:
        user = User(
            tenant_id=resolve_tenant_id(db),
            full_name=profile.get("name") or "Facebook user",
            email=email,
            oauth_provider=OAUTH_PROVIDER_FACEBOOK,
            oauth_id=facebook_id,
            role=Role.USER.value,
        )
        db.add(user)
    _ensure_active(user)
    db.commit()
    db.refresh(user)
    return user


# --- Google Login (Section 16.2 pattern, added post-plan) ----------------------


def login_with_google(db: Session, id_token: str) -> User:
    """The client-side Google Identity Services button hands us a signed ID
    token; we verify it against Google's own tokeninfo endpoint (audience +
    signature) rather than trusting the `sub`/email claims a client could
    otherwise fabricate - same posture as `login_with_facebook` above."""
    client_id = runtime_settings.get("google_client_id")
    if not client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="google login is not configured")

    try:
        response = httpx.get(GOOGLE_TOKENINFO_URL, params={"id_token": id_token}, timeout=10)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="could not reach Google") from exc
    if not response.is_success:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="google token rejected")

    claims = response.json()
    if claims.get("aud") != client_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="google token is not valid for this app")
    if str(claims.get("email_verified", "")).lower() != "true":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="google email is not verified")

    google_id = str(claims.get("sub") or "")
    if not google_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="google profile unavailable")

    user = (
        db.query(User)
        .filter(User.oauth_provider == OAUTH_PROVIDER_GOOGLE, User.oauth_id == google_id)
        .first()
    )
    email = claims.get("email")
    if user is None and email:
        user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
        if user is not None and user.oauth_provider is None:
            user.oauth_provider = OAUTH_PROVIDER_GOOGLE
            user.oauth_id = google_id
    if user is None:
        user = User(
            tenant_id=resolve_tenant_id(db),
            full_name=claims.get("name") or "Google user",
            email=email,
            oauth_provider=OAUTH_PROVIDER_GOOGLE,
            oauth_id=google_id,
            role=Role.USER.value,
        )
        db.add(user)
    _ensure_active(user)
    db.commit()
    db.refresh(user)
    return user


# --- WebSocket tickets (Section 10 / 14.3) --------------------------------------


def create_ws_ticket(current_user: CurrentUser) -> tuple[str, int]:
    """The browser never sees the JWT (httpOnly cookie), so it authenticates the
    socket with a single-use ticket that inherits the access token's expiry."""
    ticket = secrets.token_urlsafe(32)
    payload = json.dumps({"user_id": current_user.user_id, "exp": current_user.expires_at})
    get_redis().setex(f"ws:ticket:{ticket}", settings.WS_TICKET_TTL_SECONDS, payload)
    return ticket, settings.WS_TICKET_TTL_SECONDS


def consume_ws_ticket(ticket: str) -> tuple[str, datetime] | None:
    raw = get_redis().getdel(f"ws:ticket:{ticket}")
    if not raw:
        return None
    data = json.loads(raw)
    expires_at = datetime.fromtimestamp(data["exp"], tz=timezone.utc)
    if expires_at <= _now():
        return None
    return data["user_id"], expires_at
