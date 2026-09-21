import unittest
from datetime import date
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException

from app.documents import categories, other_med_info


PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
CAREGIVER_ID = UUID("33333333-3333-3333-3333-333333333333")
DOC_ID = UUID("77777777-7777-7777-7777-777777777777")

MOCK_COUNT = len(categories.institutional_placeholders("other_med_info"))


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
        return self._permission

    async def execute(self, statement, params=None):
        if params is None:
            self.list_statement = statement
            return FakeResult(self._rows)
        self.audit_params.append(params)
        return None

    async def commit(self):
        self.commits += 1


def make_doc(**overrides):
    base = dict(
        id=DOC_ID,
        document_type="allergy_record",
        document_date=date(2026, 3, 5),
        specialty="Allergology",
        practitioner_name="Dr. Ana Ceban",
        issuer_name="Repromed",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class OtherMedInfoListTests(unittest.IsolatedAsyncioTestCase):
    async def test_owner_gets_self_uploads_merged_with_institutional(self):
        db = FakeDB(rows=[make_doc()])

        items = await other_med_info.list_other_med_info(
            patient_id=None, ctx=SimpleNamespace(user_id=str(PATIENT_ID), db=db)
        )

        self.assertEqual(len(items), 1 + MOCK_COUNT)
        selfup = next(i for i in items if i.id == DOC_ID)
        self.assertEqual(selfup.type, "allergy_record")
        self.assertEqual(selfup.source, "Self-uploaded")
        self.assertEqual(selfup.original_path, f"/documents/{DOC_ID}/original")
        self.assertTrue(any(i.source != "Self-uploaded" for i in items))
        dates = [i.document_date for i in items]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertEqual(db.audit_params[-1]["outcome"], "success")
        self.assertEqual(db.commits, 1)

    async def test_no_self_uploads_still_returns_institutional_placeholders(self):
        db = FakeDB(rows=[])

        items = await other_med_info.list_other_med_info(
            patient_id=None, ctx=SimpleNamespace(user_id=str(PATIENT_ID), db=db)
        )

        self.assertEqual(len(items), MOCK_COUNT)
        self.assertTrue(all(i.source != "Self-uploaded" for i in items))
        self.assertEqual(db.audit_params[-1]["outcome"], "success")

    async def test_caregiver_with_permission_sees_patient_other_med_info(self):
        db = FakeDB(rows=[make_doc()], permission=True)

        items = await other_med_info.list_other_med_info(
            patient_id=PATIENT_ID, ctx=SimpleNamespace(user_id=str(CAREGIVER_ID), db=db)
        )

        self.assertEqual(len(items), 1 + MOCK_COUNT)
        self.assertEqual(db.audit_params[-1]["outcome"], "success")
        self.assertEqual(db.audit_params[-1]["subject_patient_id"], str(PATIENT_ID))

    async def test_caregiver_without_permission_gets_403_and_zero_data(self):
        db = FakeDB(rows=[make_doc()], permission=False)

        with self.assertRaises(HTTPException) as raised:
            await other_med_info.list_other_med_info(
                patient_id=PATIENT_ID, ctx=SimpleNamespace(user_id=str(CAREGIVER_ID), db=db)
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail, other_med_info.FORBIDDEN_MESSAGE)
        self.assertEqual(db.audit_params[-1]["outcome"], "denied")
        self.assertIsNone(db.list_statement)


if __name__ == "__main__":
    unittest.main()
