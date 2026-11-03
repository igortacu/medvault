import asyncio
import re
import unittest
from uuid import uuid4

from app.audit.logger import AUDIT_OUTCOMES, write_audit_log
from app.models.audit import AuditLog


class UnreachableDB:
    async def execute(self, statement, params=None):
        raise AssertionError("an invalid outcome must not reach the database")


class AuditOutcomeTests(unittest.TestCase):
    def test_outcomes_match_the_database_constraint(self):
        constraint = next(
            c for c in AuditLog.__table__.constraints
            if "outcome IN" in str(getattr(c, "sqltext", ""))
        )
        allowed = set(re.findall(r"'(\w+)'", str(constraint.sqltext)))
        self.assertEqual(allowed, set(AUDIT_OUTCOMES))

    def test_unknown_outcome_fails_before_the_database(self):
        # "rejected" passed the unit tests' fake database, then returned a 500 in production.
        with self.assertRaises(ValueError):
            asyncio.run(
                write_audit_log(
                    UnreachableDB(),
                    actor_user_id=uuid4(),
                    subject_patient_id=uuid4(),
                    action="upload_document",
                    resource_type="document",
                    resource_id=None,
                    outcome="rejected",
                )
            )
