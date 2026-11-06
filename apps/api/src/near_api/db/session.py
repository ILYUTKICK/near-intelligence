"""Internal transaction boundary; callers must first verify the JWT (NI-018).

A UUID here is trusted backend context, never an HTTP user_id authorization claim.
RLS protects against missing predicates; it does not protect a leaked DB password
from an attacker who can execute arbitrary SQL and set a different identity.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import Connection, Engine, create_engine, event, text
from sqlalchemy.engine import make_url


class DatabaseConfigurationError(RuntimeError):
    """A runtime credential must not be an administrator or schema owner."""


def create_runtime_engine(database_url: str, *, pool_size: int = 5) -> Engine:
    try:
        url = make_url(database_url)
    except Exception:
        raise DatabaseConfigurationError("Invalid DATABASE_URL") from None
    if (url.drivername != "postgresql+psycopg" or url.username != "near_app"
            or not url.password or "REPLACE" in url.password.upper()):
        raise DatabaseConfigurationError("DATABASE_URL requires the near_app psycopg credential")
    engine = create_engine(url, pool_size=pool_size, max_overflow=0, pool_timeout=5,
                           pool_pre_ping=True, hide_parameters=True,
                           isolation_level="READ COMMITTED",
                           connect_args={"connect_timeout": 5, "options": "-c timezone=UTC"})

    @event.listens_for(engine, "reset")
    def clear_identity(dbapi_connection, connection_record, reset_state):
        if not reset_state.terminate_only:
            dbapi_connection.rollback()
            with dbapi_connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute("SELECT set_config('app.user_id', '', false)")
            dbapi_connection.commit()

    return engine


def _assert_runtime_role(connection: Connection) -> None:
    role = connection.execute(text("""
        SELECT current_user AS name, session_user AS login, rolsuper, rolbypassrls,
               rolcreatedb, rolcreaterole, rolreplication,
               has_schema_privilege(current_user, 'app', 'CREATE') AS can_create,
               EXISTS (SELECT 1 FROM pg_auth_members WHERE member = r.oid) AS has_membership,
               EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                       WHERE n.nspname = 'app' AND c.relowner = r.oid) AS owns_table
        FROM pg_roles r WHERE rolname = current_user
    """)).mappings().one()
    if (role["name"] != "near_app" or role["login"] != "near_app"
            or any(role[key] for key in ("rolsuper", "rolbypassrls", "rolcreatedb", "rolcreaterole", "rolreplication",
                                        "can_create", "has_membership", "owns_table"))
            or connection.connection.driver_connection.autocommit):
        raise DatabaseConfigurationError("Runtime role is privileged or transaction mode is unsafe")


@contextmanager
def user_transaction(engine: Engine, verified_subject: UUID | None) -> Iterator[Connection]:
    if verified_subject is not None and not isinstance(verified_subject, UUID):
        raise ValueError("Transaction identity must be a verified UUID or None")
    with engine.begin() as connection:
        _assert_runtime_role(connection)
        connection.execute(text("SELECT set_config('app.user_id', :subject, true)"),
                           {"subject": str(verified_subject) if verified_subject is not None else ""})
        # Fail closed if the transaction-local identity did not actually take
        # effect; repositories and RLS both rely on app.current_user_id().
        identity = connection.execute(text("SELECT app.current_user_id()")).scalar_one_or_none()
        if identity != verified_subject:
            raise DatabaseConfigurationError("Transaction-local identity did not take effect")
        yield connection
