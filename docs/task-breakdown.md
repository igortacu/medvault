# MedVault — Backend & Frontend Task Breakdown (v3)

Rewritten against the **current state of the repository**. Tasks keep the existing epics
and user stories, but each is now marked with an implementation status and, where the
shipped code diverged from v2, redefined to match what is actually built.

## Status legend

| Tag | Meaning |
|---|---|
| **[DONE]** | Implemented and verified in the repo. |
| **[PARTIAL]** | Foundation in place (DB objects, models, scaffolding) but application logic still pending. |
| **[TODO]** | Not started. |
| **[DEFERRED]** | Intentionally postponed (schema reserves space where relevant). |
| **[REMOVED]** | Dropped from scope. |

## Implementation snapshot (what is already done)

- **Database (Alembic `0001`–`0007`)**: all 9 tables, 11 enums (~40 document subtypes), all CHECK
  constraints and indexes; RLS enabled **and forced** on every user-data table with the full policy
  set; helper functions `current_user_id()` and `caregiver_can()`; the six pre-auth `SECURITY DEFINER`
  functions; append-only `audit_logs` (REVOKE + blocking triggers); `set_updated_at` triggers;
  `migrator`/`app_user` role split and grants; **10 real Moldovan institutions seeded (6 public, 4 private)**.
- **ORM models** (`backend/app/models/`) mirroring the schema; wired into Alembic autogenerate.
- **Endpoints**: `GET /diagnostics` and `GET /prescriptions` (RLS-filtered self-uploads + explicit
  `caregiver_can` 403 gate + audit, via a shared `list_category_documents` helper), each **merged with
  placeholder institutional rows** (a `source` field; stand-ins until the live-FHIR layer exists);
  `GET /documents/{id}/original` (MinIO presigned, `view_original` check, audit). App factory
  `app/main.py` + `/health`. `asyncpg` added for the async app session.
- **Audit/storage plumbing**: `write_audit_log` helper, `get_minio_client`.
- **Frontend**: category pages (Diagnoses, Prescriptions, Certificates, Other), Profile, Recipients,
  Institutions — scaffolded against a **mock** data service; shared UI components (Card, Modal,
  ConfirmDialog, EmptyState, Skeleton, Toast, Sidebar, OTPInput, `formatDate`).

The big gaps are everything FHIR/aggregation (Epic 2 aggregation layer), the whole mock institutional
API (Epic 6), the authentication/session HTTP layer (Epic 1 endpoints + the request-context
middleware — currently a `NotImplementedError` stub), the connection/OAuth flow, exports,
and rate limiting. **Self-upload (`POST /documents/upload`) and the full caregiver
access/permissions API (Epic 3.1) are now implemented.**

---

## Decisions this version is built on

| # | Decision |
|---|---|
| D1 | Institutional data is fetched live and never stored. MedVault's database holds only identity, connections, caregiver permissions, self-uploaded documents, exports and audit. |
| D2 | The IDNP is never stored. It is typed on the connect screen, sent server-to-server to the institution in a pushed authorization request, used for matching, then discarded. |
| D3 | **(updated)** Public institutions are offered automatically after IDNP entry; private ones are added through an "Add institution" button. **10 institutions are already seeded: 6 public, 4 private** (see the catalogue list below). |
| D4 | Caregiving is many-to-many. A patient can have several caregivers, a caregiver can look after several patients, and permissions are per link, per category, per action. |
| D5 | Six data categories: Diagnoses, Certificates, Analyses and lab reports, Prescriptions, Patient's info, Other med info — with ~40 document subtypes shared between self-uploads and institutional records. |
| D6 | The mock institutional API stores FHIR R4 resources as JSON, one dataset per institution, behind a SMART on FHIR OAuth flow with PKCE, pushed authorization requests and revocable tokens. |
| D7 | Automatic extraction stays deferred. Uploads carry manually entered metadata; the schema reserves space for extraction without implementing it. |
| D8 | One consent screen covers all public institutions at once, rather than one screen per institution. |
| D9 | Caregiver uploads are kept: with `can_upload` on a category, a caregiver may add documents and record weight or height on the patient's behalf. |
| D10 | **(confirmed)** Weight and height are stored as a **single current value** on `patient_profiles` (`weight_kg`, `height_cm`, `measurements_updated_at`) — matching the shipped schema. The team keeps the single value; **no `body_measurements` history table**. A **caregiver may update or correct** the current measurement. |
| D11 | Institution calls use a 4-second connect and 10-second read timeout, run in parallel, with partial results and a per-source retry. |
| D12 | Synthetic IDNPs are random 13 digits, format-checked only, with no checksum algorithm. |
| D13 | Mock storage: clinical seed data as read-only JSON per institution, OAuth records and the access log in a small runtime store (SQLite or Redis). |
| D14 | **(revised)** Session idle threshold is **15 minutes** with a warning modal ~60 s before expiry (gentler for the elderly primary persona, still defensible for medical data). SMS codes expire in **5 minutes**. An export download link expires **30 minutes** after the file is ready (countdown starts when ready, and an expired link regenerates in one click). |
| D15 | SMS remains a mandatory authentication factor at signup, at every sign-in and during password reset. It is the second factor, so no separate MFA enrolment step is needed. |
| D16 | Birth certificate stays a self-upload subtype only; the mock never generates one. |

