"""GET /diagnostics — list a patient's self-uploaded diagnoses.

Thin wrapper over the shared category-list helper (see app/documents/categories.py),
which enforces RLS row-filtering plus an explicit caregiver_can 403 gate and audit.
"""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.dependencies import RequestContext, get_request_context
from app.documents.categories import (
    CategoryListItem,
    forbidden_message,
    list_category_documents,
)

router = APIRouter(tags=["diagnostics"])

CATEGORY = "diagnoses"
LABEL = "diagnostics"
FORBIDDEN_MESSAGE = forbidden_message(LABEL)

# Backwards-compatible alias for the generic list item.
DiagnosticListItem = CategoryListItem


@router.get(
    "/diagnostics",
    response_model=list[CategoryListItem],
    response_model_exclude_none=True,
)
async def list_diagnostics(
    patient_id: UUID | None = None,
    source: str | None = None,
    date: date | None = None,
    specialty: str | None = None,
    ctx: RequestContext = Depends(get_request_context),
) -> list[CategoryListItem]:
    return await list_category_documents(
        ctx,
        category=CATEGORY,
        label=LABEL,
        patient_id=patient_id,
        source=source,
        document_date=date,
        specialty=specialty,
    )
