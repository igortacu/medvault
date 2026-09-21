"""GET/PUT /patient-info — the patient's profile (category 5, "Patient's info").

Single current weight/height on patient_profiles (shipped schema — no history).
Name/DOB come from the medvault.patient_basics() SECURITY DEFINER function so a
permitted caregiver can see them without a broad SELECT on users. Writes go
through RLS: owner via profiles_owner, caregiver via the profiles_caregiver_*
policies (migration 0008), gated on caregiver_can(..., 'patient_info', ...).

Institutional body-weight/height Observations are placeholder rows for now (a
`source` per entry), pending the Epic 2 live-FHIR aggregation. No IDNP is ever
returned — none is stored.
"""
import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from app.audit.logger import write_audit_log
from app.auth.dependencies import RequestContext, get_request_context
from app.models.user import PatientProfile

router = APIRouter(tags=["patient-info"])

CATEGORY = "patient_info"
VIEW_FORBIDDEN = "You do not have access to this patient's info."
UPLOAD_FORBIDDEN = "You are not allowed to update this patient's measurements."

WEIGHT_MIN, WEIGHT_MAX = 0, 500
HEIGHT_MIN, HEIGHT_MAX = 0, 300


class InstitutionalMeasurement(BaseModel):
    source: str
    measured_at: datetime.date
    weight_kg: float | None = None
    height_cm: float | None = None


class PatientInfoResponse(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: datetime.date | None = None
    weight_kg: float | None = None
    height_cm: float | None = None
    measurements_updated_at: datetime.datetime | None = None
    source: str = "Self-entered"
    institutional_measurements: list[InstitutionalMeasurement] = []


class MeasurementResponse(BaseModel):
    weight_kg: float | None = None
    height_cm: float | None = None
    measurements_updated_at: datetime.datetime | None = None


class MeasurementUpdate(BaseModel):
    weight_kg: float | None = None
    height_cm: float | None = None


def _institutional_measurements() -> list[InstitutionalMeasurement]:
    """Placeholder institutional body measurements until live FHIR exists."""
    return [
        InstitutionalMeasurement(
            source="IMSP Institutul de Cardiologie",
            measured_at=datetime.date(2026, 2, 1),
            weight_kg=78.5,
            height_cm=176.0,
        ),
    ]


async def _caregiver_gate(ctx, target: UUID, action: str, forbidden: str) -> None:
    allowed = await ctx.db.scalar(
        text(
            "SELECT medvault.caregiver_can("
            "CAST(:patient AS uuid), 'patient_info', :action)"
        ),
        {"patient": str(target), "action": action},
    )
    if not allowed:
        await write_audit_log(
            ctx.db,
            actor_user_id=UUID(str(ctx.user_id)),
            subject_patient_id=target,
            action="patient_info",
            resource_type="patient_info",
            resource_id=None,
            outcome="denied",
            metadata={"action": action},
        )
        await ctx.db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=forbidden)


@router.get("/patient-info", response_model=PatientInfoResponse)
async def get_patient_info(
    patient_id: UUID | None = None,
    ctx: RequestContext = Depends(get_request_context),
) -> PatientInfoResponse:
    actor = UUID(str(ctx.user_id))
    target = patient_id or actor

    if target != actor:
        await _caregiver_gate(ctx, target, "view", VIEW_FORBIDDEN)

    # Name/DOB via the SECURITY DEFINER function (safe columns only, self-gated).
    basics = (
        await ctx.db.execute(
            text(
                "SELECT first_name, last_name, date_of_birth "
                "FROM medvault.patient_basics(CAST(:p AS uuid))"
            ),
            {"p": str(target)},
        )
    ).first()

    # Current measurement (RLS: owner, or caregiver with patient_info view).
    profile = await ctx.db.get(PatientProfile, target)

    await write_audit_log(
        ctx.db,
        actor_user_id=actor,
        subject_patient_id=target,
        action="patient_info",
        resource_type="patient_info",
        resource_id=None,
        outcome="success",
        metadata={"action": "view"},
    )
    await ctx.db.commit()

    return PatientInfoResponse(
        first_name=basics[0] if basics else None,
        last_name=basics[1] if basics else None,
        date_of_birth=basics[2] if basics else None,
        weight_kg=float(profile.weight_kg) if profile and profile.weight_kg is not None else None,
        height_cm=float(profile.height_cm) if profile and profile.height_cm is not None else None,
        measurements_updated_at=profile.measurements_updated_at if profile else None,
        institutional_measurements=_institutional_measurements(),
    )


@router.put("/patient-info", response_model=MeasurementResponse)
async def update_patient_info(
    body: MeasurementUpdate,
    patient_id: UUID | None = None,
    ctx: RequestContext = Depends(get_request_context),
) -> MeasurementResponse:
    actor = UUID(str(ctx.user_id))
    target = patient_id or actor

    if body.weight_kg is None and body.height_cm is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide weight_kg and/or height_cm.",
        )
    if body.weight_kg is not None and not (WEIGHT_MIN < body.weight_kg < WEIGHT_MAX):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="weight_kg out of range.",
        )
    if body.height_cm is not None and not (HEIGHT_MIN < body.height_cm < HEIGHT_MAX):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="height_cm out of range.",
        )

    if target != actor:
        await _caregiver_gate(ctx, target, "upload", UPLOAD_FORBIDDEN)

    now = datetime.datetime.now(datetime.timezone.utc)
    profile = await ctx.db.get(PatientProfile, target)
    if profile is None:
        profile = PatientProfile(
            user_id=target,
            weight_kg=body.weight_kg,
            height_cm=body.height_cm,
            measurements_updated_at=now,
        )
        ctx.db.add(profile)
    else:
        if body.weight_kg is not None:
            profile.weight_kg = body.weight_kg
        if body.height_cm is not None:
            profile.height_cm = body.height_cm
        profile.measurements_updated_at = now

    await write_audit_log(
        ctx.db,
        actor_user_id=actor,
        subject_patient_id=target,
        action="patient_info",
        resource_type="patient_info",
        resource_id=None,
        outcome="success",
        metadata={"action": "update"},
    )
    await ctx.db.commit()

    return MeasurementResponse(
        weight_kg=float(profile.weight_kg) if profile.weight_kg is not None else None,
        height_cm=float(profile.height_cm) if profile.height_cm is not None else None,
        measurements_updated_at=profile.measurements_updated_at,
    )
