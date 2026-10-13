"""SMS one-time-code challenges (Epic 1, stories 1-4).

A challenge is an opaque id the client holds between "code sent" and "code entered".
It lives in Redis under `sms:challenge:{id}` for 5 minutes and records the purpose
(signup / login / reset), the user and a keyed hash of the code. The code itself is
never stored or logged by the app. A challenge with no user_id is a decoy used to keep
password-reset requests indistinguishable for unknown phones; it never verifies.

Every limit is enforced with a single atomic Redis command so concurrent requests
cannot beat it (a read-modify-write of the challenge JSON would let a burst of guesses
share one stale attempt count):

* wrong-code attempts   INCR  `sms:attempts:{id}`   (cap MAX_ATTEMPTS, then the challenge is burned)
* resends               INCR  `sms:resends:{id}`    (cap MAX_RESENDS)
* resend cooldown       SET NX EX `sms:cooldown:{id}`
* consuming the code    GETDEL on the challenge     (exactly one caller wins)
* replacing the hash    SET XX EX                   (never resurrects a consumed challenge)
"""
import hashlib
import hmac
import json
import re
import secrets

from fastapi import HTTPException, status

from app.auth.sms import get_sms_provider
from app.database import redis_client

CODE_TTL_SECONDS = 5 * 60
CODE_LENGTH = 6
MAX_ATTEMPTS = 5
MAX_RESENDS = 3
RESEND_COOLDOWN_SECONDS = 30
# Outlives the longest possible challenge (initial TTL plus MAX_RESENDS extensions).
_COUNTER_TTL_SECONDS = CODE_TTL_SECONDS * (MAX_RESENDS + 2)

INVALID_CODE = "Invalid or expired code."
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
_CODE_RE = re.compile(rf"^[0-9]{{{CODE_LENGTH}}}$")


def _key(challenge_id: str) -> str:
    return f"sms:challenge:{challenge_id}"


def _attempts_key(challenge_id: str) -> str:
    return f"sms:attempts:{challenge_id}"


def _resends_key(challenge_id: str) -> str:
    return f"sms:resends:{challenge_id}"


def _cooldown_key(challenge_id: str) -> str:
    return f"sms:cooldown:{challenge_id}"


def _digest(challenge_id: str, code: str) -> str:
    return hmac.new(
        challenge_id.encode(), code.encode("utf-8", "replace"), hashlib.sha256
    ).hexdigest()


def _new_code() -> str:
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"


def _message(code: str) -> str:
    return f"MedVault code: {code}. Valid for {CODE_TTL_SECONDS // 60} minutes. Do not share it."


def _check_id(challenge_id: str) -> None:
    """Reject malformed ids before they reach Redis (also keeps odd unicode out of keys)."""
    if not isinstance(challenge_id, str) or not _ID_RE.match(challenge_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_CODE)


async def _burn(challenge_id: str) -> None:
    await redis_client.delete(
        _key(challenge_id),
        _attempts_key(challenge_id),
        _resends_key(challenge_id),
        _cooldown_key(challenge_id),
    )


async def start(
    purpose: str, phone: str, user_id: str | None, *, send=None
) -> str:
    """Create a challenge and text the code. user_id=None creates a silent decoy.

    `send` lets a caller take over delivery (e.g. run it in the background); it is
    called as `send(provider, phone, message)` and awaited by the caller."""
    challenge_id = secrets.token_urlsafe(24)
    code = _new_code()
    data = {
        "purpose": purpose,
        "user_id": user_id,
        "phone": phone,
        "hash": _digest(challenge_id, code),
    }
    await redis_client.set(_key(challenge_id), json.dumps(data), ex=CODE_TTL_SECONDS)
    # The first send also starts the resend cooldown.
    await redis_client.set(
        _cooldown_key(challenge_id), "1", nx=True, ex=RESEND_COOLDOWN_SECONDS
    )
    if user_id:
        deliver = send or _deliver
        await deliver(get_sms_provider(), phone, _message(code))
    return challenge_id


async def _deliver(provider, phone: str, message: str) -> None:
    await provider.send(phone, message)


async def _load(challenge_id: str) -> dict:
    _check_id(challenge_id)
    raw = await redis_client.get(_key(challenge_id))
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_CODE)
    return json.loads(raw)


async def phone_of(challenge_id: str) -> str | None:
    """The phone a live challenge belongs to, without consuming or counting anything."""
    try:
        return (await _load(challenge_id))["phone"]
    except HTTPException:
        return None


async def resend(challenge_id: str) -> None:
    """New code for an open challenge: capped, with a cooldown, restarting the expiry."""
    data = await _load(challenge_id)

    # Cooldown gate first: only one of a burst of concurrent resends gets past it.
    if not await redis_client.set(
        _cooldown_key(challenge_id), "1", nx=True, ex=RESEND_COOLDOWN_SECONDS
    ):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Please wait before requesting another code.",
            headers={"Retry-After": str(RESEND_COOLDOWN_SECONDS)},
        )
    resends = await redis_client.incr(_resends_key(challenge_id))
    if resends == 1:
        await redis_client.expire(_resends_key(challenge_id), _COUNTER_TTL_SECONDS)
    if resends > MAX_RESENDS:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Resend limit reached. Start again."
        )

    code = _new_code()
    data["hash"] = _digest(challenge_id, code)
    # XX: if the challenge was consumed or expired meanwhile, do not bring it back.
    replaced = await redis_client.set(
        _key(challenge_id), json.dumps(data), xx=True, ex=CODE_TTL_SECONDS
    )
    if not replaced:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_CODE)
    if data["user_id"]:
        await get_sms_provider().send(data["phone"], _message(code))


async def verify(challenge_id: str, purpose: str, code: str) -> dict:
    """Consume the challenge on a correct code; count and cap wrong attempts.

    Attempts are counted for the challenge's whole life (a resend does not refill
    them), and every attempt is counted before the code is compared."""
    data = await _load(challenge_id)
    if data["purpose"] != purpose:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_CODE)

    attempts = await redis_client.incr(_attempts_key(challenge_id))
    if attempts == 1:
        await redis_client.expire(_attempts_key(challenge_id), _COUNTER_TTL_SECONDS)
    if attempts > MAX_ATTEMPTS:
        await _burn(challenge_id)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many wrong codes. Start again."
        )

    code = (code or "").strip()
    ok = (
        bool(data["user_id"])
        and bool(_CODE_RE.match(code))
        and hmac.compare_digest(data["hash"], _digest(challenge_id, code))
    )
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_CODE)

    # GETDEL is atomic, so of several concurrent correct submissions exactly one wins.
    consumed = await redis_client.getdel(_key(challenge_id))
    if not consumed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_CODE)
    await _burn(challenge_id)
    return data
