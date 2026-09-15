"""audit_log RLS and controlled insert function

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-14

Addresses two audit_logs findings from code review:

1. SELECT exposes every patient's audit history — app_user could read any
   patient's audit trail with a plain SELECT. Fix: enable RLS with a policy
   that limits visibility to rows where the caller is the actor OR the target
   patient.

2. INSERT lets app_user supply arbitrary actor_user_id / target_patient_id —
   forging who performed an action defeats the audit trail's integrity. Fix:
   revoke direct INSERT from app_user and replace it with a SECURITY DEFINER
   function that derives actor_user_id from app.current_user_id (the trusted
   server-set GUC) and raises if that context is missing.
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_CUID = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"


def upgrade():
    # ------------------------------------------------------------------
    # SECURITY DEFINER insert function — actor_user_id is always derived
    # from the server-side GUC; it cannot be supplied by the caller.
    # Raises immediately if no session context is set, so a missing
    # middleware SET LOCAL is a hard error, not a silent NULL actor.
    # ------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION medvault.audit_log_insert(
            p_target_patient_id  UUID,
            p_action             VARCHAR(100),
            p_resource_type      VARCHAR(50)  DEFAULT NULL,
            p_resource_id        UUID         DEFAULT NULL,
            p_ip_address         INET         DEFAULT NULL,
            p_user_agent         TEXT         DEFAULT NULL,
            p_metadata           JSONB        DEFAULT '{}'
        )
        RETURNS VOID
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        DECLARE
            v_actor_id UUID;
        BEGIN
            v_actor_id := NULLIF(current_setting('app.current_user_id', true), '')::uuid;
            IF v_actor_id IS NULL THEN
                RAISE EXCEPTION
                    'audit_log_insert: app.current_user_id is not set — '
                    'middleware must call SET LOCAL before any audit write'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;

            INSERT INTO medvault.audit_logs (
                actor_user_id,
                target_patient_id,
                action,
                resource_type,
                resource_id,
                ip_address,
                user_agent,
                metadata
            ) VALUES (
                v_actor_id,
                p_target_patient_id,
                p_action,
                p_resource_type,
                p_resource_id,
                p_ip_address,
                p_user_agent,
                p_metadata
            );
        END;
        $$;
    """)
    op.execute("""
        REVOKE ALL ON FUNCTION medvault.audit_log_insert(
            UUID, VARCHAR, VARCHAR, UUID, INET, TEXT, JSONB
        ) FROM PUBLIC
    """)
    op.execute("""
        GRANT EXECUTE ON FUNCTION medvault.audit_log_insert(
            UUID, VARCHAR, VARCHAR, UUID, INET, TEXT, JSONB
        ) TO app_user
    """)

    # Revoke direct INSERT — all writes must go through audit_log_insert()
    op.execute("REVOKE INSERT ON medvault.audit_logs FROM app_user")

    # ------------------------------------------------------------------
    # RLS on audit_logs
    # ENABLE without FORCE: migrator (schema owner) bypasses, which is
    # intentional — the SECURITY DEFINER function runs as migrator and
    # needs unrestricted INSERT; internal admin queries also need access.
    # app_user is not the table owner and is always subject to RLS.
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE medvault.audit_logs ENABLE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY audit_logs_select ON medvault.audit_logs
        FOR SELECT USING (
            actor_user_id     = {_CUID}
            OR target_patient_id = {_CUID}
        )
    """)


def downgrade():
    op.execute("DROP POLICY IF EXISTS audit_logs_select ON medvault.audit_logs")
    op.execute("ALTER TABLE medvault.audit_logs DISABLE ROW LEVEL SECURITY")
    op.execute("REVOKE EXECUTE ON FUNCTION medvault.audit_log_insert(UUID, VARCHAR, VARCHAR, UUID, INET, TEXT, JSONB) FROM app_user")
    op.execute("DROP FUNCTION IF EXISTS medvault.audit_log_insert(UUID, VARCHAR, VARCHAR, UUID, INET, TEXT, JSONB)")
    op.execute("GRANT INSERT ON medvault.audit_logs TO app_user")
