"""Browser security headers on every API response.

Added after the OWASP ZAP scan reported missing anti-clickjacking, CSP and
X-Content-Type-Options headers. The API only ever returns JSON or files, never a
page meant to run scripts, so the policy can be the strictest one: load nothing and
never be framed. Routes that set one of these headers themselves keep their own
value (originals use `Content-Security-Policy: sandbox`, for example).
"""
import os

from fastapi import FastAPI, Request

HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    # Responses carry medical data: never keep them in a shared or browser cache.
    "Cache-Control": "no-store",
}

# Only over HTTPS, which production always is; local development is plain http.
HSTS = "max-age=63072000; includeSubDomains"

# FastAPI's interactive docs load their scripts from a CDN; a 'none' policy would
# blank them. They are turned off in production (see main.py).
_DOCS_PATHS = ("/docs", "/redoc")


def is_production() -> bool:
    return os.getenv("APP_ENV", "production").lower() == "production"


def install(app: FastAPI) -> None:
    production = is_production()

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(_DOCS_PATHS):
            return response
        for name, value in HEADERS.items():
            response.headers.setdefault(name, value)
        if production:
            response.headers.setdefault("Strict-Transport-Security", HSTS)
        return response
