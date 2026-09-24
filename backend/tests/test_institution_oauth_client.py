import base64
import hashlib
import importlib
import os
import unittest
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import httpx
from cryptography.fernet import Fernet

from institution_mock.app import ACCESS_LOG, RUNTIME
from institution_mock.app import app as mock_app

integration = importlib.import_module("app.institutions.router")
INSTITUTION_ID = "imsp-scr-t-mosneaga"
USER_ID = "11111111-1111-1111-1111-111111111111"


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def setex(self, key, ttl, value):
        self.values[key] = (ttl, value)


class FakeDB:
    def __init__(self, institution):
        self.results = [institution, None]
        self.added = None

    async def scalar(self, _statement):
        return self.results.pop(0)

    def add(self, value):
        self.added = value

    async def flush(self):
        self.added.id = uuid4()


class InstitutionOAuthClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for collection in RUNTIME.values():
            collection.clear()
        ACCESS_LOG.clear()
        self.previous_base_url = integration.MOCK_BASE_URL
        integration.MOCK_BASE_URL = "http://institution-mock"
        self.previous_redis = integration.redis_client
        integration.redis_client = FakeRedis()
        self.previous_key = os.environ.get("TOKEN_ENCRYPTION_KEY")
        os.environ["TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
        self.institution = SimpleNamespace(
            external_id=INSTITUTION_ID,
            oauth_client_id=f"medvault-{INSTITUTION_ID}",
            oauth_client_secret_ciphertext=b"DEV_PLACEHOLDER_SECRET_REPLACE_BEFORE_PROD",
            oauth_secret_key_version=0,
            id=UUID("22222222-2222-2222-2222-222222222222"),
            supported_scopes=[
                "patient/Patient.read",
                "patient/Observation.read",
                "offline_access",
            ],
        )

    def tearDown(self):
        integration.MOCK_BASE_URL = self.previous_base_url
        integration.redis_client = self.previous_redis
        if self.previous_key is None:
            os.environ.pop("TOKEN_ENCRYPTION_KEY", None)
        else:
            os.environ["TOKEN_ENCRYPTION_KEY"] = self.previous_key

    async def test_pkce_token_and_live_fhir_round_trip(self):
        verifier = "v" * 64
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        transport = httpx.ASGITransport(app=mock_app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://institution-mock",
            follow_redirects=False,
        ) as client:
            pushed = await integration._post_oauth(
                client,
                integration._endpoint(self.institution, "par"),
                self.institution,
                {
                    "client_id": self.institution.oauth_client_id,
                    "redirect_uri": integration.CALLBACK_URL,
                    "scope": "patient/Observation.read offline_access",
                    "state": "state-value",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "idnp": "2001234567890",
                },
            )
            authorized = await client.get(
                integration._endpoint(self.institution, "authorize"),
                params={"request_uri": pushed["request_uri"]},
            )
            code = parse_qs(urlparse(authorized.headers["location"]).query)["code"][0]
            tokens = await integration._post_oauth(
                client,
                integration._endpoint(self.institution, "token"),
                self.institution,
                {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": integration.CALLBACK_URL,
                    "code_verifier": verifier,
                },
            )
            observations = await client.get(
                f"{integration._endpoint(self.institution, 'fhir')}/Observation",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )

        self.assertEqual(observations.status_code, 200)
        self.assertEqual(observations.json()["total"], 1)
        encrypted = integration._encrypt(tokens["access_token"])
        self.assertNotIn(tokens["access_token"].encode(), encrypted)
        self.assertEqual(integration._decrypt(encrypted), tokens["access_token"])

    async def test_connect_stores_pkce_state_without_idnp(self):
        db = FakeDB(self.institution)
        context = SimpleNamespace(user_id=USER_ID, db=db)
        transport = httpx.ASGITransport(app=mock_app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://institution-mock",
            follow_redirects=False,
        ) as client:
            result = await integration.connect_institution(
                self.institution.id,
                integration.ConnectRequest(
                    idnp="2001234567890",
                    consent_text_version="2026-09",
                ),
                context,
                client,
            )

        stored = next(iter(integration.redis_client.values.values()))[1]
        self.assertNotIn("2001234567890", stored)
        self.assertIn("code_verifier", stored)
        self.assertEqual(result.connection_id, db.added.id)
        self.assertEqual(db.added.status, "authorizing")


if __name__ == "__main__":
    unittest.main()
