"""Shared helper for category list endpoints.

Every category page (diagnostics, prescriptions, certificates, analyses, other med
info) lists the patient's own `documents` in that category merged with records fetched
live from their connected institutions (see app/aggregation). Self-uploaded rows are
filtered by RLS (`documents_select`); an explicit `caregiver_can(patient, category,
'view')` gate returns 403 for a caregiver without permission, because RLS alone would
return an empty list indistinguishable from "this patient has no documents".

The response is an envelope: `items` plus a per-institution `sources` status list, so a
slow or failing institution degrades only its own rows and the UI can say so. Live
fetching runs only after the caregiver gate, so an unpermitted caregiver gets a clean 403
and no outbound call is made.
"""
import enum
from datetime import date, datetime
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError
from sqlalchemy import select, text

from app.aggregation import service as aggregation
from app.aggregation.service import SourceStatus
from app.audit.logger import write_audit_log
from app.auth.dependencies import RequestContext
from app.documents.models import Document


SELF_UPLOADED = "Self-uploaded"


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
    # Where the record came from: "Self-uploaded" for documents in this DB, or the
    # institution name for records fetched live. Derived, never stored — read-only
    # for the client.
    source: str = SELF_UPLOADED
    # When the record entered the vault (self-uploads: created_at). Institutional
    # rows are never stored, so they have none and omit it.
    date_added: datetime | None = None
    # Self-uploads: the original file route (GET /documents/{id}/original).
    # Institutional rows: the stable record reference
    # `institution:<external_id>/<ResourceType>/<id>`.
    original_path: str


class CategoryListResponse(BaseModel):
    items: list[CategoryListItem]
    # One entry per active connection consulted; empty when the patient has none.
    sources: list[SourceStatus] = []


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
    source: str | None = None,
    document_date: date | None = None,
    specialty: str | None = None,
    include_institutional: bool = True,
) -> CategoryListResponse:
    """List one patient's documents in `category`, merged with live institutional
    records and a per-source status.

    `label` is the human word used in the 403 message ("diagnostics",
    "prescriptions", ...). Own vault when `patient_id` is None/self; otherwise a
    caregiver read gated by `caregiver_can(..., 'view')`. Audit reflects the
    number of stored self-uploads read from the DB; each institution fetch is audited
    separately by the aggregation layer.
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
    # check (schema section 5). date/specialty filters apply in SQL (combined AND);
    # newest dated first, then most recently added.
    stmt = select(Document).where(
        Document.patient_user_id == target_patient_id,
        Document.category == category,
        Document.status == "stored",
    )
    if document_date is not None:
        stmt = stmt.where(Document.document_date == document_date)
    if specialty is not None:
        stmt = stmt.where(Document.specialty == specialty)
    stmt = stmt.order_by(
        Document.document_date.desc().nullslast(),
        Document.created_at.desc(),
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
            date_added=getattr(doc, "created_at", None),
            original_path=f"/documents/{doc.id}/original",
        )
        for doc in documents
    ]
    self_upload_count = len(items)

    sources: list[SourceStatus] = []
    # Filtering to "Self-uploaded" can't match any institutional row: skip the fetch.
    if include_institutional and source != SELF_UPLOADED:
        live_rows, sources = await aggregation.fetch_institutional(
            ctx, category, target_patient_id
        )
        live = []
        for row in live_rows:
            try:
                live.append(CategoryListItem(**row))
            except (ValidationError, TypeError):
                continue  # one bad institutional record must not fail the page
        # Same date/specialty filters (combined AND) applied to institutional rows.
        if document_date is not None:
            live = [i for i in live if i.document_date == document_date]
        if specialty is not None:
            live = [i for i in live if i.specialty == specialty]
        items.extend(live)
        # Re-sort the merged list newest-dated first (undated last).
        items.sort(key=lambda i: i.document_date or date.min, reverse=True)

    # Filter-by-source (Epic 2.9): exact match on the derived source label.
    if source is not None:
        items = [i for i in items if i.source == source]

    await write_audit_log(
        ctx.db,
        actor_user_id=actor_user_id,
        subject_patient_id=target_patient_id,
        action=f"list_{category}",
        resource_type=category,
        resource_id=None,
        outcome="success",
        metadata={"category": category, "count": self_upload_count},
    )
    await ctx.db.commit()

    return CategoryListResponse(items=items, sources=sources)
