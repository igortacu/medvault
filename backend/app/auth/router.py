"""Authentication (Epic 1): sign-up, two-step sign-in, password reset, logout.

Every sign-in and sign-up ends with an SMS code (D15): credentials alone never
produce a session. Flows hand the client an opaque `challenge_id` between "code
sent" and "code entered" (see challenges.py). Pre-auth DB access goes through the
SECURITY DEFINER functions `auth_*`, since no app.current_user_id exists yet.
Responses never reveal whether a phone is registered.
"""
import asyncio
import json
import logging
import os
import secrets
from datetime import date, datetime
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.audit.logger import write_audit_log
from app.auth import challenges, sessions, throttle, validation
from app.auth.dependencies import RequestContext, get_request_context
from app.database import get_session_factory, redis_client
from app.models.user import User
from app.security import rate_limit

router = APIRouter(tags=["auth"])
log = logging.getLogger("medvault.auth")

SESSION_COOKIE = "session_id"
COOKIE_MAX_AGE_SECONDS = 8 * 60 * 60  # browser cap; the Redis idle TTL is authoritative
# Secure by default; plain-http local dev (APP_ENV=development) turns it off, and
# SESSION_COOKIE_SECURE overrides either way.
COOKIE_SECURE = os.getenv(
    "SESSION_COOKIE_SECURE",
    "false" if os.getenv("APP_ENV", "production").lower() == "development" else "true",
).lower() == "true"
INVALID_CREDENTIALS = "Invalid phone or password."
RESET_TOKEN_TTL_SECONDS = 10 * 60

_hasher = PasswordHasher()
# Verified against when the phone is unknown, so both paths cost one argon2 check.
_DUMMY_HASH = _hasher.hash(secrets.token_hex(16))


# --- Schemas ------------------------------------------------------------------
# Length caps keep oversized input away from argon2 and out of Redis keys.
class SignupRequest(BaseModel):
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    phone: str = Field(max_length=32)
    date_of_birth: date
    password: str = Field(max_length=validation.PASSWORD_MAX * 2)


class LoginRequest(BaseModel):
    phone: str = Field(max_length=32)
    password: str = Field(max_length=validation.PASSWORD_MAX * 2)


class CodeRequest(BaseModel):
    challenge_id: str = Field(max_length=64)
    code: str = Field(max_length=16)


class ChallengeRequest(BaseModel):
    challenge_id: str = Field(max_length=64)


class ChallengeResponse(BaseModel):
    challenge_id: str
    expires_in: int = challenges.CODE_TTL_SECONDS


class PasswordResetRequest(BaseModel):
    phone: str = Field(max_length=32)


class ResetTokenResponse(BaseModel):
    reset_token: str


class PasswordResetConfirm(BaseModel):
    reset_token: str = Field(max_length=64)
    new_password: str = Field(max_length=validation.PASSWORD_MAX * 2)


class CurrentUser(BaseModel):
    id: UUID
    phone: str
    status: str
    created_at: datetime


