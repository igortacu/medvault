import os
from functools import lru_cache

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    url = os.environ.get("DATABASE_URL_ASYNC")
    if not url:
        raise RuntimeError("DATABASE_URL_ASYNC is required")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return async_sessionmaker(
        create_async_engine(url, pool_pre_ping=True),
        expire_on_commit=False,
        class_=AsyncSession,
    )


redis_client = Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True
)
