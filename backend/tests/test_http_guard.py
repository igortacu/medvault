import os
import unittest
from unittest.mock import patch

from fastapi import Response
from fastapi.testclient import TestClient

from app.main import create_app

FRONTEND = "https://app.medvault.test"
PRODUCTION = {"APP_ENV": "production", "FRONTEND_URL": FRONTEND, "ALLOWED_ORIGINS": ""}
DEVELOPMENT = {"APP_ENV": "development", "FRONTEND_URL": FRONTEND, "ALLOWED_ORIGINS": ""}


def client(env):
    """An app with probe routes, so these tests need no database or Redis."""
    patcher = patch.dict(os.environ, env)
    patcher.start()
    app = create_app()

    @app.post("/probe")
    async def probe() -> dict:
        return {"ok": True}

    @app.get("/own-policy")
    async def own_policy() -> Response:
        return Response(headers={"Content-Security-Policy": "sandbox"})

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("unexpected")

    return TestClient(app, raise_server_exceptions=False), patcher


class GuardCase(unittest.TestCase):
    env = PRODUCTION

    def setUp(self):
        self.client, patcher = client(self.env)
        self.addCleanup(patcher.stop)


class HeaderTests(GuardCase):
    def assert_hardened(self, response):
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["referrer-policy"], "no-referrer")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("default-src 'none'", response.headers["content-security-policy"])
        self.assertIn("max-age=", response.headers["strict-transport-security"])

    def test_normal_response(self):
        self.assert_hardened(self.client.get("/health"))

    def test_not_found_response(self):
        self.assert_hardened(self.client.get("/nope"))

    def test_blocked_request(self):
        self.assert_hardened(self.client.post("/probe", headers={"Origin": "https://evil.test"}))

    def test_unhandled_error_stays_generic_and_hardened(self):
        response = self.client.get("/boom")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("unexpected", response.text)
        self.assert_hardened(response)

    def test_a_route_keeps_its_own_policy(self):
        self.assertEqual(self.client.get("/own-policy").headers["content-security-policy"], "sandbox")


class ProductionTests(GuardCase):
    def test_api_docs_are_not_served(self):
        for path in ("/docs", "/redoc", "/openapi.json"):
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_foreign_origins_are_refused(self):
        for origin in ("https://evil.test", "null", "http://localhost:5173", FRONTEND + ".evil.test"):
            response = self.client.post("/probe", headers={"Origin": origin})
            self.assertEqual(response.status_code, 403, origin)

    def test_frontend_origin_is_allowed(self):
        self.assertEqual(self.client.post("/probe", headers={"Origin": FRONTEND}).status_code, 200)

    def test_extra_configured_origin_is_allowed(self):
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": "https://a.test/, https://b.test"}):
            for origin in ("https://a.test", "https://b.test"):
                self.assertEqual(self.client.post("/probe", headers={"Origin": origin}).status_code, 200)

    def test_every_unsafe_method_is_checked(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            response = self.client.request(method, "/probe", headers={"Origin": "https://evil.test"})
            self.assertEqual(response.status_code, 403, method)

    def test_reads_are_not_checked(self):
        self.assertEqual(self.client.get("/health", headers={"Origin": "https://evil.test"}).status_code, 200)

    def test_no_browser_headers_passes(self):
        self.assertEqual(self.client.post("/probe").status_code, 200)

    def test_fetch_metadata_is_used_when_origin_is_missing(self):
        for site, expected in (("cross-site", 403), ("same-site", 403), ("same-origin", 200), ("none", 200)):
            response = self.client.post("/probe", headers={"Sec-Fetch-Site": site})
            self.assertEqual(response.status_code, expected, site)


class DevelopmentTests(GuardCase):
    env = DEVELOPMENT

    def test_api_docs_are_served_without_the_api_policy(self):
        response = self.client.get("/docs")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("content-security-policy", response.headers)

    def test_no_hsts_over_plain_http(self):
        self.assertNotIn("strict-transport-security", self.client.get("/health").headers)

    def test_any_localhost_port_is_allowed(self):
        for origin in ("http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173"):
            self.assertEqual(self.client.post("/probe", headers={"Origin": origin}).status_code, 200, origin)

    def test_lookalike_hosts_are_still_refused(self):
        for origin in ("http://localhost.evil.test", "http://evil.test/localhost", "http://127.0.0.1.evil.test"):
            self.assertEqual(self.client.post("/probe", headers={"Origin": origin}).status_code, 403, origin)
