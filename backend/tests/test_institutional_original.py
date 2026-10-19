"""Live institutional originals: the file is read from the institution's Binary
endpoint on demand and handed back, never stored."""
import base64
import hashlib
import importlib
import os
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import httpx
from cryptography.fernet import Fernet

from app.aggregation import client, mapping, originals
from institution_mock.app import ACCESS_LOG, RUNTIME
from institution_mock.app import app as mock_app

institutions = importlib.import_module("app.institutions.router")

PATIENT = UUID("11111111-1111-1111-1111-111111111111")
CAREGIVER = UUID("33333333-3333-3333-3333-333333333333")
DEV_IDNP = "2001234567890"
# The dev patient's consultation report at Medpark, with its PDF in Binary/bin-0004.
DOC_REF = "institution:medpark/DocumentReference/doc-0001"


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class FakeDB:
    """Just enough AsyncSession: the institution lookup, the visible-connections
    function and the caregiver_can gate."""

    def __init__(self, institution, connections, *, caregiver_can=False):
        self.institution = institution
        self.connections = connections
        self.caregiver_can = caregiver_can
        self.commits = 0

    async def scalar(self, statement, params=None):
        if "caregiver_can" in str(statement):
            return self.caregiver_can
        return self.institution

    async def execute(self, statement, params=None):
        if params is not None and "p" in params:
            return FakeResult(self.connections)
        return FakeResult([])

    async def commit(self):
        self.commits += 1


def medpark():
    return SimpleNamespace(
        id=uuid4(),
        name="Spitalul Internațional Medpark",
        external_id="medpark",
        oauth_client_id="medvault-medpark",
        oauth_client_secret_ciphertext=b"DEV_PLACEHOLDER_SECRET_REPLACE_BEFORE_PROD",
        oauth_secret_key_version=0,
    )


class InstitutionalOriginalTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for collection in RUNTIME.values():
            collection.clear()
        ACCESS_LOG.clear()
        client.reset_breakers()
        previous = (institutions.MOCK_BASE_URL, client.RETRY_BACKOFF_SECONDS)
        institutions.MOCK_BASE_URL = "http://institution-mock"
        client.RETRY_BACKOFF_SECONDS = 0
        key = os.environ.get("TOKEN_ENCRYPTION_KEY")
        os.environ["TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

        def restore():
            institutions.MOCK_BASE_URL, client.RETRY_BACKOFF_SECONDS = previous
            if key is None:
                os.environ.pop("TOKEN_ENCRYPTION_KEY", None)
            else:
                os.environ["TOKEN_ENCRYPTION_KEY"] = key

        self.addCleanup(restore)
        self.institution = medpark()

    def mock_http(self):
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mock_app),
            base_url="http://institution-mock",
            follow_redirects=False,
        )

    async def connect(self, http) -> SimpleNamespace:
        """Run the real PAR -> authorize -> token flow against the mock and return
        the connection row the visible-connections function would give back."""
        verifier = "v" * 64
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        scopes = [mapping.scope_for(t) for t in mapping.ALL_RESOURCE_TYPES]
        pushed = await institutions._post_oauth(
            http,
            institutions._endpoint(self.institution, "par"),
            self.institution,
            {
                "client_id": self.institution.oauth_client_id,
                "redirect_uri": institutions.CALLBACK_URL,
                "scope": " ".join(scopes),
                "state": "s",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "idnp": DEV_IDNP,
            },
        )
        authorized = await http.get(
            institutions._endpoint(self.institution, "authorize"),
            params={"request_uri": pushed["request_uri"]},
        )
        code = parse_qs(urlparse(authorized.headers["location"]).query)["code"][0]
        tokens = await institutions._post_oauth(
            http,
            institutions._endpoint(self.institution, "token"),
            self.institution,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": institutions.CALLBACK_URL,
                "code_verifier": verifier,
            },
        )
        return SimpleNamespace(
            id=uuid4(),
            institution_id=self.institution.id,
            granted_scopes=tokens["scope"].split(),
            access_token_ciphertext=institutions._encrypt(tokens["access_token"]),
            access_token_expires_at=datetime.now(UTC) + timedelta(minutes=10),
            refresh_token_ciphertext=None,
        )

    async def fetch(self, db, http, ref=DOC_REF, category="diagnoses", actor=PATIENT):
        ctx = SimpleNamespace(user_id=str(actor), db=db)
        return await originals.fetch_original(ctx, ref, category, PATIENT, http)

    async def test_owner_gets_the_pdf_live_from_the_institution(self):
        async with self.mock_http() as http:
            row = await self.connect(http)
            db = FakeDB(self.institution, [row])
            original = await self.fetch(db, http)

        self.assertEqual(original.content_type, "application/pdf")
        self.assertTrue(original.content.startswith(b"%PDF-"))
        self.assertEqual(original.institution_id, self.institution.id)
        # The DB connection is handed back while the institution answers.
        self.assertGreaterEqual(db.commits, 1)

    async def test_caregiver_needs_view_original(self):
        async with self.mock_http() as http:
            row = await self.connect(http)
            with self.assertRaises(originals.OriginalError) as denied:
                await self.fetch(FakeDB(self.institution, [row]), http, actor=CAREGIVER)
            self.assertEqual(denied.exception.reason, "forbidden")

            allowed = await self.fetch(
                FakeDB(self.institution, [row], caregiver_can=True), http, actor=CAREGIVER
            )
        self.assertTrue(allowed.content.startswith(b"%PDF-"))

    async def test_record_must_belong_to_the_category_it_is_opened_from(self):
        # doc-0001 is a consultation report (diagnoses), not a certificate:
        # naming another page must not borrow that page's caregiver permission.
        async with self.mock_http() as http:
            row = await self.connect(http)
            with self.assertRaises(originals.OriginalError) as error:
                await self.fetch(
                    FakeDB(self.institution, [row], caregiver_can=True),
                    http,
                    category="certificates",
                    actor=CAREGIVER,
                )
        self.assertEqual(error.exception.reason, "not_found")

    async def test_disconnected_institution_has_no_original(self):
        async with self.mock_http() as http:
            with self.assertRaises(originals.OriginalError) as error:
                await self.fetch(FakeDB(self.institution, []), http)
        self.assertEqual(error.exception.reason, "not_found")

    async def test_record_from_another_patient_is_not_found(self):
        async with self.mock_http() as http:
            row = await self.connect(http)
            with self.assertRaises(originals.OriginalError) as error:
                await self.fetch(
                    FakeDB(self.institution, [row]),
                    http,
                    ref="institution:medpark/DocumentReference/doc-9999",
                )
        self.assertEqual(error.exception.reason, "not_found")

    async def test_bad_reference_or_wrong_category_is_not_found(self):
        db = FakeDB(self.institution, [])
        for ref, category in (
            ("institution:medpark/../../etc", "certificates"),
            ("https://evil.example/x.pdf", "certificates"),
            ("institution:medpark/Condition/c1", "certificates"),
        ):
            with self.assertRaises(originals.OriginalError) as error:
                await self.fetch(db, None, ref=ref, category=category)
            self.assertEqual(error.exception.reason, "not_found", ref)

    async def test_unreachable_institution_is_reported_as_such(self):
        row = SimpleNamespace(
            id=uuid4(),
            institution_id=self.institution.id,
            granted_scopes=[mapping.scope_for("DocumentReference")],
            access_token_ciphertext=institutions._encrypt("token"),
            access_token_expires_at=datetime.now(UTC) + timedelta(minutes=10),
            refresh_token_ciphertext=None,
        )
        down = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(503))
        )
        async with down:
            with self.assertRaises(originals.OriginalError) as error:
                await self.fetch(FakeDB(self.institution, [row]), down)
        self.assertEqual(error.exception.reason, "unreachable")

    async def test_attachment_outside_the_fhir_base_is_never_followed(self):
        base = "http://institution-mock/medpark/fhir"
        self.assertEqual(
            originals._binary_url("Binary/bin-1", base), f"{base}/Binary/bin-1"
        )
        for url in (
            "http://evil.example/medpark/fhir/Binary/bin-1",
            "http://institution-mock/other/fhir/Binary/bin-1",
            "http://institution-mock/medpark/fhir/Patient/p1",
        ):
            self.assertIsNone(originals._binary_url(url, base), url)


class HasOriginalTests(unittest.TestCase):
    def row(self, resource, category="certificates"):
        return mapping.normalize(
            category, resource, external_id="inst-a", institution_name="A"
        )

    def test_attachments_in_every_place_an_institution_puts_them(self):
        cert = {
            "resourceType": "DocumentReference",
            "id": "d1",
            "type": {"coding": [{"system": mapping.DOCUMENT_TYPE_SYSTEM, "code": "illness_certificate"}]},
            "content": [{"attachment": {"url": "Binary/b1"}}],
        }
        self.assertTrue(self.row(cert)["has_original"])
        report = {"resourceType": "DiagnosticReport", "id": "r1", "presentedForm": [{"url": "Binary/b2"}]}
        self.assertEqual(mapping.attachment_url(report), "Binary/b2")
        prescription = {
            "resourceType": "MedicationRequest",
            "id": "m1",
            "extension": [
                {"url": mapping.ORIGINAL_DOCUMENT_EXTENSION, "valueAttachment": {"url": "Binary/b3"}}
            ],
        }
        self.assertTrue(self.row(prescription, "prescriptions")["has_original"])

    def test_record_without_a_file_says_so(self):
        self.assertFalse(
            self.row({"resourceType": "Condition", "id": "c1"}, "diagnoses")["has_original"]
        )
        self.assertIsNone(mapping.attachment_url({"content": "oops", "presentedForm": [None]}))


if __name__ == "__main__":
    unittest.main()
