import base64
import hashlib
import importlib.util
import re
import unittest
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from institution_mock.app import ACCESS_LOG, FIXTURE_DATA, RUNTIME, app

INSTITUTION = "imsp-scr-t-mosneaga"
DEV_IDNP = "2001234567890"
ROOT = Path(__file__).resolve().parent.parent
# Planted IDNPs (README.md); stable because the generator is seeded.
IN_PROGRESS_IDNP = "0944635038347"
ZERO_RECORD_IDNP = "0769711762628"
CRITICAL_IDNP = "0798727493313"
INJECTION_IDNP = "0715591277785"
REVOKED_IDNP = "0357073380867"
NO_MATCH_IDNP = "0549206992192"
CLIENT_ID = f"medvault-{INSTITUTION}"
CLIENT_SECRET = "DEV_PLACEHOLDER_SECRET_REPLACE_BEFORE_PROD"
REDIRECT_URI = "http://localhost:8000/api/v1/institutions/callback"


def patient_ref(institution, idnp=DEV_IDNP):
    for patient in FIXTURE_DATA[institution]["Patient"]:
        if patient["identifier"][0]["value"] == idnp:
            return f"Patient/{patient['id']}"
    return None


def owned(institution, rtype, idnp=DEV_IDNP):
    ref = patient_ref(institution, idnp)
    return [
        item
        for item in FIXTURE_DATA[institution].get(rtype, [])
        if (item.get("subject") or item.get("patient"))["reference"] == ref
    ]


