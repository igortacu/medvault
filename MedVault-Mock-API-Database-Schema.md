# MedVault — Mock Institutional API: Data Schema (JSON)

*Extends `MedVault-FHIR-Mock-Structure.md`. Same format: each record is shown as the JSON document the mock stores and returns, followed by what every field is for. Clinical records are FHIR R4 resources (trimmed to what we use); no invented fields: every field exists in the spec. Synthetic data only.*

This data backs the simulated SMART on FHIR API (ADR-03) that plays every **public** and **private** institution. MedVault never writes here. It reads resources live through OAuth tokens and **does not store them** (see `MedVault-App-Database-Schema.md` §0).

---

## 0. Format and storage

- **Collections of JSON documents.** Each section below is one collection (e.g. `Observation`), stored as an array of documents. Clinical documents are stored exactly in the FHIR shape they're returned in, so the API does no translation.
- **Where they live.** One file per institution per collection is enough for the mock: `data/{institution_id}/{Collection}.json`, plus `data/_shared/` for catalogues and `data/_oauth/` for OAuth records (or the same documents in a document store / JSONB column, if the team prefers).
- **Splitting by institution in folders** means a request scoped to Clinic A physically only reads Clinic A's files, so data can't leak between institutions.
- **Integrity rules replace SQL constraints.** The rules listed under each collection are checked by the generator when it writes and by the loader when the API starts. The API refuses to start on invalid data, so a broken reference can't reach a test.
- **OAuth records** (codes, tokens, pushed requests) change at runtime; keep them in a separate writable store (e.g. `data/_oauth/*.json` or Redis) so seed data stays read-only.

### Conventions used in every clinical resource

| Field | Why it's needed |
|---|---|
| `resourceType` | FHIR requires it; tells the API and MedVault which parser to use. |
| `id` | Resource id in the FHIR mock doc style (`obs-0001`); used in references like `Observation/obs-0001`. |
| `meta.source` | Which institution holds the record (`urn:medvault:institution:inst-clinic-a`). Every query filters on it together with the token's institution, and it tells MedVault what to show as the source label (Story 2.8). |
| `subject` / `patient` | The patient the record belongs to. Every query filters on it with the token's `patient` claim; the client never supplies it (R2). |
| `encounter` | Optional link to the hospitalization/visit it came from. Connects analyses, prescriptions and documents to an admission without duplicating data (FHIR mock doc §2.6). |
| `category` coding with system `urn:medvault:document-type` | The fixed document type code from the shared vocabulary / `medvault.document_type` enum. Lets MedVault put every resource on the right category page without guessing. |

**Rules applied to all clinical resources**

- `subject`/`patient` must reference a `Patient` of the **same institution** (same folder / same `meta.source`).
- `encounter`, if present, must reference an `Encounter` of the same institution and same patient.
- Every `Practitioner`/`Organization` reference must belong to the same institution.
- The `urn:medvault:document-type` code must exist in `DocumentType` and belong to the category the mapping table (§1) assigns to that resource.

---

## 1. Category → FHIR resource mapping

| App category | Document type code | FHIR resource |
|---|---|---|
| **1. Diagnoses** | `medical_history` | `Condition` (category `problem-list-item`) |
| | `surgical_history` | `Procedure` (completed, historical) |
| | `family_history` | `FamilyMemberHistory` |
| | `progress_note` | `DocumentReference` (LOINC 11506-3) |
| | `diagnosis_record` | `Condition` (category `encounter-diagnosis`) |
| | `medical_examination_report` | `DocumentReference` |
| | `consultation_report` | `DocumentReference` (LOINC 11488-4) |
| **2. Certificates** | all 9 `*_certificate` codes | `DocumentReference` |
| **3. Analyses** | `blood_test`, `urinalysis`, `biochemistry_report`, `hormone_test`, `microbiology_report` | `DiagnosticReport` + `Observation` |
| | `pathology_report`, `xray_report`, `ultrasound_report`, `ct_report`, `mri_report`, `ecg_report`, `endoscopy_report` | `DiagnosticReport` (conclusion + PDF) |
| | `radiology_images` | `ImagingStudy` |
| | `operative_report` | `Procedure` + `DocumentReference` (LOINC 11504-8) |
| **4. Prescriptions** | `prescription` | `MedicationRequest` |
| | `medication_record` | `MedicationStatement` |
| | `treatment_plan` | `CarePlan` |
| | `procedure_record` | `Procedure` |
| **5. Patient's info** | — | `Patient`; `Observation` vital-signs (29463-7 weight, 8302-2 height) |
| **6. Other med info** | `hospitalization_record` | `Encounter` (class `IMP`) |
| | `discharge_summary` | `DocumentReference` (LOINC 18842-5) |
| | `pregnancy_record` | `Observation` (pregnancy history) + `Condition` (complications) |
| | `allergy_record` | `AllergyIntolerance` |
| | `immunization_record` | `Immunization` |
| | `referral` | `ServiceRequest` |

---

## 2. Collections overview

| Collection | Kind | Stored in | Changes at runtime |
|---|---|---|---|
| `Institution` | mock config | `_shared` | no |
| `DocumentType`, `LoincCatalog`, `MedicationCatalog`, `AdmissionReason` | fixed pools (FHIR mock doc §3) | `_shared` | no |
| `Organization` (departments), `Practitioner` | FHIR | per institution | no |
| `Patient` | FHIR | per institution | no |
| `OAuthClient` | OAuth config | `_oauth` | no |
| `PushedAuthorizationRequest`, `AuthorizationCode`, `AccessToken`, `RefreshToken` | OAuth state | `_oauth` | yes |
| `Encounter`, `Condition`, `FamilyMemberHistory`, `Procedure`, `DiagnosticReport`, `Observation`, `ImagingStudy`, `MedicationRequest`, `MedicationStatement`, `CarePlan`, `AllergyIntolerance`, `Immunization`, `ServiceRequest`, `DocumentReference`, `Binary` | FHIR | per institution | no |
| `AccessLog` | mock diagnostics | `_oauth` | yes (append-only) |

---

## 3. Configuration and fixed pools

### 3.1 `Institution`

```json
{
  "kind": "Institution",
  "id": "inst-clinic-a",
  "name": "Demo Clinic A",
  "type": "public",
  "city": "Chișinău",
  "fhirBasePath": "/inst-clinic-a/fhir",
  "active": true
}
```

| Field | Why it's needed |
|---|---|
| `kind` | Marks a mock config document (not FHIR), so the loader validates it with the right rules. |
| `id` | Stable id used in URLs and in `meta.source`; equals `medvault.institutions.external_id`, so both systems name the same institution. |
| `name` | Shown on the consent screen and source labels. Always synthetic, so no real affiliation is implied (ADR-03). |
| `type` | `public` = offered automatically after IDNP entry; `private` = only via "Add institution". Lets the seed data test both flows. |
| `city` | Helps the patient tell institutions apart in the selection list. |
| `fhirBasePath` | Route prefix for this institution's API. Must be unique so two institutions never share a route. |
| `active` | Set to `false` to simulate an unavailable institution and test MedVault's "source unavailable" state. |

