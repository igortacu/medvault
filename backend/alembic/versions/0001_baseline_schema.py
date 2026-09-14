"""baseline schema — enums and tables in medvault

Revision ID: 0001
Revises:
Create Date: 2026-09-09
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TYPE medvault.document_category    AS ENUM ('diagnostic', 'prescription', 'certificate', 'other');
        CREATE TYPE medvault.document_source       AS ENUM ('self_upload', 'institution');
        CREATE TYPE medvault.document_status       AS ENUM ('processing', 'available', 'rejected', 'deleted');
        CREATE TYPE medvault.verification_purpose  AS ENUM ('signup', 'login_mfa', 'password_reset');
        CREATE TYPE medvault.connection_status     AS ENUM ('pending', 'active', 'revoked', 'failed');
        CREATE TYPE medvault.caregiver_link_status AS ENUM ('pending', 'active', 'revoked');
        CREATE TYPE medvault.prescription_status   AS ENUM ('current', 'previous');
        CREATE TYPE medvault.export_status         AS ENUM ('pending', 'ready', 'failed');
        CREATE TYPE medvault.export_format         AS ENUM ('pdf', 'json');
        CREATE TYPE medvault.step_up_factor        AS ENUM ('idnp', 'password');
    """)

    # ------------------------------------------------------------------
    # 1. AUTHENTICATION & AUTHORIZATION
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE medvault.users (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            first_name          VARCHAR(50)  NOT NULL,
            last_name           VARCHAR(50)  NOT NULL,
            phone_number        VARCHAR(16)  NOT NULL UNIQUE,
            date_of_birth       DATE         NOT NULL,
            password_hash       TEXT         NOT NULL,

            idnp_encrypted      BYTEA,
            idnp_last4          VARCHAR(4),
            idnp_hash           TEXT,

            is_phone_verified   BOOLEAN NOT NULL DEFAULT FALSE,
            mfa_enabled         BOOLEAN NOT NULL DEFAULT FALSE,
            account_status      VARCHAR(20) NOT NULL DEFAULT 'pending_verification',
            failed_login_count  INT NOT NULL DEFAULT 0,
            locked_until        TIMESTAMPTZ,

            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT chk_users_first_name_letters
                CHECK (first_name ~ '^[A-Za-zĂÂÎȘȚăâîșț]{2,50}$'),
            CONSTRAINT chk_users_last_name_letters
                CHECK (last_name ~ '^[A-Za-zĂÂÎȘȚăâîșț]{2,50}$'),
            CONSTRAINT chk_users_phone_format
                CHECK (phone_number ~ '^\\+373[0-9]{8}$'),
            CONSTRAINT chk_users_dob_range
                CHECK (date_of_birth <= CURRENT_DATE
                       AND date_of_birth >= CURRENT_DATE - INTERVAL '120 years')
        );
    """)

    op.execute("""
        CREATE TABLE medvault.verification_codes (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID NOT NULL REFERENCES medvault.users(id) ON DELETE CASCADE,
            purpose         medvault.verification_purpose NOT NULL,
            code_hash       TEXT NOT NULL,
            attempt_count   INT  NOT NULL DEFAULT 0,
            resend_count    INT  NOT NULL DEFAULT 0,
            expires_at      TIMESTAMPTZ NOT NULL,
            used_at         TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_verification_codes_user_purpose
            ON medvault.verification_codes(user_id, purpose, created_at DESC);
    """)

    op.execute("""
        CREATE TABLE medvault.step_up_verifications (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID NOT NULL REFERENCES medvault.users(id) ON DELETE CASCADE,
            action          VARCHAR(100) NOT NULL,
            resource_type   VARCHAR(50),
            resource_id     UUID,
            factor_used     medvault.step_up_factor NOT NULL DEFAULT 'idnp',
            status          VARCHAR(20) NOT NULL DEFAULT 'pending',
            attempt_count   INT NOT NULL DEFAULT 0,
            verified_at     TIMESTAMPTZ,
            expires_at      TIMESTAMPTZ NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT chk_step_up_status CHECK (status IN ('pending', 'verified', 'failed', 'expired'))
        );
        CREATE INDEX idx_step_up_verifications_user
            ON medvault.step_up_verifications(user_id, created_at DESC);
    """)

    # ------------------------------------------------------------------
    # 2. INSTITUTIONAL INTEGRATION
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE medvault.institutions (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name            VARCHAR(200) NOT NULL,
            fhir_base_url   TEXT NOT NULL UNIQUE,
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE medvault.institution_connections (
            id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            patient_id                UUID NOT NULL REFERENCES medvault.users(id) ON DELETE CASCADE,
            institution_id            UUID NOT NULL REFERENCES medvault.institutions(id),
            status                    medvault.connection_status NOT NULL DEFAULT 'pending',

            consent_shown_at          TIMESTAMPTZ,
            consent_given_at          TIMESTAMPTZ,
            scopes_requested          TEXT[] NOT NULL DEFAULT '{}',
            scopes_granted            TEXT[] NOT NULL DEFAULT '{}',

            access_token_encrypted    BYTEA,
            refresh_token_encrypted   BYTEA,
            token_expires_at          TIMESTAMPTZ,

            connected_at              TIMESTAMPTZ,
            revoked_at                TIMESTAMPTZ,
            failure_reason            VARCHAR(100),

            created_at                TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_institution_connections_patient
            ON medvault.institution_connections(patient_id);
        CREATE UNIQUE INDEX ux_institution_connections_active
            ON medvault.institution_connections(patient_id, institution_id)
            WHERE status IN ('pending', 'active');
    """)

    # ------------------------------------------------------------------
    # 3. DOCUMENTS
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE medvault.documents (
            id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            patient_id                  UUID NOT NULL REFERENCES medvault.users(id) ON DELETE CASCADE,
            category                    medvault.document_category NOT NULL,
            source                      medvault.document_source NOT NULL,
            institution_connection_id   UUID REFERENCES medvault.institution_connections(id),

            storage_key                 TEXT NOT NULL,
            original_filename           VARCHAR(255),
            mime_type                   VARCHAR(100) NOT NULL,
            file_size_bytes             BIGINT NOT NULL,

            title                       VARCHAR(255),
            record_date                 DATE,

            status                      medvault.document_status NOT NULL DEFAULT 'processing',
            rejection_reason            VARCHAR(200),

            uploaded_by_user_id         UUID NOT NULL REFERENCES medvault.users(id),
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

            deleted_at                  TIMESTAMPTZ,
            purge_scheduled_at          TIMESTAMPTZ,
            purged_at                   TIMESTAMPTZ,

            CONSTRAINT chk_documents_source_consistency CHECK (
                (source = 'institution' AND institution_connection_id IS NOT NULL) OR
                (source = 'self_upload' AND institution_connection_id IS NULL)
            )
        );
        CREATE INDEX idx_documents_patient_category ON medvault.documents(patient_id, category);
        CREATE INDEX idx_documents_connection ON medvault.documents(institution_connection_id);
        CREATE INDEX idx_documents_purge_due
            ON medvault.documents(purge_scheduled_at)
            WHERE deleted_at IS NOT NULL AND purged_at IS NULL;
    """)

    # ------------------------------------------------------------------
    # 4. MEDICAL DATA VISUALIZATION
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE medvault.diagnostics (
            id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            patient_id                  UUID NOT NULL REFERENCES medvault.users(id) ON DELETE CASCADE,
            document_id                 UUID REFERENCES medvault.documents(id),
            institution_connection_id   UUID REFERENCES medvault.institution_connections(id),

            record_date                 DATE NOT NULL,
            diagnostic_name             VARCHAR(255) NOT NULL,
            specialty                   VARCHAR(100),
            doctor_name                 VARCHAR(150),

            created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_diagnostics_patient_date ON medvault.diagnostics(patient_id, record_date);
        CREATE INDEX idx_diagnostics_patient_specialty ON medvault.diagnostics(patient_id, specialty);
    """)

    op.execute("""
        CREATE TABLE medvault.prescriptions (
            id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            patient_id                  UUID NOT NULL REFERENCES medvault.users(id) ON DELETE CASCADE,
            document_id                 UUID REFERENCES medvault.documents(id),
            institution_connection_id   UUID REFERENCES medvault.institution_connections(id),

            medication_name             VARCHAR(255) NOT NULL,
            record_date                 DATE NOT NULL,
            status                      medvault.prescription_status NOT NULL,
            instructions                TEXT,

            created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_prescriptions_patient_status ON medvault.prescriptions(patient_id, status);
    """)

    op.execute("""
        CREATE TABLE medvault.certificates (
            id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            patient_id                  UUID NOT NULL REFERENCES medvault.users(id) ON DELETE CASCADE,
            document_id                 UUID REFERENCES medvault.documents(id),
            institution_connection_id   UUID REFERENCES medvault.institution_connections(id),

            issue_date                  DATE NOT NULL,
            reason                      VARCHAR(255),
            issuing_doctor              VARCHAR(150),
            issuing_institution_name    VARCHAR(200),

            visible_to_caregiver        BOOLEAN NOT NULL DEFAULT FALSE,

            created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_certificates_patient ON medvault.certificates(patient_id);
    """)

    op.execute("""
        CREATE TABLE medvault.other_medical_info (
            id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            patient_id                  UUID NOT NULL REFERENCES medvault.users(id) ON DELETE CASCADE,
            document_id                 UUID REFERENCES medvault.documents(id),
            institution_connection_id   UUID REFERENCES medvault.institution_connections(id),

            field_type                  VARCHAR(50) NOT NULL,
            field_value                 TEXT NOT NULL,

            created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_other_info_patient_type ON medvault.other_medical_info(patient_id, field_type);
    """)

    # ------------------------------------------------------------------
    # 5. ACCOUNT MANAGEMENT (caregiver delegation)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE medvault.caregiver_links (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            elder_patient_id    UUID NOT NULL REFERENCES medvault.users(id) ON DELETE CASCADE,
            caregiver_user_id   UUID NOT NULL REFERENCES medvault.users(id) ON DELETE CASCADE,
            status              medvault.caregiver_link_status NOT NULL DEFAULT 'pending',

            invited_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            activated_at        TIMESTAMPTZ,
            revoked_at          TIMESTAMPTZ,

            CONSTRAINT chk_caregiver_not_self CHECK (elder_patient_id <> caregiver_user_id)
        );
        CREATE INDEX idx_caregiver_links_elder ON medvault.caregiver_links(elder_patient_id);
        CREATE INDEX idx_caregiver_links_caregiver ON medvault.caregiver_links(caregiver_user_id);
        CREATE UNIQUE INDEX ux_caregiver_links_active
            ON medvault.caregiver_links(elder_patient_id, caregiver_user_id)
            WHERE status IN ('pending', 'active');
    """)

    op.execute("""
        CREATE TABLE medvault.caregiver_permissions (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            caregiver_link_id   UUID NOT NULL REFERENCES medvault.caregiver_links(id) ON DELETE CASCADE,
            category             medvault.document_category NOT NULL,
            can_view              BOOLEAN NOT NULL DEFAULT FALSE,
            can_export            BOOLEAN NOT NULL DEFAULT FALSE,
            granted_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

            UNIQUE (caregiver_link_id, category)
        );
    """)

    # ------------------------------------------------------------------
    # 6. DATA EXPORT
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE medvault.data_export_requests (
            id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            patient_id             UUID NOT NULL REFERENCES medvault.users(id) ON DELETE CASCADE,
            requested_by_user_id   UUID NOT NULL REFERENCES medvault.users(id),
            scope                  VARCHAR(50) NOT NULL,
            format                 medvault.export_format NOT NULL,
            status                 medvault.export_status NOT NULL DEFAULT 'pending',
            storage_key            TEXT,
            created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at           TIMESTAMPTZ
        );
        CREATE INDEX idx_export_requests_patient
            ON medvault.data_export_requests(patient_id, created_at DESC);
    """)

    # ------------------------------------------------------------------
    # 7. AUDIT LOG
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE medvault.audit_logs (
            id                  BIGSERIAL PRIMARY KEY,
            actor_user_id       UUID REFERENCES medvault.users(id),
            target_patient_id   UUID REFERENCES medvault.users(id),
            action              VARCHAR(100) NOT NULL,
            resource_type       VARCHAR(50),
            resource_id         UUID,
            ip_address          INET,
            user_agent          TEXT,
            metadata            JSONB NOT NULL DEFAULT '{}',
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_audit_logs_target ON medvault.audit_logs(target_patient_id, created_at DESC);
        CREATE INDEX idx_audit_logs_actor ON medvault.audit_logs(actor_user_id, created_at DESC);
        CREATE INDEX idx_audit_logs_action ON medvault.audit_logs(action, created_at DESC);
    """)


def downgrade():
    for table in [
        "audit_logs", "data_export_requests", "caregiver_permissions", "caregiver_links",
        "other_medical_info", "certificates", "prescriptions", "diagnostics",
        "documents", "institution_connections", "institutions",
        "step_up_verifications", "verification_codes", "users",
    ]:
        op.execute(f"DROP TABLE IF EXISTS medvault.{table} CASCADE")

    for enum_type in [
        "document_category", "document_source", "document_status", "verification_purpose",
        "connection_status", "caregiver_link_status", "prescription_status",
        "export_status", "export_format", "step_up_factor",
    ]:
        op.execute(f"DROP TYPE IF EXISTS medvault.{enum_type}")
