import datetime
import unittest
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException

from app.documents import patient_info
from app.documents.patient_info import MeasurementUpdate


PATIENT_ID = UUID("11111111-1111-1111-1111-111111111111")
CAREGIVER_ID = UUID("33333333-3333-3333-3333-333333333333")

BASICS = ("Maria", "Ionescu", datetime.date(1950, 4, 12))


class FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class FakeDB:
    def __init__(self, basics=None, profile=None, permission=None):
        self.basics = basics
        self.profile = profile
        self._permission = permission
        self.audit_params = []
        self.added = []
        self.commits = 0

    async def scalar(self, statement, params=None):
        return self._permission

    async def execute(self, statement, params=None):
        # Audit inserts carry an 'action' key; the basics query carries 'p'.
        if params and "action" in params:
            self.audit_params.append(params)
            return None
        return FakeResult(self.basics)

    async def get(self, model, pk):
        return self.profile

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


def make_profile(weight=72.0, height=170.0):
    return SimpleNamespace(
        user_id=PATIENT_ID,
        weight_kg=weight,
        height_cm=height,
        measurements_updated_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
    )


class GetPatientInfoTests(unittest.IsolatedAsyncioTestCase):
    async def test_owner_gets_basics_and_measurements(self):
        db = FakeDB(basics=BASICS, profile=make_profile())

        resp = await patient_info.get_patient_info(
            patient_id=None, ctx=SimpleNamespace(user_id=str(PATIENT_ID), db=db)
        )

        self.assertEqual(resp.first_name, "Maria")
        self.assertEqual(resp.date_of_birth, datetime.date(1950, 4, 12))
        self.assertEqual(resp.weight_kg, 72.0)
        self.assertEqual(resp.source, "Self-entered")
        self.assertTrue(len(resp.institutional_measurements) >= 1)
        self.assertEqual(db.audit_params[-1]["outcome"], "success")

    async def test_owner_without_profile_gets_null_measurements(self):
        db = FakeDB(basics=BASICS, profile=None)

        resp = await patient_info.get_patient_info(
            patient_id=None, ctx=SimpleNamespace(user_id=str(PATIENT_ID), db=db)
        )

        self.assertIsNone(resp.weight_kg)
        self.assertIsNone(resp.measurements_updated_at)
        self.assertEqual(resp.first_name, "Maria")

    async def test_caregiver_without_view_gets_403(self):
        db = FakeDB(permission=False)

        with self.assertRaises(HTTPException) as raised:
            await patient_info.get_patient_info(
                patient_id=PATIENT_ID, ctx=SimpleNamespace(user_id=str(CAREGIVER_ID), db=db)
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail, patient_info.VIEW_FORBIDDEN)
        self.assertEqual(db.audit_params[-1]["outcome"], "denied")


class UpdatePatientInfoTests(unittest.IsolatedAsyncioTestCase):
    async def test_owner_updates_existing_measurement(self):
        db = FakeDB(profile=make_profile(weight=72.0))

        resp = await patient_info.update_patient_info(
            body=MeasurementUpdate(weight_kg=80.0),
            patient_id=None,
            ctx=SimpleNamespace(user_id=str(PATIENT_ID), db=db),
        )

        self.assertEqual(resp.weight_kg, 80.0)
        self.assertIsNotNone(resp.measurements_updated_at)
        self.assertEqual(db.commits, 1)
        self.assertEqual(db.audit_params[-1]["outcome"], "success")

    async def test_owner_without_profile_inserts_row(self):
        db = FakeDB(profile=None)

        resp = await patient_info.update_patient_info(
            body=MeasurementUpdate(weight_kg=65.0, height_cm=168.0),
            patient_id=None,
            ctx=SimpleNamespace(user_id=str(PATIENT_ID), db=db),
        )

        self.assertEqual(len(db.added), 1)
        self.assertEqual(resp.weight_kg, 65.0)
        self.assertEqual(resp.height_cm, 168.0)

    async def test_empty_body_is_422(self):
        db = FakeDB(profile=make_profile())

        with self.assertRaises(HTTPException) as raised:
            await patient_info.update_patient_info(
                body=MeasurementUpdate(),
                patient_id=None,
                ctx=SimpleNamespace(user_id=str(PATIENT_ID), db=db),
            )
        self.assertEqual(raised.exception.status_code, 422)

    async def test_out_of_range_weight_is_422(self):
        db = FakeDB(profile=make_profile())

        with self.assertRaises(HTTPException) as raised:
            await patient_info.update_patient_info(
                body=MeasurementUpdate(weight_kg=900.0),
                patient_id=None,
                ctx=SimpleNamespace(user_id=str(PATIENT_ID), db=db),
            )
        self.assertEqual(raised.exception.status_code, 422)

    async def test_caregiver_without_upload_gets_403(self):
        db = FakeDB(profile=make_profile(), permission=False)

        with self.assertRaises(HTTPException) as raised:
            await patient_info.update_patient_info(
                body=MeasurementUpdate(weight_kg=70.0),
                patient_id=PATIENT_ID,
                ctx=SimpleNamespace(user_id=str(CAREGIVER_ID), db=db),
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail, patient_info.UPLOAD_FORBIDDEN)
        self.assertEqual(db.audit_params[-1]["outcome"], "denied")

    async def test_caregiver_with_upload_updates(self):
        db = FakeDB(profile=make_profile(), permission=True)

        resp = await patient_info.update_patient_info(
            body=MeasurementUpdate(height_cm=175.0),
            patient_id=PATIENT_ID,
            ctx=SimpleNamespace(user_id=str(CAREGIVER_ID), db=db),
        )

        self.assertEqual(resp.height_cm, 175.0)
        self.assertEqual(db.audit_params[-1]["outcome"], "success")
        self.assertEqual(db.audit_params[-1]["subject_patient_id"], str(PATIENT_ID))


if __name__ == "__main__":
    unittest.main()
