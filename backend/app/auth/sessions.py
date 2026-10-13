"""Redis session store (Epic 1, stories 2, 5, 6).

`session:{sid}` holds the session payload with a sliding 15-minute idle TTL that
get_request_context refreshes on every authenticated request. `user_sessions:{uid}`
is the set of a user's live sids so a password reset can sign every device out.
"""
import json
import secrets
import time

from app.database import redis_client

SESSION_IDLE_TTL_SECONDS = 15 * 60
# Hard cap regardless of activity; enforced in get_request_context.
SESSION_MAX_AGE_SECONDS = 8 * 60 * 60
# Upper bound on the per-user index; refreshed alongside the sessions it lists.
_INDEX_TTL_SECONDS = 24 * 60 * 60


def _skey(sid: str) -> str:
    return f"session:{sid}"


def _ukey(user_id: str) -> str:
    return f"user_sessions:{user_id}"


async def create(user_id: str) -> str:
    sid = secrets.token_urlsafe(32)
    await redis_client.set(
        _skey(sid), json.dumps({"user_id": user_id, "created_at": int(time.time())}), ex=SESSION_IDLE_TTL_SECONDS
    )
    await redis_client.sadd(_ukey(user_id), sid)
    await redis_client.expire(_ukey(user_id), _INDEX_TTL_SECONDS)
    return sid


async def touch(sid: str, user_id: str) -> None:
    """Slide the idle TTL, and keep the per-user index alive as long as the session is,
    so a password reset can still find and revoke long-lived sessions."""
    await redis_client.expire(_skey(sid), SESSION_IDLE_TTL_SECONDS)
    # SADD is idempotent; it also repairs the index for a session it never listed.
    await redis_client.sadd(_ukey(user_id), sid)
    await redis_client.expire(_ukey(user_id), _INDEX_TTL_SECONDS)


async def destroy(sid: str, user_id: str | None) -> None:
    await redis_client.delete(_skey(sid))
    if user_id:
        await redis_client.srem(_ukey(user_id), sid)


async def destroy_all(user_id: str) -> None:
    sids = await redis_client.smembers(_ukey(user_id))
    if sids:
        await redis_client.delete(*[_skey(s) for s in sids])
    await redis_client.delete(_ukey(user_id))