**Rules:** `id` and `fhirBasePath` unique; `type` ∈ `public | private`.

### 3.2 `DocumentType`

```json
{
  "kind": "DocumentType",
  "code": "discharge_summary",
  "category": "other_med_info",
  "label": { "en": "Discharge summary", "ro": "Epicriză de externare" },
  "loinc": "18842-5"
}
```

| Field | Why it's needed |
|---|---|
| `code` | The shared fixed vocabulary; values correspond to the app DB's `medvault.document_type` enum. One source-controlled definition should feed both systems so they cannot diverge. |
| `category` | Which of the six app categories the code belongs to; decides the page and caregiver permission. |
| `label` | Readable names in both UI languages, for the mock's consent/debug pages. |
| `loinc` | Real LOINC document code where one exists, emitted in `DocumentReference.type`, so data looks like genuine FHIR. Optional. |

**Rules:** `code` unique; `category` ∈ the six app categories. Seeded with the same 40 codes as the app DB.

### 3.3 `LoincCatalog` (FHIR mock doc §3a)

```json
{
  "kind": "LoincCatalog",
  "code": "718-7",
  "display": "Hemoglobin",
  "observationCategory": "laboratory",
  "unit": "g/dL",
  "ucum": "g/dL",
  "referenceRange": {
    "female": { "low": 12.0, "high": 15.5 },
    "male":   { "low": 13.5, "high": 17.5 },
    "text": "12.0-15.5 g/dL (F) / 13.5-17.5 g/dL (M)"
  },
  "reportType": "blood_test"
}
```

| Field | Why it's needed |
|---|---|
| `code` | Real LOINC code, copied into `Observation.code.coding`. The pool is the only allowed source, so no absurd codes appear. |
| `display` | Human name shown in the UI. |
| `observationCategory` | `laboratory` → Analyses page; `vital-signs` → Patient's info (weight/height). |
| `unit` / `ucum` | Correct unit per code, copied into `valueQuantity`, so a value never gets a wrong unit. |
| `referenceRange.female` / `.male` | Sex-specific ranges. The generator uses them to produce ~85% normal / ~15% out-of-range values and to set the flag. |
| `referenceRange.text` | Display text, including one-sided ranges like `<200 mg/dL` that low/high can't express. |
| `reportType` | Which panel the test belongs to, so observations are generated as coherent panels, not random values. |

Seed: the 11 codes from FHIR mock doc §3a, plus `29463-7` Body weight (kg) and `8302-2` Body height (cm) as `vital-signs`.

### 3.4 `MedicationCatalog` (FHIR mock doc §3b)

```json
{
  "kind": "MedicationCatalog",
  "id": "metformin-500",
  "display": "Metformin 500mg",
  "defaultDosage": "1 tabletă, de 2 ori pe zi, după masă"
}
```

| Field | Why it's needed |
|---|---|
| `id` | Stable key the generator picks from. |
| `display` | Copied into `medicationCodeableConcept.text`; what the prescription list shows. |
| `defaultDosage` | Fixed dosage, so the generator never invents unrealistic doses. |

Seed: the 10 medications from FHIR mock doc §3b.

### 3.5 `AdmissionReason` (FHIR mock doc §3c)

```json
{
  "kind": "AdmissionReason",
  "id": "reason-heart-failure",
  "text": "Insuficiență cardiacă decompensată",
  "specialty": "Cardiologie"
}
```

| Field | Why it's needed |
|---|---|
| `id` | Stable key the generator picks from. |
| `text` | Copied into `Encounter.reasonCode.text`. |
| `specialty` | Matched to the department's specialty so the reason and ward always agree. |

Seed: the 6 reasons from FHIR mock doc §3c.

### 3.6 `Organization` — departments

```json
{
  "resourceType": "Organization",
  "id": "dep-a-cardio",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "active": true,
  "type": [{ "text": "Cardiologie" }],
  "name": "Demo Clinic A — Secția Cardiologie",
  "partOf": { "display": "Demo Clinic A" }
}
```

| Field | Why it's needed |
|---|---|
| `id` | Referenced as `serviceProvider` / `performer` on clinical resources. |
| `meta.source` | The institution the department belongs to. |
| `active` | FHIR status of the department. |
| `type[0].text` | The specialty. Source of the specialty filter (Story 2.6) and matched to admission reasons. |
| `name` | Rendered wherever a department is displayed ("Secția Cardiologie"). |
| `partOf` | Places the department inside its institution in FHIR terms. |

### 3.7 `Practitioner`

```json
{
  "resourceType": "Practitioner",
  "id": "prac-a-001",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "active": true,
  "name": [{ "family": "Popescu", "given": ["Ion"], "prefix": ["Dr."] }],
  "qualification": [{ "code": { "text": "Cardiologie" } }]
}
```

| Field | Why it's needed |
|---|---|
| `id` | Referenced as performer/requester/author on clinical resources. |
| `meta.source` | The institution where the doctor works; a Clinic A doctor can't sign Clinic B records. |
| `active` | FHIR status. |
| `name` | Shown in list rows ("Dr. Popescu"; Stories 2.1, 2.5). |
| `qualification[0].code.text` | Doctor's specialty; used when picking a doctor matching the encounter and for the specialty filter. |

---

## 4. `Patient`

```json
{
  "resourceType": "Patient",
  "id": "pat-001",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "identifier": [
    { "system": "urn:medvault:idnp", "value": "2001234567890" }
  ],
  "name": [
    { "family": "Rusu", "given": ["Maria"] }
  ],
  "gender": "female",
  "birthDate": "1958-03-14",
  "telecom": [{ "system": "phone", "value": "+37369000001" }],
  "address": [{ "city": "Chișinău" }]
}
```

| Field | Why it's needed |
|---|---|
| `id` | The institution's own patient id. MedVault only receives it in the token's `patient` claim and in references. |
| `meta.source` | The institution holding this record. One person has one `Patient` per institution that knows them, as in real hospital systems. |
| `identifier[system=urn:medvault:idnp]` | The matching key. Looked up once when MedVault pushes an authorization request; never accepted on FHIR endpoints (R2). |
| `name` | Shown on the consent screen so the patient can confirm it's their record. |
| `gender` | Selects the correct sex-specific reference range for lab values. |
| `birthDate` | Realistic age; generator weights toward 50+ (main persona is an elderly patient). |
| `telecom`, `address` | Realism for the Patient resource; not used in matching. |

