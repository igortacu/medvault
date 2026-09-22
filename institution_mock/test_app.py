import base64
import hashlib
import unittest
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from institution_mock.app import ACCESS_LOG, RUNTIME, app

INSTITUTION = "imsp-scr-t-mosneaga"
CLIENT_ID = f"medvault-{INSTITUTION}"
CLIENT_SECRET = "DEV_PLACEHOLDER_SECRET_REPLACE_BEFORE_PROD"
REDIRECT_URI = "http://localhost:8000/api/v1/institutions/callback"


class InstitutionMockFlowTests(unittest.TestCase):
    def setUp(self):
        for collection in RUNTIME.values():
            collection.clear()
        ACCESS_LOG.clear()
        self.client = TestClient(app)

    def test_oauth_fhir_isolation_replay_and_revocation(self):
        verifier = "a" * 48
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        client_auth = (CLIENT_ID, CLIENT_SECRET)

        pushed = self.client.post(
            f"/{INSTITUTION}/oauth/par",
            auth=client_auth,
            data={
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "scope": "patient/Patient.read patient/Observation.read offline_access",
                "state": "expected-state",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "idnp": "2001234567890",
            },
        )
        self.assertEqual(pushed.status_code, 200)
        self.assertNotIn("2001234567890", str(RUNTIME))
        self.assertNotIn(pushed.json()["request_uri"], RUNTIME["par"])

        authorized = self.client.get(
            f"/{INSTITUTION}/oauth/authorize",
            params={"request_uri": pushed.json()["request_uri"]},
            follow_redirects=False,
        )
        query = parse_qs(urlparse(authorized.headers["location"]).query)
        self.assertEqual(query["state"], ["expected-state"])
        code = query["code"][0]

        exchanged = self.client.post(
            f"/{INSTITUTION}/oauth/token",
            auth=client_auth,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": verifier,
            },
        )
        self.assertEqual(exchanged.status_code, 200)
        access_token = exchanged.json()["access_token"]

        replayed = self.client.post(
            f"/{INSTITUTION}/oauth/token",
            auth=client_auth,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": verifier,
            },
        )
        self.assertEqual(replayed.status_code, 400)
        self.assertEqual(replayed.json()["detail"], "invalid_grant")

        headers = {"Authorization": f"Bearer {access_token}"}
        observations = self.client.get(
            f"/{INSTITUTION}/fhir/Observation", headers=headers
        )
        self.assertEqual(observations.status_code, 200)
        self.assertEqual(observations.json()["total"], 1)
        self.assertEqual(observations.headers["cache-control"], "no-store")

        refreshed = self.client.post(
            f"/{INSTITUTION}/oauth/token",
            auth=client_auth,
            data={
                "grant_type": "refresh_token",
                "refresh_token": exchanged.json()["refresh_token"],
            },
        )
        self.assertEqual(refreshed.status_code, 200)
        self.assertNotEqual(
            refreshed.json()["refresh_token"], exchanged.json()["refresh_token"]
        )
        replayed_refresh = self.client.post(
            f"/{INSTITUTION}/oauth/token",
            auth=client_auth,
            data={
                "grant_type": "refresh_token",
                "refresh_token": exchanged.json()["refresh_token"],
            },
        )
        self.assertEqual(replayed_refresh.status_code, 400)

        idor = self.client.get(
            f"/{INSTITUTION}/fhir/Observation",
            params={"patient": "Patient/pat-999"},
            headers=headers,
        )
        self.assertEqual(idor.status_code, 400)

        revoked = self.client.post(
            f"/{INSTITUTION}/oauth/revoke",
            auth=client_auth,
            data={"token": access_token},
        )
        self.assertEqual(revoked.status_code, 204)
        denied = self.client.get(f"/{INSTITUTION}/fhir/Observation", headers=headers)
        self.assertEqual(denied.status_code, 401)

        self.assertEqual([entry["httpStatus"] for entry in ACCESS_LOG], [200, 400, 401])
        self.assertNotIn("idnp", str(ACCESS_LOG).lower())


if __name__ == "__main__":
    unittest.main()