class InstitutionMockFlowTests(unittest.TestCase):
    def setUp(self):
        for collection in RUNTIME.values():
            collection.clear()
        ACCESS_LOG.clear()
        self.client = TestClient(app)

    def _token(self, scope, institution=INSTITUTION, idnp=DEV_IDNP, full=False):
        client_id = f"medvault-{institution}"
        verifier = "b" * 48
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        auth = (client_id, CLIENT_SECRET)
        pushed = self.client.post(
            f"/{institution}/oauth/par",
            auth=auth,
            data={
                "client_id": client_id,
                "redirect_uri": REDIRECT_URI,
                "scope": scope,
                "state": "s",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "idnp": idnp,
            },
        )
        authorized = self.client.get(
            f"/{institution}/oauth/authorize",
            params={"request_uri": pushed.json()["request_uri"]},
            follow_redirects=False,
        )
        code = parse_qs(urlparse(authorized.headers["location"]).query)["code"][0]
        exchanged = self.client.post(
            f"/{institution}/oauth/token",
            auth=auth,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "code_verifier": verifier,
            },
        )
        if full:
            return exchanged.json()
        return {"Authorization": f"Bearer {exchanged.json()['access_token']}"}

    def test_resource_search_is_scoped_to_token_patient_and_scope(self):
        headers = self._token("patient/Condition.read patient/Patient.read")
        ok = self.client.get(f"/{INSTITUTION}/fhir/Encounter", headers=headers)
        self.assertEqual(ok.status_code, 403)  # Encounter scope was not granted

        headers = self._token("patient/Encounter.read patient/Patient.read")
        found = self.client.get(f"/{INSTITUTION}/fhir/Encounter", headers=headers)
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.json()["total"], len(owned(INSTITUTION, "Encounter")))
        self.assertTrue(
            all(
                e["resource"]["subject"]["reference"] == patient_ref(INSTITUTION)
                for e in found.json()["entry"]
            )
        )
        rejected = self.client.get(
            f"/{INSTITUTION}/fhir/Encounter",
            params={"patient": "Patient/pat-999"},
            headers=headers,
        )
        self.assertEqual(rejected.status_code, 400)
        unknown = self.client.get(f"/{INSTITUTION}/fhir/NotAType", headers=headers)
        self.assertEqual(unknown.status_code, 404)

    def test_every_optional_fixture_is_served_to_its_institution(self):
        from institution_mock.app import OPTIONAL_RESOURCE_TYPES

        for institution in FIXTURE_DATA:
            for rtype in OPTIONAL_RESOURCE_TYPES:
                headers = self._token(f"patient/{rtype}.read", institution)
                res = self.client.get(f"/{institution}/fhir/{rtype}", headers=headers)
                self.assertEqual(res.status_code, 200, (institution, rtype))
                self.assertEqual(
                    res.json()["total"], len(owned(institution, rtype)), (institution, rtype)
                )

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
        self.assertEqual(
            observations.json()["total"], len(owned(INSTITUTION, "Observation"))
        )
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


    # --- planted cases (README.md) -------------------------------------------------------
    def test_no_match_idnp_is_denied_everywhere(self):
        for institution in FIXTURE_DATA:
            verifier = "c" * 48
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                .rstrip(b"=")
                .decode()
            )
            client_id = f"medvault-{institution}"
            pushed = self.client.post(
                f"/{institution}/oauth/par",
                auth=(client_id, CLIENT_SECRET),
                data={
                    "client_id": client_id,
                    "redirect_uri": REDIRECT_URI,
                    "scope": "patient/Patient.read",
                    "state": "s",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "idnp": NO_MATCH_IDNP,
                },
            )
            authorized = self.client.get(
                f"/{institution}/oauth/authorize",
                params={"request_uri": pushed.json()["request_uri"]},
                follow_redirects=False,
            )
            query = parse_qs(urlparse(authorized.headers["location"]).query)
            self.assertEqual(query["error"], ["access_denied"], institution)

    def test_zero_record_patient_gets_empty_bundles(self):
        from institution_mock.app import OPTIONAL_RESOURCE_TYPES

        for institution in ("imsp-institutul-oncologic", "imsp-scm-balti"):
            scope = " ".join(
                f"patient/{t}.read" for t in ("Observation", *OPTIONAL_RESOURCE_TYPES)
            )
            headers = self._token(scope, institution, ZERO_RECORD_IDNP)
            for rtype in ("Observation", *OPTIONAL_RESOURCE_TYPES):
                res = self.client.get(f"/{institution}/fhir/{rtype}", headers=headers)
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.json()["total"], 0, (institution, rtype))

    def test_in_progress_hospitalization_has_no_discharge(self):
        institution = "imsp-scm-sfanta-treime"
        headers = self._token(
            "patient/Encounter.read patient/DocumentReference.read", institution, IN_PROGRESS_IDNP
        )
        stays = self.client.get(
            f"/{institution}/fhir/Encounter", params={"class": "IMP"}, headers=headers
        ).json()
        self.assertEqual(stays["total"], 1)
        stay = stays["entry"][0]["resource"]
        self.assertEqual(stay["status"], "in-progress")
        self.assertNotIn("end", stay["period"])
        documents = self.client.get(
            f"/{institution}/fhir/DocumentReference", headers=headers
        ).json()["entry"]
        types = {e["resource"]["type"]["coding"][0]["code"] for e in documents}
        self.assertIn("hospitalization_certificate", types)
        self.assertNotIn("discharge_summary", types)

    def test_critical_values_are_flagged(self):
        institution = "imsp-scm-balti"
        headers = self._token(
            "patient/Observation.read patient/DiagnosticReport.read", institution, CRITICAL_IDNP
        )
        observations = self.client.get(f"/{institution}/fhir/Observation", headers=headers)
        flags = [
            e["resource"]["interpretation"][0]["coding"][0]["code"]
            for e in observations.json()["entry"]
            if "interpretation" in e["resource"]
        ]
        self.assertGreaterEqual(flags.count("HH"), 3)
        reports = self.client.get(f"/{institution}/fhir/DiagnosticReport", headers=headers)
        self.assertTrue(
            any("VALORI CRITICE" in e["resource"]["conclusion"] for e in reports.json()["entry"])
        )

    def test_caregiver_visibility_case_has_certificates_and_a_stay(self):
        headers = self._token("patient/Encounter.read patient/DocumentReference.read")
        stays = self.client.get(
            f"/{INSTITUTION}/fhir/Encounter", params={"class": "IMP"}, headers=headers
        ).json()
        self.assertEqual(stays["total"], 1)
        self.assertIn("end", stays["entry"][0]["resource"]["period"])
        certificates = self.client.get(
            f"/{INSTITUTION}/fhir/DocumentReference",
            params={"type": "urn:medvault:document-type|hospitalization_certificate"},
            headers=headers,
        ).json()
        self.assertEqual(certificates["total"], 1)

    def test_prompt_injection_fixture_is_present(self):
        institution = "terramed"
        headers = self._token("patient/DocumentReference.read", institution, INJECTION_IDNP)
        documents = self.client.get(
            f"/{institution}/fhir/DocumentReference", headers=headers
        ).json()["entry"]
        injected = [
            e["resource"]
            for e in documents
            if "ignore all previous instructions" in e["resource"]["description"]
        ]
        self.assertEqual(len(injected), 1)
        url = injected[0]["content"][0]["attachment"]["url"]
        pdf = self.client.get(f"/{institution}/fhir/{url}", headers=headers)
        self.assertEqual(pdf.status_code, 200)
        self.assertIn(b"ignore all previous instructions", pdf.content)
        self.assertIn(b"1.00 g", pdf.content)  # drawn white-on-white: hidden on the page

    def test_planted_revocation_kills_tokens_after_the_first_read(self):
        institution = "medpark"
        tokens = self._token(
            "patient/Observation.read offline_access", institution, REVOKED_IDNP, full=True
        )
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        first = self.client.get(f"/{institution}/fhir/Observation", headers=headers)
        self.assertEqual(first.status_code, 200)
        second = self.client.get(f"/{institution}/fhir/Observation", headers=headers)
        self.assertEqual(second.status_code, 401)
        refreshed = self.client.post(
            f"/{institution}/oauth/token",
            auth=(f"medvault-{institution}", CLIENT_SECRET),
            data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]},
        )
        self.assertEqual(refreshed.json()["detail"], "invalid_grant")
        # The same patient's other institution keeps working.
        other = self._token("patient/Observation.read", INSTITUTION, REVOKED_IDNP)
        for _ in range(2):
            ok = self.client.get(f"/{INSTITUTION}/fhir/Observation", headers=other)
            self.assertEqual(ok.status_code, 200)

    # --- Binary ------------------------------------------------------------------------------
    def test_binary_is_served_only_for_the_token_patients_resources(self):
        headers = self._token("patient/DocumentReference.read")
        mine = owned(INSTITUTION, "DocumentReference")[0]
        url = mine["content"][0]["attachment"]["url"]
        pdf = self.client.get(f"/{INSTITUTION}/fhir/{url}", headers=headers)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.headers["content-type"], "application/pdf")
        self.assertEqual(pdf.headers["cache-control"], "no-store")
        self.assertTrue(pdf.content.startswith(b"%PDF-"))
        self.assertIn(b"date sintetice", pdf.content)
        self.assertEqual(len(pdf.content), mine["content"][0]["attachment"]["size"])

        as_fhir = self.client.get(
            f"/{INSTITUTION}/fhir/{url}",
            headers={**headers, "Accept": "application/fhir+json"},
        )
        self.assertEqual(base64.b64decode(as_fhir.json()["data"]), pdf.content)
        self.assertEqual(
            as_fhir.json()["securityContext"]["reference"], f"DocumentReference/{mine['id']}"
        )

        theirs = owned(INSTITUTION, "DocumentReference", REVOKED_IDNP)[0]
        foreign = self.client.get(
            f"/{INSTITUTION}/fhir/{theirs['content'][0]['attachment']['url']}", headers=headers
        )
        missing = self.client.get(f"/{INSTITUTION}/fhir/Binary/bin-9999", headers=headers)
        self.assertEqual((foreign.status_code, missing.status_code), (404, 404))
        self.assertEqual(foreign.json(), missing.json())  # no existence oracle

        report = owned(INSTITUTION, "DiagnosticReport")[0]
        no_scope = self.client.get(
            f"/{INSTITUTION}/fhir/{report['presentedForm'][0]['url']}", headers=headers
        )
        self.assertEqual(no_scope.status_code, 403)  # DiagnosticReport scope not granted
        injected = self.client.get(
            f"/{INSTITUTION}/fhir/{url}", params={"patient": "Patient/x"}, headers=headers
        )
        self.assertEqual(injected.status_code, 400)
        anonymous = self.client.get(f"/{INSTITUTION}/fhir/{url}")
        self.assertEqual(anonymous.status_code, 401)

    def test_every_attachment_resolves_to_a_binary_of_the_same_resource(self):
        for institution, collections in FIXTURE_DATA.items():
            binaries = {b["id"]: b for b in collections["Binary"]}
            for rtype in ("DocumentReference", "DiagnosticReport", "MedicationRequest"):
                for item in collections.get(rtype, []):
                    attachments = [c["attachment"] for c in item.get("content", [])]
                    attachments += item.get("presentedForm", [])
                    attachments += [
                        e["valueAttachment"] for e in item.get("extension", [])
                        if "valueAttachment" in e
                    ]
                    self.assertTrue(attachments, (institution, item["id"]))
                    for attachment in attachments:
                        binary = binaries[attachment["url"].removeprefix("Binary/")]
                        self.assertEqual(
                            binary["securityContext"]["reference"], f"{rtype}/{item['id']}"
                        )

    # --- search parameters ----------------------------------------------------------------
    def test_search_parameters_and_paging(self):
        scope = "patient/Observation.read patient/DiagnosticReport.read patient/MedicationRequest.read"
        headers = self._token(scope, "imsp-institutul-cardiologie")
        base = "/imsp-institutul-cardiologie/fhir"
        everything = self.client.get(f"{base}/Observation", headers=headers).json()

        seen, url, params = [], f"{base}/Observation", {"_count": 5}
        while url:
            page = self.client.get(url, params=params, headers=headers).json()
            self.assertEqual(page["total"], everything["total"])
            self.assertLessEqual(len(page["entry"]), 5)
            seen += [e["resource"]["id"] for e in page["entry"]]
            url = next((l["url"] for l in page["link"] if l["relation"] == "next"), None)
            params = None
        self.assertEqual(seen, [e["resource"]["id"] for e in everything["entry"]])

        dated = self.client.get(
            f"{base}/DiagnosticReport",
            params=[("date", "ge2026-01-01"), ("date", "le2026-06-30")],
            headers=headers,
        ).json()
        self.assertTrue(dated["total"] > 0)
        self.assertTrue(
            all("2026-01-01" <= e["resource"]["effectiveDateTime"][:10] <= "2026-06-30"
                for e in dated["entry"])
        )
        active = self.client.get(
            f"{base}/MedicationRequest", params={"status": "active"}, headers=headers
        ).json()
        self.assertTrue(all(e["resource"]["status"] == "active" for e in active["entry"]))
        labs = self.client.get(
            f"{base}/Observation", params={"category": "laboratory", "code": "http://loinc.org|718-7"},
            headers=headers,
        ).json()
        self.assertTrue(labs["total"] > 0)

        included = self.client.get(
            f"{base}/DiagnosticReport", params={"_include": "DiagnosticReport:result"}, headers=headers
        ).json()
        modes = [e["search"]["mode"] for e in included["entry"]]
        self.assertIn("include", modes)
        self.assertEqual(modes.count("match"), included["total"])

        without_obs = self._token("patient/DiagnosticReport.read", "imsp-institutul-cardiologie")
        hidden = self.client.get(
            f"{base}/DiagnosticReport", params={"_include": "DiagnosticReport:result"},
            headers=without_obs,
        ).json()
        self.assertNotIn("include", [e["search"]["mode"] for e in hidden["entry"]])


