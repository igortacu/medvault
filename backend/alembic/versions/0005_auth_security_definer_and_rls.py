"""pre-auth SECURITY DEFINER functions (schema section 8.4)

Signup, sign-in, password reset and caregiver invite matching all happen before
app.current_user_id exists, so fail-closed RLS would block them. Instead of
relaxing policies, expose narrow SECURITY DEFINER functions owned by migrator.
Each does exactly one thing and returns only what that step needs.

These rely on migrator holding BYPASSRLS (set in bootstrap) so the definer can
act despite FORCE ROW LEVEL SECURITY; app_user stays NOBYPASSRLS. The doc
elides the bodies ($$ ... $$); they are implemented here to match the described
behaviour.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-17
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------------
    # Signup (Story 1.1). Returns the new id, or NULL on a phone conflict so
    # the caller can show a generic message without learning which number exists.
    # ------------------------------------------------------------------
    op.execute("""
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
          RETURNING id INTO v_id;
          RETURN v_id;
        EXCEPTION WHEN unique_violation THEN
          RETURN NULL;
        END $$;
    """)

    # ------------------------------------------------------------------
    # Sign-in lookup (Story 1.2). One row, exact phone match only, so it can't
    # be used to enumerate accounts. The app compares name/surname + hash and
    # shows a single generic error on any mismatch.
    # ------------------------------------------------------------------
    op.execute("""
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
    """)

    # ------------------------------------------------------------------
    # Activation after SMS verification (Story 1.4). Only permitted change for
    # an unverified account; sets phone_verified_at to satisfy the consistency
    # constraint that ties 'active' to a verified phone.
    # ------------------------------------------------------------------
    op.execute("""
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
    """)

    # ------------------------------------------------------------------
    # Password reset (Story 1.3). Bumps password_changed_at so sessions created
    # before the reset are rejected (the app also wipes Redis sessions).
    # ------------------------------------------------------------------
    op.execute("""
        CREATE FUNCTION medvault.auth_set_password(
          p_user_id       uuid,
          p_password_hash text
        ) RETURNS void
        LANGUAGE sql SECURITY DEFINER SET search_path = medvault, pg_temp AS $$
          UPDATE users
          SET password_hash = p_password_hash,
              password_changed_at = now()
          WHERE id = p_user_id
        $$;
    """)

    # ------------------------------------------------------------------
    # Accept a caregiver invite. Succeeds only if the invited phone equals the
    # caller's own verified phone, so nobody can claim someone else's invite.
    # Changes only caregiver_user_id, status and responded_at.
    # ------------------------------------------------------------------
    op.execute("""
        CREATE FUNCTION medvault.caregiver_accept_invite(
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
    """)

    # ------------------------------------------------------------------
    # Reject an invite, or end an active caregiving relationship from the
    # caregiver's side ("Reject Recipient"). Changes only status/responded_at.
    # ------------------------------------------------------------------
    op.execute("""
        CREATE FUNCTION medvault.caregiver_reject_invite(
          p_link_id uuid
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = medvault, pg_temp AS $$
        DECLARE
          v_caller uuid := current_user_id();
          v_phone  varchar;
        BEGIN
          SELECT phone_e164 INTO v_phone FROM users WHERE id = v_caller;

          UPDATE caregiver_links
          SET status       = 'rejected',
              responded_at = now()
          WHERE id = p_link_id
            AND status IN ('pending', 'active')
            AND (caregiver_user_id = v_caller
                 OR (status = 'pending' AND invited_phone_e164 = v_phone));

          IF NOT FOUND THEN
            RAISE EXCEPTION 'link not found or not addressable by caller';
          END IF;
        END $$;
    """)

    # The application role may call these functions and nothing else pre-auth.
    op.execute("""
        GRANT EXECUTE ON FUNCTION
          medvault.auth_register_user(varchar, varchar, varchar, date, text),
          medvault.auth_lookup_for_signin(varchar),
          medvault.auth_activate_user(uuid),
          medvault.auth_set_password(uuid, text),
          medvault.caregiver_accept_invite(uuid),
          medvault.caregiver_reject_invite(uuid)
        TO app_user;
    """)


def downgrade():
    op.execute("DROP FUNCTION IF EXISTS medvault.caregiver_reject_invite(uuid);")
    op.execute("DROP FUNCTION IF EXISTS medvault.caregiver_accept_invite(uuid);")
    op.execute("DROP FUNCTION IF EXISTS medvault.auth_set_password(uuid, text);")
    op.execute("DROP FUNCTION IF EXISTS medvault.auth_activate_user(uuid);")
    op.execute("DROP FUNCTION IF EXISTS medvault.auth_lookup_for_signin(varchar);")
    op.execute("DROP FUNCTION IF EXISTS medvault.auth_register_user(varchar, varchar, varchar, date, text);")
