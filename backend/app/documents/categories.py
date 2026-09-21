"""Shared helper for self-uploaded document category list endpoints.

Every category page (diagnostics, prescriptions, certificates, analyses, other
med info) lists the patient's own `documents` in that category, newest first.
Row visibility is enforced by RLS (`documents_select`); an explicit
`caregiver_can(patient, category, 'view')` gate returns 403 for a caregiver
without permission, because RLS alone would return an empty list that is
indistinguishable from "this patient has no documents".

Live institutional (FHIR) records are intentionally out of scope here — that is
the Epic 2 aggregation layer, a later story.
"""
import enum
from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, text

from app.audit.logger import write_audit_log
from app.auth.dependencies import RequestContext
from app.documents.models import Document


class CategoryListItem(BaseModel):
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


def forbidden_message(label: str) -> str:
    return f"You do not have access to this patient's {label}."


async def list_category_documents(
    ctx: RequestContext,
    *,
    category: str,
    label: str,
    patient_id: UUID | None,
) -> list[CategoryListItem]:
    """List one patient's self-uploaded documents in `category`.

    `label` is the human word used in the 403 message ("diagnostics",
    "prescriptions", ...). Own vault when `patient_id` is None/self; otherwise a
    caregiver read gated by `caregiver_can(..., 'view')`.
    """
    actor_user_id = UUID(str(ctx.user_id))
    target_patient_id = patient_id or actor_user_id

    # Caregiver access is an explicit gate. current_user_id() inside caregiver_can
    # is the caller, set by the RLS middleware; a missing 'view' grant is a 403.
    if target_patient_id != actor_user_id:
        allowed = await ctx.db.scalar(
            text(
                "SELECT medvault.caregiver_can("
                "CAST(:patient AS uuid), "
                "CAST(:category AS medvault.data_category), 'view')"
            ),
            {"patient": str(target_patient_id), "category": category},
        )
        if not allowed:
            await write_audit_log(
                ctx.db,
                actor_user_id=actor_user_id,
                subject_patient_id=target_patient_id,
                action=f"list_{category}",
                resource_type=category,
                resource_id=None,
                outcome="denied",
                metadata={"category": category},
            )
            await ctx.db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=forbidden_message(label),
            )

    # RLS is the row filter. status='stored' hides documents that failed a later
    # check (schema section 5). Newest dated first, then most recently added.
    stmt = (
        select(Document)
        .where(
            Document.patient_user_id == target_patient_id,
            Document.category == category,
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
        CategoryListItem(
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
        action=f"list_{category}",
        resource_type=category,
        resource_id=None,
        outcome="success",
        metadata={"category": category, "count": len(items)},
    )
    await ctx.db.commit()

    return items
