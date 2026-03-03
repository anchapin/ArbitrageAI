"""Alembic migration environment configuration."""

from logging.config import fileConfig
import os
import sys

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Add the project root to the path so we can import our models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Base metadata from your models
# This is needed for autogenerate support
from src.api.models import Base
from src.api.database import DATABASE_URL

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override the sqlalchemy.url with the actual DATABASE_URL from environment
# This allows using different databases for development/production
actual_db_url = os.getenv("DATABASE_URL", DATABASE_URL)
config.set_main_option("sqlalchemy.url", actual_db_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically the same as the .ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

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

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Compare types to detect changes in column types
            compare_type=True,
            # Render item type for better migration generation
            render_item=render_item,
        )

        with context.begin_transaction():
            context.run_migrations()


def render_item(type_, obj, name):
    """Apply custom rendering for autogenerate.

    This function helps with autogenerate by providing
    custom rendering for certain types of database objects.
    """
    # Return False for default rendering
    return False


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
