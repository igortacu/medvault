"""email as the one-time-code channel (Option A: sign-in stays phone + password)

The second factor moves from an SMS to an emailed code, so every account now has an
email address that the sign-up code proves:

1. users.email (lowercase, unique) and users.email_verified_at. Existing rows get a
   placeholder on the reserved `.invalid` domain (it can never receive mail) so the
   column can be NOT NULL; the dev seed overwrites the demo accounts' addresses.
   Already-active rows count as verified, so the new consistency rule holds for them.
2. users_verified_consistency ties 'active' to a verified *email* now. phone_verified_at
   stays for accounts verified by SMS before this change.
3. auth_register_user takes the email. A verified account holding the phone OR the
   email still yields NULL (the API answers with a decoy). Unverified rows holding
   either one are removed and the sign-up is inserted fresh, which keeps 0011's
   "an abandoned sign-up cannot squat an identifier" rule with two unique keys, and
   orphans any code issued for the abandoned row.
4. auth_lookup_for_signin also returns the email, so login knows where to send the code.
5. auth_activate_user marks the email verified and reports whether it activated a row.
6. caregiver_accept_invite requires a verified email instead of a verified phone.
   Trade-off accepted by the product owner: the phone of a new account is no longer
   proven, so an invite addressed to a number can be claimed by whoever registered
   that number first. Restore a phone check if SMS verification comes back.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-20
"""
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

EMAIL_RE = r"^[a-z0-9._+-]+@[a-z0-9.-]+\.[a-z]{2,}$"


def upgrade():
    op.execute("""
        ALTER TABLE medvault.users
          ADD COLUMN email varchar(254),
          ADD COLUMN email_verified_at timestamptz;

        UPDATE medvault.users
        SET email = CAST(id AS text) || '@users.invalid',
            email_verified_at = phone_verified_at;

        ALTER TABLE medvault.users ALTER COLUMN email SET NOT NULL;
    """)
    op.execute(f"""
        ALTER TABLE medvault.users
          ADD CONSTRAINT users_email_unique UNIQUE (email),
          ADD CONSTRAINT users_email_format CHECK (email ~ '{EMAIL_RE}'),
          DROP CONSTRAINT users_verified_consistency,
          ADD CONSTRAINT users_verified_consistency
            CHECK (status = 'pending_verification' OR email_verified_at IS NOT NULL);
    """)

    op.execute("""
        DROP FUNCTION medvault.auth_register_user(varchar, varchar, varchar, date, text);

        CREATE FUNCTION medvault.auth_register_user(
          p_first_name    varchar,
          p_last_name     varchar,
          p_phone_e164    varchar,
          p_email         varchar,
          p_date_of_birth date,
          p_password_hash text
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = medvault, pg_temp AS $$
        DECLARE
          v_id uuid;
        BEGIN
          -- NULL when the phone or the email belongs to a verified account.
          IF EXISTS (
            SELECT 1 FROM users
            WHERE (phone_e164 = p_phone_e164 OR email = p_email)
              AND status <> 'pending_verification'
          ) THEN
            RETURN NULL;
          END IF;

          -- Abandoned sign-ups never hold an identifier against a new one.
          DELETE FROM users
          WHERE (phone_e164 = p_phone_e164 OR email = p_email)
            AND status = 'pending_verification';

          INSERT INTO users
            (first_name, last_name, phone_e164, email, date_of_birth, password_hash)
          VALUES
            (p_first_name, p_last_name, p_phone_e164, p_email, p_date_of_birth, p_password_hash)
          RETURNING id INTO v_id;
          RETURN v_id;
        EXCEPTION WHEN unique_violation THEN
          -- A concurrent sign-up won the race for one of the identifiers.
          RETURN NULL;
        END $$;

        DROP FUNCTION medvault.auth_lookup_for_signin(varchar);

        CREATE FUNCTION medvault.auth_lookup_for_signin(
          p_phone_e164 varchar
        ) RETURNS TABLE (
          id            uuid,
          first_name    varchar,
          last_name     varchar,
          email         varchar,
          password_hash text,
          status        medvault.user_status
        )
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = medvault, pg_temp AS $$
          SELECT u.id, u.first_name, u.last_name, u.email, u.password_hash, u.status
          FROM users u
          WHERE u.phone_e164 = p_phone_e164
        $$;

        DROP FUNCTION medvault.auth_activate_user(uuid);

        CREATE FUNCTION medvault.auth_activate_user(
          p_user_id uuid
        ) RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = medvault, pg_temp AS $$
        BEGIN
          UPDATE users
          SET status = 'active',
              email_verified_at = COALESCE(email_verified_at, now())
          WHERE id = p_user_id
            AND status = 'pending_verification';
          RETURN FOUND;
        END $$;

        CREATE OR REPLACE FUNCTION medvault.caregiver_accept_invite(
          p_link_id uuid
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = medvault, pg_temp AS $$
        DECLARE
          v_caller uuid := current_user_id();
          v_phone  varchar;
        BEGIN
          SELECT phone_e164 INTO v_phone
          FROM users
          WHERE id = v_caller AND email_verified_at IS NOT NULL;

          IF v_phone IS NULL THEN
            RAISE EXCEPTION 'caller has no verified account';
          END IF;

          UPDATE caregiver_links
          SET caregiver_user_id = v_caller,
              status            = 'active',
              responded_at      = now()
          WHERE id = p_link_id
            AND status = 'pending'
            AND invited_phone_e164 = v_phone;

          IF NOT FOUND THEN
            RAISE EXCEPTION 'invite not found or not addressed to caller';
          END IF;
        END $$;

        GRANT EXECUTE ON FUNCTION
          medvault.auth_register_user(varchar, varchar, varchar, varchar, date, text),
          medvault.auth_lookup_for_signin(varchar),
          medvault.auth_activate_user(uuid)
        TO app_user;
    """)


