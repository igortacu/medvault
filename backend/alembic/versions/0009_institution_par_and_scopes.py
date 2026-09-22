"""add PAR endpoint and replace wildcard institution scopes

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-21
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE medvault.institutions ADD COLUMN par_url text;")
    op.execute("""
        UPDATE medvault.institutions
        SET par_url = 'https://fhir-mock.medvault.md/' || external_id || '/oauth/par',
            supported_scopes = ARRAY[
              'patient/Patient.read',
              'patient/Observation.read',
              'offline_access',
              'openid',
              'fhirUser'
            ];
        ALTER TABLE medvault.institutions ALTER COLUMN par_url SET NOT NULL;
    """)


def downgrade():
    op.execute("""
        UPDATE medvault.institutions
        SET supported_scopes = ARRAY[
          'launch/patient', 'patient/*.read', 'offline_access', 'openid', 'fhirUser'
        ];
        ALTER TABLE medvault.institutions DROP COLUMN par_url;
    """)
