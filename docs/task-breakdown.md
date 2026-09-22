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
middleware — currently a `NotImplementedError` stub), uploads, the connection/OAuth flow, exports,
and rate limiting.

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

#### 1. Sign up
- **[DONE]** `users` table per the app schema (name, surname, normalised phone, DOB, Argon2id hash, status, `phone_verified_at`, `password_changed_at`; **no IDNP column**; no per-user MFA column). DB CHECKs enforce phone format, name length and DOB range.
- **[DONE]** Duplicate-phone generic conflict via the `auth_register_user` `SECURITY DEFINER` function (RLS is fail-closed, no session at signup).
- **[TODO]** Name/surname validation in the app (diacritics allowed, digits/symbols rejected, 2–50 chars, trimmed) — DB currently enforces length only.
- **[TODO]** Phone validation + normalisation to `+373XXXXXXXX` in the app layer.
- **[TODO]** DOB validation in the app (real date, age 0–120, not future).
- **[TODO]** Password rules (10–128 chars, upper/lower/digit/special; reject breached passwords).
- **[TODO]** Argon2id hashing in the app (`argon2-cffi` is a dependency but unused); plaintext never logged.
- **[TODO]** Trigger the SMS verification flow once all fields validate.
- **[PARTIAL]** Audit `auth.signup` with no user context — the append-only audit table, insert policy and `write_audit_log` helper exist; the signup call site does not.
- **[TODO]** `POST /signup` orchestrating the above with field-specific errors.

#### 2. Sign in
- **[DONE]** Credential lookup via `auth_lookup_for_signin` (one row, exact phone match).
- **[TODO]** Compare name/surname/hash in the app and return a single generic error.
- **[TODO]** Withhold session issuance until the SMS code is confirmed (password **plus** SMS every time).
- **[TODO]** Failed-attempt/lockout counters in Redis (`status='locked'` is admin-only).
- **[TODO]** On success create the Redis session (`session:{sid}`, `user_sessions:{user_id}`) and set the HTTP-only cookie holding only the sid.

#### 3. Reset forgotten password
- **[DONE]** `auth_set_password` function (stores the new hash, bumps `password_changed_at`).
- **[TODO]** Reset-request endpoint keyed on the registered phone.
- **[TODO]** SMS code with 5-minute expiry in `sms:reset:{phone}`, deleted on use.
- **[TODO]** Code-verification endpoint gating the password change.
- **[TODO]** Validate the new password against the signup rules before calling `auth_set_password`.
- **[TODO]** Invalidate all sessions (delete every sid in `user_sessions:{user_id}`); `password_changed_at` is the DB backstop.
- **[TODO]** Log every step.

#### 4. Verify phone number via SMS
- **[DONE]** `auth_activate_user` flips `pending_verification → active` and sets `phone_verified_at` (a DB constraint requires it).
- **[TODO]** Generate/send the numeric code via the SMS provider.
- **[TODO]** Enforce the 5-minute expiry, cap resends, rate-limit and log incorrect attempts.

#### 5. Log out
- **[TODO]** Delete `session:{sid}` and remove it from `user_sessions:{user_id}`.
- **[TODO]** Log the logout event.

#### 6. Session timeout **(redefined: 15-minute idle)**
- **[TODO]** Expire the Redis session after **15 minutes** of inactivity, refreshing the TTL on each request.
- **[TODO]** Reject requests carrying an expired session in authentication middleware.
- **[TODO]** Require full re-authentication (password plus SMS) for a new session.
- **[TODO]** Log timeouts distinctly from manual logouts.

#### 7. Request context and RLS plumbing (cross-cutting)
- **[PARTIAL]** Per-request middleware that opens a transaction and runs `SET LOCAL app.current_user_id` from the session — the `RequestContext`/`get_request_context` **interface exists but is a stub** (`NotImplementedError`); the real implementation (cookie → Redis → transaction) is pending.
- **[TODO]** Verify with pooled connections that context never leaks between requests.
- **[DONE]** Application role granted EXECUTE only on the six pre-auth functions and SELECT on the reference table(s).
- **[DONE]** Separate `migrator` role owns the schema; `app_user` has no DDL rights (and is `NOBYPASSRLS`).

