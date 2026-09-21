"""Shared helper for self-uploaded document category list endpoints.

Every category page (diagnostics, prescriptions, certificates, analyses, other
med info) lists the patient's own `documents` in that category, newest first.
Row visibility is enforced by RLS (`documents_select`); an explicit
`caregiver_can(patient, category, 'view')` gate returns 403 for a caregiver
without permission, because RLS alone would return an empty list that is
indistinguishable from "this patient has no documents".

Institutional records are, for now, **placeholder** rows keyed to seeded Moldovan
institutions (see `_PLACEHOLDERS`). They stand in for the Epic 2 live-FHIR
aggregation until that layer exists and show the frontend the merged shape via
the `source` field. They are appended only on the success path (after the
caregiver gate), so an unpermitted caregiver still gets a clean 403.
"""
import enum
from datetime import date, datetime
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
    # Where the record came from: "Self-uploaded" for documents in this DB, or the
    # institution name for records fetched live (placeholder until the FHIR layer lands).
    # Derived, never stored — read-only for the client.
    source: str = "Self-uploaded"
    # When the record entered the vault (self-uploads: created_at). Placeholder
    # institutional rows have none and omit it.
    date_added: datetime | None = None
    # Reference to the original file (served by GET /documents/{id}/original), or the
    # planned institutional record-reference for placeholder rows (not fetchable yet).
    original_path: str


# --- Placeholder institutional records ----------------------------------------
# One list of raw kwargs per category. Built into fresh CategoryListItem objects
# on each request. document_type values are real subtypes for the category.
_PLACEHOLDERS: dict[str, list[dict]] = {
    "diagnoses": [
        dict(
            id="bbbbbbbb-0000-0000-0000-000000000001",
            type="diagnosis_record",
            title="Essential hypertension",
            document_date=date(2026, 3, 2),
            specialty="Cardiology",
            practitioner_name="Dr. Mihai Popa",
            source="IMSP Institutul de Cardiologie",
            original_path="/institutions/imsp-institutul-cardiologie/Condition/cond-0001",
        ),
        dict(
            id="bbbbbbbb-0000-0000-0000-000000000002",
            type="consultation_report",
            title="Neurology consultation",
            document_date=date(2025, 11, 18),
            specialty="Neurology",
            practitioner_name="Dr. Ana Ceban",
            source="Spitalul Clinic Republican „Timofei Moșneaga”",
            original_path="/institutions/imsp-scr-t-mosneaga/DocumentReference/note-0001",
        ),
    ],
    "prescriptions": [
        dict(
            id="aaaaaaaa-0000-0000-0000-000000000001",
            type="prescription",
            title="Amoxicillin 500mg",
            document_date=date(2026, 3, 12),
            specialty="General Medicine",
            practitioner_name="Dr. Andrei Rusu",
            source="Spitalul Clinic Republican „Timofei Moșneaga”",
            original_path="/institutions/imsp-scr-t-mosneaga/MedicationRequest/med-0001",
        ),
        dict(
            id="aaaaaaaa-0000-0000-0000-000000000002",
            type="medication_record",
            title="Metformin 850mg",
            document_date=date(2026, 1, 28),
            specialty="Endocrinology",
            practitioner_name="Dr. Elena Cojocaru",
            source="Spitalul Internațional Medpark",
            original_path="/institutions/medpark/MedicationStatement/med-0002",
        ),
        dict(
            id="aaaaaaaa-0000-0000-0000-000000000003",
            type="treatment_plan",
            title="Hypertension treatment plan",
            document_date=date(2025, 12, 5),
            specialty="Cardiology",
            practitioner_name="Dr. Mihai Popa",
            source="IMSP Institutul de Cardiologie",
            original_path="/institutions/imsp-institutul-cardiologie/CarePlan/cp-0001",
        ),
    ],
    "certificates": [
        dict(
            id="cccccccc-0000-0000-0000-000000000001",
            type="illness_certificate",
            title="Medical certificate of illness",
            document_date=date(2026, 2, 20),
            specialty="Family Medicine",
            practitioner_name="Dr. Victor Moraru",
            source="Spitalul Clinic Municipal „Sfânta Treime”",
            original_path="/institutions/imsp-scm-sfanta-treime/DocumentReference/cert-0001",
        ),
        dict(
            id="cccccccc-0000-0000-0000-000000000002",
            type="vaccination_certificate",
            title="COVID-19 vaccination certificate",
            document_date=date(2025, 10, 9),
            specialty="Immunology",
            practitioner_name="Dr. Ana Ceban",
            source="Spitalul Internațional Medpark",
            original_path="/institutions/medpark/DocumentReference/cert-0002",
        ),
    ],
    "analyses": [
        dict(
            id="dddddddd-0000-0000-0000-000000000001",
            type="blood_test",
            title="Complete blood count",
            document_date=date(2026, 3, 15),
            specialty="Hematology",
            practitioner_name="Dr. Elena Cojocaru",
            source="Spitalul Internațional Medpark",
            original_path="/institutions/medpark/DiagnosticReport/lab-0001",
        ),
        dict(
            id="dddddddd-0000-0000-0000-000000000002",
            type="xray_report",
            title="Chest X-ray",
            document_date=date(2026, 1, 10),
            specialty="Radiology",
            practitioner_name="Dr. Sergiu Balan",
            source="Spitalul Clinic Republican „Timofei Moșneaga”",
            original_path="/institutions/imsp-scr-t-mosneaga/DiagnosticReport/img-0001",
        ),
    ],
    "other_med_info": [
        dict(
            id="eeeeeeee-0000-0000-0000-000000000001",
            type="hospitalization_record",
            title="Admission — cardiology ward",
            document_date=date(2026, 2, 1),
            specialty="Cardiology",
            practitioner_name="Dr. Mihai Popa",
            source="IMSP Institutul de Cardiologie",
            original_path="/institutions/imsp-institutul-cardiologie/Encounter/enc-0001",
        ),
        dict(
            id="eeeeeeee-0000-0000-0000-000000000002",
            type="immunization_record",
            title="Influenza immunization",
            document_date=date(2025, 10, 3),
            specialty="Family Medicine",
            practitioner_name="Dr. Victor Moraru",
            source="Spitalul Clinic Municipal Bălți",
            original_path="/institutions/imsp-scm-balti/Immunization/imm-0001",
        ),
    ],
}


def institutional_placeholders(category: str) -> list["CategoryListItem"]:
    """Fresh placeholder institutional records for a category (empty if none)."""
    return [CategoryListItem(**spec) for spec in _PLACEHOLDERS.get(category, [])]


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
    include_institutional: bool = True,
) -> list[CategoryListItem]:
    """List one patient's documents in `category`, merged with placeholder
    institutional records.

    `label` is the human word used in the 403 message ("diagnostics",
    "prescriptions", ...). Own vault when `patient_id` is None/self; otherwise a
    caregiver read gated by `caregiver_can(..., 'view')`. Audit reflects the
    number of stored self-uploads read from the DB, not the placeholders.
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
            date_added=getattr(doc, "created_at", None),
            original_path=f"/documents/{doc.id}/original",
        )
        for doc in documents
    ]
    self_upload_count = len(items)

    if include_institutional:
        items.extend(institutional_placeholders(category))
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

    return items
