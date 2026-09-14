"""auth SECURITY DEFINER functions and RLS on remaining sensitive tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-14

Addresses two findings from code review:

1. app.current_user_id GUC — the GUC is user-settable, so any direct INSERT on
   auth tables (users, verification_codes) by app_user is a risk if the application
   ever has a bug that runs privileged SQL under the wrong context. Replace direct
   grants for those operations with SECURITY DEFINER functions that run as `migrator`
   (which owns the schema and is not subject to RLS when FORCE is not set), keeping
   the auth lookup/insert path entirely outside app_user's direct reach.

2. No RLS on sensitive tables — verification_codes, step_up_verifications, and
   data_export_requests had no row-level filtering, giving app_user unrestricted
   table-wide access. This migration enables RLS on all three.

   users table RLS is deferred: the login phone-lookup and signup INSERT paths need
   all access patterns mapped before adding FORCE RLS without breaking the auth flow.
   The SECURITY DEFINER functions below are the first step — they remove the need for
   app_user to ever INSERT into users or verification_codes directly.
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_CUID = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"


def upgrade():
    # ------------------------------------------------------------------
    # SECURITY DEFINER functions — run as `migrator` (schema owner),
    # which bypasses RLS on tables where FORCE ROW LEVEL SECURITY is not
    # set. All functions are locked down to app_user only; PUBLIC execute
    # is revoked immediately after creation.
    # ------------------------------------------------------------------

    # Login flow: find a user by phone number before any session context exists.
    # Returns at most one row; the caller must verify password_hash client-side.
    op.execute("""
        CREATE OR REPLACE FUNCTION medvault.auth_lookup_user_by_phone(p_phone TEXT)
        RETURNS SETOF medvault.users
        LANGUAGE sql
        SECURITY DEFINER
        STABLE
        AS $$
            SELECT * FROM medvault.users
            WHERE phone_number = p_phone
            LIMIT 1;
        $$;
    """)
    op.execute("REVOKE ALL ON FUNCTION medvault.auth_lookup_user_by_phone(TEXT) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION medvault.auth_lookup_user_by_phone(TEXT) TO app_user")

    # Signup flow: insert a new user row before a session context exists.
    # IDNP fields are left NULL at creation; they are set later via a normal
    # authenticated UPDATE (which is subject to RLS — id = current_user_id).
    op.execute("""
        CREATE OR REPLACE FUNCTION medvault.auth_create_user(
            p_first_name    TEXT,
            p_last_name     TEXT,
            p_phone_number  TEXT,
            p_date_of_birth DATE,
            p_password_hash TEXT
        )
        RETURNS medvault.users
        LANGUAGE sql
        SECURITY DEFINER
        AS $$
            INSERT INTO medvault.users (
                first_name, last_name, phone_number, date_of_birth, password_hash
            )
            VALUES (
                p_first_name, p_last_name, p_phone_number, p_date_of_birth, p_password_hash
            )
            RETURNING *;
        $$;
    """)
    op.execute("""
        REVOKE ALL ON FUNCTION medvault.auth_create_user(TEXT, TEXT, TEXT, DATE, TEXT)
        FROM PUBLIC
    """)
    op.execute("""
        GRANT EXECUTE ON FUNCTION medvault.auth_create_user(TEXT, TEXT, TEXT, DATE, TEXT)
        TO app_user
    """)

    # Signup / login MFA: create a verification code before or during auth,
    # when app.current_user_id may not yet be set.
    op.execute("""
        CREATE OR REPLACE FUNCTION medvault.auth_create_verification_code(
            p_user_id   UUID,
            p_purpose   medvault.verification_purpose,
            p_code_hash TEXT,
            p_expires_at TIMESTAMPTZ
        )
        RETURNS medvault.verification_codes
        LANGUAGE sql
        SECURITY DEFINER
        AS $$
            INSERT INTO medvault.verification_codes (user_id, purpose, code_hash, expires_at)
            VALUES (p_user_id, p_purpose, p_code_hash, p_expires_at)
            RETURNING *;
        $$;
    """)
    op.execute("""
        REVOKE ALL ON FUNCTION medvault.auth_create_verification_code(
            UUID, medvault.verification_purpose, TEXT, TIMESTAMPTZ
        ) FROM PUBLIC
    """)
    op.execute("""
        GRANT EXECUTE ON FUNCTION medvault.auth_create_verification_code(
            UUID, medvault.verification_purpose, TEXT, TIMESTAMPTZ
        ) TO app_user
    """)

    # ------------------------------------------------------------------
    # Revoke direct INSERT on users and verification_codes from app_user.
    # All inserts go through the SECURITY DEFINER functions above.
    # ------------------------------------------------------------------
    op.execute("REVOKE INSERT ON medvault.users FROM app_user")
    op.execute("REVOKE INSERT ON medvault.verification_codes FROM app_user")

    # ------------------------------------------------------------------
    # RLS on verification_codes
    # ENABLE without FORCE: migrator (schema owner) and SECURITY DEFINER
    # functions running as migrator bypass RLS, which is intentional —
    # auth_create_verification_code must be able to insert for any user.
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE medvault.verification_codes ENABLE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY verification_codes_select ON medvault.verification_codes
        FOR SELECT USING (user_id = {_CUID})
    """)
    op.execute(f"""
        CREATE POLICY verification_codes_update ON medvault.verification_codes
        FOR UPDATE USING (user_id = {_CUID})
        WITH CHECK (user_id = {_CUID})
    """)

    # ------------------------------------------------------------------
    # RLS on step_up_verifications
    # Step-up flows always run for an already-authenticated user, so
    # app.current_user_id is always set — INSERT is safe under RLS here.
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE medvault.step_up_verifications ENABLE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY step_up_verifications_owner ON medvault.step_up_verifications
        FOR ALL USING (user_id = {_CUID})
        WITH CHECK (user_id = {_CUID})
    """)

    # ------------------------------------------------------------------
    # RLS on data_export_requests
    # Export requests are always initiated by an authenticated patient.
    # Background jobs updating status (pending → ready/failed) must set
    # app.current_user_id to the patient's UUID before the UPDATE.
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE medvault.data_export_requests ENABLE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY data_export_requests_owner ON medvault.data_export_requests
        FOR ALL USING (patient_id = {_CUID})
        WITH CHECK (patient_id = {_CUID})
    """)


