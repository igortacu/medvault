"""The IDNP is used once and kept nowhere (Epic 5, story 1).

Drives both connect routes through the real HTTP stack (middleware, logging,
exception handlers, rate limiting) against the in-process institution mock, and then
searches everything the backend touched for the IDNP: log records, Redis, database
statements and rows, audit metadata, and the responses. The only place it may
appear is the body of the pushed authorization request (PAR) sent server-to-server
to each institution being connected.
"""
import asyncio
import importlib
import json
import logging
import os
import unittest
from uuid import UUID

import httpx
from cryptography.fernet import Fernet

from app.auth.dependencies import get_request_context
from app.main import create_app
from app.security import rate_limit
from institution_mock.app import ACCESS_LOG, RUNTIME
from institution_mock.app import app as mock_app
from tests.test_auth_sms import FakeRedis as CounterRedis
from tests.test_institution_oauth_client import (
    USER_ID,
    FakeDB,
    FakeRedis as StateRedis,
    make_institution,
)

integration = importlib.import_module("app.institutions.router")

IDNP = "2009876543210"


class RecordingDB(FakeDB):
    """FakeDB that also keeps every statement's parameters (audit rows included)."""

    def __init__(self, *results, institutions=()):
        super().__init__(*results, institutions=institutions)
        self.params = []

    async def execute(self, statement, params=None):
        self.params.append(params)
        await super().execute(statement, params)


class RecordingTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner):
        self.inner = inner
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request):
        await request.aread()
        self.requests.append(request)
        return await self.inner.handle_async_request(request)


class CapturingHandler(logging.Handler):
    """Snapshots each record as it arrives: records are shared objects, and the
    redacting handler later rewrites them in place."""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records: list[tuple[str, str]] = []

    def emit(self, record):
        self.records.append((record.name, _dump(record)))


def _dump(record: logging.LogRecord) -> str:
    """Everything a handler could print: message, raw args, extras, traceback."""
    text = [record.getMessage(), repr(record.args), repr(vars(record))]
    if record.exc_info:
        text.append(logging.Formatter().formatException(record.exc_info))
    return "\n".join(text)


class IdnpNeverKeptTests(unittest.TestCase):
    def setUp(self):
        for collection in RUNTIME.values():
            collection.clear()
        ACCESS_LOG.clear()
        self.saved = (
            integration.MOCK_BASE_URL,
            integration.redis_client,
            rate_limit.redis_client,
            os.environ.get("TOKEN_ENCRYPTION_KEY"),
        )
        integration.MOCK_BASE_URL = "http://institution-mock"
        integration.redis_client = self.state_redis = StateRedis()
        rate_limit.redis_client = self.counter_redis = CounterRedis()
        os.environ["TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

        self.app = create_app()  # configures logging, so capture after it
        self.logs = CapturingHandler()
        root = logging.getLogger()
        self.saved_level = root.level
        # First in line, so it sees what the app hands to logging rather than what
        # survives redaction.
        root.handlers.insert(0, self.logs)
        root.setLevel(logging.DEBUG)

        self.outbound = RecordingTransport(httpx.ASGITransport(app=mock_app))

        async def http_client():
            async with httpx.AsyncClient(
                transport=self.outbound,
                base_url="http://institution-mock",
                follow_redirects=False,
            ) as client:
                yield client

        self.app.dependency_overrides[integration.get_http_client] = http_client

    def tearDown(self):
        root = logging.getLogger()
        root.removeHandler(self.logs)
        root.setLevel(self.saved_level)
        (
            integration.MOCK_BASE_URL,
            integration.redis_client,
            rate_limit.redis_client,
            key,
        ) = self.saved
        if key is None:
            os.environ.pop("TOKEN_ENCRYPTION_KEY", None)
        else:
            os.environ["TOKEN_ENCRYPTION_KEY"] = key

    def use_db(self, db):
        self.db = db
        context = type("Ctx", (), {"user_id": USER_ID, "db": db})()
        self.app.dependency_overrides[get_request_context] = lambda: context

    def post(self, path, body):
        async def go():
            transport = httpx.ASGITransport(app=self.app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://api") as c:
                return await c.post(path, json=body)

        return asyncio.run(go())

    def assert_kept_nowhere(self, *responses):
        for response in responses:
            self.assertNotIn(IDNP, response.text)
            self.assertNotIn(IDNP, repr(response.headers))
        for name, text in self.logs.records:
            self.assertNotIn(IDNP, text, f"logged by {name}")
        for values in (self.state_redis.values, self.counter_redis.store):
            self.assertNotIn(IDNP, repr(values))
        self.assertNotIn(IDNP, repr(self.db.params))  # statements + audit metadata
        for row in self.db.added:
            self.assertNotIn(IDNP, repr(vars(row)))
        self.assertTrue(self.logs.records, "expected the request to be logged")

    def assert_only_sent_in_pars(self, institutions):
        carrying = [r for r in self.outbound.requests if IDNP.encode() in r.content]
        self.assertEqual(
            sorted(str(r.url) for r in carrying),
            sorted(
                f"http://institution-mock/{i.external_id}/oauth/par" for i in institutions
            ),
        )
        for request in carrying:
            self.assertEqual(request.method, "POST")
        for request in self.outbound.requests:
            self.assertNotIn(IDNP, str(request.url))
            self.assertNotIn(IDNP, repr(request.headers))

    def test_connect_one_institution(self):
        institution = make_institution(
            "imsp-scr-t-mosneaga", UUID("22222222-2222-2222-2222-222222222222")
        )
        self.use_db(RecordingDB(institution, None))

        response = self.post(
            f"/api/v1/institutions/{institution.id}/connect",
            {"idnp": IDNP, "consent_text_version": "2026-10"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("request_uri", response.json()["authorize_url"])
        self.assert_kept_nowhere(response)
        self.assert_only_sent_in_pars([institution])

    def test_connect_public_institutions_including_one_that_fails(self):
        reachable = make_institution("imsp-scr-t-mosneaga")
        unreachable = make_institution("not-a-real-institution")
        self.use_db(RecordingDB(institutions=[reachable, unreachable]))

        response = self.post(
            "/api/v1/institutions/connect",
            {"idnp": IDNP, "consent_text_version": "2026-10"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        statuses = {c["status"] for c in response.json()["connections"]}
        self.assertEqual(statuses, {"authorizing", "error"})
        self.assert_kept_nowhere(response)
        self.assert_only_sent_in_pars([reachable, unreachable])

    def test_malformed_idnp_is_not_echoed_or_sent(self):
        self.use_db(RecordingDB())
        malformed = IDNP + "1"

        response = self.post(
            "/api/v1/institutions/connect",
            {"idnp": malformed, "consent_text_version": "2026-10"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertNotIn(malformed, response.text)
        self.assert_kept_nowhere(response)
        self.assertEqual(self.outbound.requests, [])

    def test_rate_limited_connect_sends_nothing(self):
        self.use_db(RecordingDB())
        limit = rate_limit.INSTITUTION_CONNECT
        subject = rate_limit._subject(USER_ID, "127.0.0.1")
        self.counter_redis.store[f"ratelimit:{limit.name}:count:{subject}"] = str(limit.limit)
        self.counter_redis.ttls[f"ratelimit:{limit.name}:count:{subject}"] = 1200

        response = self.post(
            "/api/v1/institutions/connect",
            {"idnp": IDNP, "consent_text_version": "2026-10"},
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["retry-after"], "1200")
        self.assert_kept_nowhere(response)
        self.assertEqual(self.outbound.requests, [])


if __name__ == "__main__":
    unittest.main()
