import datetime
import unittest
from datetime import date
from types import SimpleNamespace
from uuid import UUID

from app.documents import categories, diagnostics


PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
DOC_ID = UUID("22222222-2222-2222-2222-222222222222")

DIAG_PLACEHOLDERS = categories.institutional_placeholders("diagnoses")
INSTITUTION_SOURCE = DIAG_PLACEHOLDERS[0].source  # a real placeholder source label


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class FakeDB:
    def __init__(self, rows=None):
        self._rows = rows or []
        self.audit_params = []
        self.commits = 0

    async def scalar(self, statement, params=None):
        return None

    async def execute(self, statement, params=None):
        if params is None:
            return FakeResult(self._rows)
        self.audit_params.append(params)
        return None

    async def commit(self):
        self.commits += 1


def make_doc():
    return SimpleNamespace(
        id=DOC_ID,
        document_type="diagnosis_record",
        document_date=date(2026, 1, 15),
        specialty="Cardiology",
        practitioner_name="Dr. Popescu",
        issuer_name="Terramed",
        created_at=datetime.datetime(2026, 1, 16, 8, 0, tzinfo=datetime.timezone.utc),
    )


def ctx(db):
    return SimpleNamespace(user_id=str(PATIENT_ID), db=db)


class SourceFilterTests(unittest.IsolatedAsyncioTestCase):
    async def test_date_added_comes_from_created_at(self):
        db = FakeDB(rows=[make_doc()])
        items = await diagnostics.list_diagnostics(patient_id=None, source=None, ctx=ctx(db))
        selfup = next(i for i in items if i.id == DOC_ID)
        self.assertEqual(
            selfup.date_added,
            datetime.datetime(2026, 1, 16, 8, 0, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(selfup.source, "Self-uploaded")

    async def test_filter_self_uploaded_excludes_institutional(self):
        db = FakeDB(rows=[make_doc()])
        items = await diagnostics.list_diagnostics(
            patient_id=None, source="Self-uploaded", ctx=ctx(db)
        )
        self.assertTrue(items)
        self.assertTrue(all(i.source == "Self-uploaded" for i in items))
        self.assertTrue(all(i.date_added is not None for i in items))

    async def test_filter_by_institution_returns_only_that_source(self):
        db = FakeDB(rows=[make_doc()])
        items = await diagnostics.list_diagnostics(
            patient_id=None, source=INSTITUTION_SOURCE, ctx=ctx(db)
        )
        self.assertTrue(items)
        self.assertTrue(all(i.source == INSTITUTION_SOURCE for i in items))
        # None of them is the self-upload.
        self.assertTrue(all(i.id != DOC_ID for i in items))

    async def test_unknown_source_returns_empty_list(self):
        db = FakeDB(rows=[make_doc()])
        items = await diagnostics.list_diagnostics(
            patient_id=None, source="Nonexistent Clinic", ctx=ctx(db)
        )
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
