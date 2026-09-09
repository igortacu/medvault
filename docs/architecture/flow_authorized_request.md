# S2 — Authorized request under Row-Level Security

> **The most important flow in the system.** Every other authenticated request
> is a special case of this one.

**Spec:** ADR-02 (authorization enforced by PostgreSQL RLS, fail-closed when the
context is missing), R1 and R4 in §6 (omitted middleware; connection recycled
from the pool without resetting the context).

```mermaid
sequenceDiagram
    autonumber
    actor U as Browser
    participant MW as Backend · authorization<br/>(FastAPI dependency)
    participant H as Backend · endpoint handler
    participant R as Redis
    participant PG as PostgreSQL (as app_user)

    U->>MW: GET /api/documents<br/>Cookie: mv_session=opaque_id

    MW->>MW: verify cookie HMAC
    MW->>R: GET session:{opaque_id}

    alt no session (expired, revoked, forged id)
        R-->>MW: nil
        MW-->>U: 401 — request never reaches the database
    else session valid
        R-->>MW: {user_id, role}

        MW->>PG: BEGIN
        MW->>PG: SELECT set_config('app.current_user_id', user_id, true)
        Note right of MW: is_local => true, i.e. SET LOCAL semantics.<br/>Scoped to the TRANSACTION, not the connection.<br/>Connections are pooled and reused across patients —<br/>a per-connection SET would leak one patient's<br/>context into the next request (risk R4).

        MW->>H: hand over the session-scoped txn
        H->>PG: SELECT * FROM documents
        Note right of PG: The query carries NO "WHERE patient_id = ..." clause.<br/>The RLS policy is the filter:<br/>USING (patient_id = current_patient_id())

        PG-->>H: only this patient's rows
        H-->>MW: result
        MW->>PG: COMMIT
        Note right of PG: COMMIT discards app.current_user_id.<br/>The connection returns to the pool with no context.
        MW-->>U: 200 + rows
    end
```

## The fail-closed branch — test **TC-SEC-01**

A new endpoint is added and the author forgets the `authorization` dependency
(risk **R1**). The request still reaches the database, but with no context set.

```mermaid
sequenceDiagram
    autonumber
    actor U as Browser
    participant H as Backend · endpoint handler<br/>(authorization dependency MISSING)
    participant PG as PostgreSQL (as app_user)

    U->>H: GET /api/some-new-endpoint
    Note over H: BUG — no BEGIN + SET LOCAL.<br/>app.current_user_id was never set.

    H->>PG: SELECT * FROM documents

    Note right of PG: current_setting('app.current_user_id', true) => NULL<br/>policy: USING (patient_id = NULL)<br/>NULL comparison is never true.

    PG-->>H: 0 rows
    H-->>U: 200 with an empty list

    Note over U,PG: TC-SEC-01 — the bug degrades to "no data",<br/>never to another patient's data.<br/>Not a 500, and not a cross-patient leak.<br/>app_user is NOBYPASSRLS and does not own the tables,<br/>so it cannot escape the policy.
```

**What TC-SEC-01 asserts:** query a patient-data table as `app_user` with no
`app.current_user_id` set, and get exactly zero rows while the same rows are
visible to a role that bypasses RLS. Failing open — any row count above zero —
is a release blocker.

Run it against a live stack:

```bash
curl -s http://localhost/api/_rls/selftest
```

## Why fail-closed rather than an error

Raising an exception on a missing context would also be safe, but it depends on
application code remembering to check. The RLS policy is evaluated by the
database engine on every query, including queries written by code that has
never heard of the check. Zero rows is the weakest outcome that is still safe,
and it needs no cooperation from the caller — which is the whole point of
ADR-02.
