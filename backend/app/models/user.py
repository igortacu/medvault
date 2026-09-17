"""users and patient_profiles (schema sections 2.1, 2.2)."""
import datetime
import decimal
import uuid

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .enums import user_status


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    phone_e164: Mapped[str] = mapped_column(String(12), nullable=False)
    date_of_birth: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        user_status, nullable=False, server_default=text("'pending_verification'")
    )
    phone_verified_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    password_changed_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    profile: Mapped["PatientProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (
        UniqueConstraint("phone_e164", name="users_phone_unique"),
        CheckConstraint(r"phone_e164 ~ '^\+373[0-9]{8}$'", name="users_phone_format"),
        CheckConstraint("char_length(first_name) BETWEEN 2 AND 50", name="users_first_name_len"),
        CheckConstraint("char_length(last_name) BETWEEN 2 AND 50", name="users_last_name_len"),
        CheckConstraint(
            "date_of_birth <= current_date "
            "AND date_of_birth >= current_date - interval '120 years'",
            name="users_dob_range",
        ),
        CheckConstraint(
            "status = 'pending_verification' OR phone_verified_at IS NOT NULL",
            name="users_verified_consistency",
        ),
    )


class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("medvault.users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    weight_kg: Mapped[decimal.Decimal | None] = mapped_column(Numeric(5, 2))
    height_cm: Mapped[decimal.Decimal | None] = mapped_column(Numeric(5, 1))
    measurements_updated_at: Mapped[datetime.datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    user: Mapped["User"] = relationship(back_populates="profile")

    __table_args__ = (
        CheckConstraint("weight_kg > 0 AND weight_kg < 500", name="patient_profiles_weight_kg_check"),
        CheckConstraint("height_cm > 0 AND height_cm < 300", name="patient_profiles_height_cm_check"),
    )
