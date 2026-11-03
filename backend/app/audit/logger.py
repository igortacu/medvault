import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.security.redaction import redact

# Mirrors the audit_logs_outcome_check constraint (app/models/audit.py). Checked here
# too so a bad value fails in unit tests, which run against a fake database.
AUDIT_OUTCOMES = frozenset({"success", "denied", "failure"})


async def write_audit_log(
    db: AsyncSession,
    *,
    actor_user_id: UUID | str | None,
    subject_patient_id: UUID | str | None,
    action: str,
    resource_type: str,
    resource_id: UUID | str | None,
    outcome: str,
    institution_id: UUID | str | None = None,
    metadata: dict | None = None,
) -> None:
    """Append an audit row. `metadata` is scrubbed (redaction.redact): identifiers,
    tokens, filenames and medical values never reach the audit trail."""
    if outcome not in AUDIT_OUTCOMES:
        raise ValueError(f"Unknown audit outcome: {outcome!r}")
    await db.execute(
        text(
            """
            INSERT INTO medvault.audit_logs (
                actor_user_id,
                subject_patient_id,
                action,
                resource_type,
                resource_id,
                institution_id,
                outcome,
                metadata
            ) VALUES (
                CAST(:actor_user_id AS uuid),
                CAST(:subject_patient_id AS uuid),
                :action,
                :resource_type,
                :resource_id,
                CAST(:institution_id AS uuid),
                :outcome,
                CAST(:metadata AS jsonb)
            )
            """
        ),
        {
            "actor_user_id": str(actor_user_id) if actor_user_id else None,
            "subject_patient_id": (
                str(subject_patient_id) if subject_patient_id else None
            ),
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
            "institution_id": str(institution_id) if institution_id else None,
            "outcome": outcome,
            "metadata": json.dumps(redact(metadata or {}), default=str),
        },
    )
