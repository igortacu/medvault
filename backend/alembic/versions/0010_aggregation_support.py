"""live aggregation support — connection lookup for caregivers, per-resource scopes

1. caregiver_visible_connections(p_patient, p_category) — SECURITY DEFINER. Institution
   connections are patient-only under RLS (they hold the OAuth tokens), but a caregiver
   with 'view' on a category must still see the institutional records in it. This
   narrow function returns the *active* connections of the patient, and only when the
   caller is that patient or a caregiver with 'view' on the category. It never writes;
   token refresh therefore only happens on the patient's own requests.

2. supported_scopes now lists a read scope per FHIR resource type the aggregation layer
   requests. Existing connections keep their old granted scopes until reconnected.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-13
"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

RESOURCE_TYPES = (
    "Condition",
    "DocumentReference",
    "MedicationRequest",
    "MedicationStatement",
    "CarePlan",
    "Procedure",
    "DiagnosticReport",
    "ImagingStudy",
    "Encounter",
    "Immunization",
)


def upgrade():
    op.execute("""
        CREATE FUNCTION medvault.caregiver_visible_connections(
          p_patient  uuid,
          p_category medvault.data_category
        ) RETURNS TABLE (
          id                       uuid,
          institution_id           uuid,
          fhir_patient_ref         text,
          granted_scopes           text[],
          access_token_ciphertext  bytea,
          access_token_expires_at  timestamptz,
          refresh_token_ciphertext bytea
        )
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = medvault, pg_temp AS $$
          SELECT c.id, c.institution_id, c.fhir_patient_ref, c.granted_scopes,
                 c.access_token_ciphertext, c.access_token_expires_at,
                 c.refresh_token_ciphertext
          FROM institution_connections c
          WHERE c.patient_user_id = p_patient
            AND c.status = 'active'
            AND (p_patient = current_user_id()
                 OR caregiver_can(p_patient, p_category, 'view'))
        $$;
    """)
    # Returns token ciphertext: nobody but the app role may call it.
    op.execute(
        "REVOKE EXECUTE ON FUNCTION "
        "medvault.caregiver_visible_connections(uuid, medvault.data_category) FROM PUBLIC;"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION "
        "medvault.caregiver_visible_connections(uuid, medvault.data_category) TO app_user;"
    )
    scopes = ", ".join(f"'patient/{t}.read'" for t in RESOURCE_TYPES)
    op.execute(f"""
        UPDATE medvault.institutions
        SET supported_scopes = ARRAY[
          'patient/Patient.read', 'patient/Observation.read', {scopes},
          'offline_access', 'openid', 'fhirUser'
        ];
    """)


def downgrade():
    op.execute("""
        UPDATE medvault.institutions
        SET supported_scopes = ARRAY[
          'patient/Patient.read', 'patient/Observation.read',
          'offline_access', 'openid', 'fhirUser'
        ];
        DROP FUNCTION IF EXISTS
          medvault.caregiver_visible_connections(uuid, medvault.data_category);
    """)
