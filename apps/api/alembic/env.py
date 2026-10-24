"""Alembic environment. The database URL comes from app settings unless set on the config."""

from logging.config import fileConfig

from alembic import context

from app.core.config import get_settings, resolve_sqlite_url
from app.core.db import create_db_engine
from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def database_url() -> str:
    # Tests (or callers) may set sqlalchemy.url explicitly; otherwise use DATABASE_URL.
    explicit = config.get_main_option("sqlalchemy.url")
    return resolve_sqlite_url(explicit) if explicit else get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_db_engine(database_url())
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                # SQLite cannot ALTER most constraints; batch mode recreates tables instead.
                render_as_batch=True,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
