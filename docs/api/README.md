# MedVault API — Frontend Contract

Covers the endpoints implemented so far: the six medical-data category views,
patient info, the original-file endpoint, **document upload**, and the
**caregiver access & permissions** API. Reflects the backend code
(`backend/app/documents/*`, `backend/app/caregivers/*`, `backend/app/main.py`).

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
| `POST` | `/documents/upload` | Upload a document (multipart) | `201` `UploadResponse` |
| `POST` | `/caregivers/invite` | Invite a caregiver (name + phone) | `201` `InviteResponse` |
| `POST` | `/caregivers/links/{link_id}/accept` | Accept an invite addressed to you | `200` `LinkActionResponse` |
| `POST` | `/caregivers/links/{link_id}/reject` | Reject an invite / leave a link | `200` `LinkActionResponse` |
| `GET` | `/caregivers` | People with access to my vault | `200` `CaregiverLinkItem[]` |
| `GET` | `/caregivers/patients` | Patients I care for | `200` `CaredPatientItem[]` |
| `PUT` | `/caregivers/links/{link_id}/permissions` | Set a link's per-category permissions | `200` `PermissionItem[]` |
| `POST` | `/caregivers/links/{link_id}/revoke` | Revoke a caregiver's access | `200` `LinkActionResponse` |
| `GET` | `/caregivers/vault` | Which vault I'm acting in | `200` `VaultResponse` |
| `POST` | `/caregivers/vault/switch` | Switch which vault I act in | `200` `VaultResponse` |
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

## `POST /documents/upload`

Upload a self-uploaded document into a vault. **`multipart/form-data`** (not JSON) —
send the file plus metadata as form fields. The real file type is detected from the
file's **magic bytes**; the client `Content-Type`/filename is not trusted. All
validation runs **before** the file is stored, so a rejected upload never persists.

### Request — form fields

