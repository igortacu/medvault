# Dev database seed

`seed_dev.py` fills a **development** MedVault database with coherent demo data:
patients, caregivers, connections, self-uploaded documents, an export and audit
entries. It is **not** a migration — it never runs in prod — and is idempotent
(every row has a fixed id + `ON CONFLICT DO NOTHING`, audit rows are guarded by a
`seed` marker), so you can run it repeatedly.

## Prerequisites

- The schema is migrated to head: from `backend/`, `alembic upgrade head`.
- `.env` provides `DATABASE_URL` (the **migrator** connection — the script needs
  BYPASSRLS to write across the RLS-forced tables).
- Deps installed: `pip install -r requirements.txt` (uses `psycopg2`, `argon2-cffi`).

## Run

```bash
cd backend
python -m db.seed_dev
```

Expected output (row counts):

```
users 5 · patient_profiles 3 · caregiver_links 3 · caregiver_permissions 5
institution_connections 5 · documents 4 · data_exports 1 · audit_logs 3
```

`institutions` (10) come from migration `0007`, not this script.

## Demo accounts

Every account's password is **`Parola123!`**.

| Person | Role | Phone |
|---|---|---|
| Maria Rusu | patient | `+37369000001` |
| Ion Popa | patient | `+37369000002` |
| Elena Ciobanu | patient | `+37369000003` |
| Andrei Rusu | caregiver (of Maria) | `+37369100001` |
| Daniela Munteanu | caregiver (of Ion; pending invite from Maria) | `+37369100002` |

Highlights: Maria has active connections (Timofei Moșneaga, Medpark), a revoked one
(Cardiologie) and 3 documents; Elena has a `no_match` connection; Andrei can view
Maria's prescriptions/analyses/certificates and update her measurement.

## Coherence with the other systems

- User/institution ids and the shared dev IDNP (`2001234567890`, Maria) match the
  **mock API** fixtures (`institution_mock/fixtures/`) and the **frontend** mock
  (`frontend/src/mocks/seed.json`), so all three tell the same story.
- Encrypted columns (document titles, tokens) hold **placeholder** bytea — there is
  no crypto util yet — and document `object_key`s may not exist in MinIO, so listing
  works but `/documents/{id}/original` can 404 until real files are uploaded.
