# MedVault API — Frontend Contract

Covers the endpoints implemented so far: the six medical-data category views,
patient info, and the original-file endpoint. Reflects the backend code
(`backend/app/documents/*`, `backend/app/main.py`).

- **Base URL (local):** `http://127.0.0.1:8000`
- **Content-Type:** `application/json`
- **Auth:** session cookie `sid` — send `credentials: "include"`. Enforced once the
  auth/RLS middleware lands; see [Auth states](#auth-states).
- **Live schema / playground:** `GET /docs` (Swagger UI), `GET /openapi.json`.

---

## Endpoints at a glance

| Method | Path | Purpose | Success |
|---|---|---|---|
| `GET` | `/diagnostics` | List diagnoses | `200` `CategoryListItem[]` |
| `GET` | `/prescriptions` | List prescriptions | `200` `CategoryListItem[]` |
| `GET` | `/analyses` | List analyses & lab reports | `200` `CategoryListItem[]` |
| `GET` | `/certificates` | List certificates | `200` `CategoryListItem[]` |
| `GET` | `/other-med-info` | List other medical info | `200` `CategoryListItem[]` |
| `GET` | `/patient-info` | Profile: name/DOB + current weight/height | `200` `PatientInfoResponse` |
| `PUT` | `/patient-info` | Update the current weight/height | `200` `MeasurementResponse` |
| `GET` | `/documents/{document_id}/original` | Short-lived file URL for a document | `200` `OriginalDocumentResponse` |
| `GET` | `/health` | Liveness probe | `200` `{ "status": "ok" }` |

### Caregiver access — the `patient_id` query param

Every data endpoint takes an optional `patient_id` (UUID):

- **Omitted** (or your own id) → your own vault.
- **Another patient's id** → you're acting as their **caregiver**; the request is gated
  by that patient's grant to you. Missing permission → `403` (see each endpoint).

Permission actions are independent: **view** (appear in a list / read profile),
**view_original** (open a file), **upload** (add a document / update a measurement).
A caregiver may have some and not others.

---

## Category list endpoints

`GET /diagnostics`, `/prescriptions`, `/analyses`, `/certificates`, `/other-med-info`
all share the same shape and behaviour.

### Request

| Query param | Type | Required | Description |
|---|---|---|---|
| `patient_id` | UUID | No | Whose data to list (see [caregiver access](#caregiver-access--the-patient_id-query-param)). |
| `source` | string | No | Exact match on the row `source` (`Self-uploaded` or an institution name). |
| `date` | string (`YYYY-MM-DD`) | No | Only records whose `document_date` equals this. |
| `specialty` | string | No | Only records with this `specialty` (exact match). |

Filters combine with **AND**. No matches → `200 []`. A malformed `date` → `422`.

```http
GET /prescriptions HTTP/1.1
GET /prescriptions?patient_id=11111111-1111-1111-1111-111111111111 HTTP/1.1
GET /diagnostics?specialty=Cardiology&date=2026-03-02 HTTP/1.1
GET /analyses?source=Self-uploaded HTTP/1.1
```

### Response `200 OK` — `CategoryListItem[]`

Ordered newest dated first (undated last). An empty vault returns `[]` (not an error).

```json
[
  {
    "id": "22222222-2222-2222-2222-222222222222",
    "type": "prescription",
    "title": null,
    "document_date": "2026-03-12",
    "specialty": "General Medicine",
    "practitioner_name": "Dr. Andrei Rusu",
    "issuer_name": null,
    "source": "Spitalul Clinic Republican „Timofei Moșneaga”",
    "original_path": "/institutions/imsp-scr-t-mosneaga/MedicationRequest/med-0001"
  },
  {
    "id": "aaaa1111-...",
    "type": "medication_record",
    "title": null,
    "document_date": "2026-02-20",
    "specialty": "Cardiology",
    "practitioner_name": "Dr. Popescu",
    "issuer_name": "Terramed",
    "source": "Self-uploaded",
    "original_path": "/documents/aaaa1111-.../original"
  }
]
```

#### `CategoryListItem`

> Nullable fields are **omitted** from the JSON when absent (not sent as `null`). Treat a
> missing key as "not provided". `id`, `type`, `source`, `original_path` are always present.

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `id` | string (UUID) | no | Document id (self-uploads) or a synthetic id (placeholder institutional rows). |
| `type` | string (enum) | no | Fixed subtype code — map to a label; never show raw. See [type values](#type-values-per-category). |
| `title` | string | **yes** | Patient's free-text name. **Currently always `null`** (encrypted at rest; decryption is a later story). Fall back to `type`. |
| `document_date` | string (`YYYY-MM-DD`) | yes | Date on the document. |
| `specialty` | string | yes | Medical specialty. |
| `practitioner_name` | string | yes | Doctor named on the document. |
| `date_added` | string (ISO datetime) | yes | When the record entered the vault (self-uploads: created_at). Omitted for placeholder institutional rows. |
| `issuer_name` | string | yes | Institution as typed by the patient (self-uploads); show as "declared by patient". |
| `source` | string | no | `"Self-uploaded"` for stored documents, or the institution name for institutional rows. Use it to badge each row. |
| `original_path` | string | no | For self-uploads, call it via [`GET /documents/{id}/original`](#get-documentsdocument_idoriginal). For institutional rows it's a placeholder reference (not fetchable yet). |

> ⚠️ **Placeholder institutional rows.** Every category list currently includes a few
> **stand-in** institutional records (rows where `source != "Self-uploaded"`), so you can
> build the merged UI now. They'll be replaced by live FHIR data later; their
> `original_path` is not yet fetchable. Distinguish them by `source`.

### Errors

| Status | Condition | Body |
|---|---|---|
| `403 Forbidden` | Caregiver requested a `patient_id` they lack **view** on for this category. | `{ "detail": "You do not have access to this patient's <category>." }` |
| `422 Unprocessable Entity` | `patient_id` is not a valid UUID. | FastAPI validation error. |
| `401 Unauthorized` | No/invalid session (after middleware is live). | `{ "detail": "..." }` |

`403` (no permission) is distinct from `200 []` (access OK, nothing there) — handle
them differently.

---

## `GET /patient-info`

Profile for category 5 ("Patient's info"): name + DOB and the single current
weight/height. No IDNP is ever returned.

### Request

| Query param | Type | Required | Description |
|---|---|---|---|
| `patient_id` | UUID | No | Caregiver access gated by **view** on `patient_info`. |

### Response `200 OK` — `PatientInfoResponse`

```json
{
  "first_name": "Maria",
  "last_name": "Ionescu",
  "date_of_birth": "1950-04-12",
  "weight_kg": 72.0,
  "height_cm": 170.0,
  "measurements_updated_at": "2026-01-01T09:30:00Z",
  "source": "Self-entered",
  "institutional_measurements": [
    { "source": "IMSP Institutul de Cardiologie", "measured_at": "2026-02-01", "weight_kg": 78.5, "height_cm": 176.0 }
  ]
}
```

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `first_name`, `last_name` | string | yes | From the patient's account. |
| `date_of_birth` | string (`YYYY-MM-DD`) | yes | Derive age in the UI; age is never stored. |
| `weight_kg` | number | yes | Current self-entered weight; `null` if never set. |
| `height_cm` | number | yes | Current self-entered height; `null` if never set. |
| `measurements_updated_at` | string (ISO datetime) | yes | When weight/height was last set. |
| `source` | string | no | `"Self-entered"` for the current value. |
| `institutional_measurements` | array | no | **Placeholder** institutional observations (weight/height) with a `source` and `measured_at`; replaced by live FHIR later. |

**Errors:** `403` (`{ "detail": "You do not have access to this patient's info." }`) when a
caregiver lacks **view**; `422` for a bad `patient_id`.

## `PUT /patient-info`

Set/correct the single current weight and/or height. Owner, or a caregiver with
**upload** on `patient_info`.

### Request body — `MeasurementUpdate`

```json
{ "weight_kg": 80.0, "height_cm": 175.0 }
```

| Field | Type | Required | Rules |
|---|---|---|---|
| `weight_kg` | number | one of the two | `0 < weight_kg < 500` |
| `height_cm` | number | one of the two | `0 < height_cm < 300` |

At least one field must be present. Provided fields overwrite the current value and
refresh `measurements_updated_at`; a missing profile is created.

### Response `200 OK` — `MeasurementResponse`

```json
{ "weight_kg": 80.0, "height_cm": 175.0, "measurements_updated_at": "2026-09-21T12:00:00Z" }
```

### Errors

| Status | Condition | Body (`detail`) |
|---|---|---|
| `422` | Empty body, or weight/height out of range. | `"Provide weight_kg and/or height_cm."` / `"weight_kg out of range."` / `"height_cm out of range."` |
| `403` | Caregiver lacks **upload** on `patient_info`. | `"You are not allowed to update this patient's measurements."` |

---

## `GET /documents/{document_id}/original`

Exchange a self-uploaded document id (from a `CategoryListItem.original_path`) for a
short-lived, direct file URL.

### Response `200 OK` — `OriginalDocumentResponse`

```json
{ "url": "https://storage.example/...signed...", "expires_in_seconds": 300 }
```

- `url` is valid for `expires_in_seconds` (300 = 5 min). Fetch promptly; re-call to refresh.

### Errors

| Status | Condition | Body (`detail`) |
|---|---|---|
| `403` | Not owner and no **view_original** permission, or malformed id. | `"You do not have access to this document."` |
| `404` | Document not in `stored` state, or object missing in storage. | `"The original file is no longer available."` / `"The original file is unavailable."` |
| `502` | Storage backend unreachable. | `"The document storage service is unavailable."` |

> **view** (list) and **view_original** (open file) are separate. A caregiver may see a
> row yet get `403` here — render the row and handle the `403` on click. Institutional
> placeholder rows have no fetchable original yet.

---

## `GET /health`

```json
{ "status": "ok" }
```

---

## type values per category

`type` is a fixed code; map each to a localized label. A category list only returns
codes from its own group.

**diagnoses** — `medical_history`, `surgical_history`, `family_history`, `progress_note`,
`diagnosis_record`, `medical_examination_report`, `consultation_report`

**certificates** — `disability_certificate`, `illness_certificate`, `fitness_certificate`,
`vaccination_certificate`, `birth_certificate`, `hospitalization_certificate`,
`medical_examination_certificate`, `pregnancy_certificate`, `health_certificate`

**analyses** — `blood_test`, `urinalysis`, `biochemistry_report`, `hormone_test`,
`microbiology_report`, `pathology_report`, `xray_report`, `ultrasound_report`,
`ct_report`, `mri_report`, `ecg_report`, `endoscopy_report`, `radiology_images`,
`operative_report`

**prescriptions** — `prescription`, `medication_record`, `treatment_plan`, `procedure_record`

**other_med_info** — `hospitalization_record`, `discharge_summary`, `pregnancy_record`,
`allergy_record`, `immunization_record`, `referral`

---

## Auth states

- **Now (auth/RLS middleware not merged):** live calls to the data endpoints return
  `500` because the per-request session/RLS context is still a stub. `/health`, `/docs`,
  `/openapi.json` work. Build against this contract meanwhile; the shapes are stable.
- **After the foundation branch:** a valid session cookie is required (`401` otherwise).
  A caregiver "switches vault" via the session, so passing `patient_id` targets a
  specific patient.

## Not yet available (planned)

- **Live institutional (FHIR) data** — will replace the placeholder rows / measurements
  and make institutional `original_path`s fetchable.
- **Decrypted `title`** — populated once the metadata-decryption utility ships.
- **Detail endpoints** per record, filtering (date/specialty), and export.
