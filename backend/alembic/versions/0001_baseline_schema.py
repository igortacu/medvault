"""baseline schema — enums and tables in medvault

Hand-written raw SQL (op.execute) that mirrors MedVault-App-Database-Schema.md.
RLS, helper functions, triggers, grants and pre-auth SECURITY DEFINER functions
live in the follow-up migrations (0002-0006); institution seed data in 0007.

Revision ID: 0001
Revises:
Create Date: 2026-09-17
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------------
    # 1. Shared enums (schema section 1)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TYPE medvault.data_category AS ENUM (
          'diagnoses', 'certificates', 'analyses',
          'prescriptions', 'patient_info', 'other_med_info'
        );

        CREATE TYPE medvault.document_type AS ENUM (
          'medical_history', 'surgical_history', 'family_history', 'progress_note',
          'diagnosis_record', 'medical_examination_report', 'consultation_report',
          'disability_certificate', 'illness_certificate', 'fitness_certificate',
          'vaccination_certificate', 'birth_certificate', 'hospitalization_certificate',
          'medical_examination_certificate', 'pregnancy_certificate', 'health_certificate',
          'blood_test', 'urinalysis', 'biochemistry_report', 'hormone_test',
          'microbiology_report', 'pathology_report', 'xray_report', 'ultrasound_report',
          'ct_report', 'mri_report', 'ecg_report', 'endoscopy_report',
          'radiology_images', 'operative_report',
          'prescription', 'medication_record', 'treatment_plan', 'procedure_record',
          'hospitalization_record', 'discharge_summary', 'pregnancy_record',
          'allergy_record', 'immunization_record', 'referral'
        );

        CREATE TYPE medvault.user_status AS ENUM (
          'pending_verification', 'active', 'locked', 'disabled'
        );

        CREATE TYPE medvault.institution_type AS ENUM ('public', 'private');

        CREATE TYPE medvault.connection_origin AS ENUM ('auto_public', 'user_added');

        CREATE TYPE medvault.connection_status AS ENUM (
          'pending_consent', 'authorizing', 'active',
          'no_match', 'revoked', 'expired', 'error'
        );

        CREATE TYPE medvault.caregiver_link_status AS ENUM (
          'pending', 'active', 'rejected', 'revoked'
        );

        CREATE TYPE medvault.document_status AS ENUM ('stored', 'rejected');

        CREATE TYPE medvault.extraction_status AS ENUM (
          'not_requested', 'pending', 'awaiting_review', 'confirmed', 'rejected'
        );

        CREATE TYPE medvault.export_format AS ENUM ('pdf', 'json');

        CREATE TYPE medvault.export_status AS ENUM (
          'requested', 'processing', 'ready', 'failed', 'expired'
        );
    """)

    # ------------------------------------------------------------------
    # 2. Identity and authentication (schema sections 2.1, 2.2)
    # ------------------------------------------------------------------
    op.execute(r"""
        CREATE TABLE medvault.users (
          id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          first_name            varchar(50)  NOT NULL,
          last_name             varchar(50)  NOT NULL,
          phone_e164            varchar(12)  NOT NULL,
          date_of_birth         date         NOT NULL,
          password_hash         text         NOT NULL,
          status                medvault.user_status NOT NULL DEFAULT 'pending_verification',
          phone_verified_at     timestamptz,
          password_changed_at   timestamptz  NOT NULL DEFAULT now(),
          created_at            timestamptz  NOT NULL DEFAULT now(),
          updated_at            timestamptz  NOT NULL DEFAULT now(),

          CONSTRAINT users_phone_unique UNIQUE (phone_e164),
          CONSTRAINT users_phone_format CHECK (phone_e164 ~ '^\+373[0-9]{8}$'),
          CONSTRAINT users_first_name_len CHECK (char_length(first_name) BETWEEN 2 AND 50),
          CONSTRAINT users_last_name_len  CHECK (char_length(last_name)  BETWEEN 2 AND 50),
          CONSTRAINT users_dob_range CHECK (date_of_birth <= current_date
                                            AND date_of_birth >= current_date - interval '120 years'),
          CONSTRAINT users_verified_consistency CHECK (status = 'pending_verification' OR phone_verified_at IS NOT NULL)
        );

        CREATE TABLE medvault.patient_profiles (
          user_id                 uuid PRIMARY KEY REFERENCES medvault.users(id) ON DELETE CASCADE,
          weight_kg               numeric(5,2) CHECK (weight_kg > 0 AND weight_kg < 500),
          height_cm               numeric(5,1) CHECK (height_cm > 0 AND height_cm < 300),
          measurements_updated_at timestamptz,
          created_at              timestamptz NOT NULL DEFAULT now(),
          updated_at              timestamptz NOT NULL DEFAULT now()
        );
    """)

    # ------------------------------------------------------------------
    # 3. Institutions and connections (schema sections 3.1, 3.2)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE medvault.institutions (
          id                             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          external_id                    text NOT NULL UNIQUE,
          name                           text NOT NULL,
          type                           medvault.institution_type NOT NULL,
          city                           text,
          fhir_base_url                  text NOT NULL,
          authorize_url                  text NOT NULL,
          token_url                      text NOT NULL,
          revoke_url                     text NOT NULL,
          oauth_client_id                text NOT NULL,
          oauth_client_secret_ciphertext bytea NOT NULL,
          oauth_secret_key_version       smallint NOT NULL,
          supported_scopes               text[] NOT NULL,
          is_active                      boolean NOT NULL DEFAULT true,
          created_at                     timestamptz NOT NULL DEFAULT now(),
          updated_at                     timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE medvault.institution_connections (
          id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          patient_user_id           uuid NOT NULL REFERENCES medvault.users(id) ON DELETE CASCADE,
          institution_id            uuid NOT NULL REFERENCES medvault.institutions(id),
          origin                    medvault.connection_origin NOT NULL,
          status                    medvault.connection_status NOT NULL DEFAULT 'pending_consent',
          consent_text_version      text,
          consented_at              timestamptz,
          requested_scopes          text[] NOT NULL,
          granted_scopes            text[],
          fhir_patient_ref          text,
          access_token_ciphertext   bytea,
          access_token_expires_at   timestamptz,
          refresh_token_ciphertext  bytea,
          token_key_version         smallint,
          connected_at              timestamptz,
          last_fetched_at           timestamptz,
          revoked_at                timestamptz,
          revoked_by_user_id        uuid REFERENCES medvault.users(id),
          failure_reason            text,
          created_at                timestamptz NOT NULL DEFAULT now(),
          updated_at                timestamptz NOT NULL DEFAULT now(),

          CONSTRAINT conn_consent_before_active CHECK (
            status NOT IN ('authorizing', 'active') OR consented_at IS NOT NULL
          ),
          CONSTRAINT conn_active_has_token CHECK (
            status <> 'active' OR (access_token_ciphertext IS NOT NULL AND connected_at IS NOT NULL)
          ),
          CONSTRAINT conn_revoked_consistency CHECK (
            (status = 'revoked') = (revoked_at IS NOT NULL)
          ),
          CONSTRAINT conn_revoked_wipes_tokens CHECK (
            status <> 'revoked' OR (access_token_ciphertext IS NULL AND refresh_token_ciphertext IS NULL)
          )
        );

        CREATE UNIQUE INDEX institution_connections_one_live
          ON medvault.institution_connections (patient_user_id, institution_id)
          WHERE status IN ('pending_consent', 'authorizing', 'active');

        CREATE INDEX institution_connections_patient
          ON medvault.institution_connections (patient_user_id, status);
    """)

    # ------------------------------------------------------------------
    # 4. Caregiver access (schema sections 4.1, 4.2)
    # ------------------------------------------------------------------
    op.execute(r"""
        CREATE TABLE medvault.caregiver_links (
          id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          patient_user_id         uuid NOT NULL REFERENCES medvault.users(id) ON DELETE CASCADE,
          caregiver_user_id       uuid REFERENCES medvault.users(id) ON DELETE CASCADE,
          invited_first_name      varchar(50) NOT NULL,
          invited_last_name       varchar(50) NOT NULL,
          invited_phone_e164      varchar(12) NOT NULL CHECK (invited_phone_e164 ~ '^\+373[0-9]{8}$'),
          status                  medvault.caregiver_link_status NOT NULL DEFAULT 'pending',
          invited_at              timestamptz NOT NULL DEFAULT now(),
          responded_at            timestamptz,
          revoked_at              timestamptz,
          revoked_by_user_id      uuid REFERENCES medvault.users(id),

          CONSTRAINT link_not_self CHECK (caregiver_user_id IS NULL OR caregiver_user_id <> patient_user_id),
          CONSTRAINT link_active_has_user CHECK (status <> 'active' OR caregiver_user_id IS NOT NULL),
          CONSTRAINT link_revoked_consistency CHECK ((status = 'revoked') = (revoked_at IS NOT NULL))
        );

        CREATE UNIQUE INDEX caregiver_links_one_live_invite
          ON medvault.caregiver_links (patient_user_id, invited_phone_e164)
          WHERE status IN ('pending', 'active');

        CREATE UNIQUE INDEX caregiver_links_one_live_pair
          ON medvault.caregiver_links (patient_user_id, caregiver_user_id)
          WHERE status IN ('pending', 'active') AND caregiver_user_id IS NOT NULL;

        CREATE INDEX caregiver_links_patient   ON medvault.caregiver_links (patient_user_id, status);
        CREATE INDEX caregiver_links_caregiver ON medvault.caregiver_links (caregiver_user_id, status);

        CREATE TABLE medvault.caregiver_permissions (
          link_id           uuid NOT NULL REFERENCES medvault.caregiver_links(id) ON DELETE CASCADE,
          category          medvault.data_category NOT NULL,
          can_view          boolean NOT NULL DEFAULT false,
          can_view_original boolean NOT NULL DEFAULT false,
          can_export        boolean NOT NULL DEFAULT false,
          can_upload        boolean NOT NULL DEFAULT false,
          granted_at        timestamptz NOT NULL DEFAULT now(),
          updated_at        timestamptz NOT NULL DEFAULT now(),

          PRIMARY KEY (link_id, category),
          CONSTRAINT perm_actions_imply_view CHECK (
            can_view OR NOT (can_view_original OR can_export OR can_upload)
          )
        );
    """)

    # ------------------------------------------------------------------
    # 5. Self-uploaded documents (schema section 5.2)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE medvault.documents (
          id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          patient_user_id         uuid NOT NULL REFERENCES medvault.users(id) ON DELETE CASCADE,
          uploaded_by_user_id     uuid NOT NULL REFERENCES medvault.users(id),
          category                medvault.data_category NOT NULL CHECK (category <> 'patient_info'),
          document_type           medvault.document_type NOT NULL,
          title_ciphertext        bytea NOT NULL,
          notes_ciphertext        bytea,
          metadata_key_version    smallint NOT NULL,
          document_date           date,
          specialty               text,
          issuer_name             text,
          practitioner_name       text,
          storage_bucket          text NOT NULL,
          object_key              text NOT NULL,
          original_filename_ciphertext bytea,
          mime_type               text NOT NULL,
          size_bytes              bigint NOT NULL,
          sha256                  bytea NOT NULL,
          status                  medvault.document_status NOT NULL DEFAULT 'stored',
          extraction_status       medvault.extraction_status NOT NULL DEFAULT 'not_requested',
          created_at              timestamptz NOT NULL DEFAULT now(),
          updated_at              timestamptz NOT NULL DEFAULT now(),

          CONSTRAINT documents_type_matches_category CHECK (
            (document_type IN ('medical_history', 'surgical_history', 'family_history', 'progress_note',
                        'diagnosis_record', 'medical_examination_report', 'consultation_report')
              AND category = 'diagnoses')
            OR
            (document_type IN ('disability_certificate', 'illness_certificate', 'fitness_certificate',
                         'vaccination_certificate', 'birth_certificate', 'hospitalization_certificate',
                         'medical_examination_certificate', 'pregnancy_certificate', 'health_certificate')
              AND category = 'certificates')
            OR
            (document_type IN ('blood_test', 'urinalysis', 'biochemistry_report', 'hormone_test',
                         'microbiology_report', 'pathology_report', 'xray_report', 'ultrasound_report',
                         'ct_report', 'mri_report', 'ecg_report', 'endoscopy_report',
                         'radiology_images', 'operative_report')
              AND category = 'analyses')
            OR
            (document_type IN ('prescription', 'medication_record', 'treatment_plan', 'procedure_record')
              AND category = 'prescriptions')
            OR
            (document_type IN ('hospitalization_record', 'discharge_summary', 'pregnancy_record',
                         'allergy_record', 'immunization_record', 'referral')
              AND category = 'other_med_info')
          ),
          CONSTRAINT documents_object_key_unique UNIQUE (storage_bucket, object_key),
          CONSTRAINT documents_mime_allowed CHECK (mime_type IN ('application/pdf', 'image/jpeg', 'image/png')),
          CONSTRAINT documents_size_range CHECK (size_bytes > 0 AND size_bytes <= 10485760),
          CONSTRAINT documents_sha256_len CHECK (octet_length(sha256) = 32),
          CONSTRAINT documents_date_not_future CHECK (document_date IS NULL OR document_date <= current_date)
        );

        CREATE INDEX documents_patient_category_date
          ON medvault.documents (patient_user_id, category, document_date DESC);

        CREATE INDEX documents_patient_specialty
          ON medvault.documents (patient_user_id, specialty) WHERE specialty IS NOT NULL;
    """)

    # ------------------------------------------------------------------
    # 6. Data export (schema section 6)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE medvault.data_exports (
          id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          patient_user_id       uuid NOT NULL REFERENCES medvault.users(id) ON DELETE CASCADE,
          requested_by_user_id  uuid NOT NULL REFERENCES medvault.users(id),
          format                medvault.export_format NOT NULL,
          categories            medvault.data_category[] NOT NULL,
          scope_ref             text,
          status                medvault.export_status NOT NULL DEFAULT 'requested',
          storage_bucket        text,
          object_key            text,
          expires_at            timestamptz,
          created_at            timestamptz NOT NULL DEFAULT now(),
          completed_at          timestamptz,

          CONSTRAINT export_ready_has_file CHECK (
            status <> 'ready' OR (object_key IS NOT NULL AND expires_at IS NOT NULL)
          )
        );
    """)

    # ------------------------------------------------------------------
    # 7. Audit log (schema section 7) — table + indexes only.
    #    Append-only trigger, REVOKEs and RLS live in migration 0006.
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE medvault.audit_logs (
          id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
          occurred_at         timestamptz NOT NULL DEFAULT now(),
          request_id          uuid,
          actor_user_id       uuid,
          subject_patient_id  uuid,
          action              text NOT NULL,
          resource_type       text,
          resource_id         text,
          institution_id      uuid,
          outcome             text NOT NULL CHECK (outcome IN ('success', 'denied', 'failure')),
          ip_hash             bytea,
          metadata            jsonb NOT NULL DEFAULT '{}'::jsonb
        );

        CREATE INDEX audit_logs_subject_time ON medvault.audit_logs (subject_patient_id, occurred_at DESC);
        CREATE INDEX audit_logs_actor_time   ON medvault.audit_logs (actor_user_id, occurred_at DESC);
    """)


