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


async def get_request_context(session_id: str | None = Cookie(default=None)):
    if not session_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")

    session = await redis_client.get(f"session:{session_id}")
    if not session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    try:
        user_id = (
            json.loads(session).get("user_id") if session.startswith("{") else session
        )
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
            yield RequestContext(user_id=user_id, db=db)
        except Exception:
            await db.rollback()
            raise
        else:
            await db.commit()
