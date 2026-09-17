"""documents — self-uploaded files (schema section 5.2)."""
import datetime
import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .enums import data_category, document_status, document_type, extraction_status

# The category<->document_type mapping, mirrored from the DB CHECK constraint.
_TYPE_MATCHES_CATEGORY = """
    (document_type IN ('medical_history', 'surgical_history', 'family_history', 'progress_note',
                'diagnosis_record', 'medical_examination_report', 'consultation_report')
      AND category = 'diagnoses')
    OR
    (document_type IN ('disability_certificate', 'illness_certificate', 'fitness_certificate',
                 'vaccination_certificate', 'birth_certificate', 'hospitalization_certificate',
                 'medical_examination_certificate', 'pregnancy_certificate', 'health_certificate')
      AND category = 'certificates')
    OR
    (document_type IN ('blood_test', 'urinalysis', 'biochemistry_report', 'hormone_test',
                 'microbiology_report', 'pathology_report', 'xray_report', 'ultrasound_report',
                 'ct_report', 'mri_report', 'ecg_report', 'endoscopy_report',
                 'radiology_images', 'operative_report')
      AND category = 'analyses')
    OR
    (document_type IN ('prescription', 'medication_record', 'treatment_plan', 'procedure_record')
      AND category = 'prescriptions')
    OR
    (document_type IN ('hospitalization_record', 'discharge_summary', 'pregnancy_record',
                 'allergy_record', 'immunization_record', 'referral')
      AND category = 'other_med_info')
"""


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    patient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medvault.users.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medvault.users.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(data_category, nullable=False)
    document_type: Mapped[str] = mapped_column(document_type, nullable=False)
    title_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    notes_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    metadata_key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    document_date: Mapped[datetime.date | None] = mapped_column(Date)
    specialty: Mapped[str | None] = mapped_column(Text)
    issuer_name: Mapped[str | None] = mapped_column(Text)
    practitioner_name: Mapped[str | None] = mapped_column(Text)
    storage_bucket: Mapped[str] = mapped_column(Text, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    status: Mapped[str] = mapped_column(
        document_status, nullable=False, server_default=text("'stored'")
    )
    extraction_status: Mapped[str] = mapped_column(
        extraction_status, nullable=False, server_default=text("'not_requested'")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("category <> 'patient_info'", name="documents_category_not_patient_info"),
        CheckConstraint(_TYPE_MATCHES_CATEGORY, name="documents_type_matches_category"),
        UniqueConstraint("storage_bucket", "object_key", name="documents_object_key_unique"),
        CheckConstraint(
            "mime_type IN ('application/pdf', 'image/jpeg', 'image/png')",
            name="documents_mime_allowed",
        ),
        CheckConstraint("size_bytes > 0 AND size_bytes <= 10485760", name="documents_size_range"),
        CheckConstraint("octet_length(sha256) = 32", name="documents_sha256_len"),
        CheckConstraint(
            "document_date IS NULL OR document_date <= current_date",
            name="documents_date_not_future",
        ),
        Index(
            "documents_patient_category_date",
            "patient_user_id",
            "category",
            text("document_date DESC"),
        ),
        Index(
            "documents_patient_specialty",
            "patient_user_id",
            "specialty",
            postgresql_where=text("specialty IS NOT NULL"),
        ),
    )
