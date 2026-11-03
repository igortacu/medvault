# MedVault: Security Requirements Analysis and Vulnerability Identification

**Task 1: Security Requirements Analysis and Vulnerability Identification**
**Reference list:** [OWASP Top 10:2025](https://top10.owasp.org/2025)
**Last updated:** 4 November 2026

MedVault lets a patient see their medical records from several Moldovan hospitals in one
place. It fetches records live from each institution, stores documents the patient uploads,
and lets a patient give a caregiver limited access. Medical data is among the most sensitive
personal data there is, so a security failure here can do lasting harm: leaked records cannot
be made private again.

This document covers:

1. Secure development practices and how MedVault applies them
2. A summary of each OWASP Top 10:2025 risk and its impact on MedVault
3. The data MedVault handles and the security requirements that protect it
4. The protections implemented during this task, and how they were tested
5. Risks that are still open
6. Who did what in the team

**Status labels used below**

| Label | Meaning |
|---|---|
| In place | Already in the codebase before this task |
| Added | Implemented during this task |
| Open | Known gap, not solved yet (see [section 5](#5-open-risks)) |

---

## 1. Introduction to secure development practices

Secure development means treating security as part of building the software, not as a check
at the end. These are the practices that matter most for MedVault:

| Practice | What it means | Example in MedVault |
|---|---|---|
| Least privilege | Give each component only the access it needs | The API connects as `app_user`, which is limited by row-level security; only migrations use the more powerful `migrator` role |
| Defence in depth | Use several layers, so one mistake is not fatal | Access is checked in the API and again by the database |
| Secure defaults | Unset or forgotten settings should be the safe ones | If `APP_ENV` is unset, the app behaves as production: secure cookies on, mock SMS refused, API docs hidden |
| Data minimisation | Data you never store cannot leak from your database | The IDNP (national ID number) is used once to find records and is never stored; hospital records are fetched live, not copied |
| Fail safely | Errors must not expose data or skip a check | Unexpected errors return a generic message, and one failing hospital does not take down the page |
| Validate input | Never trust what the client sends | Uploaded files are identified by their actual bytes, not by the type the client claims |
| Keep secrets out of code | Credentials belong in the environment | `.env` is gitignored; only `.env.example` with placeholders is committed |
| Keep dependencies patched | Most code you run was written by someone else | `scripts/security-audit.sh` checks all dependencies for known vulnerabilities |
| Log for accountability | You must be able to tell who did what, without logging secrets | An append-only audit trail, and logs scrubbed of IDNPs, tokens, phone numbers and medical values |

---

## 2. OWASP Top 10:2025 and its impact on MedVault

The OWASP Top 10 is a widely used list of the most critical web application security risks.
For each risk below: what it is, how it could hurt MedVault, and where MedVault stands today.

### A01:2025 Broken Access Control

**What it is.** Users can reach data or actions outside their permissions, for example by
changing an ID in a URL. Server-side request forgery (SSRF), where the server is tricked into
calling an attacker's address, is also included in this category.

**Impact on MedVault: critical.** One patient reading another patient's records would be the
worst realistic failure. A caregiver seeing a category the patient did not share is the same
kind of failure, on a smaller scale.

| Protection | Status |
|---|---|
| Row-level security enabled and forced on patient data tables (migration `0003`) | In place |
| Per-category caregiver permissions, checked by `caregiver_can` | In place |
| Institution `next` links followed only within that institution's FHIR address, which limits SSRF (`aggregation/client.py`) | In place |
| Browser requests from foreign origins refused on state-changing routes | Added |

### A02:2025 Security Misconfiguration

**What it is.** Insecure settings: missing headers, debug features left on, default
credentials, or more services exposed than needed.

**Impact on MedVault: high.** A leftover development setting could expose SMS login codes
through the `/dev/sms` page. Missing headers could allow the app to be framed, or medical
responses to be kept in a shared cache.

| Protection | Status |
|---|---|
| Production is the default mode; the mock SMS provider refuses to start in production | In place |
| Security headers on every API response, including `Cache-Control: no-store` | Added |
| `/docs`, `/redoc` and `/openapi.json` served only in development | Added |
| Frontend framing and content policy headers on the dev and preview servers | Added |
| Refusing to start with placeholder secrets | Open |
| Redis has no password, and all service ports are published by the dev compose file | Open |

### A03:2025 Software Supply Chain Failures

**What it is.** Risk from code you did not write: vulnerable or malicious libraries, images
and build tools.

**Impact on MedVault: high.** The API parses uploaded files and the crypto library protects
tokens. A flaw in either directly affects patient data.

| Protection | Status |
|---|---|
| Lockfile for npm, and pinned or bounded versions for Python | In place |
| All known vulnerabilities removed from Python and shipped frontend packages | Added |
| One-command dependency audit (`scripts/security-audit.sh`) | Added |
| Running the audit automatically, and fixing images to exact digests | Open |
| The MinIO image is a frozen legacy build that no longer receives updates | Open |

### A04:2025 Cryptographic Failures

**What it is.** Sensitive data that is unencrypted, or protected with weak or badly managed
cryptography.

**Impact on MedVault: high.** A stolen database backup should not reveal passwords, hospital
tokens or document names.

| Protection | Status |
|---|---|
| Passwords hashed with Argon2 | In place |
| Hospital OAuth tokens encrypted with Fernet | In place |
| Document title, notes and filename encrypted with AES-256-GCM, with key versions for rotation | In place |
| Session cookie is `HttpOnly`, `SameSite=Lax` and `Secure` outside development | In place |
| HSTS sent outside development | Added |
| TLS is not set up, because there is no production web server yet | Open |
| Uploaded files and exports are not encrypted by the app inside MinIO | Open |

### A05:2025 Injection

**What it is.** Untrusted input is run as code or as a query: SQL injection, cross-site
scripting (XSS), and similar attacks.

**Impact on MedVault: high.** SQL injection could bypass access rules. XSS could act as the
logged-in patient. Hospital data is also untrusted input, so a malicious document must not run
inside the app.

| Protection | Status |
|---|---|
| SQLAlchemy with bound parameters; the one interpolated SQL string uses only fixed function names from the code | In place |
| React escapes output; no `dangerouslySetInnerHTML` anywhere in the frontend | In place |
| Original files served with `Content-Security-Policy: sandbox` | In place |
| `default-src 'none'` policy on API responses | Added |
| Strict content policy for the built frontend, tested on the preview server | Added |

### A06:2025 Insecure Design

**What it is.** Weaknesses in the design itself, which careful coding cannot fix afterwards.

**Impact on MedVault: high.** Storing every hospital record centrally, for example, would turn
MedVault into a much larger target, however well the code was written.

| Protection | Status |
|---|---|
| IDNP never stored; there is a dedicated test for this (`test_idnp_never_kept.py`) | In place |
| Hospital records fetched live rather than copied | In place |
| Explicit patient consent before connecting a hospital | In place |
| Exports deleted after 30 minutes | In place |
| A written threat model | Open |

### A07:2025 Authentication Failures

**What it is.** Weak login, session handling or recovery that lets attackers impersonate users.

**Impact on MedVault: critical.** Taking over an account exposes the patient's whole medical
history, including everything fetched live from hospitals.

| Protection | Status |
|---|---|
| Every login needs a password and an SMS code | In place |
| SMS codes expire after 5 minutes, and a challenge is burned after 5 wrong attempts | In place |
| Login limited to 5 attempts per 15 minutes per account and IP | In place |
| Same error and same hashing cost for unknown phone and wrong password, to prevent account discovery | In place |
| Sessions expire after 15 idle minutes or 8 hours; a password reset signs out all devices | In place |
| Password rules: 10 characters minimum, plus a small list of common passwords | In place |
| A larger breached-password check, and a real SMS provider (only the mock exists today) | Open |

### A08:2025 Software or Data Integrity Failures

**What it is.** Trusting code or data without checking that it is genuine and unmodified.

**Impact on MedVault: medium to high.** A tampered hospital login flow could connect a patient
to the wrong records. A silently changed file could mislead a medical decision.

| Protection | Status |
|---|---|
| OAuth with PKCE (`S256`) and a one-time `state` value tied to the user | In place |
| SHA-256 of each upload recorded when it is stored | In place |
| Audit log rows cannot be changed or deleted, enforced by the database | In place |
| The SHA-256 is not re-checked when a file is read back | Open |

### A09:2025 Security Logging and Alerting Failures

**What it is.** Security events are not recorded, or nobody is told about them, so attacks go
unnoticed.

**Impact on MedVault: high.** Patients and auditors need to know who accessed which record. An
attack that is never noticed can continue indefinitely.

| Protection | Status |
|---|---|
| Append-only audit log for access and changes | In place |
| JSON logs scrubbed of IDNPs, tokens, phone numbers and medical values | In place |
| Rejected uploads and duplicate invites now reach the audit log (they failed before) | Added |
| Blocked cross-origin requests logged as a security warning | Added |
| Alerting on suspicious activity, as logs are not monitored yet | Open |

### A10:2025 Mishandling of Exceptional Conditions

**What it is.** Software that reacts badly to errors and unusual situations: crashing, leaking
details, or continuing in an unsafe state.

**Impact on MedVault: high.** If a request fails while loading records, a patient may see an
incomplete medical picture.

| Protection | Status |
|---|---|
| Generic error messages with no internal details | In place |
| A failing hospital affects only itself, with a timeout and circuit breaker | In place |
| Database deadlock when loading records fixed | Added |
| Wrong `500` response on rejected uploads and duplicate invites fixed | Added |

---

## 3. Initial security requirements analysis

### 3.1 Data MedVault handles

| Data | Sensitivity | Where it lives | Protection |
|---|---|---|---|
| Hospital medical records | Critical | Not stored; fetched live per request | Access checks, TLS needed in production, `no-store` on responses |
| Uploaded medical documents | Critical | MinIO, with metadata in Postgres | Access checks; metadata encrypted, file contents not yet |
| IDNP (national ID number) | Critical | Never stored; sent to institutions once when connecting | Not persisted, scrubbed from logs |
| Password | Critical | Postgres, hash only | Argon2 |
| Hospital OAuth tokens | Critical | Postgres, encrypted | Fernet |
| Name, phone, date of birth | High | Postgres | Row-level security |
| Weight and height | High | Postgres | Row-level security, caregiver permissions |
| Caregiver links and permissions | High | Postgres | Row-level security |
| Exports (PDF/JSON) | Critical | MinIO, for 30 minutes | Access checks, automatic deletion |
| Session IDs | High | Redis, and an `HttpOnly` cookie | Random 256-bit value, expiry |
| Audit logs | High | Postgres | Append-only, values scrubbed |

**MedVault does not handle payment details.**

### 3.2 Security requirements

| ID | Requirement | Measures | OWASP | Status |
|---|---|---|---|---|
| SR-01 | A patient's data must be readable only by that patient and caregivers they authorised, and only for the categories shared. | Row-level security, per-category permissions, session check on each request | A01 | In place |
| SR-02 | Login must need both a password and a one-time SMS code, and must resist password guessing. | Argon2, SMS challenge, rate limits, session expiry | A07 | In place; real SMS provider Open |
| SR-03 | Sensitive data must be protected in storage, and the IDNP must never be stored. | Argon2, Fernet, AES-256-GCM, IDNP used once | A04, A06 | In place; file encryption Open |
| SR-04 | All traffic must use encrypted connections in production. | HSTS and `Secure` cookie are ready; TLS itself needs a production web server | A04 | Open |
| SR-05 | The API must refuse state-changing requests from foreign websites, and must not let its responses be framed, sniffed or cached. | Origin check, security headers, `no-store` | A01, A02 | Added |
| SR-06 | Uploaded files must be validated before storage and must not be able to run as part of the app. | Magic-byte check, 10 MB limit, `sandbox` policy, caregiver upload permission | A05 | In place |
| SR-07 | Security-relevant actions must be recorded in a trail that cannot be altered and contains no secrets or medical values. | Append-only `audit_logs`, redaction, outcome validation | A09 | In place, improved |
| SR-08 | Dependencies must have no known vulnerabilities in anything shipped to users, and this must be easy to check. | Upgrades, `scripts/security-audit.sh` | A03 | Added |
| SR-09 | Errors must not leak internal details, and one failure must not break unrelated features. | Generic errors, per-source failure handling, ordered row updates | A10 | Added |
| SR-10 | Production must never run with development features or placeholder secrets. | Production by default, mock SMS refused, docs hidden; placeholder check not done | A02 | Partly Added; rest Open |

---

## 4. What was implemented in this task

### 4.1 Vulnerable dependencies replaced (A03)

An audit found known vulnerabilities in several packages, including the ones that parse
uploads and handle cryptography.

| Package | Before | After | Advisories before |
|---|---|---|---|
| `fastapi` (brings `starlette`) | 0.115.0 | 0.162.0 | none directly |
| `starlette` | 0.38.6 | 1.10.0 | 7 |
| `python-multipart` | 0.0.12 | 0.0.33 | 7 |
| `cryptography` | 46.0.7 | 50.0.2 | 4 |
| `vite` | 8.2.2 | 8.3.5 | high severity |
| `zod` | 4.5.4 | 4.6.7 | high severity |
| `vitest` and indirect dev packages | various | updated | high and moderate |

`scripts/security-audit.sh` now runs this check with Docker alone. It fails on any Python
advisory, and on any high or critical advisory in packages shipped to the browser.

**Result:** 0 known vulnerabilities in Python dependencies and in shipped frontend packages.
12 moderate findings remain in ESLint development tooling (see [section 5](#5-open-risks)).

**Upgrade note:** team members need to run `docker compose up --build` once.

### 4.2 Security headers and cross-origin protection (A01, A02)

New file: `backend/app/security/http_guard.py`

**Security headers on every API response**, including errors:

| Header | Protects against |
|---|---|
| `X-Content-Type-Options: nosniff` | The browser guessing a file's type and running it |
| `X-Frame-Options: DENY`, and `frame-ancestors 'none'` | Clickjacking through hidden frames |
| `Content-Security-Policy: default-src 'none'; ...` | An API response being treated as a page |
| `Cache-Control: no-store` | Medical data kept in browser or proxy caches |
| `Referrer-Policy: no-referrer` | URLs leaking to other sites |
| `Permissions-Policy` | Unneeded access to camera, microphone and location |
| `Strict-Transport-Security` (outside development) | Being downgraded to plain HTTP |

Routes can still set their own policy, so original files keep their stricter `sandbox` policy.

**Cross-origin check.** The session cookie is already `SameSite=Lax`, which stops cross-site
form posts. However, it does not stop *same-site* ones, such as a page on another port or
subdomain of the same host. So `POST`, `PUT`, `PATCH` and `DELETE` requests are now refused
with `403` when the browser reports a foreign origin:

- The `Origin` header must match `FRONTEND_URL` or `ALLOWED_ORIGINS`.
- `Origin: null`, which sandboxed frames send, is refused.
- If `Origin` is missing, `Sec-Fetch-Site` is used instead.
- Development also allows localhost on any port.
- Clients with neither header, such as curl, pass through. They have no browser cookies to abuse, and they still need a valid session.

**Also changed:**

- API docs are served only in development.
- The `server: uvicorn` response header is removed.
- The frontend dev and preview servers send framing and sniffing headers.
- The built app has a strict content policy, set on the preview server. A production web
  server must send the same headers; the policy is defined in `frontend/vite.config.ts`.

### 4.3 Error handling and audit fixes (A09, A10)

**Rejected uploads and duplicate invites returned `500`.** The code wrote the audit outcome
`"rejected"`, but the database only allows `success`, `denied` or `failure`. So every rejection
crashed with a server error, and **no audit record was saved**: exactly the events a security
trail should keep. The unit tests missed it because they use a fake database.

- Those paths now record `failure`, with the HTTP status in the upload's audit details.
- `write_audit_log` now checks the outcome itself, so the same mistake fails in unit tests.
- A new test confirms this check matches the database constraint.

**Parallel page loads could deadlock.** Each records request updates `last_fetched_at` for
every connected hospital and holds those row locks until commit. A page loads several
categories at once, and the rows had no guaranteed order. Two requests could lock the same
rows in opposite orders and wait on each other until Postgres cancelled one, which failed the
request. Connections are now always processed in ID order.

### 4.4 Test results

Every "After" result was measured on the running application. "Before" results were measured
too, except those marked "from the code" and the three `Origin` rows: no such check existed
before this task, so those requests were processed normally.

| Check | Before | After |
|---|---|---|
| Parallel records load, same load (240 requests) | **7 failed with `500`** | **0 failed** |
| Larger load (600 more requests) | not run | 0 failed, 0 deadlocks |
| Upload of the wrong file type | `500`, no audit record | `415`, audit record saved |
| Upload of an empty file | `500` (same cause, from the code) | `400`, audit record saved |
| Upload with an invalid category and type | `500` (same cause, from the code) | `422`, audit record saved |
| Second invite to the same phone | `500` (same cause, from the code) | `409` |
| `POST /auth/login` with `Origin: https://evil.example` | Processed | `403`, logged as a warning |
| `POST /auth/login` with `Origin: null` | Processed | `403`, logged as a warning |
| `POST /auth/login` with the real frontend origin | Processed | Still processed |
| Security headers on `/health` | None | All present |
| Python dependency advisories | 18 distinct | 0 |
| High-severity npm findings | 5 | 0 |

**Automated tests:** 260 backend tests (20 more than before), 18 institution mock tests and 87
frontend tests all pass.

**Browser regression test.** These flows ran in real Chromium, on both the dev server and the
built app under its strict content policy, with no console errors or failed requests:

- login with SMS code
- connecting hospitals through OAuth
- all document and profile pages
- viewing an original PDF
- creating an export
- logout

---

## 5. Open risks

These are known and not solved. They are listed so they can be planned, in rough priority order.

| # | Risk | OWASP | Why it matters | Suggested next step |
|---|---|---|---|---|
| 1 | No TLS or production web server | A04 | Without it, data and cookies travel unencrypted in a real deployment | Add a reverse proxy with TLS that also sends the frontend security headers |
| 2 | Files in MinIO not encrypted by the app | A04 | Access to the storage volume exposes uploaded documents and exports | Enable server-side encryption, or encrypt files before storing them |
| 3 | No check for placeholder secrets at startup | A02 | Production could run with values like `changeme`; seeded institution OAuth secrets are placeholders too | Refuse to start in production when a secret is a placeholder or missing |
| 4 | Redis has no password, and all ports are published | A02 | Redis holds sessions; anyone who can reach it could read or create them | Add a password and keep these services on an internal network |
| 5 | MinIO uses a frozen legacy image | A03 | It no longer receives security updates | Move to a maintained image or another S3-compatible store |
| 6 | No alerting | A09 | Attacks are logged, but nobody is notified | Alert on repeated blocks, failed logins and denied access |
| 7 | Audit not automated; images not pinned to digests | A03, A08 | New vulnerabilities appear after a clean audit | Run the audit script in CI and fix images to digests |
| 8 | Real SMS provider missing; small password blocklist | A07 | Login cannot work in production yet, and common passwords may be accepted | Integrate a provider and add a breached-password check |
| 9 | File hash not re-checked on read | A08 | Tampering in storage would go unnoticed | Compare the SHA-256 when serving a file |
| 10 | 12 moderate findings in ESLint tooling | A03 | Development only, never shipped to users; the available fix means a major downgrade of ESLint | Accepted for now; recheck when ESLint updates |
| 11 | No written threat model | A06 | Design risks are not reviewed systematically | Write one for the login, connect and caregiver flows |

---

## 6. Team contributions

*To be completed by the team. Each member should be ready to explain their own part and what
the others did.*

| Part | Done by | Notes |
|---|---|---|
| Secure development practices (section 1) | | |
| OWASP Top 10 research (section 2) | | |
| Data inventory and security requirements (section 3) | | |
| Implementation: dependency upgrades (4.1) | | |
| Implementation: headers and cross-origin check (4.2) | | |
| Implementation: error handling and audit fixes (4.3) | | |
| Testing and verification (4.4) | | |
| Open risk analysis (section 5) | | |

---

## How to check this yourself

```bash
docker compose up --build          # start everything
./scripts/security-audit.sh        # check dependencies for known vulnerabilities

# Should return 403
curl -i -X POST http://localhost:8000/auth/login \
  -H "Origin: https://evil.example" -H "Content-Type: application/json" \
  -d '{"phone":"+37369000001","password":"x"}'

# Should list the security headers
curl -sD- -o /dev/null http://localhost:8000/health
```

Backend unit tests, using the built image:

```bash
docker run --rm --network none -e PYTHONPATH=/repo -v "$PWD:/repo" -w /repo/backend \
  medvault-backend sh -c \
  'python -m unittest $(ls tests/test_*.py | sed "s#/#.#; s#\.py\$##")'
```

## References

- [OWASP Top 10:2025](https://top10.owasp.org/2025)
- [OWASP Cross-Site Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP HTTP Headers Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html)
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
