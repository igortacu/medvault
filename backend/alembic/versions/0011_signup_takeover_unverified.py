"""sign-up may take over an unverified phone number

`auth_register_user` used to return NULL on any phone conflict, so an abandoned (or
malicious) `pending_verification` sign-up reserved the number forever: the real owner
could neither sign up, sign in nor reset. Now a conflict with a still-unverified row
overwrites that row's details and password (and returns its id); the new owner proves
the number with the SMS code as usual, and whoever cannot read that SMS never
activates it. A conflict with a verified/active account still returns NULL.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-13
"""
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE OR REPLACE FUNCTION medvault.auth_register_user(
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
          -- NULL when the number belongs to a verified account.
          RETURN v_id;
        END $$;
    """)


def downgrade():
    op.execute("""
        CREATE OR REPLACE FUNCTION medvault.auth_register_user(
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
