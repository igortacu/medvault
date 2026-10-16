# medvault
pbl project

## Running locally

### With Docker (recommended)

You need Docker Desktop running.

1. Create your `.env` from `.env.example` and fill in the passwords and keys.
   Generate the two encryption keys with the commands in the file's comments.
2. From the repo root:

   ```bash
   docker compose up --build
   ```

3. Open http://localhost:5173.

| Service | Address | Notes |
|---|---|---|
| Frontend (Vite) | http://localhost:5173 | Hot reload; `/api` goes to the backend |
| Backend (FastAPI) | http://localhost:8000 | Reloads on changes in `backend/app`; docs at `/docs` |
| Institution mock | http://localhost:8001 | Synthetic hospital records |
| Postgres | localhost:5432 | Database `medvault` |
| Redis | localhost:6379 | |
| MinIO console | http://localhost:9001 | Log in with `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` |

Every `up` also runs the `migrate` step: migrations, demo accounts and the documents bucket.
All three are safe to repeat.

**Demo accounts** (see [backend/db/README.md](backend/db/README.md)): phone
`+37369000001` (also `…02`, `…03`, and caregivers `+37369100001`, `…02`),
password `Parola123!`.

**SMS codes** are not really sent. Read them at
http://localhost:8000/dev/sms/+37369000001 (put in the phone you used).

Useful commands:

```bash
docker compose logs -f backend      # follow one service's logs
docker compose down                 # stop everything, keep the data
docker compose down -v              # stop and wipe the database, files and node_modules
```

The database roles get their passwords from `.env` only when the Postgres volume is
first created. If you change those passwords later, run `docker compose down -v`.

### Without Docker

Run Postgres, Redis and MinIO yourself, then:

```bash
cd backend && alembic upgrade head && python -m db.seed_dev
cd backend && uvicorn app.main:app --reload --env-file ../.env --port 8000
uvicorn institution_mock.app:app --port 8001     # from the repo root
cd frontend && npm install && npm run dev
```

`npm run dev:mock` in `frontend/` runs the UI alone on fake data, already signed in.
