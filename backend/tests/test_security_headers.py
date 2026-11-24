import os
import unittest
from unittest import mock

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from app.security import headers


def _app() -> FastAPI:
    app = FastAPI()
    headers.install(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/original")
    async def original() -> Response:
        return Response(b"%PDF", headers={"Content-Security-Policy": "sandbox"})

    @app.get("/docs")
    async def docs() -> dict[str, str]:
        return {}

    return app


class SecurityHeadersTests(unittest.TestCase):
    def test_every_response_gets_the_headers(self):
        with mock.patch.dict(os.environ, {"APP_ENV": "development"}):
            res = TestClient(_app()).get("/health")
        for name, value in headers.HEADERS.items():
            self.assertEqual(res.headers[name], value, name)
        self.assertNotIn("Strict-Transport-Security", res.headers)

    def test_errors_get_the_headers_too(self):
        with mock.patch.dict(os.environ, {"APP_ENV": "development"}):
            res = TestClient(_app()).get("/missing")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.headers["X-Frame-Options"], "DENY")

    def test_a_route_keeps_its_own_policy(self):
        with mock.patch.dict(os.environ, {"APP_ENV": "development"}):
            res = TestClient(_app()).get("/original")
        self.assertEqual(res.headers["Content-Security-Policy"], "sandbox")
        self.assertEqual(res.headers["X-Content-Type-Options"], "nosniff")

    def test_hsts_only_in_production(self):
        with mock.patch.dict(os.environ, {"APP_ENV": "production"}):
            res = TestClient(_app()).get("/health")
        self.assertEqual(res.headers["Strict-Transport-Security"], headers.HSTS)

    def test_docs_page_is_left_alone(self):
        with mock.patch.dict(os.environ, {"APP_ENV": "development"}):
            res = TestClient(_app()).get("/docs")
        self.assertNotIn("Content-Security-Policy", res.headers)


if __name__ == "__main__":
    unittest.main()
