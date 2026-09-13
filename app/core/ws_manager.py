"""WebSocket connection registry with Redis pub/sub fan-out (Section 19.2).

Each API instance keeps its *own* sockets in memory, but `send_to_user` publishes
to a Redis channel that every instance subscribes to, so a message for a user
connected to instance B still arrives when it was produced on instance A.

If Redis is unreachable the manager degrades to local-only delivery (single
instance behaviour) instead of failing the request - chat still works in a
one-container dev stack with Redis down, it just would not fan out.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from fastapi import WebSocket

from app.core.config import settings

logger = logging.getLogger(__name__)

CHANNEL = "ws:fanout"
# How long to wait before retrying the Redis connection after a failed start
# (e.g. the API booted before the redis container was accepting connections).
RECONNECT_INTERVAL_SECONDS = 30.0


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._redis: aioredis.Redis | None = None
        self._listener: asyncio.Task[None] | None = None
        self._last_start_attempt = 0.0

    # ---- lifecycle -------------------------------------------------------

    async def start(self) -> None:
        """Called from the FastAPI lifespan and retried lazily; safe to call twice."""
        if self._listener is not None and not self._listener.done():
            return
        self._last_start_attempt = time.monotonic()
        try:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
            await self._redis.ping()
        except Exception as exc:  # noqa: BLE001 - degrade, don't crash the API
            logger.warning("ws fan-out disabled, redis unavailable: %s", exc)
            self._redis = None
            return
        self._listener = asyncio.create_task(self._listen(), name="ws-fanout-listener")
        self._listener.add_done_callback(self._on_listener_done)
        logger.info("ws fan-out listener subscribed to %s", CHANNEL)

    def _on_listener_done(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.warning("ws fan-out listener died, local-only until reconnect: %s", exc)
            self._redis = None

    async def _ensure_started(self) -> None:
        """Retries the Redis connection at most once per RECONNECT_INTERVAL_SECONDS."""
        if self._redis is not None:
            return
        if time.monotonic() - self._last_start_attempt < RECONNECT_INTERVAL_SECONDS:
            return
        await self.start()

    async def stop(self) -> None:
        if self._listener is not None:
            self._listener.cancel()
            try:
                await self._listener
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._listener = None
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def _listen(self) -> None:
        assert self._redis is not None
        pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        await pubsub.subscribe(CHANNEL)
        try:
            async for raw in pubsub.listen():
                if raw is None or raw.get("type") != "message":
                    continue
                try:
                    envelope = json.loads(raw["data"])
                    await self._deliver_local(envelope["user_id"], envelope["payload"])
                except Exception as exc:  # noqa: BLE001 - one bad frame must not stop the listener
                    logger.warning("ws fan-out: dropped frame: %s", exc)
        finally:
            await pubsub.unsubscribe(CHANNEL)
            await pubsub.aclose()

    # ---- connections ------------------------------------------------------

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await self._ensure_started()
        await websocket.accept()
        async with self._lock:
            self._connections[user_id].add(websocket)

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[user_id].discard(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]

    def local_connection_count(self, user_id: str) -> int:
        return len(self._connections.get(user_id, ()))

    # ---- delivery ---------------------------------------------------------

    async def send_to_user(self, user_id: str, payload: dict[str, Any]) -> None:
        """Publishes to every instance; falls back to local delivery without Redis."""
        await self._ensure_started()
        if self._redis is not None:
            try:
                await self._redis.publish(CHANNEL, json.dumps({"user_id": user_id, "payload": payload}))
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("ws fan-out publish failed, delivering locally: %s", exc)
        await self._deliver_local(user_id, payload)

    async def _deliver_local(self, user_id: str, payload: dict[str, Any]) -> None:
        async with self._lock:
            sockets = list(self._connections.get(user_id, ()))
        for socket in sockets:
            try:
                await socket.send_json(payload)
            except Exception:  # noqa: BLE001 - a dead socket must not break delivery to others
                await self.disconnect(user_id, socket)

    @staticmethod
    def seconds_until(expires_at: datetime) -> float:
        return max(0.0, (expires_at - datetime.now(timezone.utc)).total_seconds())


manager = ConnectionManager()
