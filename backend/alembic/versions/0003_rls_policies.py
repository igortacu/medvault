"""row-level security — enable, force and policies (schema section 8.3)

Covers every table that holds user data except audit_logs, whose RLS and
append-only enforcement live in migration 0006. institutions has no RLS: it is
reference data readable by any authenticated user and writable only by migrator
(grants in 0004).

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-17
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Tables that get RLS enabled AND forced (even the owner is subject to policies).
_RLS_TABLES = (
    "users",
    "patient_profiles",
    "institution_connections",
    "caregiver_links",
    "caregiver_permissions",
    "documents",
    "data_exports",
)


def upgrade():
    for table in _RLS_TABLES:
        op.execute(f"ALTER TABLE medvault.{table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE medvault.{table} FORCE ROW LEVEL SECURITY;")

    op.execute("""
        -- users: a user can read and edit only their own account row.
        CREATE POLICY users_self ON medvault.users
          USING (id = medvault.current_user_id())
          WITH CHECK (id = medvault.current_user_id());

        -- patient_profiles: the owner has full access to their own measurements.
        CREATE POLICY profiles_owner ON medvault.patient_profiles
          USING (user_id = medvault.current_user_id())
          WITH CHECK (user_id = medvault.current_user_id());

        -- patient_profiles: a caregiver granted 'patient_info' view may read (not edit).
        CREATE POLICY profiles_caregiver_read ON medvault.patient_profiles FOR SELECT
          USING (medvault.caregiver_can(user_id, 'patient_info', 'view'));

        -- institution_connections: patient only, all operations. No caregiver policy (FR8).
        CREATE POLICY connections_owner ON medvault.institution_connections
          USING (patient_user_id = medvault.current_user_id())
          WITH CHECK (patient_user_id = medvault.current_user_id());

        -- caregiver_links: the patient creates, lists and revokes their own links.
        CREATE POLICY links_patient ON medvault.caregiver_links
          USING (patient_user_id = medvault.current_user_id())
          WITH CHECK (patient_user_id = medvault.current_user_id());

        -- caregiver_links: a caregiver may read links where they are the caregiver (read-only;
        -- accept/reject go through SECURITY DEFINER functions in 0005).
        CREATE POLICY links_caregiver_read ON medvault.caregiver_links FOR SELECT
          USING (caregiver_user_id = medvault.current_user_id());

        -- caregiver_permissions: only the patient who owns the link may grant/change/remove.
        CREATE POLICY perms_patient ON medvault.caregiver_permissions
          USING (EXISTS (SELECT 1 FROM medvault.caregiver_links l
                         WHERE l.id = link_id AND l.patient_user_id = medvault.current_user_id()))
          WITH CHECK (EXISTS (SELECT 1 FROM medvault.caregiver_links l
                         WHERE l.id = link_id AND l.patient_user_id = medvault.current_user_id()));

        -- caregiver_permissions: a caregiver may read their own permissions on active links.
        CREATE POLICY perms_caregiver_read ON medvault.caregiver_permissions FOR SELECT
          USING (EXISTS (SELECT 1 FROM medvault.caregiver_links l
                         WHERE l.id = link_id AND l.caregiver_user_id = medvault.current_user_id()
                           AND l.status = 'active'));

        -- documents: visible to the owner or a caregiver with 'view' on the category.
        CREATE POLICY documents_select ON medvault.documents FOR SELECT
          USING (patient_user_id = medvault.current_user_id()
                 OR medvault.caregiver_can(patient_user_id, category, 'view'));

        -- documents: insert into own vault, or a patient's vault with 'upload'; uploader must be caller.
        CREATE POLICY documents_insert ON medvault.documents FOR INSERT
          WITH CHECK (uploaded_by_user_id = medvault.current_user_id()
                      AND (patient_user_id = medvault.current_user_id()
                           OR medvault.caregiver_can(patient_user_id, category, 'upload')));

        -- documents: only the owner may edit metadata / re-categorise.
        CREATE POLICY documents_update_owner ON medvault.documents FOR UPDATE
          USING (patient_user_id = medvault.current_user_id())
          WITH CHECK (patient_user_id = medvault.current_user_id());

        -- documents: only the owner may delete (FR8).
        CREATE POLICY documents_delete_owner ON medvault.documents FOR DELETE
          USING (patient_user_id = medvault.current_user_id());

        -- data_exports: the patient sees all exports of their data; a requester sees their own.
        CREATE POLICY exports_select ON medvault.data_exports FOR SELECT
          USING (patient_user_id = medvault.current_user_id()
                 OR requested_by_user_id = medvault.current_user_id());

        -- data_exports: patient may export anything of theirs; a caregiver only if they hold
        -- 'export' on EVERY requested category.
        CREATE POLICY exports_insert ON medvault.data_exports FOR INSERT
          WITH CHECK (requested_by_user_id = medvault.current_user_id()
                      AND (patient_user_id = medvault.current_user_id()
                           OR NOT EXISTS (SELECT 1 FROM unnest(categories) c
                                          WHERE NOT medvault.caregiver_can(patient_user_id, c, 'export'))));
    """)


def downgrade():
    op.execute("""
        DROP POLICY IF EXISTS exports_insert ON medvault.data_exports;
        DROP POLICY IF EXISTS exports_select ON medvault.data_exports;
        DROP POLICY IF EXISTS documents_delete_owner ON medvault.documents;
        DROP POLICY IF EXISTS documents_update_owner ON medvault.documents;
        DROP POLICY IF EXISTS documents_insert ON medvault.documents;
        DROP POLICY IF EXISTS documents_select ON medvault.documents;
        DROP POLICY IF EXISTS perms_caregiver_read ON medvault.caregiver_permissions;
        DROP POLICY IF EXISTS perms_patient ON medvault.caregiver_permissions;
        DROP POLICY IF EXISTS links_caregiver_read ON medvault.caregiver_links;
        DROP POLICY IF EXISTS links_patient ON medvault.caregiver_links;
        DROP POLICY IF EXISTS connections_owner ON medvault.institution_connections;
        DROP POLICY IF EXISTS profiles_caregiver_read ON medvault.patient_profiles;
        DROP POLICY IF EXISTS profiles_owner ON medvault.patient_profiles;
        DROP POLICY IF EXISTS users_self ON medvault.users;
    """)
    for table in _RLS_TABLES:
        op.execute(f"ALTER TABLE medvault.{table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE medvault.{table} DISABLE ROW LEVEL SECURITY;")
