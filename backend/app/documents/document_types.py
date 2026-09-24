"""The shared category -> document_type list (schema decision D5).

Mirrors the `documents_type_matches_category` CHECK constraint (see
app/models/document.py) so uploads can be validated in the app layer with a
clear field error *before* touching storage, instead of relying on a database
constraint violation. Self-uploads and institutional records draw from the same
list. `patient_info` is intentionally absent — it holds measurements, not
documents (the `documents_category_not_patient_info` CHECK).
"""

CATEGORY_DOCUMENT_TYPES: dict[str, frozenset[str]] = {
    "diagnoses": frozenset(
        {
            "medical_history",
            "surgical_history",
            "family_history",
            "progress_note",
            "diagnosis_record",
            "medical_examination_report",
            "consultation_report",
        }
    ),
    "certificates": frozenset(
        {
            "disability_certificate",
            "illness_certificate",
            "fitness_certificate",
            "vaccination_certificate",
            "birth_certificate",
            "hospitalization_certificate",
            "medical_examination_certificate",
            "pregnancy_certificate",
            "health_certificate",
        }
    ),
    "analyses": frozenset(
        {
            "blood_test",
            "urinalysis",
            "biochemistry_report",
            "hormone_test",
            "microbiology_report",
            "pathology_report",
            "xray_report",
            "ultrasound_report",
            "ct_report",
            "mri_report",
            "ecg_report",
            "endoscopy_report",
            "radiology_images",
            "operative_report",
        }
    ),
    "prescriptions": frozenset(
        {
            "prescription",
            "medication_record",
            "treatment_plan",
            "procedure_record",
        }
    ),
    "other_med_info": frozenset(
        {
            "hospitalization_record",
            "discharge_summary",
            "pregnancy_record",
            "allergy_record",
            "immunization_record",
            "referral",
        }
    ),
}


def is_valid_pair(category: str, document_type: str) -> bool:
    """True if `document_type` belongs to `category` per the shared list."""
    return document_type in CATEGORY_DOCUMENT_TYPES.get(category, frozenset())
