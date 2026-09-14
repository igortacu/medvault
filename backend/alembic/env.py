from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DATABASE_URL is set by docker-compose (see the `migrate` service) to
# postgresql://migrator:...@postgres:5432/medvault — always the `migrator`
# role. Never point this at app_user; migrator owns the schema and has the
# DDL rights these migrations need.
db_url = os.environ.get("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# Once you write SQLAlchemy models (app/models/base.py with
# MetaData(schema="medvault")), import that metadata here so that
# `alembic revision --autogenerate` can diff against it for FUTURE
# migrations. The four baseline migrations in versions/ are hand-written
# raw SQL (op.execute) matching the schema you already verified by hand,
# so target_metadata isn't required for them to run.
target_metadata = None
# from app.models.base import metadata as target_metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        version_table_schema="medvault",
        include_schemas=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema="medvault",
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
