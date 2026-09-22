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

_P1, _P2, _P3 = (p[0] for p in PATIENTS)
_C1, _C2 = (c[0] for c in CAREGIVERS)

# Caregiver links: (id, patient, caregiver_or_None, invited_first, invited_last, invited_phone, status)
LINKS = [
    (UUID("30000000-0000-0000-0000-000000000001"), _P1, _C1, "Andrei", "Rusu", "+37369100001", "active"),
    (UUID("30000000-0000-0000-0000-000000000002"), _P2, _C2, "Daniela", "Munteanu", "+37369100002", "active"),
    # A pending invite (not yet accepted): caregiver_user_id stays NULL until acceptance.
    (UUID("30000000-0000-0000-0000-000000000003"), _P1, None, "Daniela", "Munteanu", "+37369100002", "pending"),
]

# Per-link permissions: link_id -> [(category, can_view, can_view_original, can_export, can_upload)]
PERMISSIONS = {
    LINKS[0][0]: [
        ("prescriptions", True, True, True, False),
        ("analyses", True, True, False, False),
        ("certificates", True, False, False, False),
        ("patient_info", True, False, False, True),  # may update Maria's measurement
    ],
    LINKS[1][0]: [
        ("prescriptions", True, False, False, False),
    ],
}

SCOPES = ["patient/Patient.read", "patient/Observation.read", "offline_access"]

# Connections: (id, patient, institution external_id, origin, status, fhir_patient_ref)
CONNECTIONS = [
    (UUID("40000000-0000-0000-0000-000000000001"), _P1, "imsp-scr-t-mosneaga", "auto_public", "active", "Patient/pat-001"),
    (UUID("40000000-0000-0000-0000-000000000002"), _P1, "medpark", "user_added", "active", "Patient/pat-101"),
    (UUID("40000000-0000-0000-0000-000000000003"), _P1, "imsp-institutul-cardiologie", "auto_public", "revoked", "Patient/pat-001"),
    (UUID("40000000-0000-0000-0000-000000000004"), _P2, "imsp-scr-t-mosneaga", "auto_public", "active", "Patient/pat-001"),
    (UUID("40000000-0000-0000-0000-000000000005"), _P3, "medpark", "user_added", "no_match", None),
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


def seed_caregivers(cur) -> None:
    for lid, patient, caregiver, inv_first, inv_last, inv_phone, status in LINKS:
        responded = "now()" if status == "active" else "NULL"
        cur.execute(
            f"""
            INSERT INTO medvault.caregiver_links
              (id, patient_user_id, caregiver_user_id,
               invited_first_name, invited_last_name, invited_phone_e164,
               status, responded_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, {responded})
            ON CONFLICT (id) DO NOTHING
            """,
            (
                str(lid), str(patient),
                str(caregiver) if caregiver else None,
                inv_first, inv_last, inv_phone, status,
            ),
        )

    for lid, perms in PERMISSIONS.items():
        for category, can_view, can_view_original, can_export, can_upload in perms:
            cur.execute(
                """
                INSERT INTO medvault.caregiver_permissions
                  (link_id, category, can_view, can_view_original, can_export, can_upload)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (link_id, category) DO NOTHING
                """,
                (str(lid), category, can_view, can_view_original, can_export, can_upload),
            )


def seed_connections(cur) -> None:
    cur.execute("SELECT external_id, id FROM medvault.institutions")
    inst = {ext: iid for ext, iid in cur.fetchall()}

    now = datetime.datetime.now(datetime.timezone.utc)
    token = psycopg2.Binary(b"DEV_PLACEHOLDER_TOKEN")

    for cid, patient, ext, origin, status, patient_ref in CONNECTIONS:
        active = status == "active"
        revoked = status == "revoked"
        # A revoked connection must have its tokens wiped (conn_revoked_wipes_tokens).
        cur.execute(
            """
            INSERT INTO medvault.institution_connections
              (id, patient_user_id, institution_id, origin, status,
               consent_text_version, consented_at, requested_scopes, granted_scopes,
               fhir_patient_ref, access_token_ciphertext, access_token_expires_at,
               refresh_token_ciphertext, token_key_version, connected_at,
               last_fetched_at, revoked_at, revoked_by_user_id, failure_reason)
            VALUES (%s, %s, %s, %s, %s, 'v1', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                str(cid), str(patient), str(inst[ext]), origin, status,
                now,  # consented_at (given for active/revoked/no_match here)
                SCOPES,
                SCOPES if (active or revoked) else None,  # granted_scopes
                patient_ref,
                token if active else None,                # access_token_ciphertext
                (now + datetime.timedelta(minutes=15)) if active else None,
                token if active else None,                # refresh_token_ciphertext
                0 if active else None,                    # token_key_version
                now if (active or revoked) else None,     # connected_at
                now if active else None,                  # last_fetched_at
                now if revoked else None,                 # revoked_at
                str(patient) if revoked else None,        # revoked_by_user_id
                "no_match" if status == "no_match" else None,
            ),
        )


def main() -> None:
    _load_dotenv()
    ph = PasswordHasher()
    conn = psycopg2.connect(_dsn())
    try:
        with conn, conn.cursor() as cur:
            seed_users_and_profiles(cur, ph)
            seed_caregivers(cur)
            seed_connections(cur)
            counts = {}
            for table in ("users", "patient_profiles", "caregiver_links",
                          "caregiver_permissions", "institution_connections"):
                cur.execute(f"SELECT count(*) FROM medvault.{table}")
                counts[table] = cur.fetchone()[0]
    finally:
        conn.close()

    print("Seeded app database (dev).")
    for table, n in counts.items():
        print(f"  {table:<22} {n}")
    print(f"  demo password for every account: {DEV_PASSWORD}")
    print("  patients:  +37369000001..3   caregivers: +37369100001..2")


if __name__ == "__main__":
    main()
