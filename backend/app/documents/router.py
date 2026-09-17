from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from minio.error import S3Error
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from app.audit.logger import write_audit_log
from app.auth.dependencies import RequestContext, get_request_context
from app.documents.models import Document
from app.storage.minio_client import get_minio_client

router = APIRouter(prefix="/documents", tags=["documents"])

SIGNED_URL_EXPIRY = timedelta(minutes=5)
FORBIDDEN_MESSAGE = "You do not have access to this document."


class OriginalDocumentResponse(BaseModel):
    url: str
    expires_in_seconds: int


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


@router.get(
    "/{document_id}/original",
    response_model=OriginalDocumentResponse,
)
async def get_original_document(
    document_id: str,
    ctx: RequestContext = Depends(get_request_context),
) -> OriginalDocumentResponse:
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
        minio = get_minio_client()
        await run_in_threadpool(
            minio.stat_object,
            document.storage_bucket,
            document.object_key,
        )
        signed_url = await run_in_threadpool(
            minio.presigned_get_object,
            document.storage_bucket,
            document.object_key,
            expires=SIGNED_URL_EXPIRY,
        )
    except S3Error as error:
        if error.code in {"NoSuchKey", "NoSuchObject"}:
            await audit_and_commit(
                ctx,
                resource_id=document.id,
                subject_patient_id=document.patient_user_id,
                outcome="failure",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The original file is unavailable.",
            )

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

    return OriginalDocumentResponse(
        url=signed_url,
        expires_in_seconds=int(SIGNED_URL_EXPIRY.total_seconds()),
    )
