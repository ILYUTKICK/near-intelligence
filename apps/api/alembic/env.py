"""Explicit migrations only; API startup never imports or invokes this file."""

import os

from alembic import context
from dotenv import dotenv_values
from sqlalchemy import create_engine, pool, text
from sqlalchemy.engine import make_url

from near_api.db.models import Base
from near_api.settings import find_repo_root


def migration_url():
    value = os.environ.get("MIGRATION_DATABASE_URL") or dotenv_values(
        find_repo_root() / ".env").get("MIGRATION_DATABASE_URL")
    if not value:
        raise RuntimeError("MIGRATION_DATABASE_URL is required; runtime DATABASE_URL is never reused")
    try:
        url = make_url(value)
    except Exception:
        raise RuntimeError("Invalid MIGRATION_DATABASE_URL") from None
    if (url.drivername != "postgresql+psycopg" or url.username != "near_migrator"
            or not url.password or "REPLACE" in url.password.upper()):
        raise RuntimeError("Migrations require the separate near_migrator psycopg credential")
    return url


url = migration_url()
if context.is_offline_mode():
    raise RuntimeError("Offline migration SQL is not supported; role verification requires PostgreSQL")

with create_engine(url, poolclass=pool.NullPool, hide_parameters=True,
                   connect_args={"connect_timeout": 5}).connect() as connection:
    with connection.begin():
        role = connection.execute(text("""
            SELECT current_user AS name, session_user AS login, rolsuper, rolbypassrls,
                   rolcreatedb, rolcreaterole, rolreplication FROM pg_roles WHERE rolname = current_user
        """)).mappings().one()
        if (role["name"] != "near_migrator" or role["login"] != "near_migrator"
                or any(role[key] for key in ("rolsuper", "rolbypassrls", "rolcreatedb", "rolcreaterole", "rolreplication"))):
            raise RuntimeError("Migration credential has unsafe role attributes")
        context.configure(connection=connection, target_metadata=Base.metadata,
                          version_table_schema="app", include_schemas=True,
                          compare_type=True, compare_server_default=True)
        context.run_migrations()
