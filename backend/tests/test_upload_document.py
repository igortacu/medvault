import base64
import os
import unittest
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.crypto import metadata as metadata_crypto
from app.documents import router


USER = UUID("11111111-1111-1111-1111-111111111111")
PATIENT = UUID("22222222-2222-2222-2222-222222222222")

PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
GIF_BYTES = b"GIF89a" + b"\x00" * 32


class FakeUpload:
    def __init__(self, content: bytes, filename: str | None = "scan.pdf"):
        self._content = content
        self.filename = filename

    async def read(self) -> bytes:
        return self._content


class FakeDB:
    def __init__(self, *, caregiver_allowed: bool = True, flush_error: bool = False):
        self.caregiver_allowed = caregiver_allowed
        self.flush_error = flush_error
        self.added: list = []
        self.audit_calls: list = []
        self.commits = 0
        self.rollbacks = 0

    async def scalar(self, statement, params=None):
        return self.caregiver_allowed

    async def execute(self, statement, params=None):
        self.audit_calls.append(params)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        if self.flush_error:
            raise RuntimeError("database unavailable")
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class FakeMinio:
    def __init__(self, *, put_error: bool = False):
        self.put_error = put_error
        self.put_calls: list = []
        self.removed: list = []

    def put_object(self, bucket, key, data, length, content_type=None):
        if self.put_error:
            raise RuntimeError("storage unavailable")
        self.put_calls.append((bucket, key, length, content_type))

    def remove_object(self, bucket, key):
        self.removed.append((bucket, key))


def _b64_key(byte: int) -> str:
    return base64.b64encode(bytes([byte]) * 32).decode()


class UploadDocumentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._saved_client = router.get_minio_client
        self._saved_env = {
            k: os.environ.get(k)
            for k in ("METADATA_ENCRYPTION_KEYS", "METADATA_ENCRYPTION_KEY_VERSION")
        }
        os.environ["METADATA_ENCRYPTION_KEYS"] = '{"1": "%s"}' % _b64_key(7)
        os.environ["METADATA_ENCRYPTION_KEY_VERSION"] = "1"
        metadata_crypto.reset_cache()

    def tearDown(self):
        router.get_minio_client = self._saved_client
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        metadata_crypto.reset_cache()

    async def _upload(self, db, minio, **over):
        router.get_minio_client = lambda: minio
        kwargs = dict(
            file=FakeUpload(PDF_BYTES),
            category="diagnoses",
            document_type="diagnosis_record",
            patient_id=None,
            document_date=None,
            title="Follow-up visit",
            notes=None,
            specialty=None,
            issuer=None,
            doctor=None,
            ctx=SimpleNamespace(user_id=str(USER), db=db),
        )
        kwargs.update(over)
        return await router.upload_document(**kwargs)

    async def test_owner_upload_succeeds_and_records_hash_and_type(self):
        db, minio = FakeDB(), FakeMinio()
        response = await self._upload(db, minio)

        self.assertEqual(response.category, "diagnoses")
        self.assertEqual(response.document_type, "diagnosis_record")
        self.assertEqual(response.size_bytes, len(PDF_BYTES))
        self.assertEqual(len(response.sha256), 64)  # sha-256 hex digest
        self.assertEqual(len(minio.put_calls), 1)
        bucket, key, length, content_type = minio.put_calls[0]
        self.assertEqual(content_type, "application/pdf")  # from magic bytes
        self.assertTrue(key.startswith(f"vault/{USER}/"))  # scoped, random
        self.assertEqual(db.audit_calls[-1]["outcome"], "success")

    async def test_magic_bytes_override_client_filename(self):
        # A PNG payload with a .pdf filename is stored as image/png, not pdf.
        db, minio = FakeDB(), FakeMinio()
        await self._upload(
            db,
            minio,
            file=FakeUpload(PNG_BYTES, filename="scan.pdf"),
            document_type="radiology_images",
            category="analyses",
        )
        self.assertEqual(minio.put_calls[0][3], "image/png")
        self.assertEqual(db.added[0].mime_type, "image/png")

    async def test_empty_file_rejected_before_storage(self):
        db, minio = FakeDB(), FakeMinio()
        with self.assertRaises(HTTPException) as raised:
            await self._upload(db, minio, file=FakeUpload(b""))
        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(len(minio.put_calls), 0)
        self.assertEqual(db.audit_calls[-1]["outcome"], "rejected")

    async def test_oversized_file_rejected(self):
        db, minio = FakeDB(), FakeMinio()
        big = b"%PDF-" + b"0" * router.MAX_FILE_SIZE
        with self.assertRaises(HTTPException) as raised:
            await self._upload(db, minio, file=FakeUpload(big))
        self.assertEqual(raised.exception.status_code, 413)
        self.assertEqual(len(minio.put_calls), 0)

    async def test_unsupported_or_corrupt_file_rejected(self):
        db, minio = FakeDB(), FakeMinio()
        with self.assertRaises(HTTPException) as raised:
            await self._upload(db, minio, file=FakeUpload(GIF_BYTES))
        self.assertEqual(raised.exception.status_code, 415)
        self.assertEqual(len(minio.put_calls), 0)

    async def test_invalid_category_type_pair_rejected(self):
        db, minio = FakeDB(), FakeMinio()
        with self.assertRaises(HTTPException) as raised:
            await self._upload(db, minio, document_type="blood_test")  # not a diagnosis
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(len(minio.put_calls), 0)

    async def test_caregiver_without_upload_permission_forbidden(self):
        db, minio = FakeDB(caregiver_allowed=False), FakeMinio()
        with self.assertRaises(HTTPException) as raised:
            await self._upload(db, minio, patient_id=PATIENT)
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(len(minio.put_calls), 0)
        self.assertEqual(db.audit_calls[-1]["outcome"], "denied")

    async def test_caregiver_with_upload_records_owner_and_uploader(self):
        db, minio = FakeDB(caregiver_allowed=True), FakeMinio()
        await self._upload(db, minio, patient_id=PATIENT)
        document = db.added[0]
        self.assertEqual(document.patient_user_id, PATIENT)  # owner
        self.assertEqual(document.uploaded_by_user_id, USER)  # uploader (caregiver)
        self.assertTrue(minio.put_calls[0][1].startswith(f"vault/{PATIENT}/"))

    async def test_storage_failure_is_retryable_502(self):
        db, minio = FakeDB(), FakeMinio(put_error=True)
        with self.assertRaises(HTTPException) as raised:
            await self._upload(db, minio)
        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(len(db.added), 0)
        self.assertEqual(db.audit_calls[-1]["outcome"], "failure")

    async def test_db_failure_cleans_up_stored_object(self):
        db, minio = FakeDB(flush_error=True), FakeMinio()
        with self.assertRaises(HTTPException) as raised:
            await self._upload(db, minio)
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(db.rollbacks, 1)
        self.assertEqual(len(minio.removed), 1)  # orphan cleaned up
        self.assertEqual(len(minio.put_calls), 1)

    async def test_metadata_is_encrypted_and_never_in_audit(self):
        db, minio = FakeDB(), FakeMinio()
        await self._upload(
            db,
            minio,
            title="Broken arm",
            notes="Patient reported severe pain",
            file=FakeUpload(PDF_BYTES, filename="private-name.pdf"),
        )
        document = db.added[0]
        self.assertNotIn(b"Broken arm", document.title_ciphertext)
        self.assertNotIn(b"severe pain", document.notes_ciphertext)
        self.assertNotIn(b"private-name", document.original_filename_ciphertext)
        self.assertEqual(document.metadata_key_version, 1)
        # And none of it leaks into the audit metadata.
        audit_blob = str(db.audit_calls)
        self.assertNotIn("Broken arm", audit_blob)
        self.assertNotIn("severe pain", audit_blob)
        self.assertNotIn("private-name", audit_blob)

    async def test_encryption_not_configured_is_503(self):
        os.environ.pop("METADATA_ENCRYPTION_KEYS", None)
        os.environ.pop("METADATA_ENCRYPTION_KEY_VERSION", None)
        metadata_crypto.reset_cache()
        db, minio = FakeDB(), FakeMinio()
        with self.assertRaises(HTTPException) as raised:
            await self._upload(db, minio)
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(len(minio.put_calls), 0)


if __name__ == "__main__":
    unittest.main()
