"""Redis-backed fixed-window rate limiting (Section 14.1 / 19.3).

Per-account limits come first, per-IP second: Bangladeshi carriers use
carrier-grade NAT and diaspora users share campus/VPN IPs, so an IP-only limit
would block legitimate users.
"""

import logging

import redis
from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings
from app.core.dependencies import CurrentUser, get_client_ip, get_current_user, get_optional_user
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)


def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Raises 429 once more than `limit` hits land inside the current window."""
    try:
        client = get_redis()
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        count, _ = pipe.execute()
    except redis.RedisError as exc:
        # Fail closed in production (limits are a fraud control), open locally so a
        # stopped Redis container doesn't block development.
        if settings.is_production:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="rate limiter unavailable") from exc
        logger.warning("rate limiter unavailable, allowing request: %s", exc)
        return

    if int(count) > limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="too many requests, try again later")


def rate_limit_by_user(prefix: str, limit: int, window_seconds: int):
    def dependency(current_user: CurrentUser = Depends(get_current_user)) -> None:
        enforce_rate_limit(f"rl:{prefix}:user:{current_user.user_id}", limit, window_seconds)

    return dependency


def rate_limit_by_ip(prefix: str, limit: int, window_seconds: int):
    def dependency(request: Request) -> None:
        enforce_rate_limit(f"rl:{prefix}:ip:{get_client_ip(request)}", limit, window_seconds)

    return dependency


def rate_limit_by_user_or_ip(prefix: str, user_limit: int, ip_limit: int, window_seconds: int):
    """For endpoints that work both logged-in and anonymous (e.g. the public
    AI chat widget): a logged-in caller is limited per account, an anonymous
    one per IP - same per-account-first-per-IP-second posture as Section
    19.3, just applied to a single caller instead of two separate routes."""

    def dependency(request: Request, viewer: CurrentUser | None = Depends(get_optional_user)) -> None:
        if viewer is not None:
            enforce_rate_limit(f"rl:{prefix}:user:{viewer.user_id}", user_limit, window_seconds)
        else:
            enforce_rate_limit(f"rl:{prefix}:ip:{get_client_ip(request)}", ip_limit, window_seconds)

    return dependency
