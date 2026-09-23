import json
import unittest
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.caregivers import router as caregivers
from app.caregivers.router import (
    InviteRequest,
    PermissionsUpdate,
    PermissionUpdate,
    VaultSwitchRequest,
)


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
    def __init__(
        self,
        *,
        scalar_error=False,
        flush_error=False,
        results=None,
        scalar_result=None,
        get_result=None,
    ):
        self.scalar_error = scalar_error
        self.flush_error = flush_error
        self._results = list(results or [])
        self.scalar_result = scalar_result
        self.get_result = get_result
        self.added = []
        self.audit_calls = []
        self.commits = 0
        self.rollbacks = 0

    async def scalar(self, statement, params=None):
        if self.scalar_error:
            raise RuntimeError("invite not found or not addressed to caller")
        return self.scalar_result

    async def get(self, model, ident):
        return self.get_result

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


class FakeRedis:
    def __init__(self, initial=None):
        self.store = {}
        if initial is not None:
            self.store["session:sid"] = initial
        self.ttl_value = 900

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value

    async def ttl(self, key):
        return self.ttl_value


class PermissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_modify_permissions_upserts(self):
        link_id = uuid4()
        link = SimpleNamespace(id=link_id, patient_user_id=ACTOR, status="active")
        existing = SimpleNamespace(
            link_id=link_id,
            category="diagnoses",
            can_view=True,
            can_view_original=False,
            can_export=False,
            can_upload=False,
        )
        db = FakeDB(get_result=link, results=[FakeResult([existing])])

        body = PermissionsUpdate(
            permissions=[
                PermissionUpdate(category="diagnoses", can_view=True, can_export=True),
                PermissionUpdate(category="analyses", can_view=True),
            ]
        )
        items = await caregivers.modify_permissions(link_id, body, _ctx(db))

        categories = {i.category for i in items}
        self.assertEqual(categories, {"diagnoses", "analyses"})
        self.assertTrue(existing.can_export)  # updated in place
        self.assertEqual(len(db.added), 1)  # analyses inserted
        self.assertEqual(db.audit_calls[-1]["outcome"], "success")

    async def test_modify_permissions_unknown_link_404(self):
        db = FakeDB(get_result=None)
        body = PermissionsUpdate(
            permissions=[PermissionUpdate(category="diagnoses", can_view=True)]
        )
        with self.assertRaises(HTTPException) as raised:
            await caregivers.modify_permissions(uuid4(), body, _ctx(db))
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(db.audit_calls[-1]["outcome"], "denied")

    def test_action_without_view_is_rejected(self):
        with self.assertRaises(ValueError):
            PermissionUpdate(category="diagnoses", can_view=False, can_upload=True)

    def test_unknown_category_is_rejected(self):
        with self.assertRaises(ValueError):
            PermissionUpdate(category="nonsense", can_view=True)


class RevokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_revoke_active_link(self):
        link_id = uuid4()
        link = SimpleNamespace(
            id=link_id, patient_user_id=ACTOR, status="active",
            revoked_at=None, revoked_by_user_id=None,
        )
        db = FakeDB(get_result=link)
        response = await caregivers.revoke_access(link_id, _ctx(db))
        self.assertEqual(response.status, "revoked")
        self.assertEqual(link.status, "revoked")
        self.assertIsNotNone(link.revoked_at)
        self.assertEqual(link.revoked_by_user_id, ACTOR)

    async def test_revoke_already_revoked_is_404(self):
        link = SimpleNamespace(id=uuid4(), status="revoked")
        db = FakeDB(get_result=link)
        with self.assertRaises(HTTPException) as raised:
            await caregivers.revoke_access(link.id, _ctx(db))
        self.assertEqual(raised.exception.status_code, 404)


class VaultSwitchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._saved_redis = caregivers.redis_client

    def tearDown(self):
        caregivers.redis_client = self._saved_redis

    def _ctx_with_session(self, db):
        return SimpleNamespace(user_id=str(ACTOR), db=db, session_id="sid",
                               acting_patient_id=None)

    async def test_switch_to_patient_with_active_link(self):
        caregivers.redis_client = FakeRedis(initial=str(ACTOR))
        db = FakeDB(scalar_result=True)
        body = VaultSwitchRequest(patient_id=PATIENT)
        response = await caregivers.switch_vault(body, self._ctx_with_session(db))

        self.assertEqual(response.acting_patient_id, PATIENT)
        stored = caregivers.redis_client.store["session:sid"]
        self.assertIn(str(PATIENT), stored)  # persisted into the session

    async def test_switch_without_active_link_forbidden(self):
        caregivers.redis_client = FakeRedis(initial=str(ACTOR))
        db = FakeDB(scalar_result=False)
        body = VaultSwitchRequest(patient_id=PATIENT)
        with self.assertRaises(HTTPException) as raised:
            await caregivers.switch_vault(body, self._ctx_with_session(db))
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(db.audit_calls[-1]["outcome"], "denied")

    async def test_switch_back_to_own_vault_clears_selection(self):
        caregivers.redis_client = FakeRedis(
            initial=json.dumps({"user_id": str(ACTOR), "acting_patient_id": str(PATIENT)})
        )
        db = FakeDB()
        body = VaultSwitchRequest(patient_id=None)
        response = await caregivers.switch_vault(body, self._ctx_with_session(db))

        self.assertIsNone(response.acting_patient_id)
        self.assertNotIn("acting_patient_id", caregivers.redis_client.store["session:sid"])


if __name__ == "__main__":
    unittest.main()
