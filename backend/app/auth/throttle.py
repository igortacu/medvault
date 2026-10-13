"""Redis-backed counters for sign-in lockout and endpoint rate limiting (Epic 1/5)."""
from fastapi import HTTPException, status

from app.database import redis_client

LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 15 * 60


async def _remaining(key: str, window_seconds: int) -> int:
    """Seconds left on a counter; heals a counter that lost its TTL (INCR and EXPIRE are
    two commands, so a crash between them would otherwise lock the key forever)."""
    ttl = await redis_client.ttl(key)
    if ttl < 0:
        await redis_client.expire(key, window_seconds)
        return window_seconds
    return ttl


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Too many attempts. Please try again later.",
        headers={"Retry-After": str(max(retry_after, 1))},
    )


async def hit(key: str, limit: int, window_seconds: int) -> None:
    """Count one event under `key`; raise 429 once it exceeds `limit` in the window."""
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, window_seconds)
    if count > limit:
        raise _too_many(await _remaining(key, window_seconds))


async def count_login_attempt(phone: str) -> None:
    """Count a password attempt *before* checking it, so a burst of concurrent guesses
    is capped instead of all passing a read-then-write check. Cleared on success."""
    await hit(f"auth:fail:{phone}", LOGIN_MAX_FAILURES, LOGIN_WINDOW_SECONDS)


async def ensure_not_locked(phone: str) -> None:
    raw = await redis_client.get(f"auth:fail:{phone}")
    if raw and int(raw) > LOGIN_MAX_FAILURES:
        raise _too_many(await _remaining(f"auth:fail:{phone}", LOGIN_WINDOW_SECONDS))


async def register_failure(phone: str) -> None:
    key = f"auth:fail:{phone}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, LOGIN_WINDOW_SECONDS)


async def clear_failures(phone: str) -> None:
    await redis_client.delete(f"auth:fail:{phone}")
