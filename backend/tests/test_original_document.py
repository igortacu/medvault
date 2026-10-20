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


PDF_BYTES = b"%PDF-1.4 sample"


class StoredObject:
    def __init__(self):
        self.released = False

    def read(self):
        return PDF_BYTES

    def close(self):
        pass

    def release_conn(self):
        self.released = True


class MinioSuccess:
    def __init__(self):
        self.object = StoredObject()
        self.requested = None

    def get_object(self, *args):
        self.requested = args
        return self.object


class MinioMissing:
    def get_object(self, *_args):
        raise S3Error(None, "NoSuchKey", "missing", None, None, None)


class MinioDown:
    def get_object(self, *_args):
        raise ConnectionError("storage unreachable")


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
            mime_type="application/pdf",
        )

    def tearDown(self):
        original.get_minio_client = self.previous_client

    async def test_owner_gets_the_file_streamed_and_audited(self):
        db = FakeDB(self.document)
        minio = MinioSuccess()
        original.get_minio_client = lambda: minio

        response = await original.get_original_document(
            str(DOCUMENT_ID), SimpleNamespace(user_id=str(USER_ID), db=db)
        )

        self.assertEqual(response.body, PDF_BYTES)
        self.assertEqual(response.media_type, "application/pdf")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["content-security-policy"], "sandbox")
        self.assertEqual(minio.requested, ("documents", "patient/document.pdf"))
        self.assertTrue(minio.object.released)
        self.assertEqual(db.audit_params[-1]["outcome"], "success")
        self.assertEqual(db.commits, 1)
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

    async def test_unreachable_storage_is_502_and_failure_audit(self):
        db = FakeDB(self.document)
        original.get_minio_client = lambda: MinioDown()

        with self.assertRaises(HTTPException) as raised:
            await original.get_original_document(
                str(DOCUMENT_ID), SimpleNamespace(user_id=str(USER_ID), db=db)
            )

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(db.audit_params[-1]["outcome"], "failure")

    async def test_document_not_stored_is_404_without_touching_storage(self):
        self.document.status = "deleted"
        db = FakeDB(self.document)
        original.get_minio_client = lambda: self.fail("storage was called")

        with self.assertRaises(HTTPException) as raised:
            await original.get_original_document(
                str(DOCUMENT_ID), SimpleNamespace(user_id=str(USER_ID), db=db)
            )

        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