### Epic 2: Medical Data Visualization

#### 0. Aggregation layer (before the category pages)
- **[TODO]** Fetch service that, per patient+category, resolves which FHIR resource types to request, calls every active connection in parallel, and merges with the patient's `documents`.
- **[TODO]** Per-institution timeouts (4 s connect / 10 s read), run in parallel, page never waits >~10 s.
- **[TODO]** Partial-failure handling with a per-source status (ok / timeout / unauthorised / unavailable); never a whole-page error.
- **[TODO]** One retry with backoff on a timed-out read, plus a short circuit-breaker.
- **[TODO]** Token handling: refresh before the call; on failed refresh set the connection to `expired` and report the source unavailable.
- **[TODO]** Normalisation mapping each FHIR resource to the shared list-row shape via the `urn:medvault:document-type` coding.
- **[PARTIAL]** Permission gate before proxying (`caregiver_can(patient, category, 'view')`) — the helper is **built and already used by `/diagnostics`**; there is no outbound proxy yet to gate.
- **[TODO]** Audit one `institution.fetch` entry per connection per request.
- **[TODO]** Stable institutional record-reference format `institution:<external_id>/<ResourceType>/<id>`.

#### 1. Diagnoses list **(redefined: self-uploads shipped)**
- **[DONE]** `GET /diagnostics` returns **self-uploaded** diagnoses (RLS-filtered, `stored`, newest first) with an original-file reference, **merged with placeholder institutional rows** (`source` field). Real FHIR aggregation (`Condition`, `Procedure`, `FamilyMemberHistory`, note-type `DocumentReference`) is **[TODO]** and depends on Story 0 — the placeholders will be swapped for live data.
- **[TODO]** Detail endpoint resolving a local document id **or** an institutional record reference (fetched live).
- **[DONE]** Ownership/permission checks and an explicit empty result (200 `[]`) rather than an error.

#### 2. Prescriptions
- **[DONE]** `GET /prescriptions` — self-uploads (RLS + caregiver 403 gate + audit) **merged with placeholder institutional rows** (`source` field), via the shared helper.
- **[TODO]** Replace placeholders with live aggregation: `MedicationRequest` (active=current, completed/stopped=previous), `MedicationStatement`, `CarePlan`, `Procedure` mapped to Prescriptions.
- **[TODO]** Detail endpoint, export trigger, current/previous grouping, per-source permission scoping.

#### 3. Analyses and lab reports
- **[DONE]** `GET /analyses` — self-uploads (RLS + caregiver 403 gate + audit) **merged with placeholder institutional rows**, via the shared helper.
- **[TODO]** Replace placeholders with live aggregation of `DiagnosticReport` + included `Observation`, `ImagingStudy`, operative reports.
- **[TODO]** Detail endpoint returning values, units, reference ranges and interpretation flags.

#### 4. Other medical information
- **[DONE]** `GET /other-med-info` — self-uploads (RLS + caregiver 403 gate + audit) **merged with placeholder institutional rows**, via the shared helper. Covers hospitalizations, discharge summaries, pregnancy records, allergies, immunizations, referrals.
- **[TODO]** Replace placeholders with live aggregation (hospitalizations = `Encounter` class IMP, etc.).
- **[TODO]** Hospitalization detail (admission/discharge, ward, reason, attending doctor, linked analyses/prescriptions).
- **[TODO]** Handle an in-progress hospitalization (no discharge date) as a distinct state.

#### 5. Certificates
- **[DONE]** `GET /certificates` — self-uploads (RLS + caregiver 403 gate + audit) **merged with placeholder institutional rows**, via the shared helper.
- **[TODO]** Replace placeholders with live aggregation of certificate-type `DocumentReference` across the nine subtypes.
- **[DONE]** Original-file link — served by the generic `GET /documents/{id}/original`.
- **[TODO]** Detail endpoint.

