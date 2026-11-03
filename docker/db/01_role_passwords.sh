#!/bin/sh
# Runs once, right after 00_bootstrap.sql, when the Postgres volume is first created.
# The bootstrap creates migrator and app_user with placeholder passwords; this sets
# the ones from .env so DATABASE_URL / DATABASE_URL_ASYNC can log in.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v migrator_pw="$MIGRATOR_PASSWORD" -v app_pw="$APP_USER_PASSWORD" <<'EOSQL'
ALTER ROLE migrator PASSWORD :'migrator_pw';
ALTER ROLE app_user PASSWORD :'app_pw';
EOSQL
