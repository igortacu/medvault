import unittest
from datetime import date
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException

from app.documents import diagnostics


PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
CAREGIVER_ID = UUID("33333333-3333-3333-3333-333333333333")
DOC_ID = UUID("22222222-2222-2222-2222-222222222222")


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class FakeDB:
    def __init__(self, rows=None, permission=None):
        self._rows = rows or []
        self._permission = permission
        self.audit_params = []
        self.commits = 0
        self.list_statement = None

    async def scalar(self, statement, params=None):
        # Only the caregiver permission pre-check uses scalar().
        return self._permission

    async def execute(self, statement, params=None):
        if params is None:
            # The document list query.
            self.list_statement = statement
            return FakeResult(self._rows)
        # The audit-log insert.
        self.audit_params.append(params)
        return None

    async def commit(self):
        self.commits += 1


def make_doc(**overrides):
    base = dict(
        id=DOC_ID,
        document_type="diagnosis_record",
        document_date=date(2026, 1, 15),
        specialty="Cardiology",
        practitioner_name="Dr. Popescu",
        issuer_name="Spitalul Clinic Republican",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class DiagnosticsListTests(unittest.IsolatedAsyncioTestCase):
    async def test_owner_gets_their_diagnostics(self):
        db = FakeDB(rows=[make_doc()])

        items = await diagnostics.list_diagnostics(
            patient_id=None, ctx=SimpleNamespace(user_id=str(PATIENT_ID), db=db)
        )

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.id, DOC_ID)
        self.assertEqual(item.type, "diagnosis_record")
        self.assertEqual(item.specialty, "Cardiology")
        self.assertEqual(item.original_path, f"/documents/{DOC_ID}/original")
        self.assertEqual(db.audit_params[-1]["outcome"], "success")
        self.assertEqual(db.commits, 1)

    async def test_no_diagnostics_is_empty_list_not_error(self):
        db = FakeDB(rows=[])

        items = await diagnostics.list_diagnostics(
            patient_id=None, ctx=SimpleNamespace(user_id=str(PATIENT_ID), db=db)
        )

        self.assertEqual(items, [])
        self.assertEqual(db.audit_params[-1]["outcome"], "success")

    async def test_caregiver_with_permission_sees_patient_diagnostics(self):
        db = FakeDB(rows=[make_doc()], permission=True)

        items = await diagnostics.list_diagnostics(
            patient_id=PATIENT_ID, ctx=SimpleNamespace(user_id=str(CAREGIVER_ID), db=db)
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(db.audit_params[-1]["outcome"], "success")
        self.assertEqual(db.audit_params[-1]["subject_patient_id"], str(PATIENT_ID))

    async def test_caregiver_without_permission_gets_403_and_zero_data(self):
        db = FakeDB(rows=[make_doc()], permission=False)

        with self.assertRaises(HTTPException) as raised:
            await diagnostics.list_diagnostics(
                patient_id=PATIENT_ID, ctx=SimpleNamespace(user_id=str(CAREGIVER_ID), db=db)
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail, diagnostics.FORBIDDEN_MESSAGE)
        self.assertEqual(db.audit_params[-1]["outcome"], "denied")
        # The list query never ran.
        self.assertIsNone(db.list_statement)


if __name__ == "__main__":
    unittest.main()
