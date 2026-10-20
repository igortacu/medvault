"""The export job (Story 2.9): gather, render, store for 30 minutes, clean up.

Institutional data is pulled live at generation time through the same category
helpers the pages use, so the export follows exactly the permissions, caregiver
gates and source statuses the patient sees. The file is the only thing stored, in
MinIO, for DOWNLOAD_WINDOW; the cleanup deletes it after that.
"""
import asyncio
import io
import logging
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from minio.error import S3Error
from sqlalchemy import text

from app.audit.logger import write_audit_log
from app.auth.dependencies import RequestContext
from app.database import get_session_factory
from app.documents.categories import SELF_UPLOADED, list_category_documents
from app.documents.patient_info import get_patient_info
from app.exports import render
from app.models.export import DataExport
from app.storage.minio_client import get_minio_client

log = logging.getLogger("medvault.exports")

EXPORTS_BUCKET = os.getenv("MINIO_EXPORTS_BUCKET", "medvault-exports")
DOWNLOAD_WINDOW = timedelta(minutes=30)
# The order categories appear in, in the file and in "Export my data".
CATEGORIES = (
    "patient_info",
    "diagnoses",
    "certificates",
    "analyses",
    "prescriptions",
    "other_med_info",
)
# The word list_category_documents puts in its 403 message.
_LIST_LABELS = {
    "diagnoses": "diagnostics",
    "certificates": "certificates",
    "analyses": "analyses",
    "prescriptions": "prescriptions",
    "other_med_info": "other medical information",
}
CONTENT_TYPES = {"pdf": "application/pdf", "json": "application/json"}
# Cap on record references kept in one audit entry.
MAX_AUDITED_REFERENCES = 500


class ExportFailed(Exception):
    pass


async def rebind(ctx) -> None:
    """Restore the RLS user: it is set per transaction and the helpers commit."""
    await ctx.db.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(ctx.user_id)},
    )


def _reference(item) -> str:
    if item.source == SELF_UPLOADED:
        return f"document:{item.id}"
    return item.original_path


async def gather(
    ctx, patient_id: UUID, categories: list[str], scope_ref: str | None
) -> tuple[render.ExportBundle, list[str]]:
    """The bundle to render, and the record references it contains (for the audit)."""
    basics = (
        await ctx.db.execute(
            text(
                "SELECT first_name, last_name, date_of_birth "
                "FROM medvault.patient_basics(CAST(:p AS uuid))"
            ),
            {"p": str(patient_id)},
        )
    ).first()
    bundle = render.ExportBundle(
        generated_at=datetime.now(UTC),
        patient_name=" ".join(filter(None, basics[:2])) if basics else "",
        birth_date=basics[2] if basics else None,
        categories=[c for c in CATEGORIES if c in categories],
        single_record=scope_ref is not None,
    )
    references: list[str] = []
    missing: dict[str, str] = {}

    for category in bundle.categories:
        if category == "patient_info":
            info = await get_patient_info(patient_id, ctx)
            await rebind(ctx)
            bundle.measurements = render.Measurements(
                info.weight_kg, info.height_cm, info.measurements_updated_at
            )
            continue

        listed = await list_category_documents(
            ctx, category=category, label=_LIST_LABELS[category], patient_id=patient_id
        )
        await rebind(ctx)
        for item in listed.items:
            reference = _reference(item)
            if scope_ref is not None and reference != scope_ref:
                continue
            references.append(reference)
            self_uploaded = item.source == SELF_UPLOADED
            bundle.records.append(
                render.ExportRecord(
                    category=category,
                    type=item.type,
                    title=item.title,
                    date=item.document_date,
                    source=item.source,
                    self_uploaded=self_uploaded,
                    specialty=item.specialty,
                    practitioner=item.practitioner_name,
                    issuer=item.issuer_name if self_uploaded else None,
                )
            )
        for source in listed.sources:
            # One note per institution, however many categories it missed.
            if source.status != "ok" and source.institution not in missing:
                missing[source.institution] = source.status

    bundle.missing_sources = list(missing.items())
    if scope_ref is not None and not bundle.records:
        raise ExportFailed("record_not_found")
    return bundle, references


