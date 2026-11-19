"""Usage limits for the public LLM endpoints.

- Per-IP request rate (fixed one-minute windows)
- Per-session request rate (fixed one-hour windows)
- Per-session daily LLM tokens
- Global daily LLM token budget

Counters live in a small store: in-memory per process (default) or Redis
(``USAGE_STORE=redis``) so several instances share limits. If Redis fails the
store falls back to memory and logs a warning rather than failing requests.

Identifiers are never stored or logged raw: IPs and session IDs are reduced to
a keyed hash (HMAC with ``SECRET_KEY``).
"""
import hashlib
import hmac
import ipaddress
import re
import time
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

KEY_PREFIX = "thirdeye:usage:"
DAY_SECONDS = 24 * 60 * 60
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

RATE_LIMIT_MESSAGE = "Too many requests. Please wait a moment and try again."
SESSION_LIMIT_MESSAGE = "This conversation has reached its usage limit for now. Please try again later."
BUDGET_MESSAGE = "The assistant has reached its daily usage limit. Please try again tomorrow."


# --------------------------------------------------------------------- stores

class MemoryUsageStore:
    """Expiring integer counters held in this process."""

    def __init__(self):
        self._data: Dict[str, List[float]] = {}
        self._ops = 0

    def _prune(self, now: float) -> None:
        self._ops += 1
        if self._ops % 500 == 0:
            for key in [k for k, (_, exp) in self._data.items() if exp <= now]:
                self._data.pop(key, None)

    async def incr(self, key: str, amount: int, ttl: int) -> int:
        now = time.monotonic()
        self._prune(now)
        entry = self._data.get(key)
        if entry is None or entry[1] <= now:
            entry = [0, now + ttl]
            self._data[key] = entry
        entry[0] += amount
        return int(entry[0])

    async def get(self, key: str) -> int:
        entry = self._data.get(key)
        if entry is None or entry[1] <= time.monotonic():
            return 0
        return int(entry[0])

    def clear(self) -> None:
        self._data.clear()


class RedisUsageStore:
    """Counters in Redis (shared across processes and instances)."""

    def __init__(self, client):
        self._client = client

    async def incr(self, key: str, amount: int, ttl: int) -> int:
        value = int(await self._client.incrby(key, amount))
        if value == amount:  # first write in this window
            await self._client.expire(key, ttl)
        return value

    async def get(self, key: str) -> int:
        value = await self._client.get(key)
        return int(value or 0)


class ResilientUsageStore:
    """Uses the primary store, falling back to memory if it raises."""

    def __init__(self, primary, fallback: MemoryUsageStore):
        self.primary = primary
        self.fallback = fallback
        self._last_warning = 0.0

    def _warn(self, error: Exception) -> None:
        now = time.monotonic()
        if now - self._last_warning > 60:
            self._last_warning = now
            logger.warning(f"Usage store unavailable ({type(error).__name__}); using in-memory limits")

    async def incr(self, key: str, amount: int, ttl: int) -> int:
        try:
            return await self.primary.incr(key, amount, ttl)
        except Exception as error:  # noqa: BLE001 - degrade, never fail the request
            self._warn(error)
            return await self.fallback.incr(key, amount, ttl)

    async def get(self, key: str) -> int:
        try:
            return await self.primary.get(key)
        except Exception as error:  # noqa: BLE001
            self._warn(error)
            return await self.fallback.get(key)

    def clear(self) -> None:
        self.fallback.clear()


_store = None


def get_usage_store():
    global _store
    if _store is None:
        memory = MemoryUsageStore()
        if settings.USAGE_STORE == "redis":
            import redis.asyncio as redis_asyncio

            _store = ResilientUsageStore(RedisUsageStore(redis_asyncio.from_url(settings.REDIS_URL)), memory)
        else:
            _store = memory
    return _store


def reset_usage_store() -> None:
    """Drop all counters (tests and local development)."""
    global _store
    if _store is not None and hasattr(_store, "clear"):
        _store.clear()
    _store = None


# ------------------------------------------------------------ request context

@dataclass(frozen=True)
class UsageContext:
    request_id: str
    session_key: str  # keyed hash
    ip_key: str  # keyed hash


current_usage: ContextVar[Optional[UsageContext]] = ContextVar("current_usage", default=None)


