"""GET /analyses — list a patient's analyses and lab reports.

Thin wrapper over the shared category-list helper (app/documents/categories.py):
RLS row-filtering + explicit caregiver_can 403 gate + audit, merged with
placeholder institutional records until the Epic 2 live-FHIR aggregation exists.
"""
from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.dependencies import RequestContext, get_request_context
from app.documents.categories import (
    CategoryListItem,
    forbidden_message,
    list_category_documents,
)

router = APIRouter(tags=["analyses"])

CATEGORY = "analyses"
LABEL = "analyses"
FORBIDDEN_MESSAGE = forbidden_message(LABEL)


@router.get("/analyses", response_model=list[CategoryListItem])
async def list_analyses(
    patient_id: UUID | None = None,
    ctx: RequestContext = Depends(get_request_context),
) -> list[CategoryListItem]:
    return await list_category_documents(
        ctx, category=CATEGORY, label=LABEL, patient_id=patient_id
    )
