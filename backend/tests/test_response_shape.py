import unittest
from datetime import date
from uuid import UUID

from fastapi.routing import APIRoute

from app.documents.categories import CategoryListItem
from app.main import app


CATEGORY_PATHS = {
    "/diagnostics",
    "/prescriptions",
    "/certificates",
    "/analyses",
    "/other-med-info",
    "/patient-info",
}


class ResponseShapeTests(unittest.TestCase):
    def test_category_routes_exclude_none(self):
        routes = {
            r.path: r
            for r in app.routes
            if isinstance(r, APIRoute) and r.path in CATEGORY_PATHS and "GET" in r.methods
        }
        # Every listed category GET route must omit null optional fields.
        for path in CATEGORY_PATHS:
            self.assertIn(path, routes, f"missing route {path}")
            self.assertTrue(
                routes[path].response_model_exclude_none,
                f"{path} should set response_model_exclude_none",
            )

    def test_missing_optionals_are_omitted_not_null(self):
        item = CategoryListItem(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            type="diagnosis_record",
            document_date=date(2026, 1, 15),
            original_path="/documents/22222222-2222-2222-2222-222222222222/original",
        )
        dumped = item.model_dump(mode="json", exclude_none=True)

        # Present, required fields.
        self.assertIn("id", dumped)
        self.assertIn("type", dumped)
        self.assertIn("source", dumped)
        self.assertIn("original_path", dumped)
        # Missing optionals are absent, not null.
        for absent in ("title", "specialty", "practitioner_name", "issuer_name"):
            self.assertNotIn(absent, dumped)

    def test_date_is_iso_8601(self):
        item = CategoryListItem(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            type="diagnosis_record",
            document_date=date(2026, 1, 15),
            original_path="/x",
        )
        dumped = item.model_dump(mode="json", exclude_none=True)
        self.assertEqual(dumped["document_date"], "2026-01-15")


if __name__ == "__main__":
    unittest.main()
