import json
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def write_audit_log(
    db: AsyncSession,
    *,
    actor_user_id: UUID | str | None,
    subject_patient_id: UUID | str | None,
    action: str,
    resource_type: str,
    resource_id: UUID | str | None,
    outcome: str,
    metadata: dict | None = None,
) -> None:
    await db.execute(
        text(
            """
            INSERT INTO medvault.audit_logs (
                actor_user_id,
                subject_patient_id,
                action,
                resource_type,
                resource_id,
                outcome,
                metadata
            ) VALUES (
                CAST(:actor_user_id AS uuid),
                CAST(:subject_patient_id AS uuid),
                :action,
                :resource_type,
                :resource_id,
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
            "outcome": outcome,
            "metadata": json.dumps(metadata or {}),
        },
    )
