import asyncio
import io
import json
import logging
import unittest

import httpx

from app.audit.logger import write_audit_log
from app.main import create_app
from app.security import logs
from app.security.redaction import REDACTED, redact, redact_text

IDNP = "2001234567890"
PHONE = "+37369123456"
TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl"


class RedactTextTests(unittest.TestCase):
    def test_scrubs_identifiers_and_tokens(self):
        text = (
            f"idnp {IDNP} phone {PHONE} Authorization: Bearer abc.def-123 "
            f"jwt {TOKEN} /callback?state=s3cr3t&code=xyz&ok=1"
        )
        clean = redact_text(text)
        for secret in (IDNP, PHONE, "abc.def-123", TOKEN, "s3cr3t", "xyz"):
            self.assertNotIn(secret, clean)
        self.assertIn("ok=1", clean)
        self.assertIn("code=" + REDACTED, clean)

    def test_leaves_ordinary_text_alone(self):
        text = "connection 3f2a6c1e-0b6d-4d43-9a0e-2b8d3f1c4e5a returned 12 records in 431 ms"
        self.assertEqual(redact_text(text), text)

    def test_redacts_by_key_recursively(self):
        clean = redact(
            {
                "idnp": "not even digits",
                "category": "analyses",
                "nested": [{"original_filename": "hiv-test.pdf", "count": 2}],
                "Access-Token": "t",
                "note": f"typed {IDNP}",
            }
        )
        self.assertEqual(clean["idnp"], REDACTED)
        self.assertEqual(clean["category"], "analyses")
        self.assertEqual(clean["nested"], [{"original_filename": REDACTED, "count": 2}])
        self.assertEqual(clean["Access-Token"], REDACTED)
        self.assertNotIn(IDNP, clean["note"])


class LoggingTests(unittest.TestCase):
    def setUp(self):
        self.stream = io.StringIO()
        handler = logging.StreamHandler(self.stream)
        handler.setFormatter(logs.JsonFormatter())
        handler.addFilter(logs.RedactingFilter())
        self.logger = logging.getLogger("medvault.test-redaction")
        self.logger.handlers = [handler]
        self.logger.propagate = False
        self.logger.setLevel(logging.DEBUG)

    def lines(self):
        return [json.loads(line) for line in self.stream.getvalue().splitlines()]

    def test_records_are_json_and_scrubbed(self):
        self.logger.info(
            "sent PAR for %s",
            IDNP,
            extra={"access_token": "secret-token", "file_name": "scan.pdf", "count": 3},
        )
        (line,) = self.lines()
        self.assertEqual(line["level"], "INFO")
        self.assertEqual(line["logger"], "medvault.test-redaction")
        self.assertEqual(line["count"], 3)
        raw = self.stream.getvalue()
        for secret in (IDNP, "secret-token", "scan.pdf"):
            self.assertNotIn(secret, raw)

    def test_tracebacks_are_scrubbed(self):
        try:
            raise ValueError(f"bad idnp {IDNP} for {PHONE}")
        except ValueError:
            self.logger.exception("failed")
        raw = self.stream.getvalue()
        self.assertIn("ValueError", raw)
        self.assertNotIn(IDNP, raw)
        self.assertNotIn(PHONE, raw)


class ErrorResponseTests(unittest.TestCase):
    def request(self, app, method, path, **kwargs):
        async def go():
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
                return await c.request(method, path, **kwargs)

        return asyncio.run(go())

    def test_validation_errors_never_echo_the_input(self):
        password = "P@ss" + "w" * 600
        response = self.request(
            create_app(), "POST", "/auth/login", json={"phone": PHONE, "password": password}
        )
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("Pw", response.text)
        self.assertNotIn("input", response.text)
        self.assertEqual(response.json()["detail"][0]["loc"], ["body", "password"])

    def test_unexpected_errors_are_generic_and_logged_scrubbed(self):
        app = create_app()

        @app.get("/boom")
        async def boom():
            raise RuntimeError(f"institution rejected {IDNP}")

        with self.assertLogs("medvault.http", "ERROR") as captured:
            response = self.request(app, "GET", "/boom")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(IDNP, response.text)
        self.assertNotIn("RuntimeError", response.text)
        # What a handler would write: run the record through the filter.
        record = captured.records[0]
        logs.RedactingFilter().filter(record)
        self.assertNotIn(IDNP, logs.JsonFormatter().format(record))


class AuditMetadataTests(unittest.TestCase):
    def test_metadata_is_scrubbed_before_insert(self):
        params = {}

        class DB:
            async def execute(self, _statement, values):
                params.update(values)

        asyncio.run(
            write_audit_log(
                DB(),
                actor_user_id=None,
                subject_patient_id=None,
                action="test",
                resource_type="test",
                resource_id=None,
                outcome="success",
                metadata={"idnp": IDNP, "filename": "scan.pdf", "category": "analyses"},
            )
        )
        stored = json.loads(params["metadata"])
        self.assertEqual(stored, {"idnp": REDACTED, "filename": REDACTED, "category": "analyses"})


if __name__ == "__main__":
    unittest.main()
