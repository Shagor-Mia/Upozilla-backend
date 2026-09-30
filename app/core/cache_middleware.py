import hashlib
import logging
import asyncio

import redis.asyncio as aioredis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import settings

logger = logging.getLogger(__name__)

PUBLIC_CACHE_PREFIXES = (
    "/api/v1/businesses",
    "/api/v1/exchange/listings",
    "/api/v1/faqs",
    "/api/v1/govt-offices",
    "/api/v1/hospitals",
    "/api/v1/locations",
    "/api/v1/marketplace/categories",
    "/api/v1/marketplace/products",
    "/api/v1/markets",
    "/api/v1/news",
    "/api/v1/places",
    "/api/v1/recommendations",
    "/api/v1/representatives",
    "/api/v1/schools",
    "/api/v1/services",
    "/api/v1/settings/public",
    "/api/v1/shops",
)
PUBLIC_CACHE_VERSION_KEY = "public-get:version"


class PublicGetCacheMiddleware(BaseHTTPMiddleware):
    """Small Redis cache for anonymous, public JSON GET endpoints.

    It intentionally bypasses any request with Authorization so per-user fields
    such as `is_favorited` never leak into a shared cache entry.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._redis: aioredis.Redis | None = None
        self._redis_loop: asyncio.AbstractEventLoop | None = None

    async def dispatch(self, request: Request, call_next):
        ttl = settings.PUBLIC_GET_CACHE_SECONDS
        if ttl <= 0:
            return await call_next(request)
        if self._write_request(request):
            response = await call_next(request)
            if 200 <= response.status_code < 300:
                await self._bump_version()
            return response
        if not self._cacheable_request(request):
            return await call_next(request)

        client = await self._client()
        version = await self._version(client)
        key = self._key(request, version)
        if client is not None:
            try:
                cached = await client.get(key)
                if cached is not None:
                    return Response(
                        content=cached,
                        media_type="application/json",
                        headers={
                            "Cache-Control": f"public, max-age={ttl}",
                            "X-Cache": "HIT",
                        },
                    )
            except Exception as exc:  # noqa: BLE001 - cache must not break reads
                logger.warning("public GET cache read failed: %s", exc)
                await self._reset_client()

        response = await call_next(request)
        if response.status_code != 200 or not response.headers.get("content-type", "").startswith("application/json"):
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        headers = dict(response.headers)
        headers["Cache-Control"] = f"public, max-age={ttl}"
        headers["X-Cache"] = "MISS"
        cached_response = Response(content=body, status_code=response.status_code, headers=headers, media_type="application/json")

        if client is not None:
            try:
                await client.setex(key, ttl, body)
            except Exception as exc:  # noqa: BLE001
                logger.warning("public GET cache write failed: %s", exc)
                await self._reset_client()
        return cached_response

    @staticmethod
    def _write_request(request: Request) -> bool:
        return request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/v1/")

    @staticmethod
    def _cacheable_request(request: Request) -> bool:
        if request.method != "GET" or request.headers.get("authorization"):
            return False
        return any(request.url.path == prefix or request.url.path.startswith(f"{prefix}/") for prefix in PUBLIC_CACHE_PREFIXES)

    @staticmethod
    def _key(request: Request, version: str) -> str:
        raw = "|".join(
            [
                version,
                request.url.path,
                request.url.query,
                request.headers.get("accept-language", ""),
                request.headers.get("x-tenant-slug", ""),
            ]
        )
        return f"public-get:{hashlib.sha256(raw.encode()).hexdigest()}"

    async def _client(self) -> aioredis.Redis | None:
        loop = asyncio.get_running_loop()
        if self._redis is not None and self._redis_loop is loop:
            return self._redis
        await self._reset_client()
        try:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=False, socket_connect_timeout=1)
            self._redis_loop = loop
            await self._redis.ping()
        except Exception as exc:  # noqa: BLE001
            logger.warning("public GET cache disabled, redis unavailable: %s", exc)
            self._redis = None
            self._redis_loop = None
        return self._redis

    async def _version(self, client: aioredis.Redis | None) -> str:
        if client is None:
            return "0"
        try:
            raw = await client.get(PUBLIC_CACHE_VERSION_KEY)
        except Exception as exc:  # noqa: BLE001
            logger.warning("public GET cache version read failed: %s", exc)
            await self._reset_client()
            return "0"
        if raw is None:
            return "0"
        return raw.decode() if isinstance(raw, bytes) else str(raw)

    async def _bump_version(self) -> None:
        client = await self._client()
        if client is None:
            return
        try:
            await client.incr(PUBLIC_CACHE_VERSION_KEY)
        except Exception as exc:  # noqa: BLE001
            logger.warning("public GET cache version bump failed: %s", exc)
            await self._reset_client()

    async def _reset_client(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:  # noqa: BLE001
                pass
        self._redis = None
        self._redis_loop = None
