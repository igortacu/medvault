"""Stand-in for the live institutional fetch used by the category list tests.

Replaces `categories.aggregation.fetch_institutional` so these tests stay about
filtering, merging and the caregiver gate, without HTTP or institution connections.
The aggregation layer itself is covered by test_aggregation.py.
"""
from datetime import date
from uuid import UUID

from app.aggregation.service import SourceStatus
from app.documents import categories
from app.documents.categories import CategoryListItem

_PLACEHOLDERS: dict[str, list[dict]] = {
    "diagnoses": [
        dict(
            id="bbbbbbbb-0000-0000-0000-000000000001",
            type="diagnosis_record",
            title="Essential hypertension",
            document_date=date(2026, 3, 2),
            specialty="Cardiology",
            practitioner_name="Dr. Mihai Popa",
            source="IMSP Institutul de Cardiologie",
            original_path="/institutions/imsp-institutul-cardiologie/Condition/cond-0001",
        ),
        dict(
            id="bbbbbbbb-0000-0000-0000-000000000002",
            type="consultation_report",
            title="Neurology consultation",
            document_date=date(2025, 11, 18),
            specialty="Neurology",
            practitioner_name="Dr. Ana Ceban",
            source="Spitalul Clinic Republican „Timofei Moșneaga”",
            original_path="/institutions/imsp-scr-t-mosneaga/DocumentReference/note-0001",
        ),
    ],
    "prescriptions": [
        dict(
            id="aaaaaaaa-0000-0000-0000-000000000001",
            type="prescription",
            title="Amoxicillin 500mg",
            document_date=date(2026, 3, 12),
            specialty="General Medicine",
            practitioner_name="Dr. Andrei Rusu",
            source="Spitalul Clinic Republican „Timofei Moșneaga”",
            original_path="/institutions/imsp-scr-t-mosneaga/MedicationRequest/med-0001",
        ),
        dict(
            id="aaaaaaaa-0000-0000-0000-000000000002",
            type="medication_record",
            title="Metformin 850mg",
            document_date=date(2026, 1, 28),
            specialty="Endocrinology",
            practitioner_name="Dr. Elena Cojocaru",
            source="Spitalul Internațional Medpark",
            original_path="/institutions/medpark/MedicationStatement/med-0002",
        ),
        dict(
            id="aaaaaaaa-0000-0000-0000-000000000003",
            type="treatment_plan",
            title="Hypertension treatment plan",
            document_date=date(2025, 12, 5),
            specialty="Cardiology",
            practitioner_name="Dr. Mihai Popa",
            source="IMSP Institutul de Cardiologie",
            original_path="/institutions/imsp-institutul-cardiologie/CarePlan/cp-0001",
        ),
    ],
    "certificates": [
        dict(
            id="cccccccc-0000-0000-0000-000000000001",
            type="illness_certificate",
            title="Medical certificate of illness",
            document_date=date(2026, 2, 20),
            specialty="Family Medicine",
            practitioner_name="Dr. Victor Moraru",
            source="Spitalul Clinic Municipal „Sfânta Treime”",
            original_path="/institutions/imsp-scm-sfanta-treime/DocumentReference/cert-0001",
        ),
        dict(
            id="cccccccc-0000-0000-0000-000000000002",
            type="vaccination_certificate",
            title="COVID-19 vaccination certificate",
            document_date=date(2025, 10, 9),
            specialty="Immunology",
            practitioner_name="Dr. Ana Ceban",
            source="Spitalul Internațional Medpark",
            original_path="/institutions/medpark/DocumentReference/cert-0002",
        ),
    ],
    "analyses": [
        dict(
            id="dddddddd-0000-0000-0000-000000000001",
            type="blood_test",
            title="Complete blood count",
            document_date=date(2026, 3, 15),
            specialty="Hematology",
            practitioner_name="Dr. Elena Cojocaru",
            source="Spitalul Internațional Medpark",
            original_path="/institutions/medpark/DiagnosticReport/lab-0001",
        ),
        dict(
            id="dddddddd-0000-0000-0000-000000000002",
            type="xray_report",
            title="Chest X-ray",
            document_date=date(2026, 1, 10),
            specialty="Radiology",
            practitioner_name="Dr. Sergiu Balan",
            source="Spitalul Clinic Republican „Timofei Moșneaga”",
            original_path="/institutions/imsp-scr-t-mosneaga/DiagnosticReport/img-0001",
        ),
    ],
    "other_med_info": [
        dict(
            id="eeeeeeee-0000-0000-0000-000000000001",
            type="hospitalization_record",
            title="Admission — cardiology ward",
            document_date=date(2026, 2, 1),
            specialty="Cardiology",
            practitioner_name="Dr. Mihai Popa",
            source="IMSP Institutul de Cardiologie",
            original_path="/institutions/imsp-institutul-cardiologie/Encounter/enc-0001",
        ),
        dict(
            id="eeeeeeee-0000-0000-0000-000000000002",
            type="immunization_record",
            title="Influenza immunization",
            document_date=date(2025, 10, 3),
            specialty="Family Medicine",
            practitioner_name="Dr. Victor Moraru",
            source="Spitalul Clinic Municipal Bălți",
            original_path="/institutions/imsp-scm-balti/Immunization/imm-0001",
        ),
    ],
}


INSTITUTION_ID = UUID("99999999-9999-9999-9999-999999999999")


def placeholders(category: str) -> list[CategoryListItem]:
    return [CategoryListItem(**spec) for spec in _PLACEHOLDERS.get(category, [])]


def install():
    """Patch the fetch; returns the original so tests can restore it."""
    original = categories.aggregation.fetch_institutional

    async def fake(ctx, category, patient_id, http=None):
        rows = [dict(spec) for spec in _PLACEHOLDERS.get(category, [])]
        sources = [
            SourceStatus(institution_id=INSTITUTION_ID, institution="Stub", status="ok", count=len(rows))
        ] if rows else []
        return rows, sources

    categories.aggregation.fetch_institutional = fake
    return original


def uninstall(original):
    categories.aggregation.fetch_institutional = original
