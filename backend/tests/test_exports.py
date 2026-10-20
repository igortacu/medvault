"""Data export (Story 2.9): gathering, rendering, the job's lifecycle and the API rules."""
import json
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, HTTPException
from pydantic import ValidationError

from app.aggregation.service import SourceStatus
from app.documents.categories import SELF_UPLOADED, CategoryListItem, CategoryListResponse
from app.exports import render, router, service
from app.models.enums import ExportFormat

PATIENT = UUID("11111111-1111-1111-1111-111111111111")
CAREGIVER = UUID("33333333-3333-3333-3333-333333333333")
DOC_ID = UUID("50000000-0000-0000-0000-000000000001")
INST_REF = "institution:medpark/DocumentReference/doc-0001"


def self_upload():
    return CategoryListItem(
        id=DOC_ID,
        type="illness_certificate",
        title="Certificat de concediu medical",
        document_date=date(2026, 4, 2),
        issuer_name="Terramed",
        original_path=f"/documents/{DOC_ID}/original",
    )


def institutional():
    return CategoryListItem(
        id=uuid4(),
        type="vaccination_certificate",
        title="Certificat de vaccinare (formular 063-3/e)",
        document_date=date(2025, 10, 23),
        practitioner_name="Dr. Daniel Plămădeală",
        source="IMSP Institutul de Cardiologie",
        original_path=INST_REF,
    )


class Result:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row

    def all(self):
        return list(self.row or [])


class FakeDB:
    def __init__(self, *, caregiver_can=True, expired=()):
        self.caregiver_can = caregiver_can
        self.expired = list(expired)
        self.audits = []
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement, params=None):
        sql = str(statement)
        if params and "action" in params:
            self.audits.append(params)
        if "patient_basics" in sql:
            return Result(("Maria", "Rusu", date(1958, 3, 14)))
        if "expire_data_exports" in sql:
            return Result(self.expired)
        return Result(None)

    async def scalar(self, statement, params=None):
        return self.caregiver_can

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            value.id = value.id or uuid4()

    async def refresh(self, value):
        value.created_at = datetime.now(UTC)
        value.completed_at = None
        value.expires_at = None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def ctx(db, actor=PATIENT):
    return SimpleNamespace(user_id=str(actor), db=db)


class GatherTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._saved = (service.list_category_documents, service.get_patient_info)
        self.listed = []

        async def fake_list(ctx_, *, category, label, patient_id):
            self.listed.append(category)
            medpark_down = [
                SourceStatus(institution_id=uuid4(), institution="Spitalul Internațional Medpark", status="timeout")
            ]
            if category != "certificates":
                return CategoryListResponse(items=[], sources=medpark_down)
            return CategoryListResponse(
                items=[self_upload(), institutional()],
                sources=[
                    SourceStatus(institution_id=uuid4(), institution="IMSP Institutul de Cardiologie", status="ok", count=1),
                    SourceStatus(institution_id=uuid4(), institution="Spitalul Internațional Medpark", status="timeout"),
                ],
            )

        async def fake_info(patient_id, ctx_):
            return SimpleNamespace(weight_kg=72.4, height_cm=164.0, measurements_updated_at=None)

        service.list_category_documents = fake_list
        service.get_patient_info = fake_info

    def tearDown(self):
        service.list_category_documents, service.get_patient_info = self._saved

    async def test_gathers_every_category_in_a_fixed_order(self):
        bundle, references = await service.gather(
            ctx(FakeDB()), PATIENT, ["certificates", "patient_info", "diagnoses"], None
        )
        self.assertEqual(bundle.categories, ["patient_info", "diagnoses", "certificates"])
        self.assertEqual(bundle.patient_name, "Maria Rusu")
        self.assertEqual(bundle.measurements.weight_kg, 72.4)
        self.assertEqual(len(bundle.records), 2)
        self.assertEqual(references, [f"document:{DOC_ID}", INST_REF])
        # A source that couldn't be read is named once in the file, however many
        # categories it missed, not silently dropped.
        self.assertEqual(bundle.missing_sources, [("Spitalul Internațional Medpark", "timeout")])

    async def test_single_record_export_keeps_only_that_record(self):
        bundle, references = await service.gather(
            ctx(FakeDB()), PATIENT, ["certificates"], INST_REF
        )
        self.assertTrue(bundle.single_record)
        self.assertEqual(references, [INST_REF])
        self.assertEqual(bundle.records[0].source, "IMSP Institutul de Cardiologie")

    async def test_single_record_that_no_longer_exists_fails(self):
        with self.assertRaises(service.ExportFailed):
            await service.gather(
                ctx(FakeDB()), PATIENT, ["certificates"], "document:" + str(uuid4())
            )


