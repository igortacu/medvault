"""seed the institution catalogue with Moldovan public and private institutions

The "Add institution" button offers type='private' rows; type='public' rows are
offered automatically after IDNP entry. FHIR/OAuth URLs point at the mock API
host, keyed by external_id. The OAuth client secret is a clearly-labelled dev
placeholder (key version 0) — replace it with a real encrypted secret before
pointing a connection at anything but the mock. Idempotent via ON CONFLICT.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-17
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# (external_id, display name, type, city)
_INSTITUTIONS = (
    # Public — IMSP (Instituție Medico-Sanitară Publică), offered automatically.
    ("imsp-scr-t-mosneaga", "Spitalul Clinic Republican „Timofei Moșneaga”", "public", "Chișinău"),
    ("imsp-institutul-mamei-copilului", "IMSP Institutul Mamei și Copilului", "public", "Chișinău"),
    ("imsp-scm-sfanta-treime", "Spitalul Clinic Municipal „Sfânta Treime”", "public", "Chișinău"),
    ("imsp-institutul-oncologic", "IMSP Institutul Oncologic", "public", "Chișinău"),
    ("imsp-institutul-cardiologie", "IMSP Institutul de Cardiologie", "public", "Chișinău"),
    ("imsp-scm-balti", "Spitalul Clinic Municipal Bălți", "public", "Bălți"),
    # Private — reachable only through "Add institution".
    ("medpark", "Spitalul Internațional Medpark", "private", "Chișinău"),
    ("terramed", "Clinica Terramed", "private", "Chișinău"),
    ("excellence", "Clinica Excellence", "private", "Chișinău"),
    ("repromed", "Centrul Medical Repromed", "private", "Chișinău"),
)

_EXTERNAL_IDS = tuple(row[0] for row in _INSTITUTIONS)


def upgrade():
    values = ",\n          ".join(
        "(" + ", ".join(_q(x) for x in row) + ")"
        for row in _INSTITUTIONS
    )
    op.execute(f"""
        INSERT INTO medvault.institutions
          (external_id, name, type, city,
           fhir_base_url, authorize_url, token_url, revoke_url,
           oauth_client_id, oauth_client_secret_ciphertext, oauth_secret_key_version,
           supported_scopes)
        SELECT
          v.external_id,
          v.name,
          v.type::medvault.institution_type,
          v.city,
          'https://fhir-mock.medvault.md/' || v.external_id || '/fhir',
          'https://fhir-mock.medvault.md/' || v.external_id || '/oauth/authorize',
          'https://fhir-mock.medvault.md/' || v.external_id || '/oauth/token',
          'https://fhir-mock.medvault.md/' || v.external_id || '/oauth/revoke',
          'medvault-' || v.external_id,
          convert_to('DEV_PLACEHOLDER_SECRET_REPLACE_BEFORE_PROD', 'UTF8'),
          0,
          ARRAY['launch/patient', 'patient/*.read', 'offline_access', 'openid', 'fhirUser']
        FROM (VALUES
          {values}
        ) AS v(external_id, name, type, city)
        ON CONFLICT (external_id) DO NOTHING;
    """)


def downgrade():
    ids = ", ".join(_q(x) for x in _EXTERNAL_IDS)
    op.execute(f"DELETE FROM medvault.institutions WHERE external_id IN ({ids});")


def _q(value: str) -> str:
    """Single-quote and SQL-escape a string literal for inline op.execute."""
    return "'" + value.replace("'", "''") + "'"
