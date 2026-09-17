"""Python enums mirroring the medvault PostgreSQL enum types.

Each PG type is created by migration 0001, so the reusable ENUM objects here use
create_type=False (SQLAlchemy must never try to CREATE/DROP them). values_callable
sends the member *values* to Postgres, which is what the DB enum labels are.
"""
import enum

from sqlalchemy.dialects.postgresql import ENUM


class DataCategory(str, enum.Enum):
    diagnoses = "diagnoses"
    certificates = "certificates"
    analyses = "analyses"
    prescriptions = "prescriptions"
    patient_info = "patient_info"
    other_med_info = "other_med_info"


class DocumentType(str, enum.Enum):
    medical_history = "medical_history"
    surgical_history = "surgical_history"
    family_history = "family_history"
    progress_note = "progress_note"
    diagnosis_record = "diagnosis_record"
    medical_examination_report = "medical_examination_report"
    consultation_report = "consultation_report"
    disability_certificate = "disability_certificate"
    illness_certificate = "illness_certificate"
    fitness_certificate = "fitness_certificate"
    vaccination_certificate = "vaccination_certificate"
    birth_certificate = "birth_certificate"
    hospitalization_certificate = "hospitalization_certificate"
    medical_examination_certificate = "medical_examination_certificate"
    pregnancy_certificate = "pregnancy_certificate"
    health_certificate = "health_certificate"
    blood_test = "blood_test"
    urinalysis = "urinalysis"
    biochemistry_report = "biochemistry_report"
    hormone_test = "hormone_test"
    microbiology_report = "microbiology_report"
    pathology_report = "pathology_report"
    xray_report = "xray_report"
    ultrasound_report = "ultrasound_report"
    ct_report = "ct_report"
    mri_report = "mri_report"
    ecg_report = "ecg_report"
    endoscopy_report = "endoscopy_report"
    radiology_images = "radiology_images"
    operative_report = "operative_report"
    prescription = "prescription"
    medication_record = "medication_record"
    treatment_plan = "treatment_plan"
    procedure_record = "procedure_record"
    hospitalization_record = "hospitalization_record"
    discharge_summary = "discharge_summary"
    pregnancy_record = "pregnancy_record"
    allergy_record = "allergy_record"
    immunization_record = "immunization_record"
    referral = "referral"


class UserStatus(str, enum.Enum):
    pending_verification = "pending_verification"
    active = "active"
    locked = "locked"
    disabled = "disabled"


class InstitutionType(str, enum.Enum):
    public = "public"
    private = "private"


class ConnectionOrigin(str, enum.Enum):
    auto_public = "auto_public"
    user_added = "user_added"


class ConnectionStatus(str, enum.Enum):
    pending_consent = "pending_consent"
    authorizing = "authorizing"
    active = "active"
    no_match = "no_match"
    revoked = "revoked"
    expired = "expired"
    error = "error"


class CaregiverLinkStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    rejected = "rejected"
    revoked = "revoked"


class DocumentStatus(str, enum.Enum):
    stored = "stored"
    rejected = "rejected"


class ExtractionStatus(str, enum.Enum):
    not_requested = "not_requested"
    pending = "pending"
    awaiting_review = "awaiting_review"
    confirmed = "confirmed"
    rejected = "rejected"


class ExportFormat(str, enum.Enum):
    pdf = "pdf"
    json = "json"


class ExportStatus(str, enum.Enum):
    requested = "requested"
    processing = "processing"
    ready = "ready"
    failed = "failed"
    expired = "expired"


def _pg(py_enum: type[enum.Enum], name: str) -> ENUM:
    return ENUM(
        py_enum,
        name=name,
        schema="medvault",
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )


# Reusable type instances — define once, share across columns (incl. arrays).
data_category = _pg(DataCategory, "data_category")
document_type = _pg(DocumentType, "document_type")
user_status = _pg(UserStatus, "user_status")
institution_type = _pg(InstitutionType, "institution_type")
connection_origin = _pg(ConnectionOrigin, "connection_origin")
connection_status = _pg(ConnectionStatus, "connection_status")
caregiver_link_status = _pg(CaregiverLinkStatus, "caregiver_link_status")
document_status = _pg(DocumentStatus, "document_status")
extraction_status = _pg(ExtractionStatus, "extraction_status")
export_format = _pg(ExportFormat, "export_format")
export_status = _pg(ExportStatus, "export_status")
