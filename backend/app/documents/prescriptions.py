"""GET /prescriptions — list a patient's prescriptions.

Thin wrapper over the shared category-list helper (app/documents/categories.py),
which enforces RLS + the caregiver_can 403 gate + audit and merges in placeholder
institutional records until the Epic 2 live-FHIR aggregation exists.
"""
from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.dependencies import RequestContext, get_request_context
from app.documents.categories import (
    CategoryListItem,
    forbidden_message,
    list_category_documents,
)

router = APIRouter(tags=["prescriptions"])

CATEGORY = "prescriptions"
LABEL = "prescriptions"
FORBIDDEN_MESSAGE = forbidden_message(LABEL)


@router.get(
    "/prescriptions",
    response_model=list[CategoryListItem],
    response_model_exclude_none=True,
)
async def list_prescriptions(
    patient_id: UUID | None = None,
    source: str | None = None,
    ctx: RequestContext = Depends(get_request_context),
) -> list[CategoryListItem]:
    return await list_category_documents(
        ctx, category=CATEGORY, label=LABEL, patient_id=patient_id, source=source
    )
