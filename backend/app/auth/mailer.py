"""Email delivery behind a provider interface (one-time sign-in codes).

Selected by EMAIL_PROVIDER:

* `mock` (default) logs a masked address and keeps the last few messages per address
  in Redis, readable from `GET /dev/email/{address}`. Like the dev SMS outbox it replaces, that
  route fails closed: it is only mounted when ENABLE_DEV_EMAIL_OUTBOX=true,
  EMAIL_PROVIDER=mock and APP_ENV is not production (APP_ENV defaults to production
  when unset). The mock provider refuses to run in production.
* `smtp` sends through any SMTP server: Mailpit in docker-compose for local
  development, or a real relay (SES SMTP, Mailgun, Gmail...) in production.
  Configured by SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_STARTTLS,
  SMTP_USE_TLS and EMAIL_FROM.

Messages carry the code, so neither provider ever logs a body or a full address.
"""
import json
import logging
import os
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from fastapi import APIRouter, HTTPException, status

from app.database import redis_client

logger = logging.getLogger("medvault.email")

OUTBOX_TTL_SECONDS = 600
OUTBOX_MAX = 5


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str
    html: str | None = None


class EmailProvider(Protocol):
    async def send(self, message: Email) -> None: ...


def mask(address: str) -> str:
    """`d***@g***.com` style: enough to recognise in logs, not enough to harvest."""
    local, _, domain = (address or "").partition("@")
    if not local or not domain:
        return "****"
    host, dot, tld = domain.rpartition(".")
    if not dot:
        host, tld = domain, ""
    return f"{local[0]}***@{host[:1]}***{dot}{tld}"


def _is_production() -> bool:
    return os.getenv("APP_ENV", "production").lower() == "production"


def _provider_name() -> str:
    return os.getenv("EMAIL_PROVIDER", "mock").lower()


class MockEmailProvider:
    async def send(self, message: Email) -> None:
        key = f"email:outbox:{message.to}"
        await redis_client.lpush(
            key, json.dumps({"subject": message.subject, "text": message.text})
        )
        await redis_client.ltrim(key, 0, OUTBOX_MAX - 1)
        await redis_client.expire(key, OUTBOX_TTL_SECONDS)
        logger.info("MOCK email queued for %s", mask(message.to))


class SmtpEmailProvider:
    def __init__(self) -> None:
        self.host = os.getenv("SMTP_HOST", "localhost")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.username = os.getenv("SMTP_USERNAME") or None
        self.password = os.getenv("SMTP_PASSWORD") or None
        self.use_tls = os.getenv("SMTP_USE_TLS", "false").lower() == "true"
        self.start_tls = (
            not self.use_tls and os.getenv("SMTP_STARTTLS", "true").lower() == "true"
        )
        self.sender = os.getenv("EMAIL_FROM", "MedVault <no-reply@medvault.local>")
        if _is_production() and not (self.use_tls or self.start_tls):
            raise RuntimeError("SMTP without TLS is not allowed when APP_ENV=production")

    async def send(self, message: Email) -> None:
        # Imported lazily so the mock path (and the test suite) never needs it.
        import aiosmtplib

        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = message.to
        msg["Subject"] = message.subject
        msg.set_content(message.text)
        if message.html:
            msg.add_alternative(message.html, subtype="html")
        await aiosmtplib.send(
            msg,
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            use_tls=self.use_tls,
            start_tls=self.start_tls,
            timeout=15,
        )
        logger.info("Email sent to %s", mask(message.to))


def get_email_provider() -> EmailProvider:
    name = _provider_name()
    if name == "mock":
        if _is_production():
            raise RuntimeError("EMAIL_PROVIDER=mock is not allowed when APP_ENV=production")
        return MockEmailProvider()
    if name == "smtp":
        return SmtpEmailProvider()
    raise RuntimeError(f"Unknown EMAIL_PROVIDER '{name}'")


def mock_enabled() -> bool:
    return (
        os.getenv("ENABLE_DEV_EMAIL_OUTBOX", "false").lower() == "true"
        and _provider_name() == "mock"
        and not _is_production()
    )


dev_router = APIRouter(prefix="/dev", tags=["dev"])


@dev_router.get("/email/{address}")
async def read_outbox(address: str) -> dict:
    """Latest mock emails for an address (newest first). Dev only."""
    if not mock_enabled():
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    raw = await redis_client.lrange(f"email:outbox:{address.lower()}", 0, OUTBOX_MAX - 1)
    return {"email": address.lower(), "messages": [json.loads(m) for m in raw]}
