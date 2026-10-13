"""SMS delivery behind a provider interface (Epic 1, story 4).

`MockSmsProvider` is the development stand-in: it logs the message and keeps the last
few per phone in Redis so a developer (or the test suite) can read the code from
`GET /dev/sms/{phone}`. That route fails closed: it is only mounted when
ENABLE_DEV_SMS_OUTBOX=true is set explicitly, SMS_PROVIDER=mock, and APP_ENV is not
production (APP_ENV defaults to production when unset). The mock provider refuses to
run in production. A real provider implements `SmsProvider.send` and is selected
through SMS_PROVIDER.
"""
import logging
import os
from typing import Protocol

from fastapi import APIRouter, HTTPException, status

from app.database import redis_client

logger = logging.getLogger("medvault.sms")

OUTBOX_TTL_SECONDS = 600
OUTBOX_MAX = 5


class SmsProvider(Protocol):
    async def send(self, phone: str, message: str) -> None: ...


class MockSmsProvider:
    async def send(self, phone: str, message: str) -> None:
        key = f"sms:outbox:{phone}"
        await redis_client.lpush(key, message)
        await redis_client.ltrim(key, 0, OUTBOX_MAX - 1)
        await redis_client.expire(key, OUTBOX_TTL_SECONDS)
        # The message body carries the code, so only a masked number is logged.
        logger.info("MOCK SMS queued for %s", _mask(phone))


def _mask(phone: str) -> str:
    return f"{phone[:4]}****{phone[-2:]}" if len(phone) > 6 else "****"


def _is_production() -> bool:
    return os.getenv("APP_ENV", "production").lower() == "production"


def get_sms_provider() -> SmsProvider:
    name = os.getenv("SMS_PROVIDER", "mock").lower()
    if name == "mock":
        if _is_production():
            raise RuntimeError("SMS_PROVIDER=mock is not allowed when APP_ENV=production")
        return MockSmsProvider()
    raise RuntimeError(f"Unknown SMS_PROVIDER '{name}'")


def mock_enabled() -> bool:
    return (
        os.getenv("ENABLE_DEV_SMS_OUTBOX", "false").lower() == "true"
        and os.getenv("SMS_PROVIDER", "mock").lower() == "mock"
        and not _is_production()
    )


dev_router = APIRouter(prefix="/dev", tags=["dev"])


@dev_router.get("/sms/{phone}")
async def read_outbox(phone: str) -> dict:
    """Latest mock SMS messages for a phone (newest first). Dev only."""
    if not mock_enabled():
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    messages = await redis_client.lrange(f"sms:outbox:{phone}", 0, OUTBOX_MAX - 1)
    return {"phone": phone, "messages": messages}
