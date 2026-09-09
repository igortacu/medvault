# S4 — Caregiver revocation takes effect immediately

**Spec:** FR6 (invitation states pending / active / revoked), FR7 (Caregiver
sees only what the Patient marked visible), FR9 (revocation is effective
immediately), FR10 (audit entry), ADR-01, ADR-02.

The interesting part is what the system does **not** do: it does not touch the
Caregiver's Redis session.

```mermaid
sequenceDiagram
    autonumber
    actor P as Browser (Patient)
    participant B as Backend · caregiver
    participant MW as Backend · authorization
    participant PG as PostgreSQL (as app_user)
    participant R as Redis
    actor C as Browser (Caregiver)

    Note over P,C: Before — the link is active and the Caregiver can read<br/>the documents the Patient marked visible (FR7).

    C->>MW: GET /api/documents (via S2)
    MW->>PG: SET LOCAL app.current_user_id = caregiver_id
    PG-->>C: the Patient's visible documents

    Note over P,C: The Patient revokes.

    P->>B: DELETE /api/caregivers/{id}
    B->>MW: authorization context = patient_id
    MW->>PG: BEGIN + SET LOCAL app.current_user_id = patient_id
    MW->>PG: UPDATE caregiver_links SET status='revoked' WHERE id=... 
    MW->>PG: INSERT INTO audit_logs (actor=patient, subject=patient, action='caregiver.revoke') — FR10
    MW->>PG: COMMIT
    B-->>P: 200 — revoked

    rect rgb(245, 235, 235)
        Note over B,R: Redis is NOT touched. The Caregiver's session stays<br/>valid AS AUTHENTICATION — they are still themselves.<br/>What changed is what they are AUTHORIZED to see,<br/>and that lives in PostgreSQL, not in the session.
    end

    Note over P,C: The Caregiver's very next request — no logout, no waiting.

    C->>MW: GET /api/documents<br/>Cookie: mv_session=... (still valid)
    MW->>R: GET session:{id}
    R-->>MW: {user_id: caregiver_id} — still a live session
    MW->>PG: BEGIN + SET LOCAL app.current_user_id = caregiver_id
    MW->>PG: SELECT * FROM documents

    Note right of PG: The RLS policy joins through caregiver_links<br/>and requires status='active'. The row is now<br/>'revoked', so the join matches nothing.

    PG-->>MW: 0 rows
    MW-->>C: 200 with an empty list

    Note over C,PG: Effective on the NEXT QUERY, with no session invalidation,<br/>no token blocklist, and no propagation delay (FR9).
```

## Why this is not a JWT with an embedded role — ADR-01

If the Caregiver's permissions travelled inside a signed token, the token issued
*before* the revocation would keep asserting them until it expired. Making that
safe requires a server-side blocklist checked on every request — which is a
session store with extra steps, and it discards the stateless property that was
the only reason to choose JWT in the first place.

By keeping the session as an opaque id and the *permissions* in the database,
the authorization decision is re-evaluated by the RLS policy on every single
query. There is no window during which a stale credential still works.

| | Session (Redis) | Permission (PostgreSQL) |
|---|---|---|
| Answers | "who is this?" | "what may they see?" |
| Changed by revocation | no | yes |
| Re-checked | once per request | on every query, by the engine |

This is the same mechanism as FR5 (institution disconnect) and the reason
S2's fail-closed behaviour matters: revocation and a missing context converge on
the same safe result — zero rows.