def downgrade():
    # Re-grant direct INSERT removed above
    op.execute("GRANT INSERT ON medvault.users TO app_user")
    op.execute("GRANT INSERT ON medvault.verification_codes TO app_user")

    # Drop RLS
    op.execute("""
        DROP POLICY IF EXISTS data_export_requests_owner ON medvault.data_export_requests
    """)
    op.execute("ALTER TABLE medvault.data_export_requests DISABLE ROW LEVEL SECURITY")

    op.execute("""
        DROP POLICY IF EXISTS step_up_verifications_owner ON medvault.step_up_verifications
    """)
    op.execute("ALTER TABLE medvault.step_up_verifications DISABLE ROW LEVEL SECURITY")

    op.execute("""
        DROP POLICY IF EXISTS verification_codes_update ON medvault.verification_codes
    """)
    op.execute("""
        DROP POLICY IF EXISTS verification_codes_select ON medvault.verification_codes
    """)
    op.execute("ALTER TABLE medvault.verification_codes DISABLE ROW LEVEL SECURITY")

    # Drop SECURITY DEFINER functions
    op.execute("""
        DROP FUNCTION IF EXISTS medvault.auth_create_verification_code(
            UUID, medvault.verification_purpose, TEXT, TIMESTAMPTZ
        )
    """)
    op.execute("""
        DROP FUNCTION IF EXISTS medvault.auth_create_user(TEXT, TEXT, TEXT, DATE, TEXT)
    """)
    op.execute("DROP FUNCTION IF EXISTS medvault.auth_lookup_user_by_phone(TEXT)")
