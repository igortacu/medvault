# MedVault — architecture diagrams

**Published:** [igortacu.github.io/medvault](https://igortacu.github.io/medvault/) — a single-page document assembled from the files in this directory (`docs/build_site.py`). Edit the sources here, not the generated page.

Two tools, each doing what it is good at:

- **[`diagrams`](https://diagrams.mingrammer.com/) (Graphviz)** — structure and
  topology. Scripts are `.py`, committed alongside the `.png` they produce.
- **Mermaid `sequenceDiagram`** — step-by-step flows, in `.md` files so GitHub
  renders them natively.

`diagrams` cannot express temporal order, so it is never used for a process.
Mermaid is never used for topology.

Everything here follows *MedVault — Technical Requirements Specification v1.1*
(§2.1 stack, §2.2 ADR-01..ADR-05, §2.3 database setup & migration strategy,
§3 FR1..FR12, §4 non-functional, §6 R1..R6). A component that is not in the
spec is not in a diagram.

> Two documents both labelled *v1.1* are in circulation. These diagrams follow
> the **later English revision** — the one that contains §2.3 *Database Setup &
> Migration Strategy*, Alembic in the §2.1 stack table, and risk **R6**. If your
> copy stops at §2.2 and R5, it is the superseded one.

## Which diagram answers which question

| Question | Diagram |
|---|---|
| What runs where, and what talks to what? | `medvault_diagram.py` (C4 L2 — see *Known gap* below) |
| What is inside the backend, and what may touch the database? | **D1** — [`backend_components.py`](backend_components.py) → `backend_components.png` |
| What was the earlier single-Droplet deployment? | **D2 (legacy)** — [`deployment.py`](deployment.py) → `deployment.png` |
| Where does each data class live on AWS, how does it move, and how long is it retained? | **D3** — [`aws_data_architecture.py`](aws_data_architecture.py) → `aws_data_architecture.png`; details in [`AWS_DATA_ARCHITECTURE.md`](AWS_DATA_ARCHITECTURE.md) |
| How does a user sign in? | **S1** — [`flow_login.md`](flow_login.md) |
| How is a request authorized, and what happens when the middleware is missing? | **S2** — [`flow_authorized_request.md`](flow_authorized_request.md) ← *start here* |
| How does connecting an institution work, and where was the IDOR? | **S3** — [`flow_institution_connect.md`](flow_institution_connect.md) |
| Why is revoking a Caregiver instant? | **S4** — [`flow_caregiver_revoke.md`](flow_caregiver_revoke.md) |

Only four flows are drawn, and all four are places where an implementation
mistake has a security consequence. Plain CRUD paths (list, filter, export) are
deliberately not diagrammed — they carry no specific risk and would drift out of
date faster than they would earn their keep.

## Invariants every diagram must keep

These are the things to check when editing:

1. **JWT never appears for a user session.** It exists only in S3, as an
   institution-mock OAuth2 access token (ADR-01). User sessions are an opaque id
   in a cookie, with state in Redis.
2. **No feature module reaches PostgreSQL directly.** In D1 every module arrow
   passes through `authorization`, which does `BEGIN` + `SET LOCAL
   app.current_user_id` (ADR-02). The one annotated exception is the
   pre-session login lookup, which cannot have a context yet and therefore runs
   through a narrow `SECURITY DEFINER` function returning a single id.
3. **Missing context = zero rows, never an error and never data** (S2,
   TC-SEC-01).
4. **`GET /Observation` takes no `patient` query parameter** (S3, ADR-03, R2).
5. **The SMS code exists only in the sms-mock container log** (S1, ADR-05).
6. **Self-upload stores and categorises — it never parses** (D1, ADR-04).
7. **DDL never runs as `app_user`.** Schema changes reach the database only
   through the blocking `alembic upgrade head` step run by `migrator` before the
   app serves traffic — and the deploy fails closed if it errors (D2, §2.3, R6).
   Bootstrap (once per instance) and migrations (every deploy) are separate
   things and are drawn separately.

## Regenerating the PNGs

Graphviz must be installed (`brew install graphviz` / `apt install graphviz`).

```bash
cd docs/architecture
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python backend_components.py
.venv/bin/python deployment.py
.venv/bin/python aws_data_architecture.py
```

`.venv/` is gitignored. The `.png` files are committed so the diagrams are
readable on GitHub without running anything.

## Regenerating the published page

`docs/index.html` (the GitHub Pages site) is generated from the four
`flow_*.md` files plus the two PNGs above — it is not hand-edited:

```bash
.venv/bin/pip install markdown
.venv/bin/python ../build_site.py
```

Run this after changing any `flow_*.md` file or regenerating a diagram, then
commit `docs/index.html` along with the source you changed. GitHub Pages is
configured to serve the `docs/` folder from `main`.

## Checking the Mermaid files

`mermaid.parse()` is the same parser GitHub uses:

```bash
npx -y @mermaid-js/mermaid-cli -i flow_authorized_request.md -o /tmp/out.svg
```

All seven Mermaid blocks in this directory currently parse without error.

## Known gap — the container diagram (C4 L2)

`medvault_diagram.py` **does not exist in this repository.** The task that
produced D1, D2 and S1–S4 was written assuming it was already here and
explicitly said not to recreate it, so it was left alone rather than invented.

Until it is added, the set skips straight from context to components: D1 shows
the backend's internals and D2 shows deployment, but nothing shows the
container-level view of frontend / backend / mocks / stores as peers. Worth
closing.

## Notes on spec alignment

- **The two-role split is specified.** §2.3 defines `migrator` (owns the schema,
  applies DDL) and `app_user` (used by the running application, restricted by
  RLS, cannot bypass it), and states the application never connects as
  `migrator`. This is what makes ADR-02's fail-closed guarantee hold — a role
  that owned the tables would bypass RLS. It appears in D1 and D2.
  *(An earlier draft of this README claimed this decision was undocumented and
  proposed adding an "ADR-06". That was based on a superseded copy of the spec
  and is wrong: it is §2.3, not a missing ADR.)*
- **`medvault_data`** (a second Docker network, `internal: true`) is in D2 but
  not in the spec. It is a stricter form of the stated constraint, not a new
  component: Postgres, Redis and MinIO get no host ports *and* no route out.

### Implementation drift to resolve

§2.3 requires application tables to live in a dedicated **`medvault` schema
(not `public`)**, to isolate them from cluster-level objects. The diagrams show
the specified `medvault` schema. **The current backend code still uses
`public`** — see `postgres/10-bootstrap.sh` and the Alembic migrations. This is
a real gap between spec and implementation, not a diagram error.

## Deliberately absent

No diagram covers the conversational assistant (RAG), voice, or any ML
component. None of them exist in the MVP — spec v1.1 §7 lists RAG as *planned
for a later phase*, with per-patient filtering required at retrieval time.
Roughly **October–December**, outside the September MVP. Nothing is drawn for it
until there is a specification to draw from.

Also absent, for the same reason: caches, queues, workers, load balancers,
replicas, CI/CD and staging. If it is not in the spec, it is not in a picture.

## Implementation status

This repository currently holds **architecture only** — these diagrams and
this document — not an implementation. An earlier working session built a
runnable Docker Compose stack against this design (backend, institution-mock,
sms-mock, Postgres/Redis/MinIO, Caddy) to produce empirical evidence for a few
claims in S2 and S3 (the RLS fail-closed test, the IDOR rejection). That code
was deliberately removed once it had served that purpose — the deliverable at
this stage is the design, not the code.
