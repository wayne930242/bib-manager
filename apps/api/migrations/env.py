from logging.config import fileConfig

from alembic import context

from services.database import _schema, migration_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = _schema


def run_migrations_offline() -> None:
    raise RuntimeError("Offline migrations are unsupported; connect to the database")


def run_migrations_online() -> None:
    with migration_engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