#### 6. Patient's info **(redefined: single-value profile)**
- **[DONE]** `GET /patient-info` returns name + DOB (via the `patient_basics()` SECURITY DEFINER function, migration 0008), the current `weight_kg`/`height_cm`/`measurements_updated_at` from `patient_profiles`, and **placeholder** institutional body measurements (a `source` per entry) until live FHIR exists.
- **[DONE]** `PUT /patient-info` updates the single current measurement on `patient_profiles` (weight and/or height, refreshing `measurements_updated_at`; upserts if no row), with range validation.
- **[DONE]** A caregiver with `can_upload` on `patient_info` may update **or correct** the measurement — RLS `profiles_caregiver_insert`/`profiles_caregiver_update` policies (migration 0008) + explicit `caregiver_can(..., 'upload')` gate.
- **[DONE]** No IDNP is returned (none is stored anywhere).
- **[TODO]** Replace placeholder institutional measurements with live body-weight/height `Observation`s (depends on Story 0).
- **[DEFERRED]** `body_measurements` history table — the team keeps the single current value; revisit only if trends are actually needed.

#### 7. Consistent summary fields
- **[DONE]** A standardised list-row shape (`CategoryListItem`) + shared `list_category_documents` helper is used by every category endpoint, including a `source` field. Placeholder institutional rows are registered per category in one place.
- **[DONE]** Single date format: `document_date` serialises as ISO 8601 (`YYYY-MM-DD`), `measurements_updated_at` as ISO datetime, consistently across endpoints.
- **[DONE]** Missing optional fields are **omitted** from the payload (not `null`): every category GET + `/patient-info` uses `response_model_exclude_none=True`.
- **[TODO]** Front-end: one date-format function across all category views.
- **[TODO]** Normalisation layer maps real FHIR resources into the same shape (depends on Story 0).

#### 8. Filtering
- **[DONE]** `GET /<category>?date=&specialty=` — SQL filters for self-uploads and matching filters for institutional placeholders, combined **AND**; usable with `?source=` too. `date` is validated as ISO 8601 by FastAPI; no results → empty list; permission scoping (the caregiver 403 gate) still applies.
- **[TODO]** Translate the same filters into FHIR search params per institution once the live aggregation exists.

#### 9. Data source per record
- **[DONE]** Every list row carries a derived, read-only `source` ("Self-uploaded" or the institution name) plus `date_added` (self-uploads: `created_at`); `issuer_name` remains the patient-typed "declared by patient" value.
- **[DONE]** Filter-by-source: `GET /<category>?source=<label>` (exact match) across all category endpoints; unknown source → empty list.
- **[DONE]** `source` is response-only (derived, never persisted) — no endpoint accepts it as input, so it can't be modified.

#### 10. Original document
- **[DONE]** Self-upload path: `GET /documents/{id}/original` streams from MinIO via a 5-minute presigned URL, with the caregiver's `view_original` permission checked first.
- **[DONE]** Distinguishable responses for missing/deleted file (404) vs storage unavailable (502).
- **[TODO]** Institutional path: stream from the institution's `Binary` endpoint through the backend without storing, and a distinct "institution unreachable" response.

#### 11. Export **(redefined: 30-minute link)**
- **[DONE]** `data_exports` table; caregiver export requires `can_export` on every requested category — enforced by the `exports_insert` RLS policy.
- **[TODO]** Export job: pull institutional data live at generation, merge self-uploads, strip internal ids, write to MinIO, record in `data_exports`.
- **[TODO]** Download window of **30 minutes** from the moment the file is ready.
- **[TODO]** Cleanup job deleting expired files + a cheap one-click re-request path.
- **[TODO]** Log each export with categories and record references.

### Epic 3: Account Management

