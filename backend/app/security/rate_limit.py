"""Redis-backed rate limiting keyed by account + client IP (Epic 5, story 2).

Each `Limit` allows `limit` requests per `window` seconds for one account from one
IP. The request that goes over starts a cooldown: every request during it gets a 429
with `Retry-After`, without being counted. A cooldown of 0 means "wait for the window
to roll over" instead.

The account (a phone number, a user id) and the IP never appear in Redis keys or
logs: both are hashed together, so a key or log line cannot be traced back to a
person without already knowing who they are.

Every number is overridable per limit through the environment, e.g.
RATE_LIMIT_LOGIN_LIMIT=5, RATE_LIMIT_LOGIN_WINDOW_SECONDS=900,
RATE_LIMIT_LOGIN_COOLDOWN_SECONDS=900.
"""
import hashlib
import logging
import os
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from app.auth.dependencies import RequestContext, get_request_context
from app.database import redis_client

log = logging.getLogger("medvault.rate_limit")

TOO_MANY = "Too many attempts. Please try again later."


@dataclass(frozen=True)
class Limit:
    name: str
    limit: int
    window: int
    cooldown: int


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


def configured(name: str, limit: int, window: int, cooldown: int = 0) -> Limit:
    prefix = f"RATE_LIMIT_{name.upper()}"
    return Limit(
        name=name,
        limit=max(_env_int(f"{prefix}_LIMIT", limit), 1),
        window=max(_env_int(f"{prefix}_WINDOW_SECONDS", window), 1),
        cooldown=max(_env_int(f"{prefix}_COOLDOWN_SECONDS", cooldown), 0),
    )


LOGIN = configured("login", 5, 15 * 60, 15 * 60)
PASSWORD_RESET = configured("password_reset", 5, 15 * 60, 15 * 60)
SMS_CODE = configured("sms_code", 5, 15 * 60, 15 * 60)
INSTITUTION_CONNECT = configured("institution_connect", 10, 60 * 60)
DOCUMENT_UPLOAD = configured("document_upload", 30, 60 * 60)
# No export endpoint exists yet; apply with `dependencies=[Depends(limited(EXPORT))]`.
EXPORT = configured("export", 5, 60 * 60)


def client_ip(request: Request | None) -> str:
    client = getattr(request, "client", None)
    return client.host if client else "unknown"


def _subject(account: str, ip: str) -> str:
    return hashlib.sha256(f"{account}|{ip}".encode()).hexdigest()[:32]


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        TOO_MANY,
        headers={"Retry-After": str(max(retry_after, 1))},
    )


async def _ttl(key: str, fallback: int) -> int:
    """Seconds left on a key; heals one that lost its TTL (INCR and EXPIRE are two
    commands, so a crash between them would otherwise block the subject forever)."""
    ttl = await redis_client.ttl(key)
    if ttl == -2:
        return 0
    if ttl < 0:
        await redis_client.expire(key, fallback)
        return fallback
    return ttl


async def enforce(limit: Limit, *, account: str, ip: str) -> None:
    """Count one request for `account` from `ip`; raise 429 when over the limit."""
    subject = _subject(account, ip)
    cooldown_key = f"ratelimit:{limit.name}:cooldown:{subject}"
    counter_key = f"ratelimit:{limit.name}:count:{subject}"

    waiting = await _ttl(cooldown_key, limit.cooldown)
    if waiting > 0:
        raise _too_many(waiting)

    count = await redis_client.incr(counter_key)
    if count == 1:
        await redis_client.expire(counter_key, limit.window)
    if count <= limit.limit:
        return

    window_left = await _ttl(counter_key, limit.window)
    if limit.cooldown:
        # NX: of a concurrent burst, the first one over starts the clock.
        await redis_client.set(cooldown_key, "1", ex=limit.cooldown, nx=True)
        retry_after = await _ttl(cooldown_key, limit.cooldown)
    else:
        retry_after = window_left
    if count == limit.limit + 1:
        log.warning(
            "rate limit exceeded",
            extra={"limit": limit.name, "subject": subject, "retry_after": retry_after},
        )
    raise _too_many(retry_after)


def limited(limit: Limit):
    """Route dependency limiting the signed-in account from its IP."""

    async def dependency(
        request: Request, ctx: RequestContext = Depends(get_request_context)
    ) -> None:
        await enforce(limit, account=ctx.user_id, ip=client_ip(request))

    return dependency
