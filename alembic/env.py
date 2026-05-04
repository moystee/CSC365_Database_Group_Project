"""Alembic environment configuration.

Reads the database URL from the POSTGRES_URI environment variable (loaded
from .env when present), and uses the SQLAlchemy Core metadata defined in
src/database.py for autogenerate support.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Make `src` importable regardless of where alembic is invoked from.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from src.database import metadata as target_metadata  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

postgres_uri = os.environ.get("POSTGRES_URI")
if not postgres_uri:
    raise RuntimeError(
        "POSTGRES_URI is not set. Copy .env.example to .env and fill it in."
    )
config.set_main_option("sqlalchemy.url", postgres_uri)


def run_migrations_offline() -> None:
    context.configure(
        url=postgres_uri,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
