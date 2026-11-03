"""FastAPI application entrypoint.

Wires the feature routers into a single app. Cross-cutting concerns live in their
own modules (session auth behind get_request_context, logging, redaction and
error handlers in app.security.logs); keep this file to app assembly only.

Run locally with:  uvicorn app.main:app --reload
"""
import asyncio
import contextlib
import os

from fastapi import FastAPI

from app.documents import (
    analyses,
    certificates,
    diagnostics,
    other_med_info,
    patient_info,
    prescriptions,
)
from app.auth.router import router as auth_router
from app.auth.sms import dev_router as sms_dev_router, mock_enabled as sms_mock_enabled
from app.caregivers.router import router as caregivers_router
from app.documents import router as documents_router
from app.exports import router as exports_router
from app.exports.service import cleanup_periodically
from app.institutions.router import router as institutions_router
from app.security import http_guard, logs


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Expired export files are deleted every few minutes (Story 2.9). Skipped when no
    # database is configured (unit tests import the app without one).
    task = None
    if os.getenv("DATABASE_URL_ASYNC"):
        task = asyncio.create_task(cleanup_periodically())
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_app() -> FastAPI:
    logs.configure_logging()
    # The interactive API docs describe every route, so production does not serve them.
    docs = http_guard.is_development()
    app = FastAPI(
        title="MedVault API",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    http_guard.install(app)
    logs.install(app)

    app.include_router(auth_router)
    if sms_mock_enabled():
        app.include_router(sms_dev_router)
    app.include_router(documents_router.router)
    app.include_router(diagnostics.router)
    app.include_router(prescriptions.router)
    app.include_router(certificates.router)
    app.include_router(analyses.router)
    app.include_router(other_med_info.router)
    app.include_router(patient_info.router)
    app.include_router(caregivers_router)
    app.include_router(exports_router.router)
    app.include_router(institutions_router, prefix="/api/v1")

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
