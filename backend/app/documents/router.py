import io
import hashlib
import os
from datetime import date
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from minio.error import S3Error
from pydantic import BaseModel
from sqlalchemy import func, or_, select, text

from app.aggregation import mapping, originals
from app.audit.logger import write_audit_log
from app.auth.dependencies import RequestContext, get_request_context
from app.crypto import metadata as metadata_crypto
from app.documents.document_types import is_valid_pair
from app.documents.models import Document
from app.security import rate_limit
from app.storage.minio_client import get_minio_client

router = APIRouter(prefix="/documents", tags=["documents"])
limit_upload = rate_limit.limited(rate_limit.DOCUMENT_UPLOAD)

FORBIDDEN_MESSAGE = "You do not have access to this document."

# Upload constraints (mirrors the documents_size_range / documents_mime_allowed CHECKs).
MAX_FILE_SIZE = 10 * 1024 * 1024
DOCUMENTS_BUCKET = os.getenv("MINIO_DOCUMENTS_BUCKET", "medvault-documents")
UPLOAD_FORBIDDEN_MESSAGE = "You are not allowed to upload to this patient's vault."


def sniff_mime_type(head: bytes) -> str | None:
    """Detect the real file type from its leading bytes (never the client header).

    Only the three types the schema allows are accepted; anything else (including
    an empty or corrupt file whose signature we don't recognise) returns None.
    """
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


class UploadResponse(BaseModel):
    id: UUID
    category: str
    document_type: str
    document_date: date | None = None
    size_bytes: int
    sha256: str


async def _audit_upload(
    ctx: RequestContext,
    *,
    subject_patient_id: UUID | None,
    outcome: str,
    resource_id: UUID | None = None,
    extra: dict | None = None,
) -> None:
    """Record an upload attempt. Never logs title/notes/filename (Epic 5.1)."""
    metadata = {"outcome": outcome}
    if extra:
        metadata.update(extra)
    await write_audit_log(
        ctx.db,
        actor_user_id=ctx.user_id,
        subject_patient_id=subject_patient_id,
        action="upload_document",
        resource_type="document",
        resource_id=resource_id,
        outcome=outcome,
        metadata=metadata,
    )


def _read_object(bucket: str, key: str) -> bytes:
    response = get_minio_client().get_object(bucket, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def _original_headers(content_type: str) -> dict[str, str]:
    extension = "pdf" if content_type == "application/pdf" else "img"
    return {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        # Rendered in the viewer, never run as a page of our origin.
        "Content-Security-Policy": "sandbox",
        "Content-Disposition": f'inline; filename="original.{extension}"',
    }


async def audit_and_commit(
    ctx: RequestContext,
    *,
    resource_id: UUID | None,
    subject_patient_id: UUID | None,
    outcome: str,
) -> None:
    await write_audit_log(
        ctx.db,
        actor_user_id=ctx.user_id,
        subject_patient_id=subject_patient_id,
        action="view_original_document",
        resource_type="document",
        resource_id=resource_id,
        outcome=outcome,
        metadata={"outcome": outcome},
    )
    await ctx.db.commit()


@router.get("/{document_id}/original", response_class=Response)
async def get_original_document(
    document_id: str,
    ctx: RequestContext = Depends(get_request_context),
) -> Response:
    """Stream a self-uploaded document's file through the backend.

    Streamed rather than handed out as a signed storage URL, like the institutional
    originals and exports: the browser never needs to reach MinIO, and session,
    RLS and the caregiver gate are checked on every open.
    """
    try:
        parsed_id = UUID(document_id)
    except ValueError:
        await audit_and_commit(
            ctx,
            resource_id=None,
            subject_patient_id=None,
            outcome="denied",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=FORBIDDEN_MESSAGE,
        )

    actor_user_id = UUID(str(ctx.user_id))

    # RLS hides inaccessible rows. This predicate tightens caregiver access
    # from category view to the separate view_original permission.
    document = await ctx.db.scalar(
        select(Document).where(
            Document.id == parsed_id,
            or_(
                Document.patient_user_id == actor_user_id,
                func.medvault.caregiver_can(
                    Document.patient_user_id,
                    Document.category,
                    "view_original",
                ),
            ),
        )
    )

    if document is None:
        await audit_and_commit(
            ctx,
            resource_id=parsed_id,
            subject_patient_id=None,
            outcome="denied",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=FORBIDDEN_MESSAGE,
        )

    if document.status != "stored":
        await audit_and_commit(
            ctx,
            resource_id=document.id,
            subject_patient_id=document.patient_user_id,
            outcome="failure",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The original file is no longer available.",
        )

    try:
        content = await run_in_threadpool(
            _read_object, document.storage_bucket, document.object_key
        )
    except S3Error as error:
        await audit_and_commit(
            ctx,
            resource_id=document.id,
            subject_patient_id=document.patient_user_id,
            outcome="failure",
        )
        if error.code in {"NoSuchKey", "NoSuchObject"}:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The original file is unavailable.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The document storage service is unavailable.",
        )
    except Exception:
        await audit_and_commit(
            ctx,
            resource_id=document.id,
            subject_patient_id=document.patient_user_id,
            outcome="failure",
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The document storage service is unavailable.",
        )

    await audit_and_commit(
        ctx,
        resource_id=document.id,
        subject_patient_id=document.patient_user_id,
        outcome="success",
    )

    return Response(
        content,
        media_type=document.mime_type,
        headers=_original_headers(document.mime_type),
    )


