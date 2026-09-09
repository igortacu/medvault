# S3 — Connecting an institution (OAuth2 / SMART on FHIR subset)

**Spec:** FR3 (OAuth2 consent flow), FR4 (Observations ingested on success),
FR10 (audit entry), ADR-03 (simulated institution, patient id taken from the
token claim), R2 (IDOR), R3 (intercepted authorization code).

This is the **only** flow in MedVault where a JWT exists. It is a
server-to-server access token, never a user session (ADR-01).

```mermaid
sequenceDiagram
    autonumber
    actor U as Browser (Patient)
    participant B as Backend · institutions
    participant IM as institution-mock<br/>(authorization + resource server)
    participant MW as Backend · authorization
    participant PG as PostgreSQL (as app_user)

    U->>B: POST /api/institutions/connect
    B->>B: generate state (anti-CSRF), store against the session
    B-->>U: 302 -> GET /institution/authorize<br/>?response_type=code&client_id&redirect_uri<br/>&scope=patient/Observation.read&state

    U->>IM: GET /authorize (consent screen)
    Note right of IM: The patient authenticates HERE, at the institution.<br/>This step decides WHO the subject is — and it is<br/>the only place that decision is ever made.
    IM-->>U: 302 -> redirect_uri?code=...&state=...

    U->>B: GET /api/fhir/callback?code&state
    B->>B: verify state matches the session
    Note right of B: A mismatched or missing state is rejected here.<br/>Without it, an attacker could have the patient's<br/>browser deliver an attacker-issued code.

    B->>IM: POST /token (code, redirect_uri, client_id, client_secret)
    Note right of IM: Code TTL 60s, single-use. It is removed from the<br/>store BEFORE validation, so a failed exchange<br/>burns it too (risk R3).
    IM->>IM: mint JWT — sub = patient id, scope, exp
    IM-->>B: {access_token, token_type: Bearer, expires_in}

    B->>IM: GET /Observation<br/>Authorization: Bearer <token>
    Note over B,IM: NO "patient" query parameter is sent — and the<br/>endpoint would reject one with 400 if it were.<br/>The subject comes from the token's sub claim (ADR-03, R2).
    IM->>IM: validate signature, issuer, audience, exp, scope
    IM->>IM: patient_id := claims["sub"]
    IM-->>B: FHIR Bundle of Observations for that subject

    B->>MW: ingest under this patient's context
    MW->>PG: BEGIN + SET LOCAL app.current_user_id = patient_id
    MW->>PG: INSERT INTO observations (...)
    Note right of PG: WITH CHECK on the RLS policy refuses any row<br/>whose patient_id is not the current context —<br/>ingest cannot write into another patient's account.
    MW->>PG: INSERT INTO audit_logs (actor, subject_patient, action) — FR10
    MW->>PG: COMMIT
    B-->>U: 200 — institution connected, N observations imported
```

## The IDOR that this design removes

```mermaid
sequenceDiagram
    autonumber
    participant A as Any holder of a VALID token<br/>(subject = patient-001)
    participant IM as institution-mock

    A->>IM: GET /Observation?patient=patient-002<br/>Authorization: Bearer <valid token for patient-001>
    IM-->>A: 400 — "the 'patient' query parameter is not accepted —<br/>the subject is taken from the access token"

    Note over A,IM: Rejected, not silently ignored. A caller that sends<br/>?patient= believes it is choosing the subject — ignoring it<br/>would hand back patient-001's data while the caller<br/>logged it as patient-002's. The 400 makes the<br/>authorization bug visible at the source.
```

## Replayed authorization code

```mermaid
sequenceDiagram
    autonumber
    participant B as Backend · institutions
    participant IM as institution-mock

    B->>IM: POST /token (code=abc123) — first exchange
    IM->>IM: pop code from store, validate, mint token
    IM-->>B: 200 {access_token}

    B->>IM: POST /token (code=abc123) — replay
    IM->>IM: code is gone from the store
    IM-->>B: 400 {"detail": "invalid_grant"}

    Note over B,IM: Same 400 for an expired code (>60s) and for a code<br/>burned by a FAILED exchange. An attacker who<br/>intercepts a code gets one attempt at most (R3).
```

## Revocation (FR5)

Disconnecting an institution deletes the stored connection and its tokens. The
short access-token lifetime bounds the window; nothing that was ingested is
retroactively hidden, because those Observations now belong to the patient's own
record and are governed by the same RLS policies as everything else.