def downgrade():
    op.execute("""
        DROP FUNCTION medvault.auth_register_user(varchar, varchar, varchar, varchar, date, text);

        CREATE FUNCTION medvault.auth_register_user(
          p_first_name    varchar,
          p_last_name     varchar,
          p_phone_e164    varchar,
          p_date_of_birth date,
          p_password_hash text
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = medvault, pg_temp AS $$
        DECLARE
          v_id uuid;
        BEGIN
          INSERT INTO users (first_name, last_name, phone_e164, date_of_birth, password_hash)
          VALUES (p_first_name, p_last_name, p_phone_e164, p_date_of_birth, p_password_hash)
          ON CONFLICT ON CONSTRAINT users_phone_unique DO UPDATE
            SET first_name          = EXCLUDED.first_name,
                last_name           = EXCLUDED.last_name,
                date_of_birth       = EXCLUDED.date_of_birth,
                password_hash       = EXCLUDED.password_hash,
                password_changed_at = now()
            WHERE users.status = 'pending_verification'
          RETURNING id INTO v_id;
          RETURN v_id;
        END $$;

        DROP FUNCTION medvault.auth_lookup_for_signin(varchar);

        CREATE FUNCTION medvault.auth_lookup_for_signin(
          p_phone_e164 varchar
        ) RETURNS TABLE (
          id            uuid,
          first_name    varchar,
          last_name     varchar,
          password_hash text,
          status        medvault.user_status
        )
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = medvault, pg_temp AS $$
          SELECT id, first_name, last_name, password_hash, status
          FROM users
          WHERE phone_e164 = p_phone_e164
        $$;

        DROP FUNCTION medvault.auth_activate_user(uuid);

        CREATE FUNCTION medvault.auth_activate_user(
          p_user_id uuid
        ) RETURNS void
        LANGUAGE sql SECURITY DEFINER SET search_path = medvault, pg_temp AS $$
          UPDATE users
          SET status = 'active',
              phone_verified_at = COALESCE(phone_verified_at, now())
          WHERE id = p_user_id
            AND status = 'pending_verification'
        $$;

        CREATE OR REPLACE FUNCTION medvault.caregiver_accept_invite(
          p_link_id uuid
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = medvault, pg_temp AS $$
        DECLARE
          v_caller uuid := current_user_id();
          v_phone  varchar;
        BEGIN
          SELECT phone_e164 INTO v_phone
          FROM users
          WHERE id = v_caller AND phone_verified_at IS NOT NULL;

          IF v_phone IS NULL THEN
            RAISE EXCEPTION 'caller has no verified phone';
          END IF;

          UPDATE caregiver_links
          SET caregiver_user_id = v_caller,
              status            = 'active',
              responded_at      = now()
          WHERE id = p_link_id
            AND status = 'pending'
            AND invited_phone_e164 = v_phone;

          IF NOT FOUND THEN
            RAISE EXCEPTION 'invite not found or not addressed to caller';
          END IF;
        END $$;

        GRANT EXECUTE ON FUNCTION
          medvault.auth_register_user(varchar, varchar, varchar, date, text),
          medvault.auth_lookup_for_signin(varchar),
          medvault.auth_activate_user(uuid)
        TO app_user;
    """)
    # Accounts activated by email alone have no verified phone; send them back to
    # pending so the restored phone-based consistency rule holds.
    op.execute("""
        UPDATE medvault.users
        SET status = 'pending_verification'
        WHERE status <> 'pending_verification' AND phone_verified_at IS NULL;

        ALTER TABLE medvault.users
          DROP CONSTRAINT users_verified_consistency,
          ADD CONSTRAINT users_verified_consistency
            CHECK (status = 'pending_verification' OR phone_verified_at IS NOT NULL),
          DROP CONSTRAINT users_email_format,
          DROP CONSTRAINT users_email_unique,
          DROP COLUMN email_verified_at,
          DROP COLUMN email;
    """)
