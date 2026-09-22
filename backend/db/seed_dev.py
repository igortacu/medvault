"""Idempotent development seed for the MedVault app database.

Run against a DEV database only — it inserts demo people and medical data. It is
NOT a migration (keeps demo/PII out of every environment) and connects as the
`migrator` role, which holds BYPASSRLS, since RLS is forced on every user table.

Usage (from backend/, with .env providing DATABASE_URL):
    python -m db.seed_dev

Re-runnable: every row uses a fixed UUID and ON CONFLICT DO NOTHING.
All demo accounts share the password below.
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path
from uuid import UUID

import psycopg2
from argon2 import PasswordHasher

DEV_PASSWORD = "Parola123!"  # meets the signup rules; dev only

# --- demo people --------------------------------------------------------------
# Patients: (id, first, last, phone, dob, weight_kg, height_cm)
PATIENTS = [
    (UUID("10000000-0000-0000-0000-000000000001"), "Maria", "Rusu", "+37369000001", datetime.date(1958, 3, 14), 72.4, 164.0),
    (UUID("10000000-0000-0000-0000-000000000002"), "Ion", "Popa", "+37369000002", datetime.date(1949, 11, 2), 81.0, 176.5),
    (UUID("10000000-0000-0000-0000-000000000003"), "Elena", "Ciobanu", "+37369000003", datetime.date(1965, 6, 28), 60.2, 159.0),
]
# Caregivers: (id, first, last, phone, dob)
CAREGIVERS = [
    (UUID("20000000-0000-0000-0000-000000000001"), "Andrei", "Rusu", "+37369100001", datetime.date(1985, 1, 20)),
    (UUID("20000000-0000-0000-0000-000000000002"), "Daniela", "Munteanu", "+37369100002", datetime.date(1990, 9, 5)),
]


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _dsn() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL not set (expected the migrator connection).")
    # psycopg2 wants a bare postgresql:// URL, not the SQLAlchemy +psycopg2 form.
    return url.replace("+psycopg2", "")


def seed_users_and_profiles(cur, ph: PasswordHasher) -> None:
    pw_hash = ph.hash(DEV_PASSWORD)

    for uid, first, last, phone, dob, _w, _h in PATIENTS + [
        (c[0], c[1], c[2], c[3], c[4], None, None) for c in CAREGIVERS
    ]:
        cur.execute(
            """
            INSERT INTO medvault.users
              (id, first_name, last_name, phone_e164, date_of_birth,
               password_hash, status, phone_verified_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'active', now())
            ON CONFLICT (id) DO NOTHING
            """,
            (str(uid), first, last, phone, dob, pw_hash),
        )

    for uid, _f, _l, _p, _d, weight, height in PATIENTS:
        cur.execute(
            """
            INSERT INTO medvault.patient_profiles
              (user_id, weight_kg, height_cm, measurements_updated_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (user_id) DO NOTHING
            """,
            (str(uid), weight, height),
        )


def main() -> None:
    _load_dotenv()
    ph = PasswordHasher()
    conn = psycopg2.connect(_dsn())
    try:
        with conn, conn.cursor() as cur:
            seed_users_and_profiles(cur, ph)
            cur.execute("SELECT count(*) FROM medvault.users")
            users = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM medvault.patient_profiles")
            profiles = cur.fetchone()[0]
    finally:
        conn.close()

    print("Seeded app database (dev).")
    print(f"  users:            {users}")
    print(f"  patient_profiles: {profiles}")
    print(f"  demo password for every account: {DEV_PASSWORD}")
    print("  patients:  +37369000001..3   caregivers: +37369100001..2")


if __name__ == "__main__":
    main()
