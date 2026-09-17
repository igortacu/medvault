from logging.config import fileConfig
import os
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _load_dotenv():
    """Populate os.environ from the repo-root .env (backend/../.env) without a
    third-party dependency. Real environment variables always take precedence,
    so `DATABASE_URL=... alembic ...` still overrides the file."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

# DATABASE_URL is set by docker-compose (see the `migrate` service) to
# postgresql://migrator:...@postgres:5432/medvault — always the `migrator`
# role. Never point this at app_user; migrator owns the schema and has the
# DDL rights these migrations need.
db_url = os.environ.get("DATABASE_URL")
if db_url:
        config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))

# The baseline migrations (0001-0007) are hand-written raw SQL (op.execute):
# they own the initial schema, RLS, functions, triggers and grants, none of
# which autogenerate can express. The models on app.models.metadata mirror the
# tables so `alembic revision --autogenerate` can diff against them for FUTURE
# column/table changes. autogenerate will not see RLS/functions/policies — keep
# writing those by hand.
from app.models import metadata as target_metadata


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
