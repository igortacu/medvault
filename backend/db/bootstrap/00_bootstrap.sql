-- ============================================================================
-- MedVault — STEP 0: Bootstrap
-- Run this connected as the `postgres` superuser, on the `medvault` database.
-- Idempotent: safe to run more than once.
-- ============================================================================

DO $$
DECLARE
    v_super    BOOLEAN;
    v_bypass   BOOLEAN;
    v_canlogin BOOLEAN;
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'migrator') THEN
        CREATE ROLE migrator WITH LOGIN PASSWORD 'CHANGE_ME_MIGRATOR' CREATEDB;
    END IF;

    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user WITH LOGIN PASSWORD 'CHANGE_ME_APP_USER' NOSUPERUSER NOBYPASSRLS;
    END IF;

    -- Validate app_user attributes even if it already existed.
    -- A pre-existing app_user with SUPERUSER or BYPASSRLS would silently
    -- invalidate every RLS policy in the schema — fail loudly instead.
    SELECT rolsuper, rolbypassrls, rolcanlogin
    INTO v_super, v_bypass, v_canlogin
    FROM pg_roles
    WHERE rolname = 'app_user';

    IF v_super THEN
        RAISE EXCEPTION
            'Bootstrap aborted: app_user has SUPERUSER — '
            'this defeats all RLS policies. '
            'Fix: ALTER ROLE app_user NOSUPERUSER;';
    END IF;

    IF v_bypass THEN
        RAISE EXCEPTION
            'Bootstrap aborted: app_user has BYPASSRLS — '
            'this defeats all RLS policies. '
            'Fix: ALTER ROLE app_user NOBYPASSRLS;';
    END IF;

    IF NOT v_canlogin THEN
        RAISE EXCEPTION
            'Bootstrap aborted: app_user cannot login — '
            'Fix: ALTER ROLE app_user LOGIN;';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE medvault TO app_user;
GRANT CONNECT ON DATABASE medvault TO migrator;

-- pgcrypto stays in public by convention (so its functions don't mix with
-- application tables); search_path set below makes it visible from medvault anyway
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Dedicated schema for all MedVault objects — never use `public` for these
CREATE SCHEMA IF NOT EXISTS medvault AUTHORIZATION migrator;
GRANT USAGE ON SCHEMA medvault TO app_user;

ALTER ROLE migrator  SET search_path TO medvault, public;
ALTER ROLE app_user  SET search_path TO medvault, public;

-- app_user can never create objects in public, even under a SQL-injection scenario
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- Sanity check
SELECT rolname FROM pg_roles WHERE rolname IN ('migrator', 'app_user');
SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'medvault';
