"""triggers and functions — RLS helpers and updated_at maintenance

Creates the two functions every RLS policy is written in terms of
(current_user_id, caregiver_can) plus a set_updated_at trigger so the
updated_at columns actually advance on UPDATE. The pre-auth SECURITY DEFINER
functions (auth_*/caregiver_*) live in migration 0005.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-17
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------------
    # RLS context helper (schema section 8.1) — fail-closed.
    # current_setting(..., true) returns NULL instead of raising when the
    # variable is missing; NULLIF turns '' into NULL. A NULL user matches no
    # rows, so a forgotten middleware call yields zero data (not full access).
    # ------------------------------------------------------------------
    op.execute("""
        CREATE FUNCTION medvault.current_user_id() RETURNS uuid
        LANGUAGE sql STABLE AS $$
          SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid
        $$;
    """)

    # ------------------------------------------------------------------
    # Permission helper (schema section 8.2).
    # SECURITY DEFINER so it can read caregiver_links/permissions regardless
    # of the caller's own policies; search_path pinned against hijacking.
    # Used both by RLS policies and by the API before proxying live data.
    # ------------------------------------------------------------------
    op.execute("""
        CREATE FUNCTION medvault.caregiver_can(
          p_patient  uuid,
          p_category medvault.data_category,
          p_action   text
        )
        RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = medvault, pg_temp AS $$
          SELECT EXISTS (
            SELECT 1
            FROM caregiver_links l
            JOIN caregiver_permissions p ON p.link_id = l.id
            WHERE l.patient_user_id   = p_patient
              AND l.caregiver_user_id = current_user_id()
              AND l.status            = 'active'
              AND p.category          = p_category
              AND CASE p_action
                    WHEN 'view'          THEN p.can_view
                    WHEN 'view_original' THEN p.can_view_original
                    WHEN 'export'        THEN p.can_export
                    WHEN 'upload'        THEN p.can_upload
                    ELSE false
                  END
          )
        $$;
    """)

    # ------------------------------------------------------------------
    # updated_at maintenance. The schema gives every mutable table an
    # updated_at column but no trigger; without one the column never advances
    # after INSERT. This keeps it accurate as a DB-side backstop to the app.
    # ------------------------------------------------------------------
    op.execute("""
        CREATE FUNCTION medvault.set_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          NEW.updated_at := now();
          RETURN NEW;
        END $$;
    """)

    for table in (
        "users",
        "patient_profiles",
        "institutions",
        "institution_connections",
        "caregiver_permissions",
        "documents",
    ):
        op.execute(f"""
            CREATE TRIGGER {table}_set_updated_at
              BEFORE UPDATE ON medvault.{table}
              FOR EACH ROW EXECUTE FUNCTION medvault.set_updated_at();
        """)


def downgrade():
    for table in (
        "documents",
        "caregiver_permissions",
        "institution_connections",
        "institutions",
        "patient_profiles",
        "users",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_set_updated_at ON medvault.{table};")

    op.execute("DROP FUNCTION IF EXISTS medvault.set_updated_at();")
    op.execute("DROP FUNCTION IF EXISTS medvault.caregiver_can(uuid, medvault.data_category, text);")
    op.execute("DROP FUNCTION IF EXISTS medvault.current_user_id();")
