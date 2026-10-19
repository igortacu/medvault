# Institution mock

Run from the repository root:

```bash
.venv/bin/uvicorn institution_mock.app:app --port 8001
```

The service simulates the 10 seeded institutions (`external_id`s from
`backend/alembic/versions/0007_seed_institutions.py`) with synthetic data. The
shared development IDNP is `2001234567890`; the default client for an institution
is `medvault-{institution_id}` and the default secret is
`DEV_PLACEHOLDER_SECRET_REPLACE_BEFORE_PROD`. Override all secrets in a deployed
environment.

OAuth state is intentionally process-local for the single-worker development mock.
Restarting the service invalidates outstanding requests and tokens.

## Endpoints

Per institution, under `/{institution_id}`:

- `POST /oauth/par`, `GET /oauth/authorize`, `POST /oauth/token`, `POST /oauth/revoke` —
  SMART on FHIR with PKCE and pushed authorization requests (the IDNP travels only in PAR).
- `GET /fhir/Patient/{id}`, `GET /fhir/{type}` for `Observation`, `Condition`,
  `DocumentReference`, `MedicationRequest`, `MedicationStatement`, `CarePlan`,
  `Procedure`, `DiagnosticReport`, `ImagingStudy`, `Encounter`, `Immunization`.
  The subject always comes from the token; a `patient`/`subject` query parameter is
  rejected with 400. Supported search parameters: `date` (`eq/ne/gt/lt/ge/le`
  prefixes, repeatable), `status`, `category`, `type`, `code`, `class`
  (`[system|]code`, comma = OR), `_id`, `_count` (max 100) with `next` links, and
  `_include=DiagnosticReport:result` (only with `patient/Observation.read`).
  Unknown parameters are ignored.
- `GET /fhir/Binary/{id}` — the PDF behind a `DocumentReference.content.attachment`,
  `DiagnosticReport.presentedForm` or a `MedicationRequest`
  `urn:medvault:original-document` extension. Served only when the Binary's
  `securityContext` resource belongs to the token's patient and the token may read
  that resource type; someone else's file and a missing file are the same 404.
  `Accept: application/fhir+json` returns the Binary resource with base64 `data`.

Fault injection: `INSTITUTION_MOCK_FAULTS="medpark=slow:15,imsp-scm-balti=500"` delays
or fails resource searches and Binary reads for those institutions.

## Fixtures and the generator

`fixtures/` is generated — do not edit it by hand. The generator is seeded, so a run
reproduces the committed files byte for byte:

```bash
pip install -r institution_mock/requirements-dev.txt
python -m institution_mock.generate_fixtures          # rewrite fixtures/
python -m institution_mock.generate_fixtures --check  # fail if fixtures/ is stale
```

`RESEARCH.md` describes the Moldovan documents the content imitates and maps each
to a MedVault document subtype. Text is Romanian; codes stay LOINC / CIM-10 (ICD-10)
/ ATC / `urn:medvault:*`. Every PDF is watermarked *MOSTRĂ — date sintetice* and shows
the IDNP masked to its last 4 digits. Birth certificates are never generated (D16).

## Synthetic patients and planted test cases

| Key | IDNP | Patient | Known at | What it exercises |
|---|---|---|---|---|
| P01 | `2001234567890` | Maria Rusu, 1958 | all 10 | Shared dev patient, rich data. Finished hospitalization + hospitalization and vaccination certificates (**caregiver visibility**: grant certificates only and the stay stays hidden). **Critical** Hb (LL) at Institutul de Cardiologie. Known with **zero records** at Institutul Oncologic and Repromed. |
| P02 | `0944635038347` | Georgel Croitoru, 1967 | SCM „Sfânta Treime”, Terramed | **In-progress hospitalization** (Encounter `IMP`, `in-progress`, no `period.end`, no discharge summary) with an open sick-leave certificate. |
| P03 | `0769711762628` | Georgeta Ursu, 1979 | Institutul Oncologic, SCM Bălți | **Zero-record patient**: connects, every search is empty. |
| P04 | `0798727493313` | Martin Rusu, 1961 | Institutul de Cardiologie, SCM Bălți | **Critical values** (troponin I, potassium, glucose — `HH`) at SCM Bălți, with a referral 027/e. |
| P05 | `0715591277785` | Todor Croitoru, 1996 | Terramed, Medpark | **Prompt-injection fixture**: a Terramed consultation report whose `description` and PDF (white-on-white text) carry injected instructions. |
| P06 | `0357073380867` | Petronela Cebotari, 2002 | Medpark, SCR „T. Moșneaga” | **Revoked token**: Medpark revokes all of this patient's grants right after the first successful FHIR read (`fixtures/planted.json`), so the next read is 401 and the refresh is `invalid_grant` — the connection goes `expired`. Moșneaga keeps working. |
| P07 | `2843238559883` | Varvara Lungu, 2018 | Institutul Mamei și Copilului, Excellence | Child: immunizations, vaccination certificate 063-3/e, school and camp certificates (086/e), sport certificate. |
| P08 | `2722292856409` | Saveta Moraru, 1994 | Repromed, Institutul Mamei și Copilului | Pregnancy: pregnancy certificate, perinatal card, maternity leave. |
| P09 | `0398272871885` | Nechifor Guțu, 1981 | Terramed, SCM „Sfânta Treime”, SCM Bălți | Employment exam (086/e), sick leave, referral, MRI. |
| P10 | `0535053716972` | Corvin Guțu, 1955 | SCM Bălți, SCR „T. Moșneaga”, Institutul de Cardiologie | Diabetes and hypertension series, driver's certificate 083/e, X-ray images. |
| — | `0549206992192` | — | nowhere | **No-match IDNP**: every institution answers `access_denied`. |

Each patient has 2–5 ambulatory visits at every institution that holds records for them, over 12 months
(15 Oct 2025 – 15 Oct 2026), lab reports with 3–8 observations and about 15% of
values out of range; only P01 and P02 have inpatient stays.
