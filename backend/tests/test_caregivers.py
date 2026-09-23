import unittest
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.caregivers import router as caregivers
from app.caregivers.router import InviteRequest


ACTOR = UUID("11111111-1111-1111-1111-111111111111")
PATIENT = UUID("22222222-2222-2222-2222-222222222222")


class FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return FakeScalars(self._rows)


class FakeDB:
    def __init__(self, *, scalar_error=False, flush_error=False, results=None):
        self.scalar_error = scalar_error
        self.flush_error = flush_error
        self._results = list(results or [])
        self.added = []
        self.audit_calls = []
        self.commits = 0
        self.rollbacks = 0

    async def scalar(self, statement, params=None):
        if self.scalar_error:
            raise RuntimeError("invite not found or not addressed to caller")
        return None

    async def execute(self, statement, params=None):
        if params is not None:  # write_audit_log
            self.audit_calls.append(params)
            return None
        return self._results.pop(0)  # an ORM select

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        if self.flush_error:
            raise IntegrityError("insert", {}, Exception("duplicate"))
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def _ctx(db, user_id=ACTOR):
    return SimpleNamespace(user_id=str(user_id), db=db)


class InviteTests(unittest.IsolatedAsyncioTestCase):
    async def test_invite_creates_pending_link(self):
        db = FakeDB()
        body = InviteRequest(first_name="Ana", last_name="Popa", phone="+373 60 000 000")
        response = await caregivers.invite_caregiver(body, _ctx(db))

        self.assertEqual(response.status, "pending")
        self.assertEqual(response.phone, "+37360000000")  # normalised
        self.assertEqual(db.added[0].patient_user_id, ACTOR)
        self.assertEqual(db.audit_calls[-1]["outcome"], "success")

    async def test_duplicate_invite_conflict(self):
        db = FakeDB(flush_error=True)
        body = InviteRequest(first_name="Ana", last_name="Popa", phone="+37360000000")
        with self.assertRaises(HTTPException) as raised:
            await caregivers.invite_caregiver(body, _ctx(db))
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(db.rollbacks, 1)
        self.assertEqual(db.audit_calls[-1]["outcome"], "rejected")

    async def test_invalid_phone_rejected(self):
        db = FakeDB()
        body = InviteRequest(first_name="Ana", last_name="Popa", phone="12345")
        with self.assertRaises(HTTPException) as raised:
            await caregivers.invite_caregiver(body, _ctx(db))
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(len(db.added), 0)

    def test_short_name_rejected_by_model(self):
        with self.assertRaises(ValueError):
            InviteRequest(first_name="A", last_name="Popa", phone="+37360000000")


class AcceptRejectTests(unittest.IsolatedAsyncioTestCase):
    async def test_accept_success(self):
        db = FakeDB()
        link_id = uuid4()
        response = await caregivers.accept_invite(link_id, _ctx(db))
        self.assertEqual(response.status, "active")
        self.assertEqual(db.audit_calls[-1]["outcome"], "success")

    async def test_accept_failure_is_404_and_denied_audit(self):
        db = FakeDB(scalar_error=True)
        with self.assertRaises(HTTPException) as raised:
            await caregivers.accept_invite(uuid4(), _ctx(db))
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(db.rollbacks, 1)
        self.assertEqual(db.audit_calls[-1]["outcome"], "denied")

    async def test_reject_success(self):
        db = FakeDB()
        response = await caregivers.reject_invite(uuid4(), _ctx(db))
        self.assertEqual(response.status, "rejected")


class ListTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_caregivers_groups_permissions(self):
        link_id = uuid4()
        link = SimpleNamespace(
            id=link_id,
            caregiver_user_id=None,
            invited_first_name="Ana",
            invited_last_name="Popa",
            invited_phone_e164="+37360000000",
            status="pending",
            invited_at=None,
            responded_at=None,
        )
        perm = SimpleNamespace(
            link_id=link_id,
            category="diagnoses",
            can_view=True,
            can_view_original=False,
            can_export=False,
            can_upload=False,
        )
        db = FakeDB(results=[FakeResult([link]), FakeResult([perm])])

        items = await caregivers.list_caregivers(_ctx(db))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].first_name, "Ana")
        self.assertEqual(len(items[0].permissions), 1)
        self.assertEqual(items[0].permissions[0].category, "diagnoses")
        self.assertEqual(db.audit_calls[-1]["outcome"], "success")

    async def test_list_caregivers_empty_skips_permission_query(self):
        db = FakeDB(results=[FakeResult([])])  # only the links query is issued
        items = await caregivers.list_caregivers(_ctx(db))
        self.assertEqual(items, [])

    async def test_list_cared_patients(self):
        link_id = uuid4()
        link = SimpleNamespace(
            id=link_id,
            patient_user_id=PATIENT,
            status="active",
            responded_at=None,
        )
        db = FakeDB(results=[FakeResult([link]), FakeResult([])])
        items = await caregivers.list_cared_patients(_ctx(db))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].patient_user_id, PATIENT)
        self.assertEqual(items[0].status, "active")


if __name__ == "__main__":
    unittest.main()
