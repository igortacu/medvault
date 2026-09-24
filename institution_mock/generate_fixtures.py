"""Generate mock fixtures for every app-DB institution, coherent with them.

Institution ids equal the app DB `medvault.institutions.external_id`, so a
connection created in the app finds a matching mock here. Non-destructive: an
institution that already has a fixtures folder is left untouched (keeps the
hand-authored imsp-scr-t-mosneaga / medpark fixtures the tests rely on).

Run:  python -m institution_mock.generate_fixtures
"""
from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).with_name("fixtures")
SHARED_IDNP = "2001234567890"  # the shared dev IDNP (Maria Rusu)

# id -> (name, type, city). Names mirror the app DB catalogue (— Demo marks synthetic).
INSTITUTIONS: dict[str, tuple[str, str, str]] = {
    "imsp-scr-t-mosneaga": ("Spitalul Clinic Republican „Timofei Moșneaga” — Demo", "public", "Chișinău"),
    "imsp-institutul-mamei-copilului": ("IMSP Institutul Mamei și Copilului — Demo", "public", "Chișinău"),
    "imsp-scm-sfanta-treime": ("Spitalul Clinic Municipal „Sfânta Treime” — Demo", "public", "Chișinău"),
    "imsp-institutul-oncologic": ("IMSP Institutul Oncologic — Demo", "public", "Chișinău"),
    "imsp-institutul-cardiologie": ("IMSP Institutul de Cardiologie — Demo", "public", "Chișinău"),
    "imsp-scm-balti": ("Spitalul Clinic Municipal Bălți — Demo", "public", "Bălți"),
    "medpark": ("Spitalul Internațional Medpark — Demo", "private", "Chișinău"),
    "terramed": ("Clinica Terramed — Demo", "private", "Chișinău"),
    "excellence": ("Clinica Excellence — Demo", "private", "Chișinău"),
    "repromed": ("Centrul Medical Repromed — Demo", "private", "Chișinău"),
}

# Per-institution clinical variation (planted cases). Default = one normal lab value.
#   value/unit/interp let us plant an out-of-range flag; "none" plants a zero-record patient.
OBSERVATIONS: dict[str, dict] = {
    "imsp-institutul-cardiologie": {"value": 9.0, "interp": ("LL", "Critically low")},
    "imsp-institutul-oncologic": {"none": True},  # zero-record patient
}


def _institution(inst_id: str, name: str, itype: str, city: str) -> list[dict]:
    return [{
        "kind": "Institution",
        "id": inst_id,
        "name": name,
        "type": itype,
        "city": city,
        "fhirBasePath": f"/{inst_id}/fhir",
        "active": True,
    }]


def _patient(inst_id: str) -> list[dict]:
    return [{
        "resourceType": "Patient",
        "id": "pat-001",
        "meta": {"source": f"urn:medvault:institution:{inst_id}"},
        "identifier": [{"system": "urn:medvault:idnp", "value": SHARED_IDNP}],
        "name": [{"family": "Rusu", "given": ["Maria"]}],
        "gender": "female",
        "birthDate": "1958-03-14",
    }]


def _observation(inst_id: str) -> list[dict]:
    spec = OBSERVATIONS.get(inst_id, {})
    if spec.get("none"):
        return []
    value = spec.get("value", 13.2)
    interp = spec.get("interp", ("N", "Normal"))
    return [{
        "resourceType": "Observation",
        "id": "obs-001",
        "meta": {"source": f"urn:medvault:institution:{inst_id}"},
        "status": "final",
        "category": [{"coding": [
            {"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory"},
            {"system": "urn:medvault:document-type", "code": "blood_test"},
        ]}],
        "code": {"coding": [{"system": "http://loinc.org", "code": "718-7", "display": "Hemoglobin"}]},
        "subject": {"reference": "Patient/pat-001"},
        "effectiveDateTime": "2026-08-20T08:30:00Z",
        "valueQuantity": {"value": value, "unit": "g/dL", "system": "http://unitsofmeasure.org", "code": "g/dL"},
        "interpretation": [{"coding": [{"code": interp[0], "display": interp[1]}]}],
    }]


def _write(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    created, skipped = [], []
    for inst_id, (name, itype, city) in INSTITUTIONS.items():
        directory = FIXTURES / inst_id
        if directory.exists():
            skipped.append(inst_id)
            continue
        directory.mkdir(parents=True)
        _write(directory / "Institution.json", _institution(inst_id, name, itype, city))
        _write(directory / "Patient.json", _patient(inst_id))
        _write(directory / "Observation.json", _observation(inst_id))
        created.append(inst_id)

    print(f"created ({len(created)}): {', '.join(created) or '—'}")
    print(f"skipped existing ({len(skipped)}): {', '.join(skipped) or '—'}")


if __name__ == "__main__":
    main()