def sample_bundle():
    upload, inst = self_upload(), institutional()
    return render.ExportBundle(
        generated_at=datetime(2026, 10, 19, 19, 30, tzinfo=UTC),
        patient_name="Maria Rusu",
        birth_date=date(1958, 3, 14),
        categories=["patient_info", "certificates"],
        records=[
            render.ExportRecord("certificates", upload.type, upload.title, upload.document_date, SELF_UPLOADED, True, issuer="Terramed"),
            render.ExportRecord("certificates", inst.type, inst.title, inst.document_date, inst.source, False, practitioner=inst.practitioner_name),
        ],
        measurements=render.Measurements(72.4, 164.0, None),
        missing_sources=[("Spitalul Internațional Medpark", "timeout")],
    )


class RenderTests(unittest.TestCase):
    def bundle(self):
        return sample_bundle()

    def test_pdf_in_every_language(self):
        for lang in render.LANGUAGES:
            pdf = render.render_pdf(self.bundle(), lang)
            self.assertTrue(pdf.startswith(b"%PDF-"), lang)
            self.assertGreater(len(pdf), 2000, lang)

    def test_json_has_labels_and_no_internal_ids(self):
        payload = json.loads(render.render_json(self.bundle(), "ro"))
        self.assertEqual(payload["records"][1]["type_label"], "Certificat de vaccinare")
        self.assertEqual(payload["sources_not_included"][0]["status"], "timeout")
        text = json.dumps(payload)
        self.assertNotIn(str(DOC_ID), text)
        self.assertNotIn("institution:", text)
        self.assertNotIn("original_path", text)

    def test_unknown_language_falls_back_to_romanian(self):
        self.assertEqual(render.labels("de")["export"]["title"], "Export de date medicale")

    def test_labels_match_the_frontend_translations(self):
        locales = Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n" / "locales"
        if not locales.is_dir():
            self.skipTest("frontend not present")
        for lang in render.LANGUAGES:
            documents = json.loads((locales / lang / "documents.json").read_text(encoding="utf-8"))
            common = json.loads((locales / lang / "common.json").read_text(encoding="utf-8"))
            self.assertEqual(render.labels(lang)["docType"], documents["docType"], lang)
            self.assertEqual(render.labels(lang)["category"], common["category"], lang)


class GenerateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._saved = (service.gather, service._put)
        self.stored = {}

        async def fake_gather(ctx_, patient_id, categories, scope_ref):
            return sample_bundle(), [f"document:{DOC_ID}", INST_REF]

        def fake_put(key, content, content_type):
            self.stored[key] = (content, content_type)

        service.gather = fake_gather
        service._put = fake_put

    def tearDown(self):
        service.gather, service._put = self._saved

    def export(self, fmt="pdf"):
        return SimpleNamespace(
            id=uuid4(), patient_user_id=PATIENT, categories=["certificates"], scope_ref=None,
            format=fmt, status="requested", storage_bucket=None, object_key=None,
            expires_at=None, completed_at=None,
        )

    async def test_ready_export_is_stored_for_thirty_minutes_and_audited(self):
        # The DB returns the format as an enum member, not a plain string.
        db, export = FakeDB(), self.export(ExportFormat.json)
        before = datetime.now(UTC)
        await service.generate(ctx(db), export, "en")

        self.assertEqual(export.status, "ready")
        self.assertEqual(export.object_key, f"{PATIENT}/{export.id}.json")
        self.assertIn(export.object_key, self.stored)
        window = export.expires_at - before
        self.assertTrue(timedelta(minutes=29) < window <= timedelta(minutes=31))
        created = [a for a in db.audits if a["action"] == "export.created"][0]
        metadata = json.loads(created["metadata"])
        self.assertEqual(metadata["records"], [f"document:{DOC_ID}", INST_REF])
        self.assertEqual(metadata["categories"], ["certificates"])

    async def test_failed_export_is_marked_and_audited(self):
        async def broken(*args):
            raise service.ExportFailed("record_not_found")

        service.gather = broken
        db, export = FakeDB(), self.export()
        await service.generate(ctx(db), export, "ro")

        self.assertEqual(export.status, "failed")
        self.assertIsNone(export.object_key)
        failed = [a for a in db.audits if a["action"] == "export.failed"][0]
        self.assertEqual(json.loads(failed["metadata"])["reason"], "record_not_found")


class RouterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._run = service.run_export

    def tearDown(self):
        service.run_export = self._run

    async def test_caregiver_needs_export_on_every_category(self):
        db = FakeDB(caregiver_can=False)
        body = router.ExportRequest(categories=["certificates"])
        with self.assertRaises(HTTPException) as denied:
            await router.request_export(PATIENT, body, BackgroundTasks(), ctx(db, CAREGIVER))
        self.assertEqual(denied.exception.status_code, 403)
        self.assertEqual(db.audits[0]["outcome"], "denied")
        self.assertEqual(db.added, [])

    async def test_request_queues_the_job_after_committing(self):
        db = FakeDB()
        background = BackgroundTasks()
        body = router.ExportRequest(categories=["certificates", "certificates"], format="json", language="ru")
        response = await router.request_export(PATIENT, body, background, ctx(db))

        self.assertEqual(response.status, "requested")
        self.assertEqual(db.added[0].categories, ["certificates"])
        self.assertGreaterEqual(db.commits, 1)
        task = background.tasks[0]
        self.assertIs(task.func, service.run_export)
        self.assertEqual(task.args[2], "ru")

    def test_single_record_rules(self):
        with self.assertRaises(ValidationError):
            router.ExportRequest(categories=["certificates"], scope_ref="https://evil/x")
        router.ExportRequest(categories=["certificates"], scope_ref=INST_REF)

    async def test_single_record_must_name_one_category(self):
        body = router.ExportRequest(categories=["certificates", "analyses"], scope_ref=INST_REF)
        with self.assertRaises(HTTPException) as error:
            await router.request_export(PATIENT, body, BackgroundTasks(), ctx(FakeDB()))
        self.assertEqual(error.exception.status_code, 422)

    def test_ready_export_past_its_window_reads_as_expired(self):
        now = datetime.now(UTC)
        export = SimpleNamespace(
            id=uuid4(), status="ready", format="pdf", categories=["analyses"], scope_ref=None,
            created_at=now - timedelta(hours=1), completed_at=now - timedelta(minutes=40),
            expires_at=now - timedelta(minutes=10),
        )
        self.assertEqual(router._response(export).status, "expired")
        self.assertIsNone(router._response(export).download_url)
        export.expires_at = now + timedelta(minutes=5)
        self.assertEqual(router._response(export).download_url, f"/exports/{export.id}/file")

    async def test_cleanup_deletes_the_expired_files(self):
        removed = []
        saved = service.get_minio_client
        service.get_minio_client = lambda: SimpleNamespace(
            remove_object=lambda bucket, key: removed.append((bucket, key))
        )
        try:
            db = FakeDB(expired=[("medvault-exports", "p/e1.pdf"), (None, None)])
            self.assertEqual(await service.cleanup(db), 1)
        finally:
            service.get_minio_client = saved
        self.assertEqual(removed, [("medvault-exports", "p/e1.pdf")])


if __name__ == "__main__":
    unittest.main()
