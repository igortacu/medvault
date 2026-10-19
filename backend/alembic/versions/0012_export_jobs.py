"""data export jobs — status updates and expiry cleanup (Story 2.9)

1. exports_update — the requester's own export job moves its row through
   requested -> processing -> ready/failed. Only the requester (the role that
   created it under exports_insert) may update it, and only in place: the patient,
   requester and categories can't be changed (WITH CHECK keeps the same owner).
2. expire_data_exports() — SECURITY DEFINER, for the cleanup that runs without a
   user: marks every ready export past its 30-minute window `expired`, fails jobs
   stuck for over an hour, and returns the stored objects to delete. It returns
   only bucket/key, never data, and touches nothing else.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-19
"""
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE POLICY exports_update ON medvault.data_exports FOR UPDATE
          USING (requested_by_user_id = medvault.current_user_id())
          WITH CHECK (requested_by_user_id = medvault.current_user_id());

        CREATE OR REPLACE FUNCTION medvault.expire_data_exports()
        RETURNS TABLE (storage_bucket text, object_key text)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = medvault, pg_temp AS $$
        BEGIN
          UPDATE data_exports e
             SET status = 'failed', completed_at = now()
           WHERE e.status IN ('requested', 'processing')
             AND e.created_at < now() - interval '1 hour';

          RETURN QUERY
          UPDATE data_exports e
             SET status = 'expired'
           WHERE e.status = 'ready' AND e.expires_at <= now()
          RETURNING e.storage_bucket, e.object_key;
        END $$;

        REVOKE ALL ON FUNCTION medvault.expire_data_exports() FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION medvault.expire_data_exports() TO app_user;
    """)


def downgrade():
    op.execute("""
        DROP FUNCTION IF EXISTS medvault.expire_data_exports();
        DROP POLICY IF EXISTS exports_update ON medvault.data_exports;
    """)
