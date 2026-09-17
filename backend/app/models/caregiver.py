"""caregiver_links and caregiver_permissions (schema sections 4.1, 4.2)."""
import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import caregiver_link_status, data_category


class CaregiverLink(Base):
    __tablename__ = "caregiver_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    patient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medvault.users.id", ondelete="CASCADE"), nullable=False
    )
    caregiver_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medvault.users.id", ondelete="CASCADE")
    )
    invited_first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    invited_last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    invited_phone_e164: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(
        caregiver_link_status, nullable=False, server_default=text("'pending'")
    )
    invited_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    responded_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medvault.users.id")
    )

    permissions: Mapped[list["CaregiverPermission"]] = relationship(
        back_populates="link", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "caregiver_user_id IS NULL OR caregiver_user_id <> patient_user_id", name="link_not_self"
        ),
        CheckConstraint(
            "status <> 'active' OR caregiver_user_id IS NOT NULL", name="link_active_has_user"
        ),
        CheckConstraint(
            "(status = 'revoked') = (revoked_at IS NOT NULL)", name="link_revoked_consistency"
        ),
        CheckConstraint(
            r"invited_phone_e164 ~ '^\+373[0-9]{8}$'", name="caregiver_links_invited_phone_e164_check"
        ),
        Index(
            "caregiver_links_one_live_invite",
            "patient_user_id",
            "invited_phone_e164",
            unique=True,
            postgresql_where=text("status IN ('pending', 'active')"),
        ),
        Index(
            "caregiver_links_one_live_pair",
            "patient_user_id",
            "caregiver_user_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'active') AND caregiver_user_id IS NOT NULL"),
        ),
        Index("caregiver_links_patient", "patient_user_id", "status"),
        Index("caregiver_links_caregiver", "caregiver_user_id", "status"),
    )


class CaregiverPermission(Base):
    __tablename__ = "caregiver_permissions"

    link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medvault.caregiver_links.id", ondelete="CASCADE"),
        primary_key=True,
    )
    category: Mapped[str] = mapped_column(data_category, primary_key=True)
    can_view: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    can_view_original: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    can_export: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    can_upload: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    granted_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    link: Mapped["CaregiverLink"] = relationship(back_populates="permissions")

    __table_args__ = (
        CheckConstraint(
            "can_view OR NOT (can_view_original OR can_export OR can_upload)",
            name="perm_actions_imply_view",
        ),
    )