# Generic on purpose: the institution's own error text never reaches the browser.
INSTITUTIONAL_ORIGINAL_ERRORS = {
    "forbidden": (status.HTTP_403_FORBIDDEN, FORBIDDEN_MESSAGE),
    "not_found": (status.HTTP_404_NOT_FOUND, "The original file is not available."),
    "reconnect": (
        status.HTTP_409_CONFLICT,
        "Reconnect the institution to open this file.",
    ),
    "unreachable": (
        status.HTTP_502_BAD_GATEWAY,
        "The institution can't be reached right now.",
    ),
}


# One path segment, so it never collides with /{document_id}/original.
@router.get("/institutional-original", response_class=Response)
async def get_institutional_original(
    ref: str = Query(max_length=200),
    category: str = Query(max_length=40),
    patient_id: UUID | None = None,
    ctx: RequestContext = Depends(get_request_context),
) -> Response:
    """Stream an institutional record's original file, fetched live and never stored.

    `ref` is the row's `original_path` (`institution:<external_id>/<Type>/<id>`) and
    `category` the page it was listed on; the caregiver gate is `view_original` on it.
    """
    target_patient_id = patient_id or UUID(str(ctx.user_id))
    parsed = originals.parse_reference(ref)
    resource_id = mapping.reference_uuid(ref) if parsed else None

    async def audit(outcome: str, institution_id: UUID | None, reason: str | None):
        await write_audit_log(
            ctx.db,
            actor_user_id=ctx.user_id,
            subject_patient_id=target_patient_id,
            action="view_original_document",
            resource_type="institution_record",
            resource_id=resource_id,
            institution_id=institution_id,
            outcome=outcome,
            metadata={"outcome": outcome, **({"reason": reason} if reason else {})},
        )
        await ctx.db.commit()

    try:
        original = await originals.fetch_original(ctx, ref, category, target_patient_id)
    except originals.OriginalError as error:
        outcome = "denied" if error.reason == "forbidden" else "failure"
        await audit(outcome, error.institution_id, error.reason)
        code, message = INSTITUTIONAL_ORIGINAL_ERRORS[error.reason]
        raise HTTPException(status_code=code, detail=message)

    await audit("success", original.institution_id, None)
    return Response(
        original.content,
        media_type=original.content_type,
        headers=_original_headers(original.content_type),
    )


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_upload)],
)
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(...),
    document_type: str = Form(...),
    patient_id: UUID | None = Form(default=None),
    document_date: date | None = Form(default=None),
    title: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    specialty: str | None = Form(default=None),
    issuer: str | None = Form(default=None),
    doctor: str | None = Form(default=None),
    ctx: RequestContext = Depends(get_request_context),
) -> UploadResponse:
    """Upload a medical document into a patient's vault.

    Every attempt is audited (never the file's contents). All validation and the
    caregiver authorization check happen *before* the file is written to storage;
    if the database insert fails after a successful write, the stored object is
    removed so no orphan is left behind.
    """
    actor = UUID(str(ctx.user_id))
    target = patient_id or actor

    async def reject(code: int, detail: str, outcome: str = "rejected") -> HTTPException:
        await _audit_upload(
            ctx,
            subject_patient_id=target,
            outcome=outcome,
            extra={"category": category, "document_type": document_type},
        )
        await ctx.db.commit()
        return HTTPException(status_code=code, detail=detail)

    # 1. category + subtype must be a valid pair from the shared list.
    if not is_valid_pair(category, document_type):
        raise await reject(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Unknown category/document_type combination.",
        )

    # 2. Read the bytes, capping at the size limit (documents_size_range CHECK).
    content = await file.read()
    if len(content) == 0:
        raise await reject(status.HTTP_400_BAD_REQUEST, "The file is empty.")
    if len(content) > MAX_FILE_SIZE:
        raise await reject(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "The file exceeds the 10 MB limit.",
        )

    # 3. Trust the magic bytes, never the client-provided MIME type.
    mime_type = sniff_mime_type(content[:16])
    if mime_type is None:
        raise await reject(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Unsupported or corrupt file. Only PDF, JPEG and PNG are accepted.",
        )

    # 4. Authorization: uploading to someone else's vault needs caregiver 'upload'.
    #    Checked here so an unauthorized caller never causes a storage write.
    if target != actor:
        allowed = await ctx.db.scalar(
            text(
                "SELECT medvault.caregiver_can("
                "CAST(:patient AS uuid), "
                "CAST(:category AS medvault.data_category), 'upload')"
            ),
            {"patient": str(target), "category": category},
        )
        if not allowed:
            raise await reject(
                status.HTTP_403_FORBIDDEN,
                UPLOAD_FORBIDDEN_MESSAGE,
                outcome="denied",
            )

    # 5. Encrypt the sensitive metadata before it goes near the database.
    try:
        title_ciphertext, key_version = metadata_crypto.encrypt(
            title or file.filename or document_type
        )
        notes_ciphertext = (
            metadata_crypto.encrypt(notes, key_version=key_version)[0] if notes else None
        )
        filename_ciphertext = (
            metadata_crypto.encrypt(file.filename, key_version=key_version)[0]
            if file.filename
            else None
        )
    except metadata_crypto.MetadataCryptoError:
        raise await reject(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Document encryption is not configured.",
            outcome="failure",
        )

    sha256 = hashlib.sha256(content).digest()
    # Random object key, scoped to the patient's vault. No client-controlled path.
    object_key = f"vault/{target}/{uuid4().hex}"

    # 6. Store the file. A storage failure is retryable and leaves nothing behind.
    try:
        minio = get_minio_client()
        await run_in_threadpool(
            minio.put_object,
            DOCUMENTS_BUCKET,
            object_key,
            io.BytesIO(content),
            len(content),
            content_type=mime_type,
        )
    except Exception:
        raise await reject(
            status.HTTP_502_BAD_GATEWAY,
            "Document storage is temporarily unavailable. Please retry.",
            outcome="failure",
        )

    # 7. Persist the row (RLS re-checks owner/caregiver-upload as defence in depth).
    document = Document(
        patient_user_id=target,
        uploaded_by_user_id=actor,
        category=category,
        document_type=document_type,
        title_ciphertext=title_ciphertext,
        notes_ciphertext=notes_ciphertext,
        metadata_key_version=key_version,
        document_date=document_date,
        specialty=specialty,
        issuer_name=issuer,
        practitioner_name=doctor,
        storage_bucket=DOCUMENTS_BUCKET,
        object_key=object_key,
        original_filename_ciphertext=filename_ciphertext,
        mime_type=mime_type,
        size_bytes=len(content),
        sha256=sha256,
    )
    ctx.db.add(document)
    try:
        await ctx.db.flush()
    except Exception:
        # Persistence failed after the object was stored: clean up the orphan.
        await ctx.db.rollback()
        try:
            await run_in_threadpool(minio.remove_object, DOCUMENTS_BUCKET, object_key)
        except Exception:
            pass  # Best-effort; a sweep job reconciles anything left behind.
        raise await reject(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Could not save the document. Please retry.",
            outcome="failure",
        )

    document_id = document.id
    await _audit_upload(
        ctx,
        subject_patient_id=target,
        outcome="success",
        resource_id=document_id,
        extra={
            "category": category,
            "document_type": document_type,
            "size_bytes": len(content),
            "mime_type": mime_type,
        },
    )
    await ctx.db.commit()

    return UploadResponse(
        id=document_id,
        category=category,
        document_type=document_type,
        document_date=document_date,
        size_bytes=len(content),
        sha256=sha256.hex(),
    )
