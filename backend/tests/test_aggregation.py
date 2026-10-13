import asyncio
import importlib
import json
import os
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
from cryptography.fernet import Fernet

from app.aggregation import client, mapping, service
from app.documents import categories

institutions = importlib.import_module("app.institutions.router")

PATIENT = UUID("11111111-1111-1111-1111-111111111111")
CAREGIVER = UUID("33333333-3333-3333-3333-333333333333")
DT = "urn:medvault:document-type"


def normalize(category, resource):
    return mapping.normalize(
        category, resource, external_id="inst-a", institution_name="Inst A"
    )


class MappingTests(unittest.TestCase):
    def test_condition_maps_to_diagnosis_row(self):
        row = normalize(
            "diagnoses",
            {
                "resourceType": "Condition",
                "id": "c1",
                "code": {"text": "Essential hypertension"},
                "recordedDate": "2026-03-02",
                "recorder": {"display": "Dr. Popa"},
                "extension": [{"url": mapping.SPECIALTY_EXTENSION, "valueString": "Cardiology"}],
            },
        )
        self.assertEqual(row["type"], "diagnosis_record")
        self.assertEqual(row["title"], "Essential hypertension")
        self.assertEqual(str(row["document_date"]), "2026-03-02")
        self.assertEqual(row["practitioner_name"], "Dr. Popa")
        self.assertEqual(row["specialty"], "Cardiology")
        self.assertEqual(row["source"], "Inst A")
        self.assertEqual(row["original_path"], "institution:inst-a/Condition/c1")

    def test_id_is_stable_per_record_reference(self):
        res = {"resourceType": "Condition", "id": "c1", "code": {"text": "x"}}
        self.assertEqual(normalize("diagnoses", res)["id"], normalize("diagnoses", res)["id"])
        other = dict(res, id="c2")
        self.assertNotEqual(normalize("diagnoses", res)["id"], normalize("diagnoses", other)["id"])

    def test_same_resource_id_at_two_institutions_gets_different_ids(self):
        res = {"resourceType": "Condition", "id": "c1"}
        a = mapping.normalize("diagnoses", res, external_id="inst-a", institution_name="A")
        b = mapping.normalize("diagnoses", res, external_id="inst-b", institution_name="B")
        self.assertNotEqual(a["id"], b["id"])

    def test_document_reference_routed_by_document_type(self):
        cert = {
            "resourceType": "DocumentReference",
            "id": "d1",
            "type": {"coding": [{"system": DT, "code": "illness_certificate"}]},
            "description": "Sick note",
            "date": "2026-02-20T09:00:00Z",
        }
        self.assertIsNotNone(normalize("certificates", cert))
        self.assertIsNone(normalize("diagnoses", cert))

    def test_untyped_document_reference_is_dropped(self):
        self.assertIsNone(
            normalize("certificates", {"resourceType": "DocumentReference", "id": "d2"})
        )

    def test_only_inpatient_encounters_are_hospitalizations(self):
        base = {"resourceType": "Encounter", "id": "e1", "period": {"start": "2026-02-01T07:00:00Z"}}
        inpatient = normalize("other_med_info", dict(base, **{"class": {"code": "IMP"}}))
        self.assertEqual(inpatient["type"], "hospitalization_record")
        self.assertIsNone(normalize("other_med_info", dict(base, **{"class": {"code": "AMB"}})))

    def test_resource_type_must_belong_to_category(self):
        res = {"resourceType": "MedicationRequest", "id": "m1", "authoredOn": "2026-01-01"}
        self.assertIsNotNone(normalize("prescriptions", res))
        self.assertIsNone(normalize("diagnoses", res))

    def test_missing_fields_do_not_crash(self):
        row = normalize("prescriptions", {"resourceType": "Procedure", "id": "p1"})
        self.assertIsNone(row["title"])
        self.assertIsNone(row["document_date"])

    def test_malformed_payloads_never_raise_and_always_build_a_valid_row(self):
        hostile = [
            {"resourceType": "Encounter", "id": "e", "class": "IMP"},
            {"resourceType": "Encounter", "id": "e", "class": None},
            {"resourceType": "Encounter", "id": "e", "class": {"code": ["IMP"]}},
            {"resourceType": "Condition", "id": "c", "period": [1, 2]},
            {"resourceType": "Condition", "id": "c", "code": {"coding": "abc"}},
            {"resourceType": "Condition", "id": "c", "code": "just a string"},
            {"resourceType": "Condition", "id": "c", "code": {"coding": [{"system": DT, "code": ["x"]}]}},
            {"resourceType": "Condition", "id": "c", "extension": ["oops", None, 7]},
            {"resourceType": "Condition", "id": "c", "extension": [{"url": mapping.SPECIALTY_EXTENSION, "valueString": 5}]},
            {"resourceType": "Condition", "id": "c", "recorder": {"display": 12}},
            {"resourceType": "Condition", "id": "c", "asserter": [[], {}, 3]},
            {"resourceType": "Condition", "id": "c", "recordedDate": 20260302},
            {"resourceType": "Condition", "id": "c", "recordedDate": "not-a-date"},
            {"resourceType": "Condition", "id": {"x": 1}},
            {"resourceType": ["Condition"], "id": "c"},
            {"resourceType": "Condition", "id": "c", "performer": {"individual": {"actor": []}}},
            "a string, not a resource",
            None,
            42,
        ]
        for resource in hostile:
            for category in mapping.CATEGORY_RESOURCE_TYPES:
                row = normalize(category, resource)  # must not raise
                if row is not None:
                    categories.CategoryListItem(**row)  # and must be a valid list row