### Seeded institution catalogue (already in the DB)

**Public (auto-offered):** Spitalul Clinic Republican „Timofei Moșneaga", Institutul Mamei și Copilului,
SCM „Sfânta Treime", Institutul Oncologic, Institutul de Cardiologie, SCM Bălți.
**Private (via "Add institution"):** Medpark, Terramed, Excellence, Repromed.

> Each carries mock FHIR/OAuth URLs and a **placeholder dev secret** (`oauth_secret_key_version = 0`) —
> replace with real encrypted secrets before pointing at anything but the mock.

---

## Part 1 — Backend tasks

### Epic 1: Authorization and Authentication

All flows live in `backend/app/auth/` (`router.py`, `validation.py`, `challenges.py`, `sessions.py`,
`throttle.py`, `sms.py`). SMS goes through an `SmsProvider` interface; `MockSmsProvider` logs the code and
exposes it at `GET /dev/sms/{phone}` (only when `SMS_PROVIDER=mock` and `APP_ENV != production`).

#### 1. Sign up — **[DONE]**
- Name/phone/DOB/password validation and phone normalisation (`validation.py`), field-specific 422 errors.
- Argon2id hashing; `POST /auth/signup` -> `POST /auth/signup/verify` (activates the user and opens a session).
- Audit `auth.signup` / `auth.phone_verified`. Open item: breached-password check is a small offline blocklist only.
- Migration `0011`: signing up again over a still-unverified phone replaces that row, so abandoned or squatted attempts cannot lock a number; a taken (active) phone gets the same 201 + a decoy challenge, so sign-up is not an enumeration oracle.

#### 2. Sign in — **[DONE]**
- `POST /auth/login` (password, generic error) -> SMS code -> `POST /auth/login/verify` issues the session.
- Lockout: attempts are counted before they are checked (5 per phone per 15 min, wrong codes included; 30 per IP) -> 429 with `Retry-After`. A locked phone cannot finish an open challenge.

#### 3. Reset forgotten password — **[DONE]**
- `POST /auth/password-reset/request` (decoy challenge for unknown phones), `/verify`, `/confirm`
  (single-use token, signup password rules, `auth_set_password`, all sessions wiped, audited).

#### 4. Verify phone number via SMS — **[DONE]**
- 6-digit code, 5-minute expiry, 5 attempts per code, 3 resends with a 30 s cooldown (`POST /auth/sms/resend`).

#### 5. Log out — **[DONE]**
- Deletes `session:{sid}`, removes it from `user_sessions:{uid}`, audited.

#### 6. Session timeout — **[PARTIAL]**
- 15-minute sliding idle TTL plus an 8-hour absolute cap (`created_at` in the payload; sessions without it are rejected), refreshed in `get_request_context`. The per-user session index is kept alive and repaired on every request so a password reset revokes everything. Open item: timeouts are not audited separately from logouts (an expired session cannot be told apart from an unknown one).
- Known limits: a login challenge opened before a password reset can still complete afterwards; client IP comes from the socket (behind a proxy every user shares the proxy IP until trusted-proxy handling is configured).