def anonymize(value: str) -> str:
    secret = (settings.SECRET_KEY or "").encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()[:16]


def client_ip(request: Request) -> str:
    """Client IP, trusting X-Forwarded-For only for TRUSTED_PROXY_HOPS proxies.

    Each trusted proxy appends the address it received the request from, so the
    client is the entry ``hops`` positions from the right. Entries further left
    are client-controlled and ignored.
    """
    peer = request.client.host if request.client else "unknown"
    hops = settings.TRUSTED_PROXY_HOPS
    if hops <= 0:
        return peer
    forwarded = request.headers.get("x-forwarded-for", "")
    parts = [part.strip() for part in forwarded.split(",") if part.strip()]
    if len(parts) < hops:
        return peer
    candidate = parts[-hops]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return peer


def _window(seconds: int) -> tuple[int, int]:
    now = int(time.time())
    return now // seconds, seconds - (now % seconds)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _seconds_to_utc_midnight() -> int:
    now = int(time.time())
    return DAY_SECONDS - (now % DAY_SECONDS)


def session_token_key(session_key: str) -> str:
    return f"{KEY_PREFIX}session_tokens:{session_key}:{_today()}"


def global_token_key() -> str:
    return f"{KEY_PREFIX}llm_tokens:{_today()}"


def _too_many(message: str, retry_after: int, reason: str, ctx: UsageContext) -> HTTPException:
    logger.warning(
        f"Usage limit reached: {reason}",
        extra={"request_id": ctx.request_id, "event": "usage_limit",
               "usage": {"reason": reason, "session": ctx.session_key, "ip": ctx.ip_key}},
    )
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=message,
        headers={"Retry-After": str(max(1, retry_after))},
    )


async def enforce_chat_limits(
    request: Request,
    request_id: str,
    session_id: Optional[str] = None,
) -> UsageContext:
    """Apply all usage limits and bind the usage context for token accounting.

    ``session_id`` is client-supplied (``X-Session-ID`` or a graph thread ID);
    invalid or missing IDs fall back to the client IP.
    """
    ip = client_ip(request)
    if session_id and SESSION_ID_PATTERN.match(session_id):
        session_key = anonymize(f"session:{session_id}")
    else:
        session_key = anonymize(f"ip:{ip}")
    ctx = UsageContext(request_id=request_id, session_key=session_key, ip_key=anonymize(f"ip:{ip}"))
    current_usage.set(ctx)

    if not settings.RATE_LIMIT_ENABLED:
        return ctx
    store = get_usage_store()

    if settings.RATE_LIMIT_IP_PER_MINUTE:
        window, remaining = _window(60)
        count = await store.incr(f"{KEY_PREFIX}ip:{ctx.ip_key}:{window}", 1, 60)
        if count > settings.RATE_LIMIT_IP_PER_MINUTE:
            raise _too_many(RATE_LIMIT_MESSAGE, remaining, "ip_rate", ctx)

    if settings.RATE_LIMIT_SESSION_PER_HOUR:
        window, remaining = _window(3600)
        count = await store.incr(f"{KEY_PREFIX}session:{session_key}:{window}", 1, 3600)
        if count > settings.RATE_LIMIT_SESSION_PER_HOUR:
            raise _too_many(SESSION_LIMIT_MESSAGE, remaining, "session_rate", ctx)

    if settings.SESSION_DAILY_TOKEN_LIMIT:
        if await store.get(session_token_key(session_key)) >= settings.SESSION_DAILY_TOKEN_LIMIT:
            raise _too_many(SESSION_LIMIT_MESSAGE, _seconds_to_utc_midnight(), "session_tokens", ctx)

    if settings.LLM_DAILY_TOKEN_BUDGET:
        if await store.get(global_token_key()) >= settings.LLM_DAILY_TOKEN_BUDGET:
            raise _too_many(BUDGET_MESSAGE, _seconds_to_utc_midnight(), "daily_budget", ctx)

    return ctx


async def add_token_usage(tokens: int) -> None:
    """Count LLM tokens toward the session and global daily totals."""
    if tokens <= 0:
        return
    store = get_usage_store()
    await store.incr(global_token_key(), tokens, 2 * DAY_SECONDS)
    ctx = current_usage.get()
    if ctx is not None:
        await store.incr(session_token_key(ctx.session_key), tokens, 2 * DAY_SECONDS)
