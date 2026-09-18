"""GET /diagnostics — list a patient's self-uploaded diagnostics.

Row visibility is enforced by RLS (documents_select: owner OR a caregiver with
'view' on the category). The 403 for an unpermitted caregiver is a deliberate
application-level gate on top of RLS: RLS alone would return zero rows, which is
indistinguishable from "this patient has no diagnostics". See app/documents/router.py
for the sibling original-file endpoint referenced by each entry.

Institutional diagnostics fetched live from FHIR are intentionally out of scope
here (not stored, no original file, gated in the API rather than by RLS); they
belong to a follow-up story once the FHIR client exists.
"""
import enum
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text

from app.audit.logger import write_audit_log
from app.auth.dependencies import RequestContext, get_request_context
from app.documents.models import Document

router = APIRouter(tags=["diagnostics"])

CATEGORY = "diagnoses"
FORBIDDEN_MESSAGE = "You do not have access to this patient's diagnostics."


class DiagnosticListItem(BaseModel):
    id: UUID
    # Fixed subtype code (e.g. 'diagnosis_record'); the frontend maps it to a label.
    type: str
    # Patient-given name. Encrypted at rest (title_ciphertext); stays null until the
    # metadata-decryption utility lands, so we never surface ciphertext.
    title: str | None = None
    document_date: date | None = None
    specialty: str | None = None
    practitioner_name: str | None = None
    issuer_name: str | None = None
    # Reference to the original file (served by GET /documents/{id}/original).
    original_path: str


def _enum_value(value: object) -> str:
    """document_type may come back as a str-enum member or a plain string."""
    return value.value if isinstance(value, enum.Enum) else str(value)


@router.get("/diagnostics", response_model=list[DiagnosticListItem])
async def list_diagnostics(
    patient_id: UUID | None = None,
    ctx: RequestContext = Depends(get_request_context),
) -> list[DiagnosticListItem]:
    actor_user_id = UUID(str(ctx.user_id))
    target_patient_id = patient_id or actor_user_id

    # Caregiver access is an explicit gate. current_user_id() inside caregiver_can
    # is the caller, set by the RLS middleware; a missing 'view' grant is a 403.
    if target_patient_id != actor_user_id:
        allowed = await ctx.db.scalar(
            text(
                "SELECT medvault.caregiver_can("
                "CAST(:patient AS uuid), 'diagnoses', 'view')"
            ),
            {"patient": str(target_patient_id)},
        )
        if not allowed:
            await write_audit_log(
                ctx.db,
                actor_user_id=actor_user_id,
                subject_patient_id=target_patient_id,
                action="list_diagnostics",
                resource_type="diagnostics",
                resource_id=None,
                outcome="denied",
                metadata={"category": CATEGORY},
            )
            await ctx.db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=FORBIDDEN_MESSAGE,
            )

    # RLS is the row filter. status='stored' hides documents that failed a later
    # check (schema section 5). Newest dated first, then most recently added.
    stmt = (
        select(Document)
        .where(
            Document.patient_user_id == target_patient_id,
            Document.category == CATEGORY,
            Document.status == "stored",
        )
        .order_by(
            Document.document_date.desc().nullslast(),
            Document.created_at.desc(),
        )
    )
    result = await ctx.db.execute(stmt)
    documents = result.scalars().all()

    items = [
        DiagnosticListItem(
            id=doc.id,
            type=_enum_value(doc.document_type),
            document_date=doc.document_date,
            specialty=doc.specialty,
            practitioner_name=doc.practitioner_name,
            issuer_name=doc.issuer_name,
            original_path=f"/documents/{doc.id}/original",
        )
        for doc in documents
    ]

    await write_audit_log(
        ctx.db,
        actor_user_id=actor_user_id,
        subject_patient_id=target_patient_id,
        action="list_diagnostics",
        resource_type="diagnostics",
        resource_id=None,
        outcome="success",
        metadata={"category": CATEGORY, "count": len(items)},
    )
    await ctx.db.commit()

    return items
