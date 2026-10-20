# MedVault API — Frontend Contract

Covers the endpoints implemented so far: the six medical-data category views,
patient info, the original-file endpoint, **document upload**, the
**caregiver access & permissions** API and **institution connections**. Reflects the
backend code (`backend/app/documents/*`, `backend/app/caregivers/*`,
`backend/app/institutions/*`, `backend/app/main.py`).

- **Base URL (local):** `http://127.0.0.1:8000`
- **Content-Type:** `application/json`
- **Auth:** session cookie `sid` — send `credentials: "include"`. Enforced once the
  auth/RLS middleware lands; see [Auth states](#auth-states).
- **Live schema / playground:** `GET /docs` (Swagger UI), `GET /openapi.json`.

---

## Endpoints at a glance

| Method | Path | Purpose | Success |
|---|---|---|---|
| `GET` | `/diagnostics` | List diagnoses | `200` `CategoryListResponse` |
| `GET` | `/prescriptions` | List prescriptions | `200` `CategoryListResponse` |
| `GET` | `/analyses` | List analyses & lab reports | `200` `CategoryListResponse` |
| `GET` | `/certificates` | List certificates | `200` `CategoryListResponse` |
| `GET` | `/other-med-info` | List other medical info | `200` `CategoryListResponse` |
| `GET` | `/patient-info` | Profile: name/DOB + current weight/height | `200` `PatientInfoResponse` |
| `PUT` | `/patient-info` | Update the current weight/height | `200` `MeasurementResponse` |
| `GET` | `/documents/{document_id}/original` | Short-lived file URL for a document | `200` `OriginalDocumentResponse` |
| `GET` | `/documents/institutional-original` | Stream an institutional record's original, live | `200` file bytes |
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
| `GET` | `/api/v1/institutions` | Active institution catalogue | `200` `InstitutionResponse[]` |
| `GET` | `/api/v1/institution-connections` | My connections, newest first | `200` `ConnectionResponse[]` |
| `POST` | `/api/v1/institutions/connect` | Connect every public institution (one consent) | `200` `ConnectPublicResponse` |
| `POST` | `/api/v1/institutions/{institution_id}/connect` | Connect one institution (add / reconnect) | `200` `ConnectResponse` |
| `DELETE` | `/api/v1/institution-connections/{connection_id}` | Disconnect (revoke) | `204` |
| `POST` | `/patients/{patient_id}/exports` | Request a PDF/JSON export | `202` `ExportResponse` |
| `GET` | `/patients/{patient_id}/exports` | Recent exports, newest first | `200` `ExportResponse[]` |
| `GET` | `/exports/{export_id}/file` | Download a ready export (30-minute window) | `200` file bytes |
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

Filters combine with **AND**. No matches → `200` with `items: []`. A malformed `date` → `422`.

```http
GET /prescriptions HTTP/1.1
GET /prescriptions?patient_id=11111111-1111-1111-1111-111111111111 HTTP/1.1
GET /diagnostics?specialty=Cardiology&date=2026-03-02 HTTP/1.1
GET /analyses?source=Self-uploaded HTTP/1.1
```

### Response `200 OK` — `CategoryListResponse`

An envelope: `items` ordered newest dated first (undated last), plus `sources`, one entry
per connected institution the server consulted. An empty vault returns `items: []`
(not an error). Institutional rows are fetched **live** on every request and never stored.

```json
{
  "items": [
    {
      "id": "7c1f0b9e-3b0a-5d0c-9f43-2a6f1c2d9e11",
      "type": "prescription",
      "title": "Amoxicillin 500mg",
      "document_date": "2026-03-12",
      "specialty": "General Medicine",
      "practitioner_name": "Dr. Andrei Rusu",
      "source": "Spitalul Clinic Republican „Timofei Moșneaga”",
      "original_path": "institution:imsp-scr-t-mosneaga/MedicationRequest/med-001"
    },
    {
      "id": "aaaa1111-...",
      "type": "medication_record",
      "document_date": "2026-02-20",
      "specialty": "Cardiology",
      "practitioner_name": "Dr. Popescu",
      "issuer_name": "Terramed",
      "source": "Self-uploaded",
      "original_path": "/documents/aaaa1111-.../original"
    }
  ],
  "sources": [
    { "institution_id": "…", "institution": "Spitalul Clinic Republican „Timofei Moșneaga”", "status": "ok", "count": 1 },
    { "institution_id": "…", "institution": "Spitalul Internațional Medpark", "status": "timeout", "count": 0 }
  ]
}
```

#### `sources[].status`

| Status | Meaning | Suggested UI |
|---|---|---|
| `ok` | Answered (possibly with zero records). | — |
| `timeout` | No answer within the time limit (4 s connect / 10 s read, one retry). | "didn't respond in time" + Retry |
| `unavailable` | Server error, or the institution was skipped by the circuit breaker. | "unavailable right now" + Retry |
| `unauthorised` | The institution rejected the token, or refused the refresh grant (`invalid_grant`; the connection is then marked `expired`). Timeouts, 5xx and server-side config errors during a refresh are **not** treated this way. | Owner: Manage institutions, reconnect |
| `needs_reconnect` | The connection pre-dates this category's FHIR scopes. The old connection is still `active`, so the owner must remove it and add the institution again. | Owner: Manage institutions |

A failing institution only empties **its own** rows; the others still return. A malformed
record from an institution is skipped, never fatal. Each source gets at most 12 s; one that hits
the deadline is reported as `timeout` and counts toward its circuit breaker (3 failed fetches
open it for 30 s, during which it answers `unavailable` without a network call). A caregiver's
request can see an `unavailable` source when the patient's access token has expired, because
only the patient's own requests refresh tokens.

#### `CategoryListItem`

> Nullable fields are **omitted** from the JSON when absent (not sent as `null`). Treat a
> missing key as "not provided". `id`, `type`, `source`, `original_path` are always present.

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `id` | string (UUID) | no | Document id (self-uploads), or a stable id derived from the record reference (institutional rows). |
| `type` | string (enum) | no | Fixed subtype code — map to a label; never show raw. See [type values](#type-values-per-category). |
| `title` | string | **yes** | Patient's free-text name. **Currently always `null`** (encrypted at rest; decryption is a later story). Fall back to `type`. |
| `document_date` | string (`YYYY-MM-DD`) | yes | Date on the document. |
| `specialty` | string | yes | Medical specialty. |
| `practitioner_name` | string | yes | Doctor named on the document. |
| `date_added` | string (ISO datetime) | yes | When the record entered the vault (self-uploads: created_at). Omitted for institutional rows (they are never stored). |
| `issuer_name` | string | yes | Institution as typed by the patient (self-uploads); show as "declared by patient". |
| `source` | string | no | `"Self-uploaded"` for stored documents, or the institution name for institutional rows. Use it to badge each row. |
| `original_path` | string | no | Self-uploads: call it via [`GET /documents/{id}/original`](#get-documentsdocument_idoriginal). Institutional rows: the record reference `institution:<external_id>/<ResourceType>/<id>` (the original is not fetchable yet). |

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
> rows use the endpoint below instead.

---

## `GET /documents/institutional-original`

Stream an institutional record's original file (PDF or image). The file is read
**live** from the institution's FHIR `Binary` endpoint on every call and never stored by
MedVault (decision D1); disconnecting the institution makes it unreachable at once.

| Param | Type | Required | Notes |
|---|---|---|---|
| `ref` | string | Yes | The row's `original_path`: `institution:<external_id>/<ResourceType>/<id>`. |
| `category` | string | Yes | The category page the row was listed on (`diagnoses`, `certificates`, …). The record must belong to it. |
| `patient_id` | UUID | No | Whose vault, for caregivers; defaults to the caller. |

Only call it for rows with `has_original: true` (every list row now carries this flag;
always `true` for self-uploads). The response body is the file itself
(`application/pdf`, `image/png` or `image/jpeg`) with `Cache-Control: no-store` and
`Content-Security-Policy: sandbox`. Fetch it as a blob and show it from a blob URL.

| Status | Condition | Body (`detail`) |
|---|---|---|
| `403` | Caregiver without **view_original** on `category`. | `"You do not have access to this document."` |
| `404` | Bad `ref`, record not in `category`, institution not connected, record gone, or no attached file. | `"The original file is not available."` |
| `409` | The institution refused the access token: reconnect it. | `"Reconnect the institution to open this file."` |
| `502` | The institution timed out, failed, or sent something that isn't a PDF/image. | `"The institution can't be reached right now."` |

Every call writes a `view_original_document` audit entry (`resource_type`
`institution_record`, outcome and reason only, never content).

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
| `429` | More than 30 uploads per hour from this account and IP. | `"Too many attempts. Please try again later."` + `Retry-After` |

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

## Institution connections

Mounted under `/api/v1` (the dev proxy keeps that prefix). Owner only — caregivers never
connect or disconnect. The IDNP is typed on the connect screen, sent server-to-server in a
pushed authorization request and never stored or returned.

### `POST /api/v1/institutions/connect` — every public institution at once

Body `{ "idnp": "2001234567890", "consent_text_version": "2026-10", "institution_ids": ["…"] }`
(IDNP is 13 digits). `institution_ids` is optional: the public institutions the patient
ticked. Omitted means all of them; an empty list is a `422`. Ids that are not active
public institutions are ignored. Creates one connection per chosen institution that has
no live connection, all with the same consent, and pushes an authorization request to
each in parallel.

```json
{
  "authorize_url": "http://localhost:8001/imsp-scm-balti/oauth/authorize?request_uri=…",
  "connections": [
    { "connection_id": "…", "institution_id": "…", "status": "authorizing" },
    { "connection_id": "…", "institution_id": "…", "status": "error" }
  ]
}
```

Send the browser to `authorize_url`. The backend callback hands it on from one
institution to the next and finally redirects to `/institutions?connection=done`.
An institution that cannot be reached comes back `error` without blocking the rest.
`authorize_url` is `null` when nothing could be started (all connected, or none reachable).

### `POST /api/v1/institutions/{institution_id}/connect` — one institution

Same body. Used for "Add institution" (private clinics, picked from the catalogue) and
for reconnecting. Returns `{ connection_id, authorize_url }`; the callback redirects to
`/institutions?connection=<active|no_match|error>`. `409` if a live connection exists.

Both connect routes share one rate limit: 10 requests per hour per account and IP, then
`429` with `Retry-After` (see [Rate limits](#rate-limits)). A malformed IDNP is a `422`
that names the field but never echoes the value.

### Callback results (`?connection=`)

| Value | Meaning |
|---|---|
| `done` | A public batch finished; read the list for each institution's status |
| `active` | Connected |
| `no_match` | The institution has no patient with that IDNP; nothing imported |
| `error` | The token exchange failed, or the state belonged to another session |
| `expired` | The OAuth state expired (over 120 s) before the callback |

### `GET /api/v1/institution-connections` — `ConnectionResponse[]`

Every attempt is kept, newest first; use the first per institution. A connection left
`authorizing` past the state TTL is marked `error` (`authorization_abandoned`) on the next
connect so it never blocks a retry.

| Field | Type | Notes |
|---|---|---|
| `id`, `institution_id` | UUID | |
| `status` | enum | `pending_consent`, `authorizing`, `active`, `no_match`, `revoked`, `expired`, `error` |
| `origin` | enum | `auto_public` or `user_added` |
| `granted_scopes` | string[] \| null | e.g. `patient/Condition.read` |
| `failure_reason` | string \| null | `access_denied`, `token_exchange_failed`, `authorization_request_failed`, `authorization_abandoned`, … |
| `consented_at`, `connected_at`, `last_fetched_at`, `revoked_at` | datetime \| null | |
| `created_at` | datetime | |

---

## Data export

Exports are generated in the background: request one, poll the list until it is
`ready`, then download it within **30 minutes**. Institutional records are read live
when the file is made (the same sources, permissions and statuses as the pages);
only the file is stored, and it is deleted when the window ends.

### `POST /patients/{patient_id}/exports` → `202 ExportResponse`

```json
{
  "categories": ["patient_info", "diagnoses", "certificates", "analyses", "prescriptions", "other_med_info"],
  "format": "pdf",
  "language": "ro",
  "scope_ref": null
}
```

| Field | Notes |
|---|---|
| `categories` | 1–6 of the categories above (duplicates ignored). |
| `format` | `pdf` (default) or `json`. |
| `language` | `ro` (default), `en` or `ru`: headings and labels in the PDF / `type_label` in JSON. |
| `scope_ref` | One record only: `document:<uuid>` (self-upload) or the row's `original_path` for an institutional record. Needs exactly one category (not `patient_info`). |

Rate limited (5/hour). `403` when a caregiver lacks **export** on any requested category;
`422` for a bad body.

### `GET /patients/{patient_id}/exports` → `ExportResponse[]`

The 10 most recent exports. Poll every couple of seconds while one is `requested` or
`processing`.

| Field | Notes |
|---|---|
| `id`, `format`, `categories`, `single_record` | |
| `status` | `requested` → `processing` → `ready` / `failed`; `expired` after the window. |
| `created_at`, `completed_at`, `expires_at` | `expires_at` = ready time + 30 minutes. |
| `download_url` | `/exports/{id}/file` while downloadable, otherwise `null`. |

### `GET /exports/{export_id}/file`

Streams the file (`Content-Disposition: attachment`, `Cache-Control: no-store`). Only
the patient or the requester can download. `409` while not ready, `410` once expired
or deleted. Every download is audited.

The PDF names any institution that couldn't be read at export time. Neither format
contains internal ids, storage keys or record references.

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

## Authentication

Every flow ends with an SMS code (the second factor); credentials alone never open a session.
Between "code sent" and "code entered" the client holds an opaque `challenge_id`
(`ChallengeResponse { challenge_id, expires_in }`, 5-minute expiry). Wrong, expired and
unknown codes all answer `400 "Invalid or expired code."`; after 5 wrong attempts the
challenge is burned (`429`). Attempts are counted for the challenge's whole life (a resend does
not refill them) with atomic Redis commands, so parallel requests cannot beat the caps.
Responses never reveal whether a phone is registered: sign-up answers `201` + a challenge
even for a phone that already has a verified account (that decoy sends nothing and can never
be verified), and password reset always answers the same way.

| Method | Path | Body | Success |
|---|---|---|---|
| `POST` | `/auth/signup` | `first_name, last_name, phone, date_of_birth, password` | `201` `ChallengeResponse` |
| `POST` | `/auth/signup/verify` | `challenge_id, code` | `200` `CurrentUser` + session cookie |
| `POST` | `/auth/login` | `phone, password` | `200` `ChallengeResponse` |
| `POST` | `/auth/login/verify` | `challenge_id, code` | `200` `CurrentUser` + session cookie |
| `POST` | `/auth/sms/resend` | `challenge_id` | `200` `ChallengeResponse` (max 3, 30 s apart) |
| `POST` | `/auth/password-reset/request` | `phone` | `200` `ChallengeResponse` (always, even for unknown phones) |
| `POST` | `/auth/password-reset/verify` | `challenge_id, code` | `200` `{ reset_token }` (valid 10 min, single use) |
| `POST` | `/auth/password-reset/confirm` | `reset_token, new_password` | `204`; signs the user out everywhere |
| `POST` | `/auth/logout` | — | `204` |
| `GET` | `/users/me` | — | `200` `CurrentUser` |

A sign-up for a phone that is still `pending_verification` replaces that unverified row
(details and password) instead of failing, so an abandoned or squatted attempt can never lock a
number: only whoever receives the SMS code can activate it.

Errors: `401 "Invalid phone or password."` (single generic message), `422 { "detail": { "errors": { "<field>": "<message>" } } }` for
field validation, `429` with `Retry-After` for lockout (5 failures per phone per 15 min) and
rate limits (see [Rate limits](#rate-limits)). Phones are normalised to `+373XXXXXXXX` (also accepts `373…`, `0…`).
Sessions use an HTTP-only cookie (`Secure` unless `APP_ENV=development`) and expire after
**15 minutes idle** (sliding) or **8 hours** after sign-in, whichever comes first. Password
attempts are counted before they are checked (5 per phone per 15 min, 30 per IP), and a locked
phone cannot finish an open code challenge. Request fields have length caps (`422` beyond them).

**Dev SMS:** `SMS_PROVIDER=mock` stores the last messages per phone, readable at
`GET /dev/sms/{phone}` → `{ "messages": ["MedVault code: 123456. …"] }`. The route exists only
when `ENABLE_DEV_SMS_OUTBOX=true` **and** `APP_ENV` is not production (`APP_ENV` defaults to
production when unset, and the mock provider refuses to run there). The code itself is never
logged, only a masked phone number.

## Rate limits

Counted in Redis per **account + client IP** (the pair is hashed; neither reaches Redis keys
or logs). Going over answers `429 "Too many attempts. Please try again later."` with a
`Retry-After` header in seconds, and starts a cooldown during which every request gets the
same `429` without being counted. With no cooldown the wait is what is left of the window.

| Limit | Applies to | Account | Default |
|---|---|---|---|
| `login` | `POST /auth/login` | phone | 5 / 15 min, then 15 min cooldown |
| `password_reset` | `POST /auth/password-reset/request` | phone | 5 / 15 min, then 15 min cooldown |
| `sms_code` | `/auth/signup/verify`, `/auth/login/verify`, `/auth/password-reset/verify`, `/auth/sms/resend` | the challenge's phone | 5 / 15 min, then 15 min cooldown |
| `institution_connect` | both `/api/v1/institutions/…/connect` routes (shared) | user | 10 / hour |
| `document_upload` | `POST /documents/upload` | user | 30 / hour |
| `export` | the export endpoint, once it exists | user | 5 / hour |

Each number is configurable: `RATE_LIMIT_<NAME>_LIMIT`, `RATE_LIMIT_<NAME>_WINDOW_SECONDS`,
`RATE_LIMIT_<NAME>_COOLDOWN_SECONDS` (e.g. `RATE_LIMIT_LOGIN_LIMIT=10`). The older per-IP
limits on sign-up/sign-in/reset, the per-phone password lockout and the per-challenge code caps
stay in place on top. A `429` **without** `Retry-After` from a verify route means the challenge
itself was burned (start again), not a cooldown. The export limiter is ready to attach:
`dependencies=[Depends(rate_limit.limited(rate_limit.EXPORT))]`.

## Errors and logging

- Error bodies are generic and never echo input: request validation errors (`422`) list
  `loc`, `msg` and `type` per field but not the submitted value, and unexpected failures
  answer `500 "Something went wrong. Please try again."`.
- Logs are JSON lines on stderr (`LOG_LEVEL`, default `INFO`): one `request` line per
  request with method, path (never the query string), status and duration. A redacting
  filter scrubs IDNP-like numbers, phone numbers, bearer/JWT tokens and secret query
  parameters from every message, field and traceback, and replaces fields named like
  secrets or medical content (`idnp`, `access_token`, `filename`, `value`, …).
- Audit `metadata` goes through the same scrubbing before it is stored.
- The IDNP leaves the backend in exactly one place: the PAR body sent to each institution
  being connected (`tests/test_idnp_never_kept.py` checks logs, Redis, DB, audit and responses).

## Not yet available (planned)

- **Live institutional measurements** in `/patient-info` (still placeholder rows) and
  fetchable institutional originals / detail endpoints.
- **Decrypted `title`** — populated once the metadata-decryption utility ships.
- **Detail endpoints** per record, filtering (date/specialty), and export (its rate limit is
  already defined; see [Rate limits](#rate-limits)).