**Rules:** IDNP is exactly 13 digits; unique **within an institution** (the same IDNP appears in several institutions' folders, never twice in one).
**Open decision:** random 13 digits or real IDNP checksum (FHIR mock doc §6.1).
IDNP is plaintext here because the data is synthetic and this service stands in for an external system; the MedVault app does not store the IDNP at all.

---

## 5. OAuth / SMART on FHIR records

### 5.1 `OAuthClient`

```json
{
  "kind": "OAuthClient",
  "clientId": "medvault-app",
  "clientSecretHash": "$argon2id$v=19$m=65536,t=3,p=4$...",
  "name": "MedVault",
  "redirectUris": ["http://localhost:8000/api/v1/institutions/callback"],
  "allowedScopes": ["patient/Patient.read", "patient/Observation.read", "patient/DiagnosticReport.read",
                    "patient/MedicationRequest.read", "patient/DocumentReference.read", "patient/Encounter.read"],
  "institutions": ["inst-clinic-a", "inst-clinic-b", "inst-clinic-c"],
  "active": true
}
```

| Field | Why it's needed |
|---|---|
| `clientId` | Public identifier sent in every OAuth request. |
| `clientSecretHash` | Argon2id hash: authenticates MedVault's backend without storing a usable secret. |
| `name` | Shown on the mock consent page. |
| `redirectUris` | Exact allowed callbacks. Codes are only sent here, blocking code theft through an attacker's redirect. |
| `allowedScopes` | Upper limit of what the client may ever request (least privilege). |
| `institutions` | Where the client is registered; removing one simulates "MedVault not registered at this institution". |
| `active` | Disable the client instantly to test MedVault's handling of a rejected client. |

### 5.2 `PushedAuthorizationRequest` — how the IDNP reaches the mock

MedVault doesn't store the IDNP, so it sends it once, server-to-server, when a connection starts (RFC 9126). The browser redirect only carries the opaque `request_uri`.

```json
{
  "kind": "PushedAuthorizationRequest",
  "requestUriHash": "b64:Q2hhbmdlTWU...",
  "clientId": "medvault-app",
  "institutionId": "inst-clinic-a",
  "patientRef": "Patient/pat-001",
  "scopes": ["patient/Observation.read", "patient/MedicationRequest.read"],
  "redirectUri": "http://localhost:8000/api/v1/institutions/callback",
  "state": "c2b1f0...",
  "codeChallenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
  "codeChallengeMethod": "S256",
  "createdAt": "2026-09-16T10:00:00Z",
  "expiresAt": "2026-09-16T10:01:30Z",
  "usedAt": null
}
```

| Field | Why it's needed |
|---|---|
| `requestUriHash` | SHA-256 of the `request_uri`. The raw value isn't stored, so a data leak can't be replayed. |
| `clientId` | Client that pushed the request (authenticated with its secret on `/par`). |
| `institutionId` | Institution the request is for. |
| `patientRef` | **Result** of the IDNP lookup (`null` = no match). The IDNP itself is discarded after lookup, so it is never persisted on either side. |
| `scopes` | Requested scopes; shown on consent and carried into the code. |
| `redirectUri` | Must be one of the client's `redirectUris`. |
| `state` | MedVault's CSRF protection value, echoed back on redirect. |
| `codeChallenge` / `codeChallengeMethod` | PKCE; copied to the authorization code (R3). |
| `createdAt` / `expiresAt` | Short validity (max 90 s); the `request_uri` is only needed for the immediate redirect. |
| `usedAt` | Single use: a replayed `request_uri` is rejected. |

**Rules:** `expiresAt − createdAt ≤ 90 s`; `patientRef`, if set, must be a Patient of `institutionId`.
**No match** → redirect with `error=access_denied`. The response is identical to "patient declined", so the redirect can't be used to find out which IDNPs exist where.

### 5.3 `AuthorizationCode`

```json
{
  "kind": "AuthorizationCode",
  "codeHash": "b64:9f86d081884c7d65...",
  "clientId": "medvault-app",
  "institutionId": "inst-clinic-a",
  "patientRef": "Patient/pat-001",
  "scopes": ["patient/Observation.read", "patient/MedicationRequest.read"],
  "redirectUri": "http://localhost:8000/api/v1/institutions/callback",
  "codeChallenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
  "createdAt": "2026-09-16T10:00:20Z",
  "expiresAt": "2026-09-16T10:01:20Z",
  "usedAt": null
}
```

| Field | Why it's needed |
|---|---|
| `codeHash` | SHA-256 of the code; the raw code is never stored. |
| `clientId` | `/token` rejects the code for any other client. |
| `institutionId` / `patientRef` | What the code is bound to; copied into the token so reads are scoped to exactly this record. |
| `scopes` | Scopes the patient approved; the token can't exceed them. |
| `redirectUri` | Must match the value sent to `/token` (OAuth2 rule against code injection). |
| `codeChallenge` | `/token` requires the matching PKCE verifier, so an intercepted code is useless (R3). |
| `createdAt` / `expiresAt` | 60-second lifetime (R3); an old code returns `invalid_grant` (TC-SEC-04). |
| `usedAt` | Set on first exchange in one atomic step; a second use fails (TC-SEC-03). |

**Rules:** `expiresAt − createdAt ≤ 60 s`; `/token` must check-and-set `usedAt` atomically (compare-and-swap / lock), not read-then-write.

### 5.4 `AccessToken`

The access token is a JWT. This record exists so revocation is instant: every FHIR request checks the `jti` here (TC-SEC-11).

```json
{
  "kind": "AccessToken",
  "jti": "3f1c6c1e-8a7e-4c3b-9a4d-2b8e1f0c7d21",
  "clientId": "medvault-app",
  "institutionId": "inst-clinic-a",
  "patientRef": "Patient/pat-001",
  "scopes": ["patient/Observation.read", "patient/MedicationRequest.read"],
  "issuedAt": "2026-09-16T10:00:25Z",
  "expiresAt": "2026-09-16T10:15:25Z",
  "revokedAt": null
}
```

| Field | Why it's needed |
|---|---|
| `jti` | JWT id claim; the lookup key for the revocation check. |
| `clientId` | Client the token belongs to. |
| `institutionId` / `patientRef` | The only data the token may read; every FHIR query filters by these (R2). |
| `scopes` | Resource types it may read; any other type returns `insufficient_scope`. |
| `issuedAt` | Issue time (debugging/audit). |
| `expiresAt` | Short lifetime limits damage if a token leaks. |
| `revokedAt` | Set by `/revoke`; a revoked token is refused even before its JWT expires. |

### 5.5 `RefreshToken`

```json
{
  "kind": "RefreshToken",
  "tokenHash": "b64:a3f5c1...",
  "clientId": "medvault-app",
  "institutionId": "inst-clinic-a",
  "patientRef": "Patient/pat-001",
  "scopes": ["patient/Observation.read", "patient/MedicationRequest.read"],
  "issuedAt": "2026-09-16T10:00:25Z",
  "expiresAt": "2026-12-15T10:00:25Z",
  "rotatedTo": null,
  "revokedAt": null
}
```

| Field | Why it's needed |
|---|---|
| `tokenHash` | Hash of the refresh token; raw value never stored. |
| `clientId` | Client allowed to use it. |
| `institutionId` / `patientRef` | New access tokens stay scoped to the same record. |
| `scopes` | Refreshed tokens can't gain scopes. |
| `issuedAt` / `expiresAt` | After expiry the patient must reconnect (MedVault marks the connection `expired`). Needed at all because MedVault fetches live on every view and shouldn't force re-consent each time. |
| `rotatedTo` | Hash of the replacement after use. If an already-rotated token shows up again, it was stolen and the whole chain is revoked. |
| `revokedAt` | Set by `/revoke` when the patient disconnects; `/revoke` also revokes every access token for the same client + institution + patient. |

---

## 6. Clinical resources

### 6.1 `Encounter` — hospitalization and visits (FHIR mock doc §2.6)

```json
{
  "resourceType": "Encounter",
  "id": "enc-0001",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "status": "finished",
  "class": { "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "IMP", "display": "inpatient" },
  "type": [{
    "coding": [{ "system": "urn:medvault:document-type", "code": "hospitalization_record" }],
    "text": "Internare — Cardiologie"
  }],
  "subject": { "reference": "Patient/pat-001" },
  "participant": [{ "individual": { "reference": "Practitioner/prac-a-001", "display": "Dr. Popescu" } }],
  "period": { "start": "2026-07-01T08:00:00Z", "end": "2026-07-05T14:00:00Z" },
  "reasonCode": [{ "coding": [{ "system": "urn:medvault:admission-reason", "code": "reason-heart-failure" }],
                   "text": "Insuficiență cardiacă decompensată" }],
  "hospitalization": {
    "admitSource": { "text": "Trimis de medicul de familie" },
    "dischargeDisposition": { "text": "Externat la domiciliu" }
  },
  "serviceProvider": { "reference": "Organization/dep-a-cardio", "display": "Demo Clinic A — Secția Cardiologie" }
}
```

| Field | Why it's needed |
|---|---|
| `status` | `in-progress` drives the "internare în curs" UI; `finished` shows a completed stay. |
| `class.code` | `IMP` = hospitalization (Other med info), `AMB` = outpatient visit, `EMER` = emergency. The key field for telling admissions from normal visits. |
| `type` | Document type `hospitalization_record` for IMP (places it on the right page) + row title. |
| `participant` | Attending doctor, shown on the detail page. |
| `period.start` | Admission/visit time: sorting and date filter. |
| `period.end` | Discharge time; absent while the patient is still admitted. |
| `reasonCode` | Why the patient was admitted, from the fixed pool. |
| `hospitalization.admitSource` | How the patient arrived: part of the admission record. |
| `hospitalization.dischargeDisposition` | Where the patient went after discharge: part of the discharge record. |
| `serviceProvider` | Ward/department; gives the specialty for filtering. |

**Rules:** `finished` ⇒ `period.end` present; `in-progress` ⇒ no `period.end`; `end ≥ start`; `IMP` ⇒ `reasonCode` from `AdmissionReason` whose `specialty` equals the department's specialty. Mostly `AMB`; `IMP` only for 1–2 patients (FHIR mock doc §6.3).

### 6.2 `Condition` — diagnoses, medical history, pregnancy complications

```json
{
  "resourceType": "Condition",
  "id": "cond-0001",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "clinicalStatus": { "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active" }] },
  "verificationStatus": { "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed" }] },
  "category": [
    { "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/condition-category", "code": "encounter-diagnosis" }] },
    { "coding": [{ "system": "urn:medvault:document-type", "code": "diagnosis_record" }] }
  ],
  "severity": { "text": "moderate" },
  "code": { "coding": [{ "system": "http://hl7.org/fhir/sid/icd-10", "code": "I50.9" }], "text": "Insuficiență cardiacă" },
  "subject": { "reference": "Patient/pat-001" },
  "encounter": { "reference": "Encounter/enc-0001" },
  "onsetDateTime": "2026-06-20",
  "recordedDate": "2026-07-01",
  "recorder": { "reference": "Practitioner/prac-a-001", "display": "Dr. Popescu" },
  "note": [{ "text": "Dispnee la efort mic, edeme gambiere." }]
}
```

| Field | Why it's needed |
|---|---|
| `clinicalStatus` | Separates current (chronic) illnesses from resolved past ones in the medical history. |
| `verificationStatus` | Confirmed vs provisional diagnoses. |
| `category` (HL7) | `problem-list-item` = long-term history; `encounter-diagnosis` = diagnosis made at a visit. |
| `category` (`urn:medvault:document-type`) | `medical_history`, `diagnosis_record` or `pregnancy_record`: one resource type serves three subtypes, so it must say which. |
| `severity` | Shown on the detail page. |
| `code` | ICD-10 code (classification used in Moldovan records) and the diagnosis name shown in the list. |
| `onsetDateTime` | When the illness began; key for medical history. |
| `abatementDateTime` *(optional)* | When it resolved; absent = ongoing. |
| `recordedDate` | List date and date filter (Story 2.6). |
| `recorder` | Doctor who recorded it, shown in the row. |
| `note` | Clinical notes for the detail page. |

### 6.3 `FamilyMemberHistory`

```json
{
  "resourceType": "FamilyMemberHistory",
  "id": "fmh-0001",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "status": "completed",
  "patient": { "reference": "Patient/pat-001" },
  "date": "2026-03-10",
  "relationship": { "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/v3-RoleCode", "code": "MTH" }], "text": "Mamă" },
  "sex": { "coding": [{ "system": "http://hl7.org/fhir/administrative-gender", "code": "female" }] },
  "deceasedBoolean": true,
  "condition": [{
    "code": { "text": "Infarct miocardic" },
    "onsetAge": { "value": 62, "unit": "a", "system": "http://unitsofmeasure.org", "code": "a" }
  }],
  "extension": [
    { "url": "urn:medvault:family-condition-group", "valueCode": "myocardial_infarction" }
  ]
}
```

| Field | Why it's needed |
|---|---|
| `status` | Required by FHIR. |
| `patient` | Whose family history it is (this resource uses `patient`, not `subject`). |
| `date` | When it was recorded: list date. |
| `relationship` | Which relative; essential for hereditary risk. |
| `sex` | Relevant for sex-linked conditions. |
| `deceasedBoolean` | Context for conditions like MI or cancer. |
| `condition[].code` | The illness. |
| `condition[].onsetAge` | Age at onset in the relative; early onset is clinically significant. |
| `extension[urn:medvault:family-condition-group]` | Groups from the categories doc (chronic, myocardial infarction, cancer, psychiatric, neurological), so the UI can group family history the same way. Uses FHIR's standard extension mechanism rather than an invented field. |

**Rule:** group ∈ `chronic | myocardial_infarction | cancer | psychiatric | neurological | other`.

### 6.4 `Procedure` — surgical history, operative report, procedure record

```json
{
  "resourceType": "Procedure",
  "id": "proc-0001",
  "meta": { "source": "urn:medvault:institution:inst-clinic-b" },
  "status": "completed",
  "category": { "coding": [{ "system": "urn:medvault:document-type", "code": "operative_report" }] },
  "code": { "text": "Apendicectomie laparoscopică" },
  "subject": { "reference": "Patient/pat-004" },
  "encounter": { "reference": "Encounter/enc-0007" },
  "performedPeriod": { "start": "2026-05-12T10:00:00Z", "end": "2026-05-12T11:10:00Z" },
  "performer": [{ "actor": { "reference": "Practitioner/prac-b-003", "display": "Dr. Ciobanu" },
                  "onBehalfOf": { "reference": "Organization/dep-b-surgery" } }],
  "outcome": { "text": "Fără complicații" },
  "report": [{ "reference": "DocumentReference/doc-0012" }]
}
```

| Field | Why it's needed |
|---|---|
| `status` | Completed vs stopped/planned. |
| `category` | `surgical_history`, `operative_report` or `procedure_record`: one resource type, three subtypes/pages. |
| `code` | Procedure name shown in the list. |
| `encounter` | Hospitalization it happened in. |
| `performedPeriod` | List date/date filter and duration. |
| `performer.actor` | Surgeon / performing doctor. |
| `performer.onBehalfOf` | Department → specialty filter. |
| `outcome` | Result, shown on the detail page. |
| `report` | The full operative note: the original document for Story 2.7. |

### 6.5 `DiagnosticReport` (FHIR mock doc §2.4)

```json
{
  "resourceType": "DiagnosticReport",
  "id": "rep-0001",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "status": "final",
  "category": [
    { "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/v2-0074", "code": "LAB" }] },
    { "coding": [{ "system": "urn:medvault:document-type", "code": "blood_test" }] }
  ],
  "code": { "text": "Hemoleucograma completă" },
  "subject": { "reference": "Patient/pat-001" },
  "encounter": { "reference": "Encounter/enc-0001" },
  "effectiveDateTime": "2026-08-14T09:00:00Z",
  "issued": "2026-08-14T11:30:00Z",
  "performer": [{ "reference": "Organization/dep-a-lab", "display": "Demo Clinic A — Laborator" }],
  "resultsInterpreter": [{ "reference": "Practitioner/prac-a-002", "display": "Dr. Lungu" }],
  "result": [
    { "reference": "Observation/obs-0001" },
    { "reference": "Observation/obs-0002" }
  ],
  "imagingStudy": [],
  "conclusion": null,
  "presentedForm": [{ "contentType": "application/pdf", "url": "Binary/bin-0001", "title": "Hemoleucograma.pdf" }]
}
```

| Field | Why it's needed |
|---|---|
| `status` | Preliminary results can be shown differently from final ones. |
| `category` (v2-0074) | Service section: `LAB`, `MB` microbiology, `PAT` pathology, `RAD` radiology, `CUS` ultrasound, `EC` ECG, `GE` endoscopy. |
| `category` (`urn:medvault:document-type`) | Exact analysis subtype for the Analyses page label and filter. |
| `code.text` | Report name shown as the list row title. |
| `encounter` | Hospitalization the tests were done in. |
| `effectiveDateTime` | When the sample/exam was taken: list date and date filter. |
| `issued` | When results were released. |
| `performer` | Lab/department → specialty filter. |
| `resultsInterpreter` | Responsible doctor shown in the row. |
| `result` | The grouped observations: one report = one visit's panel of 3–8 values (FHIR mock doc §2.4). |
| `imagingStudy` | For radiology reports: links the written report to its images (`ImagingStudy`). Empty for lab panels. |
| `conclusion` | Narrative result for imaging, pathology, ECG and endoscopy, which have text findings instead of values. |
| `presentedForm` | PDF of the report: "view original" for institutional records (Story 2.7). |

**Rules:** every `result` reference points to an `Observation` of the same patient and institution; lab categories must have ≥ 1 result; imaging/pathology/ECG/endoscopy must have `conclusion` or `presentedForm`.

### 6.6 `Observation` (FHIR mock doc §2.2)

**Lab value**

```json
{
  "resourceType": "Observation",
  "id": "obs-0001",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "status": "final",
  "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory" }] }],
  "code": {
    "coding": [{ "system": "http://loinc.org", "code": "718-7", "display": "Hemoglobin" }],
    "text": "Hemoglobin"
  },
  "subject": { "reference": "Patient/pat-001" },
  "encounter": { "reference": "Encounter/enc-0001" },
  "effectiveDateTime": "2026-08-14T09:00:00Z",
  "issued": "2026-08-14T11:30:00Z",
  "valueQuantity": { "value": 13.5, "unit": "g/dL", "system": "http://unitsofmeasure.org", "code": "g/dL" },
  "interpretation": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "code": "N" }] }],
  "referenceRange": [{ "low": { "value": 12.0, "unit": "g/dL" }, "high": { "value": 15.5, "unit": "g/dL" }, "text": "12.0-15.5 g/dL" }],
  "performer": [{ "display": "Demo Clinic A — Dr. Popescu" }]
}
```

**Vital sign (Patient's info)**

```json
{
  "resourceType": "Observation",
  "id": "obs-0102",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "status": "final",
  "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs" }] }],
  "code": { "coding": [{ "system": "http://loinc.org", "code": "29463-7", "display": "Body weight" }], "text": "Greutate" },
  "subject": { "reference": "Patient/pat-001" },
  "effectiveDateTime": "2026-08-14T09:00:00Z",
  "valueQuantity": { "value": 72.4, "unit": "kg", "system": "http://unitsofmeasure.org", "code": "kg" }
}
```

**Pregnancy history**

```json
{
  "resourceType": "Observation",
  "id": "obs-0203",
  "meta": { "source": "urn:medvault:institution:inst-clinic-b" },
  "status": "final",
  "category": [
    { "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "social-history" }] },
    { "coding": [{ "system": "urn:medvault:document-type", "code": "pregnancy_record" }] }
  ],
  "code": { "text": "Sarcini anterioare" },
  "subject": { "reference": "Patient/pat-006" },
  "effectiveDateTime": "2026-02-03",
  "valueInteger": 2
}
```

| Field | Why it's needed |
|---|---|
| `status` | Corrected (`amended`) values can be marked in the UI. |
| `category` (HL7) | `laboratory` → Analyses; `vital-signs` → Patient's info; `social-history` → pregnancy history; `exam` → exam findings. |
| `category` (`urn:medvault:document-type`) | Only for non-lab subtypes like `pregnancy_record`; labs are categorised through their `DiagnosticReport`. |
| `code` | LOINC code from the pool (labs/vitals) and the name shown to the patient. |
| `encounter` | Hospitalization it was measured in. |
| `effectiveDateTime` | When measured: per-patient time series (not isolated random dates) and date filter. |
| `issued` | When released. |
| `valueQuantity` | Numeric result with UCUM unit, copied from the pool so units are always right. |
| `valueInteger` | Counts, e.g. previous pregnancies, miscarriages. |
| `valueString` *(optional)* | Text results, e.g. culture result "Escherichia coli". |
| `valueBoolean` *(optional)* | Yes/no results. |
| `interpretation` | `N`, `L`, `H`, `LL`, `HH`, `A`: drives the "attention" flag in the UI. |
| `referenceRange` | Copied at generation time, so the value is judged against the range that applied then. |
| `performer` | Who performed/validated it. |

**Rules:** exactly one `value[x]`; `laboratory` and `vital-signs` must use a `LoincCatalog` code with its unit; ~85% `N`, ~15% out of range, plus 1–2 planted `HH`/`LL`; value outside range ⇒ interpretation not `N`.

### 6.7 `ImagingStudy` — radiology images

```json
{
  "resourceType": "ImagingStudy",
  "id": "img-0001",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "status": "available",
  "modality": [{ "system": "http://dicom.nema.org/resources/ontology/DCM", "code": "DX" }],
  "subject": { "reference": "Patient/pat-002" },
  "encounter": { "reference": "Encounter/enc-0003" },
  "started": "2026-04-02T13:20:00Z",
  "numberOfInstances": 2,
  "description": "Radiografie toracică PA și profil",
  "extension": [{ "url": "urn:medvault:preview", "valueReference": { "reference": "Binary/bin-0020" } }]
}
```

| Field | Why it's needed |
|---|---|
| `status` | Required by FHIR. |
| `modality` | DICOM code (`CR`/`DX` X-ray, `US`, `CT`, `MR`): what kind of images these are. |
| `encounter` | Hospitalization it was done in. |
| `started` | List date. |
| `numberOfInstances` | Image count shown on the detail page. |
| `description` | Study name shown in the list. |
| `extension[urn:medvault:preview]` | JPEG/PNG preview; the mock doesn't serve real DICOM, which the app viewer can't display. |

### 6.8 `MedicationRequest` — prescriptions (FHIR mock doc §2.3)

```json
{
  "resourceType": "MedicationRequest",
  "id": "med-0001",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "status": "active",
  "intent": "order",
  "category": [{ "coding": [{ "system": "urn:medvault:document-type", "code": "prescription" }] }],
  "medicationCodeableConcept": { "coding": [{ "system": "urn:medvault:medication", "code": "metformin-500" }], "text": "Metformin 500mg" },
  "subject": { "reference": "Patient/pat-001" },
  "encounter": { "reference": "Encounter/enc-0001" },
  "authoredOn": "2026-08-01",
  "requester": { "reference": "Practitioner/prac-a-001", "display": "Demo Clinic A — Dr. Popescu" },
  "reasonReference": [{ "reference": "Condition/cond-0004" }],
  "dosageInstruction": [{ "text": "1 tabletă, de 2 ori pe zi, după masă" }],
  "dispenseRequest": { "validityPeriod": { "start": "2026-08-01", "end": "2026-10-30" } }
}
```

| Field | Why it's needed |
|---|---|
| `status` | Groups the list with no invented field: `active` → "current", `completed`/`stopped` → "previous" (Story 2.2). |
| `intent` | Required by FHIR; `order` = actual prescription. |
| `category` | `prescription` document type. |
| `medicationCodeableConcept` | Medicine from the fixed pool; the name shown in the list. |
| `encounter` | Hospitalization it was prescribed in. |
| `authoredOn` | Prescription date: list date and sort order. |
| `requester` | Prescribing doctor, shown in the row. |
| `reasonReference` | The diagnosis it treats, so the detail page can say why. |
| `dosageInstruction` | Dosage from the pool, shown on the detail page. |
| `dispenseRequest.validityPeriod` | How long it can be filled. |

**Rules:** medication from `MedicationCatalog`; mostly `completed`, ~20% `active` (FHIR mock doc §2.3).

### 6.9 `MedicationStatement` — medication record

```json
{
  "resourceType": "MedicationStatement",
  "id": "ms-0001",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "status": "active",
  "category": { "coding": [{ "system": "urn:medvault:document-type", "code": "medication_record" }] },
  "medicationCodeableConcept": { "coding": [{ "system": "urn:medvault:medication", "code": "metformin-500" }], "text": "Metformin 500mg" },
  "subject": { "reference": "Patient/pat-001" },
  "effectivePeriod": { "start": "2026-08-02" },
  "basedOn": [{ "reference": "MedicationRequest/med-0001" }],
  "informationSource": { "reference": "Patient/pat-001" },
  "dosage": [{ "text": "1 tabletă dimineața" }]
}
```

| Field | Why it's needed |
|---|---|
| `status` | Whether the patient is still taking it. This is what's *taken*, as opposed to what was *prescribed*. |
| `category` | `medication_record` document type. |
| `medicationCodeableConcept` | Medicine from the pool. |
| `effectivePeriod` | When the patient started/stopped taking it. |
| `basedOn` | Prescription it came from. |
| `informationSource` | Who reported it (patient or doctor). |
| `dosage` | How it's actually taken (may differ from the prescription). |

### 6.10 `CarePlan` — treatment plan

```json
{
  "resourceType": "CarePlan",
  "id": "cp-0001",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "status": "active",
  "intent": "plan",
  "category": [{ "coding": [{ "system": "urn:medvault:document-type", "code": "treatment_plan" }] }],
  "title": "Plan de tratament — diabet zaharat tip 2",
  "description": "Control glicemic, dietă, monitorizare trimestrială HbA1c.",
  "subject": { "reference": "Patient/pat-001" },
  "encounter": { "reference": "Encounter/enc-0001" },
  "period": { "start": "2026-08-01", "end": "2027-02-01" },
  "author": { "reference": "Practitioner/prac-a-001", "display": "Dr. Popescu" },
  "addresses": [{ "reference": "Condition/cond-0004" }],
  "activity": [
    { "reference": { "reference": "MedicationRequest/med-0001" } },
    { "detail": { "status": "in-progress", "description": "Dietă hipoglucidică" } }
  ]
}
```

| Field | Why it's needed |
|---|---|
| `status` | Separates the current plan from past ones. |
| `intent` | Required by FHIR. |
| `category` | `treatment_plan` document type. |
| `title` | Shown in the list. |
| `description` | Summary for the detail page. |
| `encounter` | E.g. a plan written at discharge. |
| `period` | Coverage dates: list date and "is it still in effect". |
| `author` | Doctor who wrote it. |
| `addresses` | The condition it treats. |
| `activity` | Plan steps: linked prescriptions or free-text actions. |

### 6.11 `AllergyIntolerance`

```json
{
  "resourceType": "AllergyIntolerance",
  "id": "alg-0001",
  "meta": { "source": "urn:medvault:institution:inst-clinic-b" },
  "clinicalStatus": { "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical", "code": "active" }] },
  "type": "allergy",
  "category": ["medication"],
  "criticality": "high",
  "code": { "text": "Penicilină" },
  "patient": { "reference": "Patient/pat-003" },
  "onsetDateTime": "2015-06-01",
  "recordedDate": "2026-01-15",
  "reaction": [{ "manifestation": [{ "text": "Urticarie" }] }]
}
```

| Field | Why it's needed |
|---|---|
| `clinicalStatus` | Whether the allergy still applies. |
| `type` | True allergy vs intolerance. |
| `category` | `food`, `medication`, `environment`, `biologic`; medication allergies matter most for caregivers and prescriptions. |
| `criticality` | Risk of a severe reaction; lets the UI highlight dangerous allergies. |
| `code` | The allergen. |
| `patient` | Whose allergy (this resource uses `patient`). |
| `onsetDateTime` | When it first appeared. |
| `recordedDate` | List date. |
| `reaction.manifestation` | What happens on exposure. |

The document type (`allergy_record`) is implied by the resource type, so no extra coding is needed.

### 6.12 `Immunization`

```json
{
  "resourceType": "Immunization",
  "id": "imm-0001",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "status": "completed",
  "vaccineCode": { "text": "Vaccin gripal 2025-2026" },
  "patient": { "reference": "Patient/pat-001" },
  "encounter": { "reference": "Encounter/enc-0010" },
  "occurrenceDateTime": "2025-10-20",
  "lotNumber": "FLU25-0931",
  "performer": [{ "actor": { "reference": "Practitioner/prac-a-004", "display": "As. med. Rotari" } }],
  "protocolApplied": [{ "doseNumberPositiveInt": 1, "seriesDosesPositiveInt": 1 }]
}
```

| Field | Why it's needed |
|---|---|
| `status` | Given vs `not-done` (refusal/contraindication). |
| `vaccineCode` | Vaccine name. |
| `patient` | Who was vaccinated. |
| `encounter` | Visit where it was given. |
| `occurrenceDateTime` | List date and "is immunization up to date". |
| `lotNumber` | Batch traceability, as on real vaccination certificates. |
| `performer` | Who administered it. |
| `protocolApplied` | Dose number / total doses, to show "2 of 3" progress. |

### 6.13 `ServiceRequest` — referral

```json
{
  "resourceType": "ServiceRequest",
  "id": "sr-0001",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "status": "active",
  "intent": "order",
  "category": [{ "coding": [{ "system": "urn:medvault:document-type", "code": "referral" }] }],
  "code": { "text": "Trimitere la consultația cardiologului" },
  "subject": { "reference": "Patient/pat-001" },
  "encounter": { "reference": "Encounter/enc-0011" },
  "authoredOn": "2026-06-10",
  "requester": { "reference": "Practitioner/prac-a-005", "display": "Dr. Munteanu" },
  "performerType": { "text": "Cardiologie" },
  "reasonCode": [{ "text": "Hipertensiune arterială necontrolată" }]
}
```

| Field | Why it's needed |
|---|---|
| `status` | Referral still open, used (`completed`) or cancelled. |
| `intent` | Required by FHIR. |
| `category` | `referral` document type. |
| `code` | What the referral is for. |
| `encounter` | Visit where it was issued. |
| `authoredOn` | List date. |
| `requester` | Referring doctor. |
| `performerType` | Specialty the patient is referred to; usable in the specialty filter. |
| `reasonCode` | Why the referral was made. |

### 6.14 `DocumentReference` — certificates, notes, discharge summaries (FHIR mock doc §2.5)

```json
{
  "resourceType": "DocumentReference",
  "id": "doc-0001",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "status": "current",
  "type": {
    "coding": [
      { "system": "urn:medvault:document-type", "code": "illness_certificate" }
    ],
    "text": "Certificat medical de concediu"
  },
  "category": [{ "coding": [{ "system": "urn:medvault:category", "code": "certificates" }] }],
  "subject": { "reference": "Patient/pat-001" },
  "date": "2026-08-14T12:00:00Z",
  "author": [{ "reference": "Practitioner/prac-a-001", "display": "Dr. Popescu" }],
  "custodian": { "reference": "Organization/dep-a-cardio" },
  "description": "Incapacitate temporară de muncă",
  "content": [{
    "attachment": {
      "contentType": "application/pdf",
      "url": "Binary/bin-0005",
      "title": "Certificat absență",
      "size": 48213,
      "hash": "2jmj7l5rSw0yVb/vlWAYkK/YBwk="
    }
  }],
  "context": {
    "encounter": [{ "reference": "Encounter/enc-0001" }],
    "period": { "start": "2026-08-14", "end": "2026-08-21" }
  }
}
```

| Field | Why it's needed |
|---|---|
| `status` | `superseded` documents can be hidden or marked. |
| `type` | Exact subtype (any certificate, note, discharge summary, operative report) plus LOINC code where one exists. Decides the category page. |
| `category` | The app category, repeated explicitly so MedVault can filter documents by category in one query. |
| `date` | Issue date: list date and date filter. |
| `author` | Issuing doctor (Story 2.4). |
| `custodian` | Issuing department → specialty filter. |
| `description` | Reason/purpose shown in the certificate list (Story 2.4). |
| `content.attachment.url` | The file: what "view original" opens (Story 2.7). |
| `content.attachment.contentType` | Lets the viewer render it correctly. |
| `content.attachment.title` | Filename shown/used on download. |
| `content.attachment.size` / `hash` | Size and SHA-1 (FHIR's attachment hash) so tests can verify MedVault streamed the file unmodified. |
| `context.encounter` | Hospitalization it belongs to (e.g. discharge summary). |
| `context.period` | Period the document covers, e.g. sick-leave dates. |

**Planted fixture:** the prompt-injection test document (Story 4.5) carries `"meta": { "tag": [{ "system": "urn:medvault:test-fixture", "code": "prompt_injection" }] }` so it's easy to find and never mistaken for normal seed data.

### 6.15 `Binary` — file content

```json
{
  "resourceType": "Binary",
  "id": "bin-0005",
  "meta": { "source": "urn:medvault:institution:inst-clinic-a" },
  "contentType": "application/pdf",
  "securityContext": { "reference": "DocumentReference/doc-0001" },
  "data": "JVBERi0xLjQKJcfsj6IK..."
}
```

| Field | Why it's needed |
|---|---|
| `contentType` | Sent as the response `Content-Type`. Limited to `application/pdf`, `image/jpeg`, `image/png` (what the viewer supports). |
| `securityContext` | The resource that "owns" the file. `GET /Binary/{id}` is only allowed if that resource belongs to the token's patient and institution, so files can't be fetched by guessing ids. |
| `data` | Base64 file content. Inline because synthetic files are small and it keeps the mock's storage separate from MedVault's MinIO. |

**Rules:** decoded size ≤ 5 MB; `securityContext` must exist and belong to the same institution.

---

## 7. Search response — `Bundle` (FHIR mock doc §2.7)

```json
{
  "resourceType": "Bundle",
  "type": "searchset",
  "total": 2,
  "link": [{ "relation": "self", "url": "/inst-clinic-a/fhir/Observation?category=laboratory&date=ge2026-01-01" }],
  "entry": [
    { "fullUrl": "Observation/obs-0001", "resource": { "...": "resource 1" }, "search": { "mode": "match" } },
    { "fullUrl": "DiagnosticReport/rep-0001", "resource": { "...": "included report" }, "search": { "mode": "include" } }
  ]
}
```

| Field | Why it's needed |
|---|---|
| `type` | `searchset` tells MedVault this is a search result. |
| `total` | Number of matches, for empty states and counts. |
| `link.self` | The executed query; helps debugging filters. |
| `entry.fullUrl` | Identifies each resource. |
| `entry.resource` | The resource itself. |
| `entry.search.mode` | `match` vs `include` (resources pulled in with `_include`), so MedVault doesn't list included reports as matches. |

Not stored, only built per request.

---

## 8. `AccessLog`

Lets the team verify from the mock side what MedVault actually requested (Story 4.3 "minimum data scope") and debug token issues. Append-only.

```json
{
  "kind": "AccessLog",
  "id": 1042,
  "occurredAt": "2026-09-16T10:02:11Z",
  "endpoint": "/inst-clinic-a/fhir/Observation",
  "clientId": "medvault-app",
  "institutionId": "inst-clinic-a",
  "patientRef": "Patient/pat-001",
  "tokenJti": "3f1c6c1e-8a7e-4c3b-9a4d-2b8e1f0c7d21",
  "scopes": ["patient/Observation.read"],
  "httpStatus": 200,
  "resultCount": 14,
  "errorCode": null
}
```

| Field | Why it's needed |
|---|---|
| `id` | Increasing number, for reading the log in order. |
| `occurredAt` | When the call happened. |
| `endpoint` | Exactly what MedVault requested. |
| `clientId` | Calling client. |
| `institutionId` / `patientRef` | Verifies MedVault never read outside the token's scope. |
| `tokenJti` | Ties calls to a connection; proves a revoked token was refused (TC-SEC-11). |
| `scopes` | Verifies minimum scope was requested. |
| `httpStatus` | Makes failures and denials easy to spot. |
| `resultCount` | Detects over-fetching or unexpectedly empty results. |
| `errorCode` | `invalid_grant`, `insufficient_scope`, `token_revoked`: the expected outcomes of the security tests. |

**Deliberately absent:** the IDNP / `login_hint` value. It must never be logged.

---

## 9. API endpoints

All FHIR routes live under `/{institution_id}/fhir`. Each request validates the JWT signature, checks `jti` isn't revoked, checks the scope, and filters by the token's institution and patient.

| Endpoint | Scope | Collections read/written |
|---|---|---|
| `POST /par` | client auth | `OAuthClient`, `Patient`, → `PushedAuthorizationRequest` |
| `GET /authorize` | — | `PushedAuthorizationRequest` → `AuthorizationCode` |
| `POST /token` | client auth | `AuthorizationCode` / `RefreshToken` → `AccessToken`, `RefreshToken` |
| `POST /revoke` | client auth | `AccessToken`, `RefreshToken` |
| `GET /Patient/{id}` (must equal token patient) | `patient/Patient.read` | `Patient` |
| `GET /Condition?category=&recorded-date=` | `patient/Condition.read` | `Condition` |
| `GET /FamilyMemberHistory` | `patient/FamilyMemberHistory.read` | `FamilyMemberHistory` |
| `GET /Procedure?category=&date=` | `patient/Procedure.read` | `Procedure` |
| `GET /DiagnosticReport?category=&date=&_include=DiagnosticReport:result` | `patient/DiagnosticReport.read` | `DiagnosticReport`, `Observation` |
| `GET /Observation?category=&code=&date=` | `patient/Observation.read` | `Observation` |
| `GET /ImagingStudy` | `patient/ImagingStudy.read` | `ImagingStudy` |
| `GET /MedicationRequest?status=` | `patient/MedicationRequest.read` | `MedicationRequest` |
| `GET /MedicationStatement` | `patient/MedicationStatement.read` | `MedicationStatement` |
| `GET /CarePlan` | `patient/CarePlan.read` | `CarePlan` |
| `GET /Encounter?class=&date=` | `patient/Encounter.read` | `Encounter` |
| `GET /AllergyIntolerance` | `patient/AllergyIntolerance.read` | `AllergyIntolerance` |
| `GET /Immunization` | `patient/Immunization.read` | `Immunization` |
| `GET /ServiceRequest` | `patient/ServiceRequest.read` | `ServiceRequest` |
| `GET /DocumentReference?type=&category=&date=` | `patient/DocumentReference.read` | `DocumentReference` |
| `GET /Binary/{id}` | scope of the `securityContext` resource | `Binary` |

Every call appends one `AccessLog` entry.

> **Scope note:** TRS §5 lists only `GET /authorize, POST /token, GET /Observation`. Extending to this list should be recorded as a TRS update.

---

## 10. Seed data and planted test cases

**Institutions**

| id | name | type | patient share |
|---|---|---|---|
| `inst-clinic-a` | Demo Clinic A | public | ~40% |
| `inst-clinic-b` | Demo Clinic B | public | ~40% |
| `inst-clinic-c` | Demo Clinic C | private | ~20% ("institution with little data") |

**Patients:** 8–10 synthetic people (FHIR mock doc proposal; *Test Plan §6 says 2–3 per institution, so pick one*). Moldovan names from a fixed pool, ages weighted to 50+, 2–5 visits each over the last 12 months as a time series.

| Planted case | How it's seeded | Tests |
|---|---|---|
| IDNP with no match anywhere | IDNP used by a MedVault test account, absent from every `Patient` file | `no_match` state (Story 4.3) |
| Patient with zero records | `Patient` with no clinical resources | empty states (Epic 2) |
| Clearly out-of-range values | 1–2 `Observation` with `HH`/`LL` | attention flag UI |
| Active hospitalization | `Encounter` `IMP`, `in-progress`, no `period.end` | "internare în curs" UI |
| Finished hospitalization with linked data | `IMP` encounter + observations, prescription, discharge summary referencing it | encounter linking |
| Same IDNP at all 3 institutions | one `Patient` per institution folder | multi-source view, source filter (Story 2.8) |
| Certificates + hospitalization for one patient | `DocumentReference` certificates + `IMP` encounter | caregiver hidden-by-default test (FHIR mock doc §5) |
| Prompt-injection document | `DocumentReference` tagged `urn:medvault:test-fixture#prompt_injection` | Story 4.5, once extraction exists |
| Revoked token | `AccessToken` with `revokedAt` set | TC-SEC-11 |
| Expired / reused code | created by the test script at runtime | TC-SEC-03, TC-SEC-04 |

---

## 11. Open decisions

1. IDNP checksum vs random (FHIR mock doc §6.1).
2. Number of synthetic patients (8–10 vs 2–3 per institution).
3. Which institutions are public vs private (proposal in §10).
4. Storage: plain JSON files per institution (simplest) vs a document store / JSONB (same documents, easier concurrent writes for OAuth records).
5. Whether `/authorize` auto-approves consent (consent is already captured in MedVault) or renders its own consent page (more realistic SMART flow).
6. Whether to generate `birth_certificate`: civil registry issues it, not a clinic.
7. Formalising Encounter / "Internare" as a user story, Trello cards and TRS FR (FHIR mock doc §7).
