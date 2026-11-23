"""Email delivery (app/auth/mailer.py): providers, dev outbox gating, masking."""
import asyncio
import json
import os
import sys
import types
import unittest
from unittest import mock

from fastapi import HTTPException

from app.auth import mailer
from app.security.redaction import REDACTED, redact, redact_text

ADDRESS = "daniel.canter@example.com"
_ENV = (
    "APP_ENV", "EMAIL_PROVIDER", "ENABLE_DEV_EMAIL_OUTBOX", "SMTP_HOST", "SMTP_PORT",
    "SMTP_STARTTLS", "SMTP_USE_TLS", "SMTP_USERNAME", "SMTP_PASSWORD", "EMAIL_FROM",
)


class ListRedis:
    """Just the list commands the mock outbox uses."""

    def __init__(self):
        self.store: dict = {}
        self.ttls: dict = {}

    async def lpush(self, key, val):
        self.store.setdefault(key, []).insert(0, val)

    async def ltrim(self, key, a, b):
        self.store[key] = self.store.get(key, [])[a : b + 1]

    async def expire(self, key, seconds):
        self.ttls[key] = seconds

    async def lrange(self, key, a, b):
        return self.store.get(key, [])[a : b + 1]


class EnvCase(unittest.TestCase):
    def setUp(self):
        self._env = {k: os.environ.get(k) for k in _ENV}
        for k in _ENV:
            os.environ.pop(k, None)
        os.environ["APP_ENV"] = "development"
        self.redis = ListRedis()
        self._redis = mailer.redis_client
        mailer.redis_client = self.redis

    def tearDown(self):
        mailer.redis_client = self._redis
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class ProviderSelectionTests(EnvCase):
    def test_mock_is_the_default_outside_production(self):
        self.assertIsInstance(mailer.get_email_provider(), mailer.MockEmailProvider)

    def test_mock_refused_in_production(self):
        os.environ["APP_ENV"] = "production"
        with self.assertRaises(RuntimeError):
            mailer.get_email_provider()

    def test_unset_app_env_means_production(self):
        os.environ.pop("APP_ENV")
        with self.assertRaises(RuntimeError):
            mailer.get_email_provider()

    def test_smtp_selected(self):
        os.environ["EMAIL_PROVIDER"] = "smtp"
        self.assertIsInstance(mailer.get_email_provider(), mailer.SmtpEmailProvider)

    def test_smtp_without_tls_refused_in_production(self):
        os.environ.update(APP_ENV="production", EMAIL_PROVIDER="smtp", SMTP_STARTTLS="false")
        with self.assertRaises(RuntimeError):
            mailer.get_email_provider()

    def test_unknown_provider(self):
        os.environ["EMAIL_PROVIDER"] = "pigeon"
        with self.assertRaises(RuntimeError):
            mailer.get_email_provider()


class MockOutboxTests(EnvCase):
    def test_keeps_the_latest_messages(self):
        provider = mailer.MockEmailProvider()
        for i in range(mailer.OUTBOX_MAX + 2):
            asyncio.run(provider.send(mailer.Email(ADDRESS, "s", f"code {i}")))
        stored = self.redis.store[f"email:outbox:{ADDRESS}"]
        self.assertEqual(len(stored), mailer.OUTBOX_MAX)
        self.assertEqual(json.loads(stored[0])["text"], f"code {mailer.OUTBOX_MAX + 1}")
        self.assertEqual(self.redis.ttls[f"email:outbox:{ADDRESS}"], mailer.OUTBOX_TTL_SECONDS)

    def test_dev_route_fails_closed(self):
        self.assertFalse(mailer.mock_enabled())  # flag not set
        with self.assertRaises(HTTPException) as cm:
            asyncio.run(mailer.read_outbox(ADDRESS))
        self.assertEqual(cm.exception.status_code, 404)

        os.environ["ENABLE_DEV_EMAIL_OUTBOX"] = "true"
        self.assertTrue(mailer.mock_enabled())
        os.environ["EMAIL_PROVIDER"] = "smtp"
        self.assertFalse(mailer.mock_enabled())
        os.environ.pop("EMAIL_PROVIDER")
        os.environ["APP_ENV"] = "production"
        self.assertFalse(mailer.mock_enabled())

    def test_dev_route_reads_outbox(self):
        os.environ["ENABLE_DEV_EMAIL_OUTBOX"] = "true"
        asyncio.run(mailer.MockEmailProvider().send(mailer.Email(ADDRESS, "subj", "code 1")))
        out = asyncio.run(mailer.read_outbox(ADDRESS.upper()))
        self.assertEqual(out["messages"], [{"subject": "subj", "text": "code 1"}])

    def test_logs_only_a_masked_address(self):
        with self.assertLogs("medvault.email", "INFO") as logs:
            asyncio.run(mailer.MockEmailProvider().send(mailer.Email(ADDRESS, "s", "123456")))
        joined = "\n".join(logs.output)
        self.assertNotIn(ADDRESS, joined)
        self.assertNotIn("123456", joined)


class SmtpProviderTests(EnvCase):
    def test_builds_and_sends_the_message(self):
        os.environ.update(
            EMAIL_PROVIDER="smtp", SMTP_HOST="mailpit", SMTP_PORT="1025",
            SMTP_STARTTLS="false", EMAIL_FROM="MedVault <no-reply@medvault.test>",
        )
        sent = mock.AsyncMock()
        fake = types.SimpleNamespace(send=sent)
        with mock.patch.dict(sys.modules, {"aiosmtplib": fake}):
            asyncio.run(
                mailer.get_email_provider().send(
                    mailer.Email(ADDRESS, "Your code", "code 1", "<p>code 1</p>")
                )
            )
        msg = sent.call_args.args[0]
        kwargs = sent.call_args.kwargs
        self.assertEqual(msg["To"], ADDRESS)
        self.assertEqual(msg["Subject"], "Your code")
        self.assertEqual(msg["From"], "MedVault <no-reply@medvault.test>")
        self.assertTrue(msg.is_multipart())
        self.assertEqual((kwargs["hostname"], kwargs["port"]), ("mailpit", 1025))
        self.assertFalse(kwargs["start_tls"])
        self.assertFalse(kwargs["use_tls"])

    def test_implicit_tls_disables_starttls(self):
        os.environ.update(EMAIL_PROVIDER="smtp", SMTP_USE_TLS="true")
        provider = mailer.get_email_provider()
        self.assertTrue(provider.use_tls)
        self.assertFalse(provider.start_tls)


class MaskAndRedactionTests(unittest.TestCase):
    def test_mask(self):
        self.assertEqual(mailer.mask("daniel@gmail.com"), "d***@g***.com")
        self.assertEqual(mailer.mask("a@b.co.uk"), "a***@b***.uk")
        self.assertEqual(mailer.mask("nonsense"), "****")
        self.assertEqual(mailer.mask(""), "****")

    def test_redaction_scrubs_emails_but_keeps_masks(self):
        self.assertEqual(redact_text(f"sent to {ADDRESS}"), f"sent to {REDACTED}")
        self.assertEqual(redact_text("sent to d***@e***.com"), "sent to d***@e***.com")
        self.assertEqual(redact({"email": "x"}), {"email": REDACTED})


if __name__ == "__main__":
    unittest.main()