| Field | Type | Required | Rules |
|---|---|---|---|
| `file` | file | **yes** | Non-empty; ≤ 10 MB; must be PDF, JPEG or PNG by magic bytes. |
| `category` | string (enum) | **yes** | One of `diagnoses`, `certificates`, `analyses`, `prescriptions`, `other_med_info`. Not `patient_info`. |
| `document_type` | string (enum) | **yes** | A subtype belonging to `category` — see [type values](#type-values-per-category). |
| `patient_id` | UUID | No | Upload into another patient's vault as their **caregiver** (needs **upload** on `category`). Omitted → your own vault. |
| `document_date` | string (`YYYY-MM-DD`) | No | Not in the future. |
| `title` | string | No | Free-text name; encrypted at rest. Falls back to the filename, then the subtype code. |
| `notes` | string | No | Encrypted at rest. |
| `specialty` | string | No | |
| `issuer` | string | No | Institution as declared by the patient. |
| `doctor` | string | No | Practitioner named on the document. |

```http
POST /documents/upload HTTP/1.1
Content-Type: multipart/form-data; boundary=...

file=<binary>; category=diagnoses; document_type=diagnosis_record;
title=Follow-up visit; document_date=2026-03-02; specialty=Cardiology
```

```js
const fd = new FormData();
fd.append('file', file);                 // File/Blob from the picker or camera
fd.append('category', 'diagnoses');
fd.append('document_type', 'diagnosis_record');
fd.append('title', 'Follow-up visit');   // optional
await fetch('/documents/upload', { method: 'POST', body: fd, credentials: 'include' });
// NOTE: do NOT set Content-Type yourself — the browser adds the multipart boundary.
```

### Response `201 Created` — `UploadResponse`

```json
{
  "id": "22222222-2222-2222-2222-222222222222",
  "category": "diagnoses",
  "document_type": "diagnosis_record",
  "document_date": "2026-03-02",
  "size_bytes": 48213,
  "sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
}
```

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `id` | string (UUID) | no | The new document; use it with `GET /documents/{id}/original` and it will appear on its category list. |
| `category` / `document_type` | string (enum) | no | Echo of the accepted values. |
| `document_date` | string (`YYYY-MM-DD`) | yes | Omitted if none was sent. |
| `size_bytes` | number | no | Stored file size. |
| `sha256` | string (hex) | no | 64-char SHA-256 of the file. |

> The uploaded `title`/`notes`/filename are **encrypted at rest** and are **not** returned
> here, nor by the category lists yet (they still send `title: null`). Keep the title in
> the UI from the value you just submitted if you need to show it immediately.

### Errors

| Status | Condition | Body (`detail`) |
|---|---|---|
| `400` | Empty file. | `"The file is empty."` |
| `413` | File over 10 MB. | `"The file exceeds the 10 MB limit."` |
| `415` | Not a PDF/JPEG/PNG by magic bytes (or corrupt). | `"Unsupported or corrupt file. Only PDF, JPEG and PNG are accepted."` |
| `422` | `category`/`document_type` not a valid pair, or bad `patient_id`/`document_date`. | `"Unknown category/document_type combination."` / FastAPI validation error |
| `403` | Caregiver without **upload** on this category for `patient_id`. | `"You are not allowed to upload to this patient's vault."` |
| `502` | Storage backend unreachable (**retryable**). | `"Document storage is temporarily unavailable. Please retry."` |
| `503` | Encryption not configured, or the DB save failed after storage (**retryable**). | `"Document encryption is not configured."` / `"Could not save the document. Please retry."` |
| `401` | No/invalid session. | `"..."` |

`502`/`503` are safe to retry with the same file. Client validation (size/type) mirrors
the `400`/`413`/`415` rules so you can fail fast before uploading.

---

## Caregiver access & permissions

The relationship is **many-to-many** and **default-deny**: an invited caregiver has no
access until the patient grants per-category permissions. The four independent actions are
**view**, **view_original**, **export**, **upload**; granting any of the latter three
requires **view**. Permissions are read fresh on every request — never cached client-side.

Two `PermissionItem` sub-objects appear throughout:

```json
{ "category": "diagnoses", "can_view": true, "can_view_original": false,
  "can_export": false, "can_upload": true }
```

### `POST /caregivers/invite`

Patient invites a caregiver by name + phone. The link is created `pending`.

**Body — `InviteRequest`**

| Field | Type | Required | Rules |
|---|---|---|---|
| `first_name` | string | yes | 2–50 chars (trimmed). |
| `last_name` | string | yes | 2–50 chars (trimmed). |
| `phone` | string | yes | Normalised to `+373XXXXXXXX` (spaces/dashes allowed on input). |

**`201 Created` — `InviteResponse`**

```json
{ "id": "…", "status": "pending", "first_name": "Ana", "last_name": "Popa",
  "phone": "+37360000000", "invited_at": "2026-09-23T10:00:00Z" }
```

**Errors:** `422` invalid name/phone (`"Phone must be a Moldovan number in +373XXXXXXXX format."`);
`409` `"There is already a live invite or link for this phone number."`

### `POST /caregivers/links/{link_id}/accept` · `/reject`

The **caregiver** accepts or rejects an invite addressed to their own verified phone
(`reject` also lets an active caregiver leave a link). Both return `LinkActionResponse`:

```json
{ "id": "…", "status": "active" }   // accept → "active", reject → "rejected"
```

**Errors:** `404` `"Invite not found or not addressed to you."`

### `GET /caregivers` — people with access to me

Everyone the caller has invited (including `pending` invites), with each link's permissions.

**`200 OK` — `CaregiverLinkItem[]`** (nullable fields omitted when absent)

```json
[
  {
    "id": "…",
    "caregiver_user_id": "…",
    "first_name": "Ana",
    "last_name": "Popa",
    "phone": "+37360000000",
    "status": "active",
    "invited_at": "2026-09-01T08:00:00Z",
    "responded_at": "2026-09-02T09:00:00Z",
    "permissions": [
      { "category": "diagnoses", "can_view": true, "can_view_original": true,
        "can_export": false, "can_upload": false }
    ]
  }
]
```

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `id` | string (UUID) | no | Link id — use it for permissions/revoke. |
| `caregiver_user_id` | string (UUID) | yes | Set once accepted; omitted while `pending`. |
| `first_name`/`last_name`/`phone` | string | no | As invited. |
| `status` | enum | no | `pending` \| `active` \| `rejected` \| `revoked`. |
| `invited_at`/`responded_at` | ISO datetime | yes | |
| `permissions` | `PermissionItem[]` | no | Empty until the patient grants any. |

### `GET /caregivers/patients` — patients I care for

Active links where the caller is the caregiver.

**`200 OK` — `CaredPatientItem[]`**

```json
[ { "link_id": "…", "patient_user_id": "…", "status": "active",
    "since": "2026-09-02T09:00:00Z", "permissions": [ /* PermissionItem[] */ ] } ]
```

> Only `patient_user_id` is returned here (not the patient's name) unless you also hold
> `patient_info` **view** — fetch `GET /patient-info?patient_id=…` for the name in that case.

### `PUT /caregivers/links/{link_id}/permissions`

Patient sets a link's permissions. Send the full desired state per category; each entry is
upserted. Effective immediately.

**Body — `PermissionsUpdate`**

```json
{ "permissions": [
  { "category": "diagnoses", "can_view": true, "can_export": true },
  { "category": "analyses",  "can_view": true }
] }
```

Each entry: `category` (required, a known `DataCategory`) plus the four boolean flags
(default `false`). **`can_view` must be `true` if any other action is `true`.**

**`200 OK` — `PermissionItem[]`** (the link's full permission set after the update).

**Errors:** `404` `"Link not found."`; `422` unknown category or
`"can_view is required when any other action is granted."`

### `POST /caregivers/links/{link_id}/revoke`

Patient-side revocation (works on a `pending` or `active` link). Access ends immediately.

**`200 OK` — `LinkActionResponse`** → `{ "id": "…", "status": "revoked" }`

**Errors:** `404` `"Link not found or already ended."`

### `GET /caregivers/vault` · `POST /caregivers/vault/switch` — vault switching

A caregiver picks which patient's vault they're acting in; the selection is stored in the
session and every subsequent request re-checks the active link. `GET` returns the current
selection; `POST` changes it. Send `patient_id: null` to return to your own vault.

**`POST` body — `VaultSwitchRequest`:** `{ "patient_id": "…" | null }`

**`200 OK` — `VaultResponse`:** `{ "acting_patient_id": "…" | null }` (`null` = own vault).

**Errors:** `403` `"You do not have an active caregiver link for that patient."`

> Vault switching is a convenience. The category/upload/patient-info endpoints still accept
> an explicit `patient_id` and enforce the caregiver gate per request regardless.

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