def bundle(*resources, next_url=None):
    links = [{"relation": "next", "url": next_url}] if next_url else []
    return {
        "resourceType": "Bundle",
        "link": links,
        "entry": [{"resource": r} for r in resources],
    }


class ClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        client.reset_breakers()
        self._backoff = client.RETRY_BACKOFF_SECONDS
        client.RETRY_BACKOFF_SECONDS = 0
        self.addCleanup(lambda: setattr(client, "RETRY_BACKOFF_SECONDS", self._backoff))

    def http(self, handler):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def search(self, http, key="inst-a"):
        return await client.search(
            http, institution_key=key, fhir_base="http://x/fhir", token="t", resource_type="Condition"
        )

    async def test_returns_resources_and_sends_bearer(self):
        seen = {}

        def handler(request):
            seen["auth"] = request.headers["authorization"]
            return httpx.Response(200, json=bundle({"id": "1"}))

        async with self.http(handler) as http:
            self.assertEqual(await self.search(http), [{"id": "1"}])
        self.assertEqual(seen["auth"], "Bearer t")

    async def test_follows_next_links(self):
        def handler(request):
            if "page2" in str(request.url):
                return httpx.Response(200, json=bundle({"id": "2"}))
            return httpx.Response(200, json=bundle({"id": "1"}, next_url="http://x/fhir/Condition?page2"))

        async with self.http(handler) as http:
            self.assertEqual([r["id"] for r in await self.search(http)], ["1", "2"])

    async def test_unauthorised_is_not_retried(self):
        calls = []

        def handler(request):
            calls.append(1)
            return httpx.Response(401)

        async with self.http(handler) as http:
            with self.assertRaises(client.SourceFailure) as raised:
                await self.search(http)
        self.assertEqual(raised.exception.status, "unauthorised")
        self.assertEqual(len(calls), 1)

    async def test_server_error_retried_once_then_unavailable(self):
        calls = []

        def handler(request):
            calls.append(1)
            return httpx.Response(503)

        async with self.http(handler) as http:
            with self.assertRaises(client.SourceFailure) as raised:
                await self.search(http)
        self.assertEqual(raised.exception.status, "unavailable")
        self.assertEqual(len(calls), 2)

    async def test_timeout_then_recovery_succeeds_on_retry(self):
        calls = []

        def handler(request):
            calls.append(1)
            if len(calls) == 1:
                raise httpx.ReadTimeout("slow", request=request)
            return httpx.Response(200, json=bundle({"id": "1"}))

        async with self.http(handler) as http:
            self.assertEqual(len(await self.search(http)), 1)

    async def test_persistent_timeout_reports_timeout(self):
        def handler(request):
            raise httpx.ConnectTimeout("down", request=request)

        async with self.http(handler) as http:
            with self.assertRaises(client.SourceFailure) as raised:
                await self.search(http)
        self.assertEqual(raised.exception.status, "timeout")

    async def test_next_link_off_the_fhir_base_is_not_followed(self):
        hosts = []

        def handler(request):
            hosts.append(str(request.url))
            return httpx.Response(
                200, json=bundle({"id": "1"}, next_url="http://169.254.169.254/latest/meta-data")
            )

        async with self.http(handler) as http:
            with self.assertRaises(client.SourceFailure) as raised:
                await self.search(http)
        self.assertEqual(raised.exception.status, "unavailable")
        self.assertEqual(len(hosts), 1)  # the foreign URL was never requested

    def test_next_link_origin_and_path_rules(self):
        base = "http://x/fhir"
        self.assertTrue(client._same_origin_under("http://x/fhir/Condition?page=2", base))
        for bad in (
            "http://evil/fhir/Condition",
            "https://x/fhir/Condition",
            "http://x:8080/fhir/Condition",
            "http://x/other/Condition",
            "http://x/fhirevil/Condition",
        ):
            self.assertFalse(client._same_origin_under(bad, base), bad)

    async def test_open_breaker_short_circuits_the_network(self):
        calls = []

        def handler(request):
            calls.append(1)
            return httpx.Response(200, json=bundle())

        for _ in range(client.BREAKER_THRESHOLD):
            client.record_failure("inst-a")
        async with self.http(handler) as http:
            with self.assertRaises(client.SourceFailure) as raised:
                await self.search(http)
            self.assertTrue(raised.exception.short_circuit)
            self.assertEqual(calls, [])
            self.assertEqual(await self.search(http, key="inst-other"), [])  # per institution

    async def test_success_closes_the_breaker(self):
        for _ in range(client.BREAKER_THRESHOLD):
            client.record_failure("inst-a")
        self.assertTrue(client._breaker_open("inst-a"))
        client.record_success("inst-a")
        self.assertFalse(client._breaker_open("inst-a"))


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class FakeDB:
    """Stands in for AsyncSession. `connections` are the rows the SQL function returns;
    `orm` the mutable InstitutionConnection objects. The connection row lock
    (SELECT ... FOR UPDATE) is an asyncio.Lock released by commit, like a real one."""

    def __init__(self, connections, institutions_, log=None):
        self.connections = connections
        self.institutions = institutions_
        self.orm = {
            c.id: SimpleNamespace(
                id=c.id,
                status="active",
                last_fetched_at=None,
                access_token_ciphertext=c.access_token_ciphertext,
                access_token_expires_at=c.access_token_expires_at,
                refresh_token_ciphertext=c.refresh_token_ciphertext,
            )
            for c in connections
        }
        self.audits = []
        self.commits = 0
        self.log = log if log is not None else []
        self._lock = asyncio.Lock()
        self._holds_lock = False

    async def execute(self, statement, params=None):
        if params is not None and "action" in params:
            self.audits.append(params)
            return None
        if params is not None and "uid" in params:
            self.log.append("rebind")
            return None
        if params is not None and "p" in params:
            return FakeResult(self.connections)
        if "institution_connections" in str(statement):
            await self._lock.acquire()
            self._holds_lock = True
            return FakeResult(list(self.orm.values())[:1] if self.orm else [])
        return FakeResult(self.institutions)

    async def get(self, model, key):
        return self.orm.get(key)

    async def commit(self):
        self.commits += 1
        self.log.append("commit")
        if self._holds_lock:
            self._holds_lock = False
            self._lock.release()


