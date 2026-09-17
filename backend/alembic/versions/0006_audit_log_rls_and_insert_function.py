"""audit_logs — RLS, grants and append-only enforcement (schema sections 7, 8.3)

The audit table is separated from the general RLS migration because its rules
are unusual: any request may append (including pre-auth events with no user),
a patient may read only entries about their own data, and nothing may ever
update, delete or truncate it (FR10 immutability, TC-FUNC-07).

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-17
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE medvault.audit_logs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE medvault.audit_logs FORCE ROW LEVEL SECURITY;")

    op.execute("""
        -- Any request may append, including pre-auth events with no user
        -- (failed logins must still be recorded).
        CREATE POLICY audit_insert ON medvault.audit_logs FOR INSERT WITH CHECK (true);

        -- A patient can read entries about their own data (e.g. who viewed it), nothing else.
        CREATE POLICY audit_read_own ON medvault.audit_logs FOR SELECT
          USING (subject_patient_id = medvault.current_user_id());
    """)

    # The app may append and read, but never mutate.
    op.execute("GRANT SELECT, INSERT ON medvault.audit_logs TO app_user;")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON medvault.audit_logs FROM app_user;")

    # ------------------------------------------------------------------
    # Backstop against any privileged role or future grant mistake: refuse
    # every UPDATE/DELETE/TRUNCATE at the trigger level too.
    # ------------------------------------------------------------------
    op.execute("""
        CREATE FUNCTION medvault.audit_logs_block_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'audit_logs is append-only';
        END $$;

        CREATE TRIGGER audit_logs_no_update_delete
          BEFORE UPDATE OR DELETE ON medvault.audit_logs
          FOR EACH ROW EXECUTE FUNCTION medvault.audit_logs_block_mutation();

        CREATE TRIGGER audit_logs_no_truncate
          BEFORE TRUNCATE ON medvault.audit_logs
          FOR EACH STATEMENT EXECUTE FUNCTION medvault.audit_logs_block_mutation();
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_truncate ON medvault.audit_logs;")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update_delete ON medvault.audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS medvault.audit_logs_block_mutation();")
    op.execute("REVOKE SELECT, INSERT ON medvault.audit_logs FROM app_user;")
    op.execute("DROP POLICY IF EXISTS audit_read_own ON medvault.audit_logs;")
    op.execute("DROP POLICY IF EXISTS audit_insert ON medvault.audit_logs;")
    op.execute("ALTER TABLE medvault.audit_logs NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE medvault.audit_logs DISABLE ROW LEVEL SECURITY;")