#### 1. Caregiver access and permissions
- **[DONE]** `caregiver_links` + `caregiver_permissions` many-to-many model; permissions per link/category/action (view, view_original, export, upload); default-deny (no row = no access).
- **[DONE]** Accept/reject backed by `caregiver_accept_invite` / `caregiver_reject_invite` (succeed only when the invite phone matches the caller's verified phone).
- **[DONE]** No delete/connect permissions exist; no policy lets a caregiver see connections.
- **[PARTIAL]** Enforcement in two places — RLS on self-uploads/profiles is **done**; the explicit `caregiver_can` pre-check is built and used by `/diagnostics`; the live-fetch gate awaits the proxy.
- **[TODO]** Invite endpoint (name + phone, pending until accepted).
- **[TODO]** Accept/reject **endpoints** exposing the functions above.
- **[TODO]** List endpoints for both directions (caregivers-with-access-to-me, patients-I-care-for) — RLS policies already permit these reads.
- **[TODO]** Modify-permissions and revoke endpoints (effective immediately; permissions read per request, never cached).
- **[TODO]** Vault switching: `acting_patient_id` in the Redis session as a UI selection; every request re-checks link + category.

### Epic 4: Data Ingestion

#### 1. Upload a medical document
- **[PARTIAL]** DB support is complete: `documents` with `category`+`document_type` CHECK, `mime`/`size`/`sha256` constraints, unique `(storage_bucket, object_key)`, encrypted metadata columns + `metadata_key_version`; `documents_insert` RLS allows owner or a `can_upload` caregiver; `get_minio_client` exists.
- **[TODO]** `POST /documents/upload` (multipart image/PDF).
- **[TODO]** Validate by magic bytes (not client header), ≤10 MB, reject empty/corrupt before storage.
- **[TODO]** Accept category+subtype from the shared `document_types` list.
- **[TODO]** Accept manual metadata (date, title, notes, specialty, issuer, doctor); **encrypt** title, notes and original filename at rest (needs the crypto util).
- **[TODO]** Store under a random object key in MinIO scoped to the vault; record SHA-256.
- **[TODO]** Caregiver `can_upload` upload path recording both owner and uploader.
- **[TODO]** Clear retryable errors; log every attempt.

#### 2. Automatic extraction
- **[DEFERRED]** `extraction_status` is reserved in the schema so adding it later needs no redesign.

#### 3. Connect to institutions
- **[DONE]** `institutions` catalogue + `institution_connections` table (with revoke/consent CHECK constraints); **10 institutions seeded**.
- **[DONE]** Institution mock integration MVP: FastAPI entrypoint and institution router; session/Redis/RLS request context; PAR + authorization-code/PKCE callback; encrypted access/refresh tokens with rotation; live `Observation` fetch with audit and `Cache-Control: no-store`; connection listing and revocation; frontend API contract and development proxy.
- **[TODO]** No profile precondition — IDNP typed on the connect screen.
- **[TODO]** Public flow: one consent screen for all public institutions; create one connection per active public institution and run OAuth against each, recording the same consent version.
- **[TODO]** Private flow: "Add institution" from the catalogue; never accept free-form URLs (SSRF).
- **[TODO]** Send the IDNP only server-to-server in a pushed authorization request; browser carries an opaque `request_uri`; IDNP stays in request memory only.
- **[TODO]** Serve consent content; record explicit consent flag + text version before any outbound request.
- **[TODO]** Request minimum scopes; store granted ones.
- **[TODO]** Handle no-match (`status='no_match'`, patient informed, nothing imported).
- **[TODO]** Store access/refresh tokens encrypted; refresh before expiry.
- **[TODO]** Audit every connection attempt and data pull.

#### 4. Manage and revoke connections
- **[DONE]** Revoke integrity is enforced by DB constraints (`conn_revoked_wipes_tokens`, `conn_revoked_consistency`).
- **[TODO]** List connections (date connected, granted scope, last fetch, status).
- **[TODO]** Revoke in one transaction: call the institution's revoke endpoint, set `revoked`, null both token columns, write the audit entry.
- **[TODO]** Log every revocation.

#### 5. Reject documents with hidden instructions
- **[DEFERRED]** The mock will seed a prompt-injection fixture so the test exists once extraction is built.

### Epic 5: Data Protection and Encryption

#### 1. Secure data
- **[DONE]** Access enforcement layer 1: RLS on every user-data table, fail-closed and **forced** even for the table owner.
- **[DONE]** IDOR protection via opaque UUID PKs + ownership checks in RLS.
- **[DONE]** Append-only audit log: UPDATE/DELETE/TRUNCATE revoked from the app role + blocking triggers.
- **[DONE]** IDNP masking is moot — nothing is stored to mask.
- **[PARTIAL]** Field-level encryption columns + `*_key_version` exist for titles/notes/filenames, institution client secrets, and tokens; the **encryption/decryption implementation** is [TODO].
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
- **[DONE]** Runnable two-institution mock MVP with validated JSON fixtures, PKCE/PAR OAuth endpoints, rotating refresh tokens, revocation, scoped `Patient`/`Observation` reads, access logging, and backend integration tests.
- **[PARTIAL]** FastAPI routing and read-only datasets exist for two institutions; expand fixtures to all 10 seeded institutions.
- **[PARTIAL]** OAuth records and access logs are process-local for the single-worker development mock; move them to Redis for multi-worker deployment.
- **[DONE]** Loader validates fixture identity, IDNP uniqueness, source ownership and patient references at startup; invalid fixtures stop startup.
- **[DONE]** OAuth endpoints `/par`, `/authorize`, `/token`, `/revoke` use PKCE, single-use codes, revocable access tokens and rotating refresh tokens.
- **[PARTIAL]** Scoped FHIR endpoints exist for `Patient` and `Observation`; add the remaining resource types and search parameters as their pages consume them.
- **[TODO]** `/Binary/{id}` serving files only when the referencing resource belongs to the token's patient.
- **[PARTIAL]** In-memory append-only access log covers scope/revocation verification; use Redis or durable storage when persistence is required.

#### Data generator
- **[TODO]** Python + faker (Moldovan names) + four fixed pools (LOINC, medications, admission reasons, document types).
- **[TODO]** **10 synthetic patients**, each a time series (2–5 visits/12 months, 3–8 observations/report, ~15% out-of-range, mostly AMB with IMP for 1–2 patients).
- **[TODO]** Seed the same IDNP across institutions that should know a patient (random 13-digit, no checksum). **Align generated datasets with the 10 already-seeded institution `external_id`s.**
- **[TODO]** Do not generate birth certificates (self-upload subtype only).
- **[TODO]** Planted test cases: no-match IDNP, zero-record patient, critical values, in-progress hospitalization, certificates+hospitalization for caregiver visibility, prompt-injection fixture, revoked token.
- **[TODO]** Synthetic PDFs/images for `Binary` content.

---

## Part 2 — Frontend tasks

### Epic 1: Authorization and Authentication
- **[TODO]** Sign up form (name, surname, phone, DOB, password) mirroring backend rules with field-specific feedback; diacritics; phone mask with normalised preview; live strength meter; route to SMS screen. No separate MFA screen.
- **[TODO]** Sign in form (name, surname, phone, password); single generic error; redirect to SMS entry; rate-limited state.
- **[TODO]** Reset flow: forgot-password link, phone entry, **SMS code screen with a 5-minute countdown**, new-password screen, success (other sessions signed out), expired/used-code restart.
- **[PARTIAL]** Verify phone via SMS: an `OTPInput` component exists; the code-entry screen, countdown, resend cap and error states are [TODO].
- **[TODO]** Log out from any authenticated screen; clear local session; route-guard protected pages; clear `acting_patient_id` from client state.
- **[TODO]** Session timeout **(15-minute idle)**: client idle timer mirroring the backend; **warning modal ~60 s before expiry** with a stay-signed-in action (the `Modal` component exists); on timeout redirect to re-auth and clear in-memory data.

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
- **[PARTIAL]** Connect to institutions: `Institutions` page scaffolded — IDNP field (with "not stored" note); single consent screen listing every public institution; "Add institution" from the catalogue; per-institution result states (connected / no match / failed); reconnect for expired/error. [REMOVED] prompt to add IDNP to profile. [TODO] the flow/wiring.

### Epic 5: Data Protection and Encryption
- **[TODO]** Avoid insecure client-side storage; rely on the HTTP-only session cookie.
- **[TODO]** Surface only generic user-facing errors, never raw backend detail.
- **[REMOVED]** IDNP masking component (never stored or returned).
- **[TODO]** Rate-limit feedback (remaining wait) on login/reset/upload/connect and the export action; disable submit / show cooldown.

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