def make_institution(name, external_id):
    return SimpleNamespace(
        id=uuid4(), name=name, external_id=external_id,
        oauth_client_id="c", oauth_client_secret_ciphertext=b"s", oauth_secret_key_version=0,
    )


def make_connection(institution, *, scopes=None, expires_in=600, refresh=True):
    return SimpleNamespace(
        id=uuid4(),
        institution_id=institution.id,
        fhir_patient_ref="Patient/pat-1",
        granted_scopes=scopes
        if scopes is not None
        else [mapping.scope_for(t) for t in mapping.ALL_RESOURCE_TYPES],
        access_token_ciphertext=institutions._encrypt(f"token-{institution.external_id}"),
        access_token_expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
        refresh_token_ciphertext=institutions._encrypt("refresh") if refresh else None,
    )


def condition(rid="c1", title="Flu", **extra):
    return {"resourceType": "Condition", "id": rid, "code": {"text": title}, **extra}


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        client.reset_breakers()
        self._env = (institutions.MOCK_BASE_URL, client.RETRY_BACKOFF_SECONDS)
        institutions.MOCK_BASE_URL = "http://mock"
        client.RETRY_BACKOFF_SECONDS = 0
        self._key = os.environ.get("TOKEN_ENCRYPTION_KEY")
        os.environ["TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

        def restore():
            institutions.MOCK_BASE_URL, client.RETRY_BACKOFF_SECONDS = self._env
            if self._key is None:
                os.environ.pop("TOKEN_ENCRYPTION_KEY", None)
            else:
                os.environ["TOKEN_ENCRYPTION_KEY"] = self._key

        self.addCleanup(restore)
        self.a = make_institution("Inst A", "inst-a")
        self.b = make_institution("Inst B", "inst-b")

    def http(self, handler):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def run_fetch(self, db, handler, actor=PATIENT, category="diagnoses"):
        async with self.http(handler) as http:
            return await service.fetch_institutional(
                SimpleNamespace(user_id=str(actor), db=db), category, PATIENT, http=http
            )

    async def test_no_connections_means_no_sources(self):
        db = FakeDB([], [])
        items, sources = await self.run_fetch(db, lambda r: httpx.Response(500))
        self.assertEqual((items, sources), ([], []))

    async def test_failing_institution_degrades_only_itself(self):
        db = FakeDB([make_connection(self.a), make_connection(self.b)], [self.a, self.b])

        def handler(request):
            if "/inst-b/" in request.url.path:
                return httpx.Response(500)
            if request.url.path.endswith("/Condition"):
                return httpx.Response(200, json=bundle(condition()))
            return httpx.Response(200, json=bundle())

        items, sources = await self.run_fetch(db, handler)

        self.assertEqual([i["title"] for i in items], ["Flu"])
        by_name = {s.institution: s for s in sources}
        self.assertEqual(by_name["Inst A"].status, "ok")
        self.assertEqual(by_name["Inst A"].count, 1)
        self.assertEqual(by_name["Inst B"].status, "unavailable")
        self.assertEqual(len(db.audits), 2)
        self.assertEqual(sorted(a["outcome"] for a in db.audits), ["failure", "success"])
        self.assertEqual(len([c for c in db.orm.values() if c.last_fetched_at]), 1)

    async def test_malformed_record_from_one_institution_does_not_fail_the_page(self):
        db = FakeDB([make_connection(self.a), make_connection(self.b)], [self.a, self.b])

        def handler(request):
            if request.url.path.endswith("/Condition"):
                if "/inst-b/" in request.url.path:
                    return httpx.Response(
                        200,
                        json=bundle(
                            {"resourceType": "Condition", "id": "bad", "extension": ["x"],
                             "recorder": {"display": 7}, "period": []},
                            {"resourceType": "Encounter", "id": "x", "class": "IMP"},
                            "garbage",
                            condition("ok-b", "Fine B"),
                        ),
                    )
                return httpx.Response(200, json=bundle(condition("a1", "Fine A")))
            return httpx.Response(200, json=bundle())

        items, sources = await self.run_fetch(db, handler)
        titles = sorted(i["title"] for i in items if i["title"])
        self.assertEqual(titles, ["Fine A", "Fine B"])
        self.assertEqual({s.status for s in sources}, {"ok"})

    async def test_requests_use_each_institutions_own_token(self):
        db = FakeDB([make_connection(self.a), make_connection(self.b)], [self.a, self.b])
        tokens = {}

        def handler(request):
            tokens.setdefault(request.url.path.split("/")[1], set()).add(
                request.headers["authorization"]
            )
            return httpx.Response(200, json=bundle())

        await self.run_fetch(db, handler)
        self.assertEqual(tokens["inst-a"], {"Bearer token-inst-a"})
        self.assertEqual(tokens["inst-b"], {"Bearer token-inst-b"})

    async def test_only_granted_resource_types_are_requested(self):
        conn = make_connection(self.a, scopes=[mapping.scope_for("Condition")])
        db = FakeDB([conn], [self.a])
        paths = []

        def handler(request):
            paths.append(request.url.path)
            return httpx.Response(200, json=bundle())

        await self.run_fetch(db, handler)
        self.assertEqual(paths, ["/inst-a/fhir/Condition"])

    async def test_connection_without_category_scopes_needs_reconnect(self):
        for scopes in (["patient/Patient.read", "patient/Observation.read"], None):
            conn = make_connection(self.a, scopes=scopes or [])
            conn.granted_scopes = scopes  # None models a NULL column
            db = FakeDB([conn], [self.a])
            calls = []

            def handler(request):
                calls.append(1)
                return httpx.Response(200, json=bundle())

            _, sources = await self.run_fetch(db, handler)
            self.assertEqual(sources[0].status, "needs_reconnect")
            self.assertEqual(calls, [])

    async def test_unauthorised_source_is_reported(self):
        db = FakeDB([make_connection(self.a)], [self.a])
        _, sources = await self.run_fetch(db, lambda r: httpx.Response(401))
        self.assertEqual(sources[0].status, "unauthorised")

    async def test_db_connection_is_released_before_calling_institutions(self):
        log = []
        db = FakeDB([make_connection(self.a)], [self.a], log=log)

        def handler(request):
            log.append("http")
            return httpx.Response(200, json=bundle())

        await self.run_fetch(db, handler)
        self.assertLess(log.index("commit"), log.index("http"))
        # ...and the RLS user is restored before the audit/last_fetched writes.
        self.assertGreater(len(log) - 1 - log[::-1].index("rebind"), log.index("http"))

    async def test_caregiver_with_expired_token_cannot_refresh(self):
        conn = make_connection(self.a, expires_in=-60)
        db = FakeDB([conn], [self.a])
        calls = []

        def handler(request):
            calls.append(request.url.path)
            return httpx.Response(200, json=bundle())

        _, sources = await self.run_fetch(db, handler, actor=CAREGIVER)
        self.assertEqual(sources[0].status, "unavailable")
        self.assertEqual(calls, [])  # no refresh, no FHIR call
        self.assertEqual(db.audits[0]["actor_user_id"], str(CAREGIVER))
        self.assertEqual(db.audits[0]["subject_patient_id"], str(PATIENT))
        self.assertIsNone(db.orm[conn.id].last_fetched_at)
        self.assertEqual(db.orm[conn.id].status, "active")

    async def test_owner_refreshes_expired_token_and_persists_the_rotation(self):
        conn = make_connection(self.a, expires_in=-60)
        db = FakeDB([conn], [self.a])
        seen = []

        def handler(request):
            seen.append((request.method, request.url.path, request.headers["authorization"]))
            if request.url.path.endswith("/oauth/token"):
                return httpx.Response(
                    200, json={"access_token": "fresh", "expires_in": 900, "refresh_token": "r2"}
                )
            return httpx.Response(200, json=bundle())

        _, sources = await self.run_fetch(db, handler)
        self.assertEqual(sources[0].status, "ok")
        fhir_calls = [s for s in seen if "/fhir/" in s[1]]
        self.assertTrue(all(c[2] == "Bearer fresh" for c in fhir_calls))
        stored = db.orm[conn.id]
        self.assertEqual(institutions._decrypt(stored.access_token_ciphertext), "fresh")
        self.assertEqual(institutions._decrypt(stored.refresh_token_ciphertext), "r2")
        self.assertGreaterEqual(db.commits, 2)  # rotation committed before the fetch

    async def test_invalid_grant_expires_the_connection(self):
        for code in (400, 401):
            conn = make_connection(self.a, expires_in=-60)
            db = FakeDB([conn], [self.a])

            def handler(request, code=code):
                if request.url.path.endswith("/oauth/token"):
                    return httpx.Response(code, json={"error": "invalid_grant"})
                return httpx.Response(200, json=bundle())

            _, sources = await self.run_fetch(db, handler)
            self.assertEqual(sources[0].status, "unauthorised")
            self.assertEqual(db.orm[conn.id].status, "expired")

    async def test_transient_refresh_failures_do_not_expire_the_connection(self):
        def timeout(request):
            raise httpx.ReadTimeout("slow", request=request)

        cases = [
            (lambda r: httpx.Response(503), "unavailable"),
            (lambda r: httpx.Response(200, json={"oops": 1}), "unavailable"),
            (timeout, "timeout"),
        ]
        for token_handler, expected in cases:
            conn = make_connection(self.a, expires_in=-60)
            db = FakeDB([conn], [self.a])

            def handler(request, token_handler=token_handler):
                if request.url.path.endswith("/oauth/token"):
                    return token_handler(request)
                return httpx.Response(200, json=bundle())

            _, sources = await self.run_fetch(db, handler)
            self.assertEqual(sources[0].status, expected)
            self.assertEqual(db.orm[conn.id].status, "active")
            self.assertGreaterEqual(db.commits, 1)  # row lock released

    async def test_wrong_encryption_key_does_not_expire_the_connection(self):
        conn = make_connection(self.a, expires_in=-60)
        db = FakeDB([conn], [self.a])
        os.environ["TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()  # rotated away
        _, sources = await self.run_fetch(db, lambda r: httpx.Response(200, json=bundle()))
        self.assertEqual(sources[0].status, "unavailable")
        self.assertEqual(db.orm[conn.id].status, "active")

    async def test_missing_connection_row_does_not_crash_the_page(self):
        conn = make_connection(self.a, expires_in=-60)
        db = FakeDB([conn], [self.a])
        db.orm.clear()  # row vanished (revoked/deleted) between the SQL function and the lock
        _, sources = await self.run_fetch(db, lambda r: httpx.Response(200, json=bundle()))
        self.assertEqual(sources[0].status, "unavailable")

        fresh = make_connection(self.a)
        db = FakeDB([fresh], [self.a])
        db.orm.clear()  # fresh token, but the later last_fetched_at lookup finds nothing
        _, sources = await self.run_fetch(db, lambda r: httpx.Response(200, json=bundle()))
        self.assertEqual(sources[0].status, "ok")

    async def test_parallel_requests_refresh_once(self):
        """Rotating refresh tokens: a second concurrent refresh would burn the first."""
        conn = make_connection(self.a, expires_in=-60)
        db = FakeDB([conn], [self.a])
        refreshes = []
        used_refresh = set()

        async def handler(request):
            if request.url.path.endswith("/oauth/token"):
                body = request.content.decode()
                token = body.split("refresh_token=")[1].split("&")[0]
                refreshes.append(token)
                await asyncio.sleep(0.01)  # a slow token endpoint widens the race window
                if token in used_refresh:
                    return httpx.Response(400, json={"error": "invalid_grant"})
                used_refresh.add(token)
                return httpx.Response(
                    200, json={"access_token": "fresh", "expires_in": 900, "refresh_token": "r2"}
                )
            return httpx.Response(200, json=bundle())

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            ctx = SimpleNamespace(user_id=str(PATIENT), db=db)
            results = await asyncio.gather(
                *(service.fetch_institutional(ctx, "diagnoses", PATIENT, http=http) for _ in range(5))
            )
        self.assertEqual(len(refreshes), 1)
        self.assertEqual({r[1][0].status for r in results}, {"ok"})
        self.assertEqual(db.orm[conn.id].status, "active")

    async def test_slow_institution_times_out_and_trips_the_breaker(self):
        old = service.SOURCE_DEADLINE_SECONDS
        service.SOURCE_DEADLINE_SECONDS = 0.05
        self.addCleanup(lambda: setattr(service, "SOURCE_DEADLINE_SECONDS", old))

        async def slow(request):
            await asyncio.sleep(5)
            return httpx.Response(200, json=bundle())

        for _ in range(client.BREAKER_THRESHOLD):
            db = FakeDB([make_connection(self.a)], [self.a])
            _, sources = await self.run_fetch(db, slow)
            self.assertEqual(sources[0].status, "timeout")
        self.assertTrue(client._breaker_open("inst-a"))

        calls = []

        def handler(request):
            calls.append(1)
            return httpx.Response(200, json=bundle())

        db = FakeDB([make_connection(self.a)], [self.a])
        _, sources = await self.run_fetch(db, handler)
        self.assertEqual(sources[0].status, "unavailable")
        self.assertEqual(calls, [])  # skipped by the breaker

    async def test_one_failing_resource_type_counts_once_not_per_type(self):
        db = FakeDB([make_connection(self.a)], [self.a])
        # Diagnoses asks for 2 resource types; one page load is one breaker failure.
        await self.run_fetch(db, lambda r: httpx.Response(500))
        failures, _ = client._breaker["inst-a"]
        self.assertEqual(failures, 1)

    async def test_breaker_short_circuits_are_not_counted_as_new_failures(self):
        for _ in range(client.BREAKER_THRESHOLD):
            client.record_failure("inst-a")
        _, open_until = client._breaker["inst-a"]
        db = FakeDB([make_connection(self.a)], [self.a])
        await self.run_fetch(db, lambda r: httpx.Response(200, json=bundle()))
        self.assertEqual(client._breaker["inst-a"][1], open_until)  # window not extended

    async def test_audit_never_contains_record_content(self):
        db = FakeDB([make_connection(self.a)], [self.a])

        def handler(request):
            return httpx.Response(200, json=bundle(condition(title="SECRET-DIAGNOSIS")))

        await self.run_fetch(db, handler)
        self.assertNotIn("SECRET-DIAGNOSIS", json.dumps(db.audits))


if __name__ == "__main__":
    unittest.main()
