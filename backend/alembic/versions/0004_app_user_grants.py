"""app_user table grants

The migrator role owns every object; app_user (NOSUPERUSER, NOBYPASSRLS) is the
role the API connects as, so it needs explicit DML privileges. RLS still
constrains every statement to the caller's own rows. institutions is reference
data: app_user reads it, only migrator writes it. audit_logs grants and the
REVOKE that makes it append-only live in migration 0006.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-17
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

# User-data tables the API reads and writes (all under RLS).
_DML_TABLES = (
    "users",
    "patient_profiles",
    "institution_connections",
    "caregiver_links",
    "caregiver_permissions",
    "documents",
    "data_exports",
)


def upgrade():
    for table in _DML_TABLES:
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON medvault.{table} TO app_user;"
        )

    # Reference data: readable by any authenticated user, writable only by migrator.
    op.execute("GRANT SELECT ON medvault.institutions TO app_user;")


def downgrade():
    op.execute("REVOKE SELECT ON medvault.institutions FROM app_user;")
    for table in _DML_TABLES:
        op.execute(
            f"REVOKE SELECT, INSERT, UPDATE, DELETE ON medvault.{table} FROM app_user;"
        )
