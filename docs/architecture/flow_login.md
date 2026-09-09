# S1 — Login with mandatory SMS verification

**Spec:** FR1 (argon2id password hash), FR2 (SMS code on *every* sign-in, a
mandatory second factor — not optional), ADR-01 (server-side session in Redis),
ADR-05 (sms-mock; the code exists only in the container log).

No JWT appears anywhere in this flow. The cookie carries an opaque session id
and nothing else.

```mermaid
sequenceDiagram
    autonumber
    actor U as Browser (Patient/Caregiver)
    participant CA as Caddy
    participant AU as Backend · auth
    participant PG as PostgreSQL
    participant SMS as sms-mock
    participant R as Redis

    Note over U,R: Step 1 — credentials

    U->>CA: POST /api/auth/login {phone, password}
    CA->>AU: forward over medvault_internal
    AU->>PG: pre-session lookup by phone (SECURITY DEFINER, returns one id)
    PG-->>AU: user_id + argon2id hash
    AU->>AU: argon2id verify (FR1)

    alt password invalid
        AU-->>U: 401 generic "invalid credentials"
        Note right of AU: Same message and timing as an unknown phone,<br/>so the response cannot be used to enumerate accounts.<br/>No session is created.
    else password valid
        AU->>AU: generate 6-digit code
        AU->>R: SETEX pending_verification:{phone} TTL 300s
        AU->>SMS: POST /send {phone, code}
        SMS->>SMS: write code to stdout
        Note right of SMS: The code exists ONLY in the container log<br/>(docker compose logs sms-mock) — ADR-05.<br/>It is never returned in an HTTP response.
        SMS-->>AU: 202 Accepted
        AU-->>U: 202 "code sent" (no code in the body)
    end

    Note over U,R: Step 2 — the second factor (FR2, always required)

    U->>CA: POST /api/auth/verify {phone, code}
    CA->>AU: forward
    AU->>R: GET pending_verification:{phone}

    alt code wrong, expired, or absent
        R-->>AU: miss / mismatch
        AU-->>U: 401 generic "invalid or expired code"
        Note right of AU: No session created. The attempt is counted<br/>against a rate limit on this endpoint —<br/>the stored code is not revealed either way.
    else code correct
        R-->>AU: match
        AU->>R: DEL pending_verification:{phone}
        Note right of AU: Single use — a correct code is burned<br/>so it cannot be replayed.
        AU->>R: SETEX session:{opaque_id} TTL 3600s {user_id, role}
        AU-->>U: 200 + Set-Cookie: mv_session=opaque_id
        Note over U,R: Cookie is HttpOnly, Secure, SameSite=Lax.<br/>It holds an opaque id + HMAC — no user data, no role,<br/>no JWT (ADR-01). Session state lives only in Redis,<br/>so DEL session:{id} revokes access instantly.
    end
```

## Why it is shaped this way

- **The code never leaves the server as data.** `POST /auth/start` responds
  `202` with no code in the body. The only readable copy is the sms-mock log.
  A network attacker who can read responses still cannot log in.
- **Both failure branches return the same shape of answer.** Wrong password and
  wrong code both produce a generic message, so neither can be used to discover
  which phone numbers are registered.
- **The cookie is opaque.** Putting the role in a JWT would make revocation
  (FR9, and S4) impossible without a blocklist — the alternative ADR-01
  explicitly rejects.
