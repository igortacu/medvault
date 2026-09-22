"""institutions and institution_connections (schema sections 3.1, 3.2)."""
import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import connection_origin, connection_status, institution_type


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(institution_type, nullable=False)
    city: Mapped[str | None] = mapped_column(Text)
    fhir_base_url: Mapped[str] = mapped_column(Text, nullable=False)
    par_url: Mapped[str] = mapped_column(Text, nullable=False)
    authorize_url: Mapped[str] = mapped_column(Text, nullable=False)
    token_url: Mapped[str] = mapped_column(Text, nullable=False)
    revoke_url: Mapped[str] = mapped_column(Text, nullable=False)
    oauth_client_id: Mapped[str] = mapped_column(Text, nullable=False)
    oauth_client_secret_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    oauth_secret_key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    supported_scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    connections: Mapped[list["InstitutionConnection"]] = relationship(back_populates="institution")

    __table_args__ = (UniqueConstraint("external_id", name="institutions_external_id_key"),)


class InstitutionConnection(Base):
    __tablename__ = "institution_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    patient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medvault.users.id", ondelete="CASCADE"), nullable=False
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medvault.institutions.id"), nullable=False
    )
    origin: Mapped[str] = mapped_column(connection_origin, nullable=False)
    status: Mapped[str] = mapped_column(
        connection_status, nullable=False, server_default=text("'pending_consent'")
    )
    consent_text_version: Mapped[str | None] = mapped_column(Text)
    consented_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    requested_scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    granted_scopes: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    fhir_patient_ref: Mapped[str | None] = mapped_column(Text)
    access_token_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    access_token_expires_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    refresh_token_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    token_key_version: Mapped[int | None] = mapped_column(SmallInteger)
    connected_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_fetched_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medvault.users.id")
    )
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    institution: Mapped["Institution"] = relationship(back_populates="connections")

    __table_args__ = (
        CheckConstraint(
            "status NOT IN ('authorizing', 'active') OR consented_at IS NOT NULL",
            name="conn_consent_before_active",
        ),
        CheckConstraint(
            "status <> 'active' OR (access_token_ciphertext IS NOT NULL AND connected_at IS NOT NULL)",
            name="conn_active_has_token",
        ),
        CheckConstraint(
            "(status = 'revoked') = (revoked_at IS NOT NULL)", name="conn_revoked_consistency"
        ),
        CheckConstraint(
            "status <> 'revoked' OR "
            "(access_token_ciphertext IS NULL AND refresh_token_ciphertext IS NULL)",
            name="conn_revoked_wipes_tokens",
        ),
        Index(
            "institution_connections_one_live",
            "patient_user_id",
            "institution_id",
            unique=True,
            postgresql_where=text("status IN ('pending_consent', 'authorizing', 'active')"),
        ),
        Index("institution_connections_patient", "patient_user_id", "status"),
    )
