import unittest
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException
from minio.error import S3Error

from app.documents import router as original


USER_ID = UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")


class FakeDB:
    def __init__(self, document):
        self.document = document
        self.statement = None
        self.audit_params = []
        self.commits = 0

    async def scalar(self, statement):
        self.statement = statement
        return self.document

    async def execute(self, _statement, params):
        self.audit_params.append(params)

    async def commit(self):
        self.commits += 1


class MinioSuccess:
    def stat_object(self, *_args):
        return None

    def presigned_get_object(self, *_args, **_kwargs):
        return "https://storage.example.test/signed"


class MinioMissing:
    def stat_object(self, *_args):
        raise S3Error(None, "NoSuchKey", "missing", None, None, None)


class OriginalDocumentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.previous_client = original.get_minio_client
        self.document = SimpleNamespace(
            id=DOCUMENT_ID,
            patient_user_id=USER_ID,
            category="analyses",
            status="stored",
            storage_bucket="documents",
            object_key="patient/document.pdf",
        )

    def tearDown(self):
        original.get_minio_client = self.previous_client

    async def test_owner_gets_five_minute_url_and_audit_without_url(self):
        db = FakeDB(self.document)
        original.get_minio_client = lambda: MinioSuccess()

        response = await original.get_original_document(
            str(DOCUMENT_ID), SimpleNamespace(user_id=str(USER_ID), db=db)
        )

        self.assertEqual(response.url, "https://storage.example.test/signed")
        self.assertEqual(response.expires_in_seconds, 300)
        self.assertEqual(db.audit_params[-1]["outcome"], "success")
        self.assertNotIn("signed", str(db.audit_params[-1]))
        self.assertIn("caregiver_can", str(db.statement))
        self.assertIn("view_original", db.statement.compile().params.values())

    async def test_missing_or_inaccessible_document_is_generic_403(self):
        db = FakeDB(None)

        with self.assertRaises(HTTPException) as raised:
            await original.get_original_document(
                str(DOCUMENT_ID), SimpleNamespace(user_id=str(USER_ID), db=db)
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail, original.FORBIDDEN_MESSAGE)
        self.assertEqual(db.audit_params[-1]["outcome"], "denied")
        self.assertIsNone(db.audit_params[-1]["subject_patient_id"])

    async def test_missing_object_returns_clear_404_and_failure_audit(self):
        db = FakeDB(self.document)
        original.get_minio_client = lambda: MinioMissing()

        with self.assertRaises(HTTPException) as raised:
            await original.get_original_document(
                str(DOCUMENT_ID), SimpleNamespace(user_id=str(USER_ID), db=db)
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, "The original file is unavailable.")
        self.assertEqual(db.audit_params[-1]["outcome"], "failure")


if __name__ == "__main__":
    unittest.main()