def downgrade():
    op.execute("""
        DROP TABLE IF EXISTS medvault.audit_logs;
        DROP TABLE IF EXISTS medvault.data_exports;
        DROP TABLE IF EXISTS medvault.documents;
        DROP TABLE IF EXISTS medvault.caregiver_permissions;
        DROP TABLE IF EXISTS medvault.caregiver_links;
        DROP TABLE IF EXISTS medvault.institution_connections;
        DROP TABLE IF EXISTS medvault.institutions;
        DROP TABLE IF EXISTS medvault.patient_profiles;
        DROP TABLE IF EXISTS medvault.users;
    """)
    op.execute("""
        DROP TYPE IF EXISTS medvault.export_status;
        DROP TYPE IF EXISTS medvault.export_format;
        DROP TYPE IF EXISTS medvault.extraction_status;
        DROP TYPE IF EXISTS medvault.document_status;
        DROP TYPE IF EXISTS medvault.caregiver_link_status;
        DROP TYPE IF EXISTS medvault.connection_status;
        DROP TYPE IF EXISTS medvault.connection_origin;
        DROP TYPE IF EXISTS medvault.institution_type;
        DROP TYPE IF EXISTS medvault.user_status;
        DROP TYPE IF EXISTS medvault.document_type;
        DROP TYPE IF EXISTS medvault.data_category;
    """)
