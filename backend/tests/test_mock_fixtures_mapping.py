"""The generated mock fixtures (institution_mock) map onto the category pages.

Every resource the mock serves for a category's FHIR types becomes exactly one list
row, with the summary fields the pages show; ambulatory visits are the only records
that are intentionally not rows.
"""
import unittest

from app.aggregation import mapping
from institution_mock.app import FIXTURE_DATA


class MockFixturesMapToCategoriesTests(unittest.TestCase):
    def test_every_record_lands_in_exactly_one_category_with_summary_fields(self):
        rows_per_category = {category: 0 for category in mapping.CATEGORY_RESOURCE_TYPES}
        for institution, collections in FIXTURE_DATA.items():
            name = collections["Institution"][0]["name"]
            for rtype in mapping.ALL_RESOURCE_TYPES:
                for resource in collections.get(rtype, []):
                    rows = {
                        category: row
                        for category, types in mapping.CATEGORY_RESOURCE_TYPES.items()
                        if rtype in types
                        and (row := mapping.normalize(
                            category, resource, external_id=institution, institution_name=name
                        ))
                    }
                    label = (institution, rtype, resource["id"])
                    if rtype == "Encounter" and resource["class"]["code"] == "AMB":
                        self.assertEqual(rows, {}, label)
                        continue
                    self.assertEqual(len(rows), 1, label)
                    (category, row), = rows.items()
                    rows_per_category[category] += 1
                    self.assertTrue(row["title"], label)
                    self.assertIsNotNone(row["document_date"], label)
                    self.assertTrue(row["practitioner_name"], label)
                    self.assertTrue(row["specialty"], label)
                    self.assertEqual(row["source"], name)
        self.assertTrue(all(rows_per_category.values()), rows_per_category)


if __name__ == "__main__":
    unittest.main()
