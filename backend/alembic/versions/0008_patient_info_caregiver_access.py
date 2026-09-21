"""patient info — caregiver read of basics + caregiver measurement writes

Two additions needed for the Patient's info endpoints:

1. patient_basics(p_patient) — a SECURITY DEFINER function returning ONLY
   first_name/last_name/date_of_birth, and only when the caller is the patient or
   a caregiver with 'patient_info' view. users itself stays self-only under RLS
   (its rows hold phone and password hash), so this narrow function is how a
   permitted caregiver sees the patient's name and DOB without exposing the row.

2. profiles_caregiver_insert / profiles_caregiver_update — RLS policies letting a
   caregiver with can_upload on patient_info record or correct the single current
   weight/height (the shipped schema only had owner writes + caregiver read).

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-21
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE FUNCTION medvault.patient_basics(p_patient uuid)
        RETURNS TABLE (
          first_name    varchar,
          last_name     varchar,
          date_of_birth date
        )
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = medvault, pg_temp AS $$
          SELECT u.first_name, u.last_name, u.date_of_birth
          FROM users u
          WHERE u.id = p_patient
            AND (p_patient = current_user_id()
                 OR caregiver_can(p_patient, 'patient_info', 'view'))
        $$;
    """)

    op.execute("""
        GRANT EXECUTE ON FUNCTION medvault.patient_basics(uuid) TO app_user;
    """)

    op.execute("""
        -- A caregiver with can_upload on patient_info may create the profile row
        -- for a patient who has none yet.
        CREATE POLICY profiles_caregiver_insert ON medvault.patient_profiles FOR INSERT
          WITH CHECK (medvault.caregiver_can(user_id, 'patient_info', 'upload'));

        -- ...and update/correct the existing single current measurement.
        CREATE POLICY profiles_caregiver_update ON medvault.patient_profiles FOR UPDATE
          USING (medvault.caregiver_can(user_id, 'patient_info', 'upload'))
          WITH CHECK (medvault.caregiver_can(user_id, 'patient_info', 'upload'));
    """)


def downgrade():
    op.execute("DROP POLICY IF EXISTS profiles_caregiver_update ON medvault.patient_profiles;")
    op.execute("DROP POLICY IF EXISTS profiles_caregiver_insert ON medvault.patient_profiles;")
    op.execute("DROP FUNCTION IF EXISTS medvault.patient_basics(uuid);")
