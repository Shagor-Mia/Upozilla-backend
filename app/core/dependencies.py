import uuid

from fastapi import Depends, Header, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.i18n import resolve_locale
from app.core.rbac import Permission, normalize_role, permissions_for
from app.core.security import decode_token
from app.db.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser:
    def __init__(
        self,
        user_id: str,
        tenant_id: str | None,
        role: str | None,
        roles: list[str] | None = None,
        phone_verified: bool = False,
        expires_at: int | None = None,
    ):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role
        self.roles = roles or ([role] if role else [])
        self.phone_verified = phone_verified
        self.expires_at = expires_at  # unix seconds, from the JWT `exp` claim

    @property
    def uuid(self) -> uuid.UUID:
        return uuid.UUID(self.user_id)

    @property
    def permissions(self) -> set[Permission]:
        return permissions_for(self.roles)

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions


def _payload_to_user(payload: dict) -> CurrentUser:
    return CurrentUser(
        user_id=payload["sub"],
        tenant_id=payload.get("tenant_id"),
        role=payload.get("role"),
        roles=payload.get("roles"),
        phone_verified=bool(payload.get("phone_verified", False)),
        expires_at=payload.get("exp"),
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    return _payload_to_user(payload)


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser | None:
    """For public endpoints that personalise when a token is present (e.g. `is_favorited`)."""
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        return None
    return _payload_to_user(payload)


def require_roles(*allowed_roles: str):
    allowed = {normalize_role(r) for r in allowed_roles}

    def dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any(normalize_role(r) in allowed for r in current_user.roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
        return current_user

    return dependency


def require_permission(*required: Permission):
    """Grants access when the caller holds ANY of the listed permissions (Section 12)."""

    def dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any(current_user.has_permission(p) for p in required):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
        return current_user

    return dependency


def require_phone_verified(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """Section 5.8 mandatory rule: marketplace/exchange writes need
    `users.phone_verified_at IS NOT NULL`. Checked against the DB, not the JWT
    claim, so a stale token can't bypass it."""
    user = db.query(User).filter(User.id == current_user.uuid).first()
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="account unavailable")
    if user.phone_verified_at is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="phone verification required")
    current_user.phone_verified = True
    return current_user


def get_locale(lang: str | None = Query(None), accept_language: str | None = Header(None)) -> str:
    """`?lang=` wins over `Accept-Language` (e.g. `en-US,en;q=0.9`); resolves
    to `bn` when neither is present or recognised (Section 5: content locale)."""
    if lang:
        return resolve_locale(lang)
    if accept_language:
        return resolve_locale(accept_language.split(",")[0].split("-")[0])
    return resolve_locale(None)


def get_client_ip(request: Request) -> str:
    """A reverse proxy (Render's edge in production) *appends* the real client
    IP to any `X-Forwarded-For` it received rather than replacing it, so the
    last entry is the one our own trusted proxy added - the first entry can
    be anything the client sent and must never be trusted for rate limiting."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"
