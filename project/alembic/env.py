from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from app.core.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url", "mysql+pymysql://user:pass@localhost/db")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    raise RuntimeError(
        "Online migrations are reserved until the real MySQL connection is provided."
    )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
