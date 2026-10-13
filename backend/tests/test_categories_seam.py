"""The seam between list_category_documents and the aggregation layer, exercised with
real mapping output (the other category tests stub the fetch entirely)."""
import unittest
from datetime import date
from types import SimpleNamespace
from uuid import UUID

from app.aggregation import mapping
from app.aggregation.service import SourceStatus
from app.documents import categories

PATIENT = UUID("11111111-1111-1111-1111-111111111111")
INSTITUTION = UUID("99999999-9999-9999-9999-999999999999")


class FakeResult:
    def scalars(self):
        return self

    def all(self):
        return []


class FakeDB:
    def __init__(self):
        self.audits = []
        self.commits = 0

    async def scalar(self, statement, params=None):
        return None

    async def execute(self, statement, params=None):
        if params is None:
            return FakeResult()
        self.audits.append(params)

    async def commit(self):
        self.commits += 1


def rows():
    def cond(rid, title, day, specialty):
        return mapping.normalize(
            "diagnoses",
            {
                "resourceType": "Condition", "id": rid, "code": {"text": title},
                "recordedDate": day,
                "extension": [{"url": mapping.SPECIALTY_EXTENSION, "valueString": specialty}],
            },
            external_id="inst-a", institution_name="Inst A",
        )

    return [
        cond("1", "Old", "2025-01-01", "Neurology"),
        cond("2", "New", "2026-03-02", "Cardiology"),
        {"id": "not-a-uuid", "type": "diagnosis_record"},  # invalid row: skipped, not fatal
    ]


class SeamTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.calls = 0
        self._orig = categories.aggregation.fetch_institutional

        async def fake(ctx, category, patient_id, http=None):
            self.calls += 1
            return rows(), [
                SourceStatus(institution_id=INSTITUTION, institution="Inst A", status="ok", count=2)
            ]

        categories.aggregation.fetch_institutional = fake
        self.addCleanup(lambda: setattr(categories.aggregation, "fetch_institutional", self._orig))

    async def list(self, **kwargs):
        ctx = SimpleNamespace(user_id=str(PATIENT), db=FakeDB())
        return await categories.list_category_documents(
            ctx, category="diagnoses", label="diagnostics", patient_id=None, **kwargs
        )

    async def test_real_mapping_output_becomes_sorted_items_and_bad_rows_are_skipped(self):
        result = await self.list()
        self.assertEqual([i.title for i in result.items], ["New", "Old"])
        self.assertEqual(result.sources[0].status, "ok")
        self.assertTrue(all(i.source == "Inst A" for i in result.items))

    async def test_filters_apply_to_institutional_rows(self):
        self.assertEqual([i.title for i in (await self.list(specialty="Neurology")).items], ["Old"])
        self.assertEqual(
            [i.title for i in (await self.list(document_date=date(2026, 3, 2))).items], ["New"]
        )
        self.assertEqual((await self.list(source="Inst B")).items, [])
        self.assertEqual(len((await self.list(source="Inst A")).items), 2)

    async def test_self_uploaded_filter_makes_no_outbound_call(self):
        result = await self.list(source="Self-uploaded")
        self.assertEqual(self.calls, 0)
        self.assertEqual((result.items, result.sources), ([], []))


if __name__ == "__main__":
    unittest.main()
