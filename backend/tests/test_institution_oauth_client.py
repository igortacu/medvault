import base64
import hashlib
import importlib
import json
import os
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import httpx
from cryptography.fernet import Fernet

from institution_mock.app import ACCESS_LOG, FIXTURE_DATA, RUNTIME
from institution_mock.app import app as mock_app

integration = importlib.import_module("app.institutions.router")
INSTITUTION_ID = "imsp-scr-t-mosneaga"
USER_ID = "11111111-1111-1111-1111-111111111111"


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def setex(self, key, ttl, value):
        self.values[key] = (ttl, value)

    async def getdel(self, key):
        entry = self.values.pop(key, None)
        return entry[1] if entry else None


class FakeScalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeDB:
    def __init__(self, *results, institutions=()):
        self.results = list(results)
        self.institutions = list(institutions)
        self.added = []
        self.audit_actions = []

    @property
    def last_added(self):
        return self.added[-1]

    async def scalar(self, _statement):
        return self.results.pop(0) if self.results else None

    async def scalars(self, _statement):
        return FakeScalars(self.institutions)

    async def execute(self, _statement, params=None):
        if params and "action" in params:
            self.audit_actions.append(params["action"])

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = uuid4()


def make_institution(external_id, institution_id=None):
    return SimpleNamespace(
        external_id=external_id,
        type="public",
        oauth_client_id=f"medvault-{external_id}",
        oauth_client_secret_ciphertext=b"DEV_PLACEHOLDER_SECRET_REPLACE_BEFORE_PROD",
        oauth_secret_key_version=0,
        id=institution_id or uuid4(),
        supported_scopes=[
            "patient/Patient.read",
            "patient/Observation.read",
            "offline_access",
        ],
    )


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
        self.institution = make_institution(
            INSTITUTION_ID, UUID("22222222-2222-2222-2222-222222222222")
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
        dev_patient = next(
            f"Patient/{p['id']}"
            for p in FIXTURE_DATA[INSTITUTION_ID]["Patient"]
            if p["identifier"][0]["value"] == "2001234567890"
        )
        self.assertEqual(
            observations.json()["total"],
            sum(
                o["subject"]["reference"] == dev_patient
                for o in FIXTURE_DATA[INSTITUTION_ID]["Observation"]
            ),
        )
        encrypted = integration._encrypt(tokens["access_token"])
        self.assertNotIn(tokens["access_token"].encode(), encrypted)
        self.assertEqual(integration._decrypt(encrypted), tokens["access_token"])

    async def test_connect_stores_pkce_state_without_idnp(self):
        db = FakeDB(self.institution, None)
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
        self.assertEqual(result.connection_id, db.last_added.id)
        self.assertEqual(db.last_added.status, "authorizing")
        self.assertEqual(db.audit_actions, ["connection.requested"])

    async def _connect_public(self, db, institution_ids=None):
        context = SimpleNamespace(user_id=USER_ID, db=db)
        transport = httpx.ASGITransport(app=mock_app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://institution-mock",
            follow_redirects=False,
        ) as client:
            return await integration.connect_public_institutions(
                integration.ConnectPublicRequest(
                    idnp="2001234567890",
                    consent_text_version="2026-10",
                    institution_ids=institution_ids,
                ),
                context,
                client,
            )

    def _states(self):
        return [
            json.loads(value)
            for _, value in integration.redis_client.values.values()
        ]

    async def test_connect_public_chains_every_institution_under_one_consent(self):
        first = self.institution
        second = make_institution("imsp-scm-balti")
        db = FakeDB(institutions=[first, second])

        result = await self._connect_public(db)

        self.assertEqual(len(result.connections), 2)
        self.assertEqual({c.status for c in result.connections}, {"authorizing"})
        self.assertEqual({c.consent_text_version for c in db.added}, {"2026-10"})
        self.assertEqual({c.origin for c in db.added}, {"auto_public"})
        self.assertIn(f"/{INSTITUTION_ID}/oauth/authorize", result.authorize_url)

        states = self._states()
        self.assertTrue(all(s["batch"] for s in states))
        self.assertNotIn("2001234567890", json.dumps(states))
        # The first institution's callback hands on to the second, which ends
        # the chain.
        tails = [s["next_url"] for s in states]
        self.assertIn(None, tails)
        self.assertIn(
            "/imsp-scm-balti/oauth/authorize", next(t for t in tails if t)
        )

    async def test_connect_public_only_connects_chosen_institutions(self):
        skipped = make_institution("imsp-scm-balti")
        db = FakeDB(institutions=[self.institution, skipped])

        result = await self._connect_public(db, [self.institution.id])

        self.assertEqual(
            [c.institution_id for c in result.connections], [self.institution.id]
        )
        self.assertEqual(len(db.added), 1)
        self.assertEqual(len(self._states()), 1)

    def test_connect_public_rejects_an_empty_selection(self):
        with self.assertRaises(ValueError):
            integration.ConnectPublicRequest(
                idnp="2001234567890",
                consent_text_version="2026-10",
                institution_ids=[],
            )

    async def test_connect_public_marks_unreachable_institution_failed(self):
        unknown = make_institution("not-a-real-institution")
        db = FakeDB(institutions=[self.institution, unknown])

        result = await self._connect_public(db)

        statuses = {c.institution_id: c.status for c in result.connections}
        self.assertEqual(statuses[self.institution.id], "authorizing")
        self.assertEqual(statuses[unknown.id], "error")
        self.assertIsNotNone(result.authorize_url)
        self.assertEqual(len(self._states()), 1)

    async def test_connect_public_skips_already_connected(self):
        live = SimpleNamespace(status="active")
        db = FakeDB(live, institutions=[self.institution])

        result = await self._connect_public(db)

        self.assertIsNone(result.authorize_url)
        self.assertEqual(result.connections, [])
        self.assertEqual(db.added, [])

    async def test_abandoned_authorization_does_not_block_retry(self):
        stale = SimpleNamespace(
            status="authorizing",
            consented_at=datetime.now(UTC) - timedelta(minutes=10),
            failure_reason=None,
        )
        context = SimpleNamespace(user_id=USER_ID, db=FakeDB(stale))

        self.assertIsNone(
            await integration._live_connection(context, self.institution.id)
        )
        self.assertEqual(stale.status, "error")
        self.assertEqual(stale.failure_reason, "authorization_abandoned")

    async def _callback(self, db, state, **params):
        context = SimpleNamespace(user_id=USER_ID, db=db)
        return await integration.institution_callback(
            state, ctx=context, client=None, **params
        )

    def _seed_state(self, connection, next_url=None, batch=False):
        integration.redis_client.values["institution_oauth:s1"] = (
            120,
            json.dumps(
                {
                    "user_id": USER_ID,
                    "connection_id": str(connection.id),
                    "code_verifier": "v",
                    "next_url": next_url,
                    "batch": batch,
                }
            ),
        )

    def _pending_connection(self):
        return SimpleNamespace(
            id=uuid4(),
            institution_id=self.institution.id,
            institution=self.institution,
            status="authorizing",
            failure_reason=None,
        )

    async def test_callback_hands_on_to_next_institution_in_chain(self):
        connection = self._pending_connection()
        self._seed_state(connection, next_url="http://mock/next/authorize", batch=True)

        response = await self._callback(FakeDB(connection), "s1", error="access_denied")

        self.assertEqual(response.headers["location"], "http://mock/next/authorize")
        self.assertEqual(connection.status, "no_match")

    async def test_callback_returns_to_page_at_end_of_chain(self):
        connection = self._pending_connection()
        self._seed_state(connection, batch=True)

        response = await self._callback(FakeDB(connection), "s1", error="access_denied")

        self.assertTrue(
            response.headers["location"].endswith("/institutions?connection=done")
        )

    async def test_callback_with_unknown_state_redirects_instead_of_erroring(self):
        response = await self._callback(FakeDB(), "missing", code="c")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response.headers["location"].endswith("/institutions?connection=expired")
        )


if __name__ == "__main__":
    unittest.main()
