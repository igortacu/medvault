"""RLS policies

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-09
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_CUID = "NULLIF(current_setting('app.current_user_id', true), '')::uuid"


def upgrade():
    # ---- diagnostics ----
    op.execute("ALTER TABLE medvault.diagnostics ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE medvault.diagnostics FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY diagnostics_select ON medvault.diagnostics
        FOR SELECT USING (
            patient_id = {_CUID}
            OR EXISTS (
                SELECT 1 FROM medvault.caregiver_links cl
                JOIN medvault.caregiver_permissions cp ON cp.caregiver_link_id = cl.id
                WHERE cl.elder_patient_id = diagnostics.patient_id
                  AND cl.caregiver_user_id = {_CUID}
                  AND cl.status = 'active'
                  AND cp.category = 'diagnostic'
                  AND cp.can_view = TRUE
            )
        )
    """)
    op.execute(f"""
        CREATE POLICY diagnostics_write ON medvault.diagnostics
        FOR ALL USING (patient_id = {_CUID})
        WITH CHECK (patient_id = {_CUID})
    """)

    # ---- prescriptions ----
    op.execute("ALTER TABLE medvault.prescriptions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE medvault.prescriptions FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY prescriptions_select ON medvault.prescriptions
        FOR SELECT USING (
            patient_id = {_CUID}
            OR EXISTS (
                SELECT 1 FROM medvault.caregiver_links cl
                JOIN medvault.caregiver_permissions cp ON cp.caregiver_link_id = cl.id
                WHERE cl.elder_patient_id = prescriptions.patient_id
                  AND cl.caregiver_user_id = {_CUID}
                  AND cl.status = 'active'
                  AND cp.category = 'prescription'
                  AND cp.can_view = TRUE
            )
        )
    """)
    op.execute(f"""
        CREATE POLICY prescriptions_write ON medvault.prescriptions
        FOR ALL USING (patient_id = {_CUID})
        WITH CHECK (patient_id = {_CUID})
    """)

    # ---- certificates (extra visible_to_caregiver check) ----
    op.execute("ALTER TABLE medvault.certificates ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE medvault.certificates FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY certificates_select ON medvault.certificates
        FOR SELECT USING (
            patient_id = {_CUID}
            OR (
                certificates.visible_to_caregiver = TRUE
                AND EXISTS (
                    SELECT 1 FROM medvault.caregiver_links cl
                    JOIN medvault.caregiver_permissions cp ON cp.caregiver_link_id = cl.id
                    WHERE cl.elder_patient_id = certificates.patient_id
                      AND cl.caregiver_user_id = {_CUID}
                      AND cl.status = 'active'
                      AND cp.category = 'certificate'
                      AND cp.can_view = TRUE
                )
            )
        )
    """)
    op.execute(f"""
        CREATE POLICY certificates_write ON medvault.certificates
        FOR ALL USING (patient_id = {_CUID})
        WITH CHECK (patient_id = {_CUID})
    """)

    # ---- other_medical_info (mapped to category = 'other') ----
    op.execute("ALTER TABLE medvault.other_medical_info ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE medvault.other_medical_info FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY other_medical_info_select ON medvault.other_medical_info
        FOR SELECT USING (
            patient_id = {_CUID}
            OR EXISTS (
                SELECT 1 FROM medvault.caregiver_links cl
                JOIN medvault.caregiver_permissions cp ON cp.caregiver_link_id = cl.id
                WHERE cl.elder_patient_id = other_medical_info.patient_id
                  AND cl.caregiver_user_id = {_CUID}
                  AND cl.status = 'active'
                  AND cp.category = 'other'
                  AND cp.can_view = TRUE
            )
        )
    """)
    op.execute(f"""
        CREATE POLICY other_medical_info_write ON medvault.other_medical_info
        FOR ALL USING (patient_id = {_CUID})
        WITH CHECK (patient_id = {_CUID})
    """)

    # ---- documents ----
    op.execute("ALTER TABLE medvault.documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE medvault.documents FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY documents_select ON medvault.documents
        FOR SELECT USING (
            patient_id = {_CUID}
            OR EXISTS (
                SELECT 1 FROM medvault.caregiver_links cl
                JOIN medvault.caregiver_permissions cp ON cp.caregiver_link_id = cl.id
                WHERE cl.elder_patient_id = documents.patient_id
                  AND cl.caregiver_user_id = {_CUID}
                  AND cl.status = 'active'
                  AND cp.category = documents.category
                  AND cp.can_view = TRUE
            )
        )
    """)
    op.execute(f"""
        CREATE POLICY documents_write ON medvault.documents
        FOR ALL USING (patient_id = {_CUID})
        WITH CHECK (patient_id = {_CUID})
    """)

    # ---- institution_connections (owner only) ----
    op.execute("ALTER TABLE medvault.institution_connections ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE medvault.institution_connections FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY institution_connections_owner ON medvault.institution_connections
        FOR ALL USING (patient_id = {_CUID})
        WITH CHECK (patient_id = {_CUID})
    """)

    # ---- caregiver_links ----
    op.execute("ALTER TABLE medvault.caregiver_links ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE medvault.caregiver_links FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY caregiver_links_select ON medvault.caregiver_links
        FOR SELECT USING (
            elder_patient_id = {_CUID}
            OR caregiver_user_id = {_CUID}
        )
    """)
    op.execute(f"""
        CREATE POLICY caregiver_links_insert ON medvault.caregiver_links
        FOR INSERT WITH CHECK (elder_patient_id = {_CUID})
    """)
    op.execute(f"""
        CREATE POLICY caregiver_links_update ON medvault.caregiver_links
        FOR UPDATE USING (elder_patient_id = {_CUID})
        WITH CHECK (elder_patient_id = {_CUID})
    """)
    op.execute(f"""
        CREATE POLICY caregiver_links_delete ON medvault.caregiver_links
        FOR DELETE USING (elder_patient_id = {_CUID})
    """)

    # ---- caregiver_permissions ----
    op.execute("ALTER TABLE medvault.caregiver_permissions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE medvault.caregiver_permissions FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY caregiver_permissions_select ON medvault.caregiver_permissions
        FOR SELECT USING (
            EXISTS (
                SELECT 1 FROM medvault.caregiver_links cl
                WHERE cl.id = caregiver_permissions.caregiver_link_id
                  AND (cl.elder_patient_id = {_CUID} OR cl.caregiver_user_id = {_CUID})
            )
        )
    """)
    op.execute(f"""
        CREATE POLICY caregiver_permissions_write ON medvault.caregiver_permissions
        FOR ALL USING (
            EXISTS (
                SELECT 1 FROM medvault.caregiver_links cl
                WHERE cl.id = caregiver_permissions.caregiver_link_id
                  AND cl.elder_patient_id = {_CUID}
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM medvault.caregiver_links cl
                WHERE cl.id = caregiver_permissions.caregiver_link_id
                  AND cl.elder_patient_id = {_CUID}
            )
        )
    """)

    # NOTE: users, verification_codes, step_up_verifications, institutions,
    # data_export_requests, audit_logs intentionally have no RLS here — see
    # the grants in 0004 for how their access is scoped instead.


def downgrade():
    tables_and_policies = [
        ("caregiver_permissions", ["caregiver_permissions_select", "caregiver_permissions_write"]),
        ("caregiver_links", ["caregiver_links_select", "caregiver_links_insert",
                              "caregiver_links_update", "caregiver_links_delete"]),
        ("institution_connections", ["institution_connections_owner"]),
        ("documents", ["documents_select", "documents_write"]),
        ("other_medical_info", ["other_medical_info_select", "other_medical_info_write"]),
        ("certificates", ["certificates_select", "certificates_write"]),
        ("prescriptions", ["prescriptions_select", "prescriptions_write"]),
        ("diagnostics", ["diagnostics_select", "diagnostics_write"]),
    ]
    for table, policies in tables_and_policies:
        for policy in policies:
            op.execute(f"DROP POLICY IF EXISTS {policy} ON medvault.{table}")
        op.execute(f"ALTER TABLE medvault.{table} DISABLE ROW LEVEL SECURITY")
