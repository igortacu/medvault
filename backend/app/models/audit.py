"""audit_logs (schema section 7).

No foreign keys on purpose: audit rows must survive deletion of the user,
document or connection they describe. RLS and append-only enforcement are in
migration 0006, not expressible in the ORM.
"""
import datetime
import uuid

from sqlalchemy import BigInteger, CheckConstraint, Identity, Index, LargeBinary, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    occurred_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    subject_patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(Text)
    resource_id: Mapped[str | None] = mapped_column(Text)
    institution_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    ip_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        CheckConstraint(
            "outcome IN ('success', 'denied', 'failure')", name="audit_logs_outcome_check"
        ),
        Index("audit_logs_subject_time", "subject_patient_id", text("occurred_at DESC")),
        Index("audit_logs_actor_time", "actor_user_id", text("occurred_at DESC")),
    )
