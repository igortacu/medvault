import json
from dataclasses import dataclass
from uuid import UUID

from app.database import get_session_factory, redis_client
from fastapi import Cookie, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class RequestContext:
    user_id: str
    db: AsyncSession
    # The opaque session id (cookie value), needed to persist a vault switch.
    session_id: str | None = None
    # The patient whose vault the caregiver is currently acting in (vault switching,
    # Epic 3). None means the caller's own vault. This is only a UI selection — every
    # request still re-checks the caregiver link/permission, nothing is cached.
    acting_patient_id: str | None = None


async def get_request_context(session_id: str | None = Cookie(default=None)):
    if not session_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")

    session = await redis_client.get(f"session:{session_id}")
    if not session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    acting_patient_id = None
    try:
        if session.startswith("{"):
            payload = json.loads(session)
            user_id = payload.get("user_id")
            acting_patient_id = payload.get("acting_patient_id")
        else:
            user_id = session
    except (json.JSONDecodeError, AttributeError):
        user_id = None
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
    try:
        user_id = str(UUID(user_id))
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")

    async with get_session_factory()() as db:
        await db.execute(
            text("SELECT set_config('app.current_user_id', :user_id, true)"),
            {"user_id": user_id},
        )
        try:
            yield RequestContext(
                user_id=user_id,
                db=db,
                session_id=session_id,
                acting_patient_id=acting_patient_id,
            )
        except Exception:
            await db.rollback()
            raise
        else:
            await db.commit()
