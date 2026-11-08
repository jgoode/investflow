from logging.config import fileConfig
from typing import Any

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.db.connection import resolve_db_path

# Ensure the DB directory exists (alembic creates the file, not the tree).
resolve_db_path().parent.mkdir(parents=True, exist_ok=True)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# InvestFlow: DB location comes from app.db.connection (INVESTFLOW_DB_PATH or
# backend/data/investflow.db default) — single source of truth for the DB path.
config.set_main_option("sqlalchemy.url", "sqlite:///" + str(resolve_db_path()))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # SQLite conventions (docs/02-architecture.md §3): every connection the
    # migration engine opens gets WAL + foreign_keys enforcement.
    from sqlalchemy import event

    from app.db.connection import apply_pragmas

    @event.listens_for(connectable, "connect")
    def _apply_sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:
        apply_pragmas(dbapi_conn)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
