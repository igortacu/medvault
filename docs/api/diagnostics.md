# MedVault API — Diagnostics

Contract for the diagnostics feature endpoints. Reflects the current backend
implementation (`backend/app/documents/diagnostics.py`,
`backend/app/documents/router.py`).

- **Base URL (local):** `http://127.0.0.1:8000`
- **Content-Type:** `application/json`
- **Auth:** session cookie `sid` (browser sends it automatically — use
  `credentials: "include"`). Enforced once the auth/RLS middleware is merged; see
  [Auth states](#auth-states).
- **Live schema / playground:** `GET /docs` (Swagger UI), `GET /openapi.json`.

---

## Endpoints at a glance

| Method | Path | Purpose | Success |
|---|---|---|---|
| `GET` | `/diagnostics` | List a vault's diagnostics | `200` `DiagnosticListItem[]` |
| `GET` | `/documents/{document_id}/original` | Get a short-lived file URL for one document | `200` `OriginalDocumentResponse` |
| `GET` | `/health` | Liveness probe | `200` `{ "status": "ok" }` |

---

## `GET /diagnostics`

List the diagnostics in a vault, ordered newest dated first (undated last).

### Request

| Query param | Type | Required | Description |
|---|---|---|---|
| `patient_id` | UUID | No | Whose diagnostics to list. **Omit** for your own vault. Supply a patient's id to read as their **caregiver**. |

```http
GET /diagnostics HTTP/1.1            # own vault
GET /diagnostics?patient_id=11111111-1111-1111-1111-111111111111   # as caregiver
```

### Response `200 OK`

Body: JSON array of `DiagnosticListItem`.

```json
[
  {
    "id": "22222222-2222-2222-2222-222222222222",
    "type": "diagnosis_record",
    "title": null,
    "document_date": "2026-01-15",
    "specialty": "Cardiology",
    "practitioner_name": "Dr. Popescu",
    "issuer_name": "Spitalul Clinic Republican",
    "original_path": "/documents/22222222-2222-2222-2222-222222222222/original"
  }
]
```

An empty vault returns `200` with `[]` — **not** an error.

#### `DiagnosticListItem`

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `id` | string (UUID) | no | Document id. Use for the original-file call. |
| `type` | string (enum) | no | Fixed subtype code — map to a label, never show raw. See [type values](#type-values). |
| `title` | string | **yes** | Patient's free-text name. **Currently always `null`** (encrypted at rest; decryption is a later story). Fall back to `type` for display. |
| `document_date` | string (ISO `YYYY-MM-DD`) | yes | Date printed on the document. |
| `specialty` | string | yes | Medical specialty. |
| `practitioner_name` | string | yes | Doctor named on the document. |
| `issuer_name` | string | yes | Institution named on the document (declared by patient). |
| `original_path` | string | no | Relative path to the original-file endpoint. Call it — don't construct it yourself. |

### Errors

| Status | Condition | Body |
|---|---|---|
| `403 Forbidden` | Caregiver requested a `patient_id` they lack `view` permission on for diagnoses. | `{ "detail": "You do not have access to this patient's diagnostics." }` |
| `422 Unprocessable Entity` | `patient_id` is not a valid UUID. | FastAPI validation error object. |
| `401 Unauthorized` | Missing/invalid session (after middleware is live). | `{ "detail": "..." }` |

> `403` (no permission) is distinct from `200 []` (access OK, nothing stored).
> Handle them differently in the UI.

---

## `GET /documents/{document_id}/original`

Exchange a document id for a short-lived, direct file URL (MinIO presigned).
Call this when the user opens/downloads a diagnostic's original file, using the
`original_path` returned by `/diagnostics`.

### Request

| Path param | Type | Description |
|---|---|---|
| `document_id` | UUID | The `id` from a `DiagnosticListItem`. |

```http
GET /documents/22222222-2222-2222-2222-222222222222/original HTTP/1.1
```

### Response `200 OK`

```json
{
  "url": "https://storage.example/medvault/...signed...",
  "expires_in_seconds": 300
}
```

#### `OriginalDocumentResponse`

| Field | Type | Notes |
|---|---|---|
| `url` | string | Presigned URL. Fetch/embed directly; valid for `expires_in_seconds`. |
| `expires_in_seconds` | number | Lifetime of `url` (currently 300 = 5 min). Re-call this endpoint if it expires. |

### Errors

| Status | Condition | Body (`detail`) |
|---|---|---|
| `403 Forbidden` | Not the owner and no `view_original` permission, or malformed id. | `"You do not have access to this document."` |
| `404 Not Found` | Document not in `stored` state, or object missing in storage. | `"The original file is no longer available."` / `"The original file is unavailable."` |
| `502 Bad Gateway` | Storage backend unreachable. | `"The document storage service is unavailable."` |

> `view` (appear in the list) and `view_original` (open the file) are **separate
> permissions**. A caregiver may see a row in `/diagnostics` yet get `403` here —
> render the row and handle the `403` on click.

---

## `GET /health`

```http
GET /health HTTP/1.1
```

```json
{ "status": "ok" }
```

---

## type values

`/diagnostics` returns only these `type` codes (the "diagnoses" category). Map
each to a localized label:

| `type` code | Suggested EN label |
|---|---|
| `medical_history` | Medical history |
| `surgical_history` | Past surgical history |
| `family_history` | Family medical history |
| `progress_note` | Progress / nursing note |
| `diagnosis_record` | Diagnosis record |
| `medical_examination_report` | Medical examination report |
| `consultation_report` | Consultation report |

---

## Auth states

- **Now (auth/RLS middleware not merged):** live calls to `/diagnostics` and
  `/documents/{id}/original` return `500` because the per-request session/RLS
  context isn't wired yet. `/health`, `/docs`, `/openapi.json` work. Backend logic
  is covered by unit tests; the frontend can build against this contract meanwhile.
- **After the foundation branch:** a valid session cookie is required
  (`401` otherwise). A caregiver "switches vault" via the session, so passing
  `patient_id` is how the frontend targets a specific patient.

---

## Not yet available (planned)

- **Live institutional (FHIR) diagnostics** — fetched on demand from connected
  institutions and merged into this list. Not stored, so no `original_path`.
- **Decrypted `title`** — populated once the metadata-decryption utility ships.