#### 7. Request context and RLS plumbing — **[DONE]**
- Open item: verify with pooled connections that context never leaks between requests.

### Epic 2: Medical Data Visualization

#### 0. Aggregation layer — **[DONE]** (`backend/app/aggregation/`)
- `service.fetch_institutional` resolves FHIR resource types per category (`mapping.CATEGORY_RESOURCE_TYPES`), calls every active connection in parallel and merges the rows with self-uploads. List endpoints now return `{items, sources}`.
- Timeouts 4 s connect / 10 s read, one retry with backoff, 12 s per-source deadline, per-institution circuit breaker (3 failed fetches, counted once per page load per source, deadline hits included -> open 30 s). Breaker state is in-process (single worker). The DB connection is released while institutions are called.
- Per-source status: ok / timeout / unauthorised / unavailable / needs_reconnect. A failing source never fails the page.
- Tokens: owner requests refresh before the call under a `FOR UPDATE` row lock, so parallel page loads refresh once (institutions rotate refresh tokens) and the rotated token is committed immediately. Only `invalid_grant` marks a connection `expired`; transient failures do not. Caregiver requests never refresh (cannot write the patient's connection).
- Caregiver access to the patient's connections goes through migration `0010` `caregiver_visible_connections()` (SECURITY DEFINER, gated by `caregiver_can(..., 'view')`), following the repo's narrow-function convention.
- Normalisation via the `urn:medvault:document-type` coding; specialty from the `urn:medvault:specialty` extension. Record reference `institution:<external_id>/<ResourceType>/<id>`.
- One `institution.fetch` audit entry per connection per request (status + count only, never content).
- Open items: connections created before this change have only Patient/Observation scopes and report `needs_reconnect` until reconnected; `/patient-info` institutional measurements are still placeholders; mock fixtures now cover all 10 institutions (Epic 6 generator).

#### 1. Diagnoses list **(redefined: self-uploads shipped)**
- **[TODO]** Detail endpoint resolving a local document id **or** an institutional record reference (fetched live).

#### 2. Prescriptions
- **[TODO]** Replace placeholders with live aggregation: `MedicationRequest` (active=current, completed/stopped=previous), `MedicationStatement`, `CarePlan`, `Procedure` mapped to Prescriptions.
- **[TODO]** Detail endpoint, export trigger, current/previous grouping, per-source permission scoping.

#### 3. Analyses and lab reports
- **[TODO]** Replace placeholders with live aggregation of `DiagnosticReport` + included `Observation`, `ImagingStudy`, operative reports.
- **[TODO]** Detail endpoint returning values, units, reference ranges and interpretation flags.

#### 4. Other medical information
- **[TODO]** Replace placeholders with live aggregation (hospitalizations = `Encounter` class IMP, etc.).
- **[TODO]** Hospitalization detail (admission/discharge, ward, reason, attending doctor, linked analyses/prescriptions).
- **[TODO]** Handle an in-progress hospitalization (no discharge date) as a distinct state.

#### 5. Certificates
- **[TODO]** Replace placeholders with live aggregation of certificate-type `DocumentReference` across the nine subtypes.
- **[TODO]** Detail endpoint.

#### 6. Patient's info **(redefined: single-value profile)**
- **[TODO]** Replace placeholder institutional measurements with live body-weight/height `Observation`s (depends on Story 0).
- **[DEFERRED]** `body_measurements` history table — the team keeps the single current value; revisit only if trends are actually needed.

#### 7. Consistent summary fields
- **[TODO]** Front-end: one date-format function across all category views.
- **[TODO]** Normalisation layer maps real FHIR resources into the same shape (depends on Story 0).

#### 8. Filtering
- **[TODO]** Translate the same filters into FHIR search params per institution once the live aggregation exists.

#### 10. Original document
- **[TODO]** Institutional path: stream from the institution's `Binary` endpoint through the backend without storing, and a distinct "institution unreachable" response.

#### 11. Export **(redefined: 30-minute link)**
- **[TODO]** Export job: pull institutional data live at generation, merge self-uploads, strip internal ids, write to MinIO, record in `data_exports`.
- **[TODO]** Download window of **30 minutes** from the moment the file is ready.
- **[TODO]** Cleanup job deleting expired files + a cheap one-click re-request path.
- **[TODO]** Log each export with categories and record references.

### Epic 3: Account Management

#### 1. Caregiver access and permissions
- **[PARTIAL]** The explicit `caregiver_can` gate before proxying **live** institutional data
  awaits the Epic 2 outbound proxy (RLS on self-uploads/profiles is already enforced). The
  invite/accept/reject/list, modify-permissions, revoke and vault-switching endpoints are done.

### Epic 4: Data Ingestion

#### 2. Automatic extraction
- **[DEFERRED]** `extraction_status` is reserved in the schema so adding it later needs no redesign.

#### 3. Connect to institutions
- **[DONE]** No profile precondition — IDNP typed on the connect screen.
- **[DONE]** Public flow: `POST /api/v1/institutions/connect` creates one connection per chosen active public institution (optional `institution_ids`; all of them when omitted) under the same consent version and pushes an authorization request to each in parallel; the callback chains the browser from one institution's authorize URL to the next, then returns to `/institutions?connection=done`. An unreachable institution is marked `error` without blocking the rest.
- **[DONE]** Private flow: "Add institution" picks from the catalogue by id; no free-form URLs.
- **[DONE]** Send the IDNP only server-to-server in a pushed authorization request; browser carries an opaque `request_uri`; IDNP stays in request memory only.
- **[PARTIAL]** Consent version + `consented_at` recorded before any outbound request. The consent wording lives in the frontend (`features/institutions/consent.ts`); the backend does not serve it yet.
- **[DONE]** Request minimum scopes (requested ∩ supported); store granted ones.
- **[DONE]** Handle no-match (`status='no_match'`, patient informed, nothing imported).
- **[DONE]** Store access/refresh tokens encrypted; refresh before expiry.
- **[DONE]** Audit every connection attempt (`connection.requested`, `.connected`, `.no_match`, `.failed`) and data pull.
- **[DONE]** Callback failures redirect back to the page (`?connection=error|expired`) instead of raw JSON; an authorization abandoned past the state TTL no longer blocks a retry.

#### 4. Manage and revoke connections
- **[DONE]** List connections (date connected, granted scope, last fetch, status, failure reason).
- **[DONE]** Revoke in one transaction: call the institution's revoke endpoint, set `revoked`, null both token columns, write the audit entry.
- **[DONE]** Log every revocation.

#### 5. Reject documents with hidden instructions
- **[DEFERRED]** Extraction itself. The mock already seeds a prompt-injection fixture (patient P05 at Terramed, see `institution_mock/README.md`) so the test exists once extraction is built.

### Epic 5: Data Protection and Encryption

#### 1. Secure data
- **[PARTIAL]** Access enforcement layer 2 (`caregiver_can` before proxying live data) — helper built; proxy pending.
- **[TODO]** Enforce TLS on all client-server and internal traffic.
- **[TODO]** Keep the database unreachable from outside the application layer (network/deploy).
- **[TODO]** Structured logging with redaction (IDNP, tokens, medical values, filenames never in logs/errors/audit metadata).
- **[TODO]** Test asserting the IDNP appears nowhere except the single outbound authorization request.

#### 2. Rate limiting
- **[TODO]** Rate-limiting middleware on login, password reset, connection and upload endpoints (keyed by account + IP, with logging and cool-down).
- **[TODO]** Also limit the export endpoint (each export triggers live fetches).

### Epic 6: Mock institutional API (new)

#### Service
- **[DONE]** FastAPI routing and read-only datasets for all 10 seeded institutions (generated, see below).
- **[PARTIAL]** OAuth records and access logs are process-local for the single-worker development mock; move them to Redis for multi-worker deployment.
- **[DONE]** Scoped FHIR endpoints for every resource type the aggregation mapping reads (`Observation`, `Condition`, `DocumentReference`, `MedicationRequest`, `MedicationStatement`, `CarePlan`, `Procedure`, `DiagnosticReport`, `ImagingStudy`, `Encounter`, `Immunization`) with `date`/`status`/`category`/`type`/`code`/`class`/`_id` search params, `_count` paging with `next` links and `_include=DiagnosticReport:result`. The subject only ever comes from the token.
- **[DONE]** `/Binary/{id}` serves a file only when its `securityContext` resource belongs to the token's patient and the token may read that type; foreign and missing files are the same 404. Honours `INSTITUTION_MOCK_FAULTS` so the backend's "institution unreachable" path can be tested.
- **[PARTIAL]** In-memory append-only access log covers scope/revocation verification; use Redis or durable storage when persistence is required.

#### Data generator
- **[DONE]** `institution_mock/generate_fixtures.py`: seeded Python + faker (`ro_RO` given names, Moldovan surnames) + four fixed pools in `pools.py` (LOINC, medications with DCI and commercial names, CIM-10 admission reasons, document types). Content is Romanian and modelled on real Moldovan forms (`institution_mock/RESEARCH.md`); `--check` fails when the committed fixtures are stale.
- **[DONE]** **10 synthetic patients**, each a 12-month series (2–5 visits per institution, 3–8 observations per lab report, ~15% out of range, mostly AMB with IMP for 2 patients).
- **[DONE]** One random 13-digit IDNP per patient, shared by every institution that knows them; datasets for all 10 seeded `external_id`s. The dev IDNP `2001234567890` keeps rich data everywhere.
- **[DONE]** No birth certificates (disability certificates are not generated either: CNDDCM, not hospitals, issues them).
- **[DONE]** Planted test cases (IDNPs in `institution_mock/README.md`): no-match IDNP, zero-record patient, critical values, in-progress hospitalization, certificates + hospitalization for caregiver visibility, prompt-injection fixture, revoked token (grants revoked after the first read).
- **[DONE]** Synthetic PDFs for `Binary` content, laid out like the real forms and watermarked *MOSTRĂ — date sintetice*; the IDNP is masked. No images (radiology `ImagingStudy` rows carry metadata only).

---

## Part 2 — Frontend tasks

### Epic 1: Authorization and Authentication
- **[DONE]** Sign up (field-level errors, strength meter, SMS code step), sign in (password then SMS code), reset flow
  (phone -> code -> new password -> success), 5-minute code countdown with capped resend. In `mock` mode the code is `123456`.
- **[PARTIAL]** Log out exists in the store; route-guarding is the `needsLogin` redirect in `App.tsx`.
- **[DONE]** Session timeout: `IdleTimeout` warns 60 s before the 15-minute idle limit and keeps the backend session alive.

### Epic 2: Medical Data Visualization
- **[TODO]** Shared aggregation UI: data-source banner ("showing data from 2 of 3 institutions"), distinct timeout-vs-no-records states, progressive loading.
- **[PARTIAL]** Diagnoses list page (scaffolded on mock data) — rename away from "Diagnostics"; wire to `GET /diagnostics`; detail page with original-file link; identical caregiver behaviour. [TODO] the wiring/detail.
- **[PARTIAL]** Prescriptions page (scaffolded on mock) — current/previous separation, empty state, detail with export button, caregiver scoping. [TODO] the wiring.
- **[TODO]** Analyses list + detail page (values/units/ranges, out-of-range flags, PDF/image link) — no page yet.
- **[PARTIAL]** Other medical info page (`MedicalInfo` scaffolded) — group by subtype; hospitalization detail; in-progress display; empty/caregiver scoping. [TODO] the detail/wiring.
- **[PARTIAL]** Certificates page (scaffolded) — issue date/purpose/issuer; detail + original-file link; empty state. [REMOVED] per-category opt-in toggle (moves to access-management).
- **[PARTIAL]** Patient's info: `Profile` page scaffolded — **show the current weight/height + `measurements_updated_at`** and an edit form (single value, matching the schema); permitted caregivers can update or correct it; no IDNP field. *(Single-value model; no history/trend UI.)*
- **[PARTIAL]** Consistent summary fields: `Card`, `EmptyState`, `formatDate` exist; ensure one row shape + one date format across pages.
- **[TODO]** Filtering: date + specialty controls, clear action, no-match message, cards keep showing date/diagnosis/specialty/doctor while filtered.
- **[TODO]** Data source per record: show source institution + date added; filter-by-source control; render source as non-editable text; show patient-typed issuer as "declared by patient".
- **[TODO]** Original document viewer: reusable PDF/image viewer; show alongside structured data; clear "unavailable" message (incl. institution unreachable). No viewer component exists yet.
- **[TODO]** Export: request-export buttons; "Export my data" in settings; format choice; progress/download states with a **30-minute countdown** and one-click regenerate.

### Epic 3: Account Management
- **[PARTIAL]** Caregiver management: `Recipients` page scaffolded — "Users with access" list; grant flow (person → categories → actions); edit-permissions; revoke with confirm; "Users I care for" (reject/leave); **vault switcher** with a persistent indicator; gate UI on actual permissions (hide export; never offer delete/connect). [TODO] wiring + vault switcher.

### Epic 4: Data Ingestion
- **[TODO]** Upload UI (file picker + camera); category/subtype selector from the shared list; manual metadata; progress; retry on error; uploaded doc appears on its category page via the shared viewer.
- **[DEFERRED]** Extraction review screen + failure retry/manual entry.
- **[DONE]** Connect to institutions: `Institutions` page — IDNP field (with "not stored" note); single consent screen listing every public institution not yet connected, each with a checkbox (all ticked by default, select all / clear all); "Add institution" from the catalogue; per-institution result states (connected / no records / failed / expired) with a summary toast after the redirect; reconnect for expired/error/no-match; disconnect with confirmation. Works in mock mode (IDNP `0000000000000` simulates no match). [REMOVED] prompt to add IDNP to profile.

### Epic 5: Data Protection and Encryption
- **[TODO]** Avoid insecure client-side storage; rely on the HTTP-only session cookie.
- **[TODO]** Surface only generic user-facing errors, never raw backend detail.
- **[REMOVED]** IDNP masking component (never stored or returned).
- **[TODO]** Rate-limit feedback (remaining wait) on login/reset/upload/connect and the export action; disable submit / show cooldown.

### Cross-cutting: Interface language
- **[DONE]** Romanian / English / Russian switch (i18next, `frontend/src/i18n/`, one JSON file per feature namespace and language). Romanian by default; the choice is saved in `localStorage` and sets `<html lang>`. The RO / EN / RU toggle sits in the sidebar (navigation drawer on phones) and above the auth cards. Dates (`formatDate`) and numbers follow the language (ro-RO / en-GB / ru-RU); counts use each language's plural forms. Every document subtype code from the API has a label in all three languages, and records carry codes that the UI labels. The consent points are translated per language under one `CONSENT_TEXT_VERSION` (same meaning). A test keeps the three languages' keys, placeholders and plural forms in step.
- **[TODO]** Backend messages shown as-is (sign-up field errors, the new-password rule message) are English only; localise them or map them to client keys.

---

## Documentation to update

| Document | Change |
|---|---|
| TRS FR4 | "ingested and stored" becomes fetched live, not stored. |
| TRS section 5 | Endpoint list extends to the full FHIR set and `/par`. |
| TRS (new FR) | Hospitalization / Encounter feature. |
| ADR-04 | Drop `source` and `institution_connection_id` from `documents`; note the category+subtype model. **Done in the shipped schema.** |
| Epic 2 stories | Rename to the six categories; add Analyses, Patient's info and Hospitalization stories. |
| Epic 3 Story 1 | State the many-to-many relationship and the four actions explicitly. **Reflected in the schema.** |
| Epic 4 Story 3 | Remove the IDNP-saved-on-profile precondition; add the public/private split. |
| Epic 5 Story 1 | Replace IDNP encryption/masking with "never stored, never logged". |
| Test plan | TC-FUNC-03 wording; new cases for partial source availability, live revocation, caregiver many-to-many, IDNP never persisted. |
| Trello | New cards for the Epic 2 aggregation layer, Analyses page, Patient's info page, Hospitalization page, and the Epic 6 mock API + generator. |
| Patient's info story | **Weight/height are a single current value** (shipped, confirmed); a caregiver may update or correct it. No history table. |
| NFR / Story 1.6 | Concrete numbers: **15-minute idle session**, 5-minute SMS code, **30-minute export link**, 4 s / 10 s institution timeouts. |

---
