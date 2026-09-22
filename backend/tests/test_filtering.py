import datetime
import unittest
from datetime import date
from types import SimpleNamespace
from uuid import UUID

from app.documents import diagnostics


PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
DOC_ID = UUID("22222222-2222-2222-2222-222222222222")

# Known diagnoses placeholders (see categories._PLACEHOLDERS["diagnoses"]):
#   Cardiology  @ 2026-03-02
#   Neurology   @ 2025-11-18
CARDIO_DATE = date(2026, 3, 2)


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class FakeDB:
    """Returns the configured rows for the list query (SQL filters are not
    re-applied here; self-upload rows should already match the filter under test)."""

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


def make_doc(specialty="Cardiology", doc_date=CARDIO_DATE):
    return SimpleNamespace(
        id=DOC_ID,
        document_type="diagnosis_record",
        document_date=doc_date,
        specialty=specialty,
        practitioner_name="Dr. Popescu",
        issuer_name=None,
        created_at=datetime.datetime(2026, 3, 3, tzinfo=datetime.timezone.utc),
    )


def ctx(db):
    return SimpleNamespace(user_id=str(PATIENT_ID), db=db)


class FilteringTests(unittest.IsolatedAsyncioTestCase):
    async def test_filter_by_specialty(self):
        db = FakeDB(rows=[])  # placeholders only
        items = await diagnostics.list_diagnostics(
            patient_id=None, source=None, date=None, specialty="Cardiology", ctx=ctx(db)
        )
        self.assertTrue(items)
        self.assertTrue(all(i.specialty == "Cardiology" for i in items))

    async def test_filter_by_date(self):
        db = FakeDB(rows=[])
        items = await diagnostics.list_diagnostics(
            patient_id=None, source=None, date=CARDIO_DATE, specialty=None, ctx=ctx(db)
        )
        self.assertTrue(items)
        self.assertTrue(all(i.document_date == CARDIO_DATE for i in items))

    async def test_combined_filters_are_anded(self):
        db = FakeDB(rows=[])
        # Cardiology exists only on 2026-03-02, so pairing it with Neurology's date matches nothing.
        items = await diagnostics.list_diagnostics(
            patient_id=None,
            source=None,
            date=date(2025, 11, 18),
            specialty="Cardiology",
            ctx=ctx(db),
        )
        self.assertEqual(items, [])

    async def test_no_results_is_empty_list(self):
        db = FakeDB(rows=[])
        items = await diagnostics.list_diagnostics(
            patient_id=None, source=None, date=None, specialty="Dermatology", ctx=ctx(db)
        )
        self.assertEqual(items, [])

    async def test_self_upload_included_when_it_matches(self):
        db = FakeDB(rows=[make_doc(specialty="Cardiology", doc_date=CARDIO_DATE)])
        items = await diagnostics.list_diagnostics(
            patient_id=None, source=None, date=None, specialty="Cardiology", ctx=ctx(db)
        )
        self.assertTrue(any(i.id == DOC_ID for i in items))
        self.assertTrue(all(i.specialty == "Cardiology" for i in items))


if __name__ == "__main__":
    unittest.main()
