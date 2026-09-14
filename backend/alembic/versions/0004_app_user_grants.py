"""app_user grants — least privilege, per table

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-09

Requires the `app_user` role to already exist (created by the bootstrap
script, before this migration ever runs). RLS-protected tables get full
DML because RLS restricts which rows that DML actually touches; tables
without RLS (users, verification_codes, step_up_verifications,
institutions, data_export_requests) get only the operations the
application genuinely performs, nothing more.
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA medvault TO app_user")

    op.execute("""
        GRANT SELECT, INSERT, UPDATE, DELETE ON
            medvault.diagnostics,
            medvault.prescriptions,
            medvault.certificates,
            medvault.other_medical_info,
            medvault.documents,
            medvault.institution_connections,
            medvault.caregiver_links,
            medvault.caregiver_permissions
        TO app_user
    """)

    op.execute("GRANT SELECT, INSERT, UPDATE ON medvault.users TO app_user")
    op.execute("GRANT SELECT, INSERT, UPDATE ON medvault.verification_codes TO app_user")
    op.execute("GRANT SELECT, INSERT, UPDATE ON medvault.step_up_verifications TO app_user")
    op.execute("GRANT SELECT ON medvault.institutions TO app_user")
    op.execute("GRANT SELECT, INSERT, UPDATE ON medvault.data_export_requests TO app_user")

    # append-only, even for app_user
    op.execute("GRANT SELECT, INSERT ON medvault.audit_logs TO app_user")


def downgrade():
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA medvault FROM app_user")
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA medvault FROM app_user")