# --- Helpers ------------------------------------------------------------------
def _verify(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def _limit_code_entry(request: Request, challenge_id: str, phone: str | None = None) -> None:
    """SMS-code limit (verify and resend), keyed by the challenge's phone + IP.
    A challenge that no longer exists is keyed by its id, so guessing still counts."""
    account = phone or await challenges.phone_of(challenge_id) or challenge_id
    await rate_limit.enforce(
        rate_limit.SMS_CODE, account=account, ip=_client_ip(request)
    )


async def _audit(
    action: str,
    outcome: str,
    user_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Audit an auth event that has no authenticated request context.
    Never put phone numbers, codes or passwords in `metadata`."""
    async with get_session_factory()() as db:
        await write_audit_log(
            db,
            actor_user_id=user_id,
            subject_patient_id=user_id,
            action=action,
            resource_type="user",
            resource_id=user_id,
            outcome=outcome,
            metadata=metadata,
        )
        await db.commit()


async def _lookup(phone: str):
    async with get_session_factory()() as db:
        return (
            await db.execute(
                text("SELECT * FROM medvault.auth_lookup_for_signin(:phone)"),
                {"phone": phone},
            )
        ).first()


async def _open_session(response: Response, user_id: str) -> None:
    sid = await sessions.create(user_id)
    response.set_cookie(
        SESSION_COOKIE,
        sid,
        max_age=COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )


# Strong references so fire-and-forget SMS sends are not garbage-collected mid-flight.
_background: set[asyncio.Task] = set()


async def _send_in_background(provider, phone: str, message: str) -> None:
    """Deliver without making the response wait on the provider. Used for password
    reset, where a registered phone (a real send) and an unknown one (nothing to send)
    must take the same time and fail the same way."""

    async def run() -> None:
        try:
            await provider.send(phone, message)
        except Exception:
            log.exception("SMS delivery failed")

    task = asyncio.create_task(run())
    _background.add(task)
    task.add_done_callback(_background.discard)


def _field_errors(errors: dict[str, str]) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"errors": errors}
    )


# --- Sign up ------------------------------------------------------------------
@router.post(
    "/auth/signup", response_model=ChallengeResponse, status_code=status.HTTP_201_CREATED
)
async def signup(body: SignupRequest, request: Request) -> ChallengeResponse:
    await throttle.hit(f"auth:signup:{_client_ip(request)}", limit=10, window_seconds=3600)

    clean, errors = validation.collect_errors(
        {
            "first_name": (validation.validate_name, body.first_name),
            "last_name": (validation.validate_name, body.last_name),
            "phone": (validation.normalize_phone, body.phone),
            "date_of_birth": (validation.validate_dob, body.date_of_birth),
            "password": (validation.validate_password, body.password),
        }
    )
    if errors:
        raise _field_errors(errors)

    password_hash = await run_in_threadpool(_hasher.hash, clean["password"])
    async with get_session_factory()() as db:
        user_id = (
            await db.execute(
                text(
                    "SELECT medvault.auth_register_user("
                    ":first, :last, :phone, :dob, :hash)"
                ),
                {
                    "first": clean["first_name"],
                    "last": clean["last_name"],
                    "phone": clean["phone"],
                    "dob": clean["date_of_birth"],
                    "hash": password_hash,
                },
            )
        ).scalar_one()
        await db.commit()

    if user_id is None:
        # The number belongs to an active account. Answer exactly as for a free number
        # (201 + a challenge) so sign-up cannot be used to find registered phones; the
        # decoy never verifies and sends nothing.
        await _audit("auth.signup", "denied")
        return ChallengeResponse(
            challenge_id=await challenges.start("signup", clean["phone"], None)
        )

    await _audit("auth.signup", "success", str(user_id))
    # Background send: a real number (SMS) and a taken one (decoy) take the same time.
    challenge_id = await challenges.start(
        "signup", clean["phone"], str(user_id), send=_send_in_background
    )
    return ChallengeResponse(challenge_id=challenge_id)


@router.post("/auth/signup/verify", response_model=CurrentUser)
async def signup_verify(
    body: CodeRequest, response: Response, request: Request
) -> CurrentUser:
    await _limit_code_entry(request, body.challenge_id)
    data = await challenges.verify(body.challenge_id, "signup", body.code)
    user_id = data["user_id"]
    async with get_session_factory()() as db:
        await db.execute(
            text("SELECT medvault.auth_activate_user(CAST(:id AS uuid))"), {"id": user_id}
        )
        await db.commit()
    await _audit("auth.phone_verified", "success", user_id)
    await _open_session(response, user_id)
    return await _current_user(user_id)


# --- Resend (any purpose) ----------------------------------------------------
@router.post("/auth/sms/resend", response_model=ChallengeResponse)
async def sms_resend(body: ChallengeRequest, request: Request) -> ChallengeResponse:
    await _limit_code_entry(request, body.challenge_id)
    await challenges.resend(body.challenge_id)
    return ChallengeResponse(challenge_id=body.challenge_id)


# --- Sign in (password, then SMS) -------------------------------------------
@router.post("/auth/login", response_model=ChallengeResponse)
async def login(body: LoginRequest, request: Request) -> ChallengeResponse:
    await throttle.hit(f"auth:login:{_client_ip(request)}", limit=30, window_seconds=15 * 60)
    try:
        phone = validation.normalize_phone(body.phone)
    except ValueError:
        # Not a phone we could ever have stored: pay the same argon2 cost, answer the
        # same way, and keep the junk string out of Redis keys.
        await run_in_threadpool(_verify, _DUMMY_HASH, body.password)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS)

    await rate_limit.enforce(rate_limit.LOGIN, account=phone, ip=_client_ip(request))
    # Count the attempt before checking it so concurrent guesses cannot all slip past.
    await throttle.count_login_attempt(phone)
    row = await _lookup(phone)
    ok = await run_in_threadpool(
        _verify, row.password_hash if row else _DUMMY_HASH, body.password
    )
    # One generic error for unknown phone, wrong password or inactive account.
    if not row or not ok or str(row.status) != "active":
        await _audit("auth.login", "failure", str(row.id) if row else None)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS)

    challenge_id = await challenges.start("login", phone, str(row.id))
    return ChallengeResponse(challenge_id=challenge_id)


@router.post("/auth/login/verify", response_model=CurrentUser)
async def login_verify(
    body: CodeRequest, response: Response, request: Request
) -> CurrentUser:
    # A locked-out phone cannot finish a sign-in it started earlier.
    phone = await challenges.phone_of(body.challenge_id)
    await _limit_code_entry(request, body.challenge_id, phone)
    if phone:
        await throttle.ensure_not_locked(phone)
    try:
        data = await challenges.verify(body.challenge_id, "login", body.code)
    except HTTPException:
        # Wrong codes count toward the same lockout as wrong passwords.
        if phone:
            await throttle.register_failure(phone)
        raise

    user_id, phone = data["user_id"], data["phone"]
    row = await _lookup(phone)
    if not row or str(row.id) != user_id or str(row.status) != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS)

    await throttle.clear_failures(phone)
    await _open_session(response, user_id)
    await _audit("auth.login", "success", user_id)
    return await _current_user(user_id)


# --- Logout -------------------------------------------------------------------
@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response, session_id: str | None = Cookie(default=None)
) -> None:
    if session_id:
        user_id = None
        raw = await redis_client.get(f"session:{session_id}")
        if raw:
            try:
                user_id = json.loads(raw).get("user_id") if raw.startswith("{") else raw
            except json.JSONDecodeError:
                user_id = None
        await sessions.destroy(session_id, user_id)
        if user_id:
            await _audit("auth.logout", "success", user_id)
    response.delete_cookie(SESSION_COOKIE)


# --- Password reset ---------------------------------------------------------
@router.post("/auth/password-reset/request", response_model=ChallengeResponse)
async def password_reset_request(
    body: PasswordResetRequest, request: Request
) -> ChallengeResponse:
    """Always answers the same way. An unknown phone gets a decoy challenge that
    never verifies, so the response doesn't reveal whether the number is registered."""
    await throttle.hit(f"auth:reset:{_client_ip(request)}", limit=10, window_seconds=3600)
    try:
        phone = validation.normalize_phone(body.phone)
    except ValueError:
        # Cannot be a registered phone: hand back a decoy without touching Redis keys
        # built from attacker-controlled text.
        return ChallengeResponse(challenge_id=await challenges.start("reset", "", None))
    await rate_limit.enforce(
        rate_limit.PASSWORD_RESET, account=phone, ip=_client_ip(request)
    )
    await throttle.hit(f"auth:reset:phone:{phone}", limit=5, window_seconds=3600)

    row = await _lookup(phone)
    user_id = str(row.id) if row and str(row.status) == "active" else None
    challenge_id = await challenges.start(
        "reset", phone, user_id, send=_send_in_background
    )
    await _audit("auth.password_reset_requested", "success", user_id)
    return ChallengeResponse(challenge_id=challenge_id)


@router.post("/auth/password-reset/verify", response_model=ResetTokenResponse)
async def password_reset_verify(
    body: CodeRequest, request: Request
) -> ResetTokenResponse:
    await _limit_code_entry(request, body.challenge_id)
    data = await challenges.verify(body.challenge_id, "reset", body.code)
    token = secrets.token_urlsafe(32)
    await redis_client.set(
        f"auth:reset_token:{token}", data["user_id"], ex=RESET_TOKEN_TTL_SECONDS
    )
    return ResetTokenResponse(reset_token=token)


@router.post("/auth/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def password_reset_confirm(body: PasswordResetConfirm) -> None:
    _, errors = validation.collect_errors(
        {"new_password": (validation.validate_password, body.new_password)}
    )
    if errors:
        raise _field_errors(errors)

    # Single use: consumed here, so a replayed token fails.
    user_id = await redis_client.getdel(f"auth:reset_token:{body.reset_token}")
    if not user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Reset link expired. Start again.")

    try:
        password_hash = await run_in_threadpool(_hasher.hash, body.new_password)
        async with get_session_factory()() as db:
            await db.execute(
                text("SELECT medvault.auth_set_password(CAST(:id AS uuid), :hash)"),
                {"id": user_id, "hash": password_hash},
            )
            await db.commit()
    except Exception:
        # The token was consumed up front to make it single-use; give it back so a
        # transient failure doesn't force the user through another SMS code.
        await redis_client.set(
            f"auth:reset_token:{body.reset_token}", user_id, ex=RESET_TOKEN_TTL_SECONDS
        )
        raise
    await sessions.destroy_all(user_id)
    await _audit("auth.password_reset", "success", user_id)


# --- Current user ------------------------------------------------------------
@router.get("/users/me", response_model=CurrentUser)
async def me(ctx: RequestContext = Depends(get_request_context)) -> CurrentUser:
    user = (
        await ctx.db.execute(select(User).where(User.id == UUID(ctx.user_id)))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
    return _to_current_user(user)


async def _current_user(user_id: str) -> CurrentUser:
    # Read the row under RLS as the user themself, like any authenticated request.
    async with get_session_factory()() as db:
        await db.execute(
            text("SELECT set_config('app.current_user_id', :user_id, true)"),
            {"user_id": user_id},
        )
        user = (
            await db.execute(select(User).where(User.id == UUID(user_id)))
        ).scalar_one()
        return _to_current_user(user)


def _to_current_user(user: User) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        phone=user.phone_e164,
        status=str(getattr(user.status, "value", user.status)),
        created_at=user.created_at,
    )