def _put(key: str, content: bytes, content_type: str) -> None:
    minio = get_minio_client()
    if not minio.bucket_exists(EXPORTS_BUCKET):
        minio.make_bucket(EXPORTS_BUCKET)
    minio.put_object(
        EXPORTS_BUCKET, key, io.BytesIO(content), len(content), content_type=content_type
    )


def read_file(bucket: str, key: str) -> bytes:
    response = get_minio_client().get_object(bucket, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


async def generate(ctx, export: DataExport, lang: str) -> None:
    """Build and store one export; marks it ready or failed and audits either way."""
    patient_id = export.patient_user_id
    # The DB hands enums back as members; files and keys need the plain value.
    fmt = getattr(export.format, "value", export.format)
    export.status = "processing"
    await ctx.db.commit()
    await rebind(ctx)
    try:
        bundle, references = await gather(
            ctx, patient_id, list(export.categories), export.scope_ref
        )
        renderer = render.render_pdf if fmt == "pdf" else render.render_json
        content = renderer(bundle, lang)
        key = f"{patient_id}/{export.id}.{fmt}"
        await run_in_threadpool(_put, key, content, CONTENT_TYPES[fmt])
    except Exception as error:
        await ctx.db.rollback()
        await rebind(ctx)
        reason = str(error) if isinstance(error, ExportFailed) else type(error).__name__
        log.error("Export %s failed: %s", export.id, reason)
        export.status = "failed"
        export.completed_at = datetime.now(UTC)
        await write_audit_log(
            ctx.db,
            actor_user_id=ctx.user_id,
            subject_patient_id=patient_id,
            action="export.failed",
            resource_type="data_export",
            resource_id=export.id,
            outcome="failure",
            metadata={"categories": list(export.categories), "reason": reason},
        )
        await ctx.db.commit()
        return

    now = datetime.now(UTC)
    export.status = "ready"
    export.storage_bucket = EXPORTS_BUCKET
    export.object_key = key
    export.completed_at = now
    export.expires_at = now + DOWNLOAD_WINDOW
    await write_audit_log(
        ctx.db,
        actor_user_id=ctx.user_id,
        subject_patient_id=patient_id,
        action="export.created",
        resource_type="data_export",
        resource_id=export.id,
        outcome="success",
        metadata={
            "categories": list(export.categories),
            "format": fmt,
            "record_count": len(references),
            "records": references[:MAX_AUDITED_REFERENCES],
            "sources_not_included": len(bundle.missing_sources),
        },
    )
    await ctx.db.commit()


async def run_export(export_id: UUID, actor_id: str, lang: str) -> None:
    """Background entry point: its own session, acting as the requester."""
    try:
        async with get_session_factory()() as db:
            ctx = RequestContext(user_id=actor_id, db=db)
            await rebind(ctx)
            export = await db.get(DataExport, export_id)
            if export is None or export.status != "requested":
                return
            await generate(ctx, export, lang)
    except Exception as error:  # the job must never take the worker down
        log.error("Export job crashed: %s", type(error).__name__)


async def cleanup(db) -> int:
    """Expire exports past their window and delete their files. Returns files removed."""
    rows = (
        await db.execute(
            text("SELECT storage_bucket, object_key FROM medvault.expire_data_exports()")
        )
    ).all()
    await db.commit()
    removed = 0
    for bucket, key in rows:
        if not bucket or not key:
            continue
        try:
            await run_in_threadpool(get_minio_client().remove_object, bucket, key)
            removed += 1
        except S3Error:
            log.warning("Could not delete an expired export file")
    return removed


async def cleanup_periodically(interval_seconds: int = 300) -> None:
    while True:
        try:
            async with get_session_factory()() as db:
                await cleanup(db)
        except Exception as error:
            log.warning("Export cleanup failed: %s", type(error).__name__)
        await asyncio.sleep(interval_seconds)
