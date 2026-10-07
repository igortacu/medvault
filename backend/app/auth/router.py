"""Sign-in / sign-out and the current-user endpoint (Epic 1, minimal).

Phone + password sign-in that issues the Redis-backed session read by
get_request_context. The account lookup goes through the
`auth_lookup_for_signin` SECURITY DEFINER function, since no
app.current_user_id exists yet for RLS. Registration, SMS verification and
lockout/rate limiting are not implemented yet.
"""
import json
import os
import re
import secrets
from datetime import datetime
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select, text

from app.auth.dependencies import RequestContext, get_request_context
from app.database import get_session_factory, redis_client
from app.models.user import User

router = APIRouter(tags=["auth"])

SESSION_COOKIE = "session_id"
SESSION_TTL_SECONDS = 8 * 60 * 60
# Off for local http dev; set SESSION_COOKIE_SECURE=true behind https.
COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
INVALID_CREDENTIALS = "Invalid phone or password."

_hasher = PasswordHasher()
# Verified against when the phone is unknown, so both paths cost one argon2 check.
_DUMMY_HASH = _hasher.hash(secrets.token_hex(16))


class LoginRequest(BaseModel):
    phone: str
    password: str


class CurrentUser(BaseModel):
    id: UUID
    phone: str
    status: str
    created_at: datetime


def _verify(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


@router.post("/auth/login", response_model=CurrentUser)
async def login(body: LoginRequest, response: Response) -> CurrentUser:
    phone = re.sub(r"[\s\-()]", "", body.phone)
    async with get_session_factory()() as db:
        row = (
            await db.execute(
                text("SELECT * FROM medvault.auth_lookup_for_signin(:phone)"),
                {"phone": phone},
            )
        ).first()

    ok = await run_in_threadpool(
        _verify, row.password_hash if row else _DUMMY_HASH, body.password
    )
    # One generic error for unknown phone, wrong password or inactive account.
    if not row or not ok or str(row.status) != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS)

    session_id = secrets.token_urlsafe(32)
    await redis_client.set(
        f"session:{session_id}",
        json.dumps({"user_id": str(row.id)}),
        ex=SESSION_TTL_SECONDS,
    )
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )
    return await _current_user(str(row.id))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response, session_id: str | None = Cookie(default=None)
) -> None:
    if session_id:
        await redis_client.delete(f"session:{session_id}")
    response.delete_cookie(SESSION_COOKIE)


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