class GeneratedFixtureTests(unittest.TestCase):
    """The generator's rules (task breakdown, Epic 6) hold for the committed fixtures."""

    @staticmethod
    def _all(rtype):
        return [
            (institution, item)
            for institution, collections in FIXTURE_DATA.items()
            for item in collections.get(rtype, [])
        ]

    def test_every_seeded_institution_has_a_dataset(self):
        seed = (ROOT / "backend/alembic/versions/0007_seed_institutions.py").read_text(
            encoding="utf-8"
        )
        external_ids = set(re.findall(r'^\s+\("([a-z0-9-]+)", "', seed, re.M))
        self.assertEqual(len(external_ids), 10)
        self.assertEqual(set(FIXTURE_DATA), external_ids)

    def test_patients_share_one_idnp_and_identity_across_institutions(self):
        identities = {}
        for _, patient in self._all("Patient"):
            idnp = patient["identifier"][0]["value"]
            self.assertRegex(idnp, r"^\d{13}$")
            identity = (patient["name"][0]["family"], patient["name"][0]["given"][0],
                        patient["gender"], patient["birthDate"])
            self.assertEqual(identities.setdefault(idnp, identity), identity)
        self.assertEqual(len(identities), 10)
        self.assertEqual(identities[DEV_IDNP][:2], ("Rusu", "Maria"))
        self.assertNotIn(NO_MATCH_IDNP, identities)
        known_to = {
            institution for institution in FIXTURE_DATA if patient_ref(institution) is not None
        }
        self.assertEqual(known_to, set(FIXTURE_DATA))

    def test_document_subtypes_follow_the_shared_list(self):
        spec = importlib.util.spec_from_file_location(
            "document_types", ROOT / "backend/app/documents/document_types.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        allowed = set().union(*module.CATEGORY_DOCUMENT_TYPES.values())
        used = set()
        for rtype in ("Condition", "DocumentReference", "DiagnosticReport", "MedicationRequest",
                      "MedicationStatement", "CarePlan", "Procedure", "ImagingStudy"):
            for _, item in self._all(rtype):
                codes = [
                    c["code"]
                    for field in ("category", "type")
                    for concept in (item.get(field) if isinstance(item.get(field), list)
                                    else [item.get(field) or {}])
                    for c in concept.get("coding", [])
                    if c.get("system") == "urn:medvault:document-type"
                ]
                self.assertEqual(len(codes), 1, item["id"])
                used.add(codes[0])
        self.assertLessEqual(used, allowed)
        self.assertNotIn("birth_certificate", used)
        certificates = module.CATEGORY_DOCUMENT_TYPES["certificates"]
        self.assertEqual(
            certificates - used, {"birth_certificate", "disability_certificate"}
        )

    def test_time_series_shape(self):
        flags = [
            o["interpretation"][0]["coding"][0]["code"]
            for _, o in self._all("Observation") if "interpretation" in o
        ]
        out_of_range = sum(f != "N" for f in flags) / len(flags)
        self.assertTrue(0.10 <= out_of_range <= 0.25, out_of_range)
        for institution, report in self._all("DiagnosticReport"):
            if report.get("result"):
                self.assertTrue(3 <= len(report["result"]) <= 8, report["id"])
        visits, inpatients = Counter(), set()
        for institution, encounter in self._all("Encounter"):
            idnp = next(
                p["identifier"][0]["value"] for p in FIXTURE_DATA[institution]["Patient"]
                if f"Patient/{p['id']}" == encounter["subject"]["reference"]
            )
            if encounter["class"]["code"] == "AMB":
                visits[(institution, idnp)] += 1
            else:
                inpatients.add(idnp)
            self.assertTrue("2025-10-15" <= encounter["period"]["start"][:10] <= "2026-10-15")
        self.assertTrue(all(2 <= n <= 5 for n in visits.values()), visits)
        self.assertEqual(len(inpatients), 2)

    def test_pdfs_never_contain_a_full_idnp(self):
        idnps = {p["identifier"][0]["value"].encode() for _, p in self._all("Patient")}
        files = list((ROOT / "institution_mock/fixtures").glob("*/Binary/*.pdf"))
        self.assertEqual(len(files), len(self._all("Binary")))
        for path in files:
            content = path.read_bytes()
            self.assertFalse(any(idnp in content for idnp in idnps), path.name)


if __name__ == "__main__":
    unittest.main()
