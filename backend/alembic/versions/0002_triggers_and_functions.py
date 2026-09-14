"""triggers and functions

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-09
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # --- set_updated_at() ---
    op.execute("""
        CREATE OR REPLACE FUNCTION medvault.set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_users_updated_at
        BEFORE UPDATE ON medvault.users
        FOR EACH ROW EXECUTE FUNCTION medvault.set_updated_at();
    """)

    # --- enforce_idnp_present() ---
    op.execute("""
        CREATE OR REPLACE FUNCTION medvault.enforce_idnp_present()
        RETURNS TRIGGER AS $$
        DECLARE
            v_idnp BYTEA;
        BEGIN
            SELECT idnp_encrypted INTO v_idnp
            FROM medvault.users WHERE id = NEW.patient_id;
            IF v_idnp IS NULL THEN
                RAISE EXCEPTION 'IDNP required before this action (patient_id=%)', NEW.patient_id
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_institution_connections_require_idnp
        BEFORE INSERT ON medvault.institution_connections
        FOR EACH ROW EXECUTE FUNCTION medvault.enforce_idnp_present();
    """)
    op.execute("""
        CREATE TRIGGER trg_documents_require_idnp
        BEFORE INSERT ON medvault.documents
        FOR EACH ROW
        WHEN (NEW.source = 'self_upload')
        EXECUTE FUNCTION medvault.enforce_idnp_present();
    """)

    # --- set_document_purge_date() ---
    op.execute("""
        CREATE OR REPLACE FUNCTION medvault.set_document_purge_date()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.deleted_at IS NOT NULL AND OLD.deleted_at IS NULL THEN
                NEW.purge_scheduled_at := NEW.deleted_at + INTERVAL '30 days';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_documents_purge_date
        BEFORE UPDATE ON medvault.documents
        FOR EACH ROW EXECUTE FUNCTION medvault.set_document_purge_date();
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS trg_documents_purge_date ON medvault.documents")
    op.execute("DROP FUNCTION IF EXISTS medvault.set_document_purge_date()")
    op.execute("DROP TRIGGER IF EXISTS trg_documents_require_idnp ON medvault.documents")
    op.execute("DROP TRIGGER IF EXISTS trg_institution_connections_require_idnp ON medvault.institution_connections")
    op.execute("DROP FUNCTION IF EXISTS medvault.enforce_idnp_present()")
    op.execute("DROP TRIGGER IF EXISTS trg_users_updated_at ON medvault.users")
    op.execute("DROP FUNCTION IF EXISTS medvault.set_updated_at()")
