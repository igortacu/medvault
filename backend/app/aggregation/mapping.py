"""FHIR resource -> shared list-row mapping (Epic 2, story 0 / 7).

Each category pulls a fixed set of FHIR resource types. A resource becomes a row only
if its MedVault subtype (the `urn:medvault:document-type` coding, or a sensible default
for the resource type) belongs to the category per the shared D5 list. Specialty comes
from the `urn:medvault:specialty` extension. Everything here is pure and tolerant of
missing fields: institutions are external, so nothing is assumed present.
"""
from datetime import date
from uuid import NAMESPACE_URL, UUID, uuid5

from app.documents.document_types import CATEGORY_DOCUMENT_TYPES

DOCUMENT_TYPE_SYSTEM = "urn:medvault:document-type"
SPECIALTY_EXTENSION = "urn:medvault:specialty"

CATEGORY_RESOURCE_TYPES: dict[str, tuple[str, ...]] = {
    "diagnoses": ("Condition", "DocumentReference"),
    "prescriptions": ("MedicationRequest", "MedicationStatement", "CarePlan", "Procedure"),
    "analyses": ("DiagnosticReport", "ImagingStudy"),
    "other_med_info": ("Encounter", "Immunization", "DocumentReference"),
    "certificates": ("DocumentReference",),
}

ALL_RESOURCE_TYPES: tuple[str, ...] = tuple(
    dict.fromkeys(t for types in CATEGORY_RESOURCE_TYPES.values() for t in types)
)

# Subtype used when the resource carries no document-type coding.
_DEFAULT_SUBTYPE = {
    "Condition": "diagnosis_record",
    "MedicationRequest": "prescription",
    "MedicationStatement": "medication_record",
    "CarePlan": "treatment_plan",
    "Procedure": "procedure_record",
    "ImagingStudy": "radiology_images",
    "Immunization": "immunization_record",
}

_DATE_FIELDS = (
    "recordedDate", "onsetDateTime", "authoredOn", "dateAsserted", "effectiveDateTime",
    "performedDateTime", "occurrenceDateTime", "issued", "started", "created", "date",
)
_TITLE_FIELDS = (
    "code", "medicationCodeableConcept", "vaccineCode", "type", "description", "title",
)


def scope_for(resource_type: str) -> str:
    return f"patient/{resource_type}.read"


def record_reference(external_id: str, resource_type: str, resource_id: str) -> str:
    return f"institution:{external_id}/{resource_type}/{resource_id}"


def reference_uuid(reference: str) -> UUID:
    """Stable id for a record so list rows keep the same id between requests."""
    return uuid5(NAMESPACE_URL, reference)


# Institutions are external: any field may be missing or the wrong type. These helpers
# make every access total, so a malformed resource yields fewer fields, not an exception.
def _d(value) -> dict:
    return value if isinstance(value, dict) else {}


def _l(value) -> list:
    return value if isinstance(value, list) else []


def _s(value) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _codings(value) -> list[dict]:
    """Codings from a CodeableConcept, or from a list of them."""
    if isinstance(value, dict):
        return [c for c in _l(value.get("coding")) if isinstance(c, dict)]
    if isinstance(value, list):
        return [c for item in value for c in _codings(item)]
    return []


def _subtype(resource: dict, rtype: str) -> str | None:
    for field in ("category", "type", "code"):
        for coding in _codings(resource.get(field)):
            code = coding.get("code")
            if coding.get("system") == DOCUMENT_TYPE_SYSTEM and isinstance(code, str) and code:
                return code
    if rtype == "Encounter":
        # Only inpatient stays are a vault record; ambulatory visits are not.
        return (
            "hospitalization_record"
            if _d(resource.get("class")).get("code") == "IMP"
            else None
        )
    return _DEFAULT_SUBTYPE.get(rtype)


def _text(concept) -> str | None:
    if isinstance(concept, list):
        concept = concept[0] if concept else None
    concept = _d(concept)
    if _s(concept.get("text")):
        return concept["text"]
    for coding in _codings(concept):
        if coding.get("system") != DOCUMENT_TYPE_SYSTEM and _s(coding.get("display")):
            return coding["display"]
    return None


def _title(resource: dict, rtype: str) -> str | None:
    if rtype == "Encounter":
        return _text(resource.get("reasonCode")) or "Hospitalization"
    for field in _TITLE_FIELDS:
        title = _text(resource.get(field)) or _s(resource.get(field))
        if title:
            return title
    return None


def _date(resource: dict, rtype: str) -> date | None:
    candidates = [resource.get(f) for f in _DATE_FIELDS]
    candidates.append(_d(resource.get("period")).get("start"))
    for value in candidates:
        if isinstance(value, str) and len(value) >= 10:
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                continue
    return None


def _display(ref) -> str | None:
    if isinstance(ref, list):
        ref = ref[0] if ref else None
    ref = _d(ref)
    if not ref:
        return None
    return _s(ref.get("display")) or _display(ref.get("individual")) or _display(
        ref.get("actor")
    )


def _practitioner(resource: dict) -> str | None:
    for field in (
        "requester", "recorder", "asserter", "performer", "participant", "author",
        "resultsInterpreter", "informationSource",
    ):
        name = _display(resource.get(field))
        if name:
            return name
    return None


def _specialty(resource: dict) -> str | None:
    for ext in _l(resource.get("extension")):
        ext = _d(ext)
        if ext.get("url") == SPECIALTY_EXTENSION and _s(ext.get("valueString")):
            return ext["valueString"]
    return None


def normalize(
    category: str, resource: dict, *, external_id: str, institution_name: str
) -> dict | None:
    """One FHIR resource -> kwargs for CategoryListItem, or None if it doesn't belong."""
    resource = _d(resource)
    rtype = _s(resource.get("resourceType"))
    rid = resource.get("id")
    if not rtype or not isinstance(rid, (str, int)) or not str(rid):
        return None
    if rtype not in CATEGORY_RESOURCE_TYPES.get(category, ()):
        return None
    subtype = _subtype(resource, rtype)
    if subtype not in CATEGORY_DOCUMENT_TYPES.get(category, frozenset()):
        return None
    reference = record_reference(external_id, rtype, str(rid))
    return dict(
        id=reference_uuid(reference),
        type=subtype,
        title=_title(resource, rtype),
        document_date=_date(resource, rtype),
        specialty=_specialty(resource),
        practitioner_name=_practitioner(resource),
        source=institution_name,
        original_path=reference,
    )
