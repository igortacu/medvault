"""FastAPI application entrypoint.

Wires the feature routers into a single app. Cross-cutting concerns (the session
auth + RLS-context middleware behind get_request_context, CORS, error handlers)
are added by the foundation branch; keep this file to app assembly only.

Run locally with:  uvicorn app.main:app --reload
"""
from fastapi import FastAPI

from app.documents import (
    analyses,
    certificates,
    diagnostics,
    other_med_info,
    patient_info,
    prescriptions,
)
from app.documents import router as documents_router


def create_app() -> FastAPI:
    app = FastAPI(title="MedVault API")

    app.include_router(documents_router.router)
    app.include_router(diagnostics.router)
    app.include_router(prescriptions.router)
    app.include_router(certificates.router)
    app.include_router(analyses.router)
    app.include_router(other_med_info.router)
    app.include_router(patient_info.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
