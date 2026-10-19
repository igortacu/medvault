"""Data export endpoints (Story 2.9).

POST   /patients/{patient_id}/exports   request an export (202; generated in the background)
GET    /patients/{patient_id}/exports   recent exports, newest first (poll while processing)
GET    /exports/{export_id}/file        download a ready export within its 30-minute window

The file is streamed through the backend rather than via a signed storage URL, so the
session, the RLS row check and the expiry are enforced on every download.
"""
import re
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from fastapi.concurrency import run_in_threadpool
from minio.error import S3Error
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, text

from app.audit.logger import write_audit_log
from app.auth.dependencies import RequestContext, get_request_context
from app.exports import render, service
from app.models.export import DataExport
from app.security import rate_limit

router = APIRouter(tags=["exports"])
limit_export = rate_limit.limited(rate_limit.EXPORT)

Category = Literal[
    "patient_info",
    "diagnoses",
    "certificates",
    "analyses",
    "prescriptions",
    "other_med_info",
]
# A single record: a self-upload, or an institutional record (fetched live at export).
SCOPE_REF = re.compile(
    r"^(document:[0-9a-f-]{36}|institution:[a-z0-9-]{1,64}/[A-Za-z]{1,40}/[A-Za-z0-9.\-]{1,64})$"
)
FORBIDDEN_MESSAGE = "You are not allowed to export this patient's data."
RECENT_EXPORTS = 10


class ExportRequest(BaseModel):
    categories: list[Category] = Field(min_length=1, max_length=6)
    format: Literal["pdf", "json"] = "pdf"
    # Language of the PDF's headings and labels.
    language: Literal["ro", "en", "ru"] = render.DEFAULT_LANGUAGE
    scope_ref: str | None = Field(default=None, max_length=200)

    @field_validator("categories")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @field_validator("scope_ref")
    @classmethod
    def _scope(cls, value: str | None) -> str | None:
        if value is not None and not SCOPE_REF.match(value):
            raise ValueError("Unknown record reference.")
        return value


class ExportResponse(BaseModel):
    id: UUID
    status: str
    format: str
    categories: list[str]
    single_record: bool
    created_at: datetime
    completed_at: datetime | None
    expires_at: datetime | None
    # Set only while the file can be downloaded.
    download_url: str | None


def _response(export: DataExport) -> ExportResponse:
    now = datetime.now(UTC)
    downloadable = (
        export.status == "ready" and export.expires_at is not None and export.expires_at > now
    )
    return ExportResponse(
        id=export.id,
        # A ready export past its window reads as expired even before the cleanup runs.
        status="expired" if export.status == "ready" and not downloadable else export.status,
        format=export.format,
        categories=list(export.categories),
        single_record=export.scope_ref is not None,
        created_at=export.created_at,
        completed_at=export.completed_at,
        expires_at=export.expires_at,
        download_url=f"/exports/{export.id}/file" if downloadable else None,
    )


async def _can_export(ctx: RequestContext, patient_id: UUID, categories: list[str]) -> bool:
    if patient_id == UUID(str(ctx.user_id)):
        return True
    for category in categories:
        allowed = await ctx.db.scalar(
            text(
                "SELECT medvault.caregiver_can(CAST(:p AS uuid), "
                "CAST(:c AS medvault.data_category), 'export')"
            ),
            {"p": str(patient_id), "c": category},
        )
        if not allowed:
            return False
    return True


@router.post(
    "/patients/{patient_id}/exports",
    response_model=ExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(limit_export)],
)
async def request_export(
    patient_id: UUID,
    body: ExportRequest,
    background: BackgroundTasks,
    ctx: RequestContext = Depends(get_request_context),
) -> ExportResponse:
    if body.scope_ref is not None and len(body.categories) != 1:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "A single-record export names exactly one category.",
        )
    if body.scope_ref is not None and body.categories == ["patient_info"]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Patient info has no single records."
        )

    if not await _can_export(ctx, patient_id, body.categories):
        await write_audit_log(
            ctx.db,
            actor_user_id=ctx.user_id,
            subject_patient_id=patient_id,
            action="export.requested",
            resource_type="data_export",
            resource_id=None,
            outcome="denied",
            metadata={"categories": body.categories},
        )
        await ctx.db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, FORBIDDEN_MESSAGE)

    export = DataExport(
        patient_user_id=patient_id,
        requested_by_user_id=UUID(str(ctx.user_id)),
        format=body.format,
        categories=body.categories,
        scope_ref=body.scope_ref,
        status="requested",
    )
    ctx.db.add(export)
    await ctx.db.flush()
    await write_audit_log(
        ctx.db,
        actor_user_id=ctx.user_id,
        subject_patient_id=patient_id,
        action="export.requested",
        resource_type="data_export",
        resource_id=export.id,
        outcome="success",
        metadata={"categories": body.categories, "format": body.format},
    )
    await ctx.db.refresh(export)
    response = _response(export)
    # Committed before the job starts so its own session can see the row.
    await ctx.db.commit()
    background.add_task(service.run_export, export.id, str(ctx.user_id), body.language)
    return response


@router.get("/patients/{patient_id}/exports", response_model=list[ExportResponse])
async def list_exports(
    patient_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
) -> list[ExportResponse]:
    # Deleting expired files here too keeps storage clean even between cleanup runs.
    await service.cleanup(ctx.db)
    await service.rebind(ctx)
    exports = (
        await ctx.db.scalars(
            select(DataExport)
            .where(DataExport.patient_user_id == patient_id)
            .order_by(DataExport.created_at.desc())
            .limit(RECENT_EXPORTS)
        )
    ).all()
    return [_response(e) for e in exports]


@router.get("/exports/{export_id}/file", response_class=Response)
async def download_export(
    export_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
) -> Response:
    export = await ctx.db.get(DataExport, export_id)  # RLS: patient or requester only
    if export is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Export not found.")
    current = _response(export)
    if current.status == "expired":
        raise HTTPException(
            status.HTTP_410_GONE, "This export has expired. Request a new one."
        )
    if current.download_url is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This export is not ready yet.")

    try:
        content = await run_in_threadpool(
            service.read_file, export.storage_bucket, export.object_key
        )
    except S3Error:
        raise HTTPException(
            status.HTTP_410_GONE, "This export is no longer available. Request a new one."
        )

    await write_audit_log(
        ctx.db,
        actor_user_id=ctx.user_id,
        subject_patient_id=export.patient_user_id,
        action="export.downloaded",
        resource_type="data_export",
        resource_id=export.id,
        outcome="success",
        metadata={"format": export.format},
    )
    await ctx.db.commit()

    stamp = (export.completed_at or datetime.now(UTC)).astimezone(render.TIMEZONE)
    filename = f"medvault-export-{stamp:%Y-%m-%d-%H%M}.{export.format}"
    return Response(
        content,
        media_type=service.CONTENT_TYPES[export.format],
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
