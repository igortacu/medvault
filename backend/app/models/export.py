"""data_exports (schema section 6)."""
import datetime
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .enums import data_category, export_format, export_status


class DataExport(Base):
    __tablename__ = "data_exports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    patient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medvault.users.id", ondelete="CASCADE"), nullable=False
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medvault.users.id"), nullable=False
    )
    format: Mapped[str] = mapped_column(export_format, nullable=False)
    categories: Mapped[list[str]] = mapped_column(ARRAY(data_category), nullable=False)
    scope_ref: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        export_status, nullable=False, server_default=text("'requested'")
    )
    storage_bucket: Mapped[str | None] = mapped_column(Text)
    object_key: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status <> 'ready' OR (object_key IS NOT NULL AND expires_at IS NOT NULL)",
            name="export_ready_has_file",
        ),
    )
