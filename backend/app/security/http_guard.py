"""HTTP hardening for every response and every state-changing request.

Security headers: set on all responses unless a route chose its own (originals keep
`Content-Security-Policy: sandbox`). `no-store` keeps medical data out of browser and
proxy caches.

Origin check: the session cookie is SameSite=Lax, which stops cross-site POSTs but not
same-site ones, such as another port or subdomain of the same host. So a POST, PUT, PATCH
or DELETE that a browser marks as coming from elsewhere is refused. Callers without those
browser headers (curl, server-to-server) hold no ambient cookie, so they pass through.
"""
import logging
import os
import re

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

log = logging.getLogger("medvault.security")

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# Only served in development; Swagger UI needs scripts that the API policy forbids.
_DOCS_PATHS = ("/docs", "/redoc")
_LOOPBACK_ORIGIN = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$")

_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    ),
}
_HSTS = "max-age=31536000; includeSubDomains"


def is_development() -> bool:
    # Same rule as the cookie and SMS settings: anything unset counts as production.
    return os.getenv("APP_ENV", "production").lower() == "development"


def security_headers() -> dict[str, str]:
    if is_development():  # Plain http locally, where HSTS would mean nothing.
        return dict(_HEADERS)
    return {**_HEADERS, "Strict-Transport-Security": _HSTS}


def allowed_origins() -> frozenset[str]:
    configured = [os.getenv("FRONTEND_URL", "http://localhost:5173")]
    configured += os.getenv("ALLOWED_ORIGINS", "").split(",")
    return frozenset(o.strip().rstrip("/") for o in configured if o.strip())


def is_cross_origin(origin: str | None, fetch_site: str | None) -> bool:
    """True when the browser says this request came from a foreign page."""
    if origin is None:
        return fetch_site in ("cross-site", "same-site")
    if origin.rstrip("/") in allowed_origins():
        return False
    return not (is_development() and _LOOPBACK_ORIGIN.match(origin))


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def guard(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method in UNSAFE_METHODS and is_cross_origin(
            origin, request.headers.get("sec-fetch-site")
        ):
            log.warning(
                "cross-origin request blocked",
                extra={"method": request.method, "path": request.url.path, "origin": origin},
            )
            response = JSONResponse(
                {"detail": "Cross-origin request rejected."},
                status_code=status.HTTP_403_FORBIDDEN,
            )
        else:
            response = await call_next(request)

        for name, value in security_headers().items():
            if name == "Content-Security-Policy" and request.url.path.startswith(_DOCS_PATHS):
                continue
            response.headers.setdefault(name, value)
        return response
