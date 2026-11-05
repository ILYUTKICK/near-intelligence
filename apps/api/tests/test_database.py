"""NI-003 real PostgreSQL tests. All identities and amounts are synthetic.

Use scripts/run-db-tests.py; direct discovery skips DB cases without its explicit
isolated-cluster environment. A skip is never successful integration evidence.
"""

import os
import unittest
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from near_api.db.numeric import exact_numeric
from near_api.db.session import DatabaseConfigurationError, create_runtime_engine, user_transaction


class ExactNumericTests(unittest.TestCase):
    def test_exact_bounds_without_float_or_silent_rounding(self):
        raw = "9" * 78
        self.assertEqual(str(exact_numeric(raw, scale=0)), raw)
        self.assertEqual(str(exact_numeric("1.000000000000000000000000000001")),
                         "1.000000000000000000000000000001")
        for value in ("1" + "0" * 78, "0.1", "NaN", "Infinity", 1.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                exact_numeric(value, scale=0)
        with self.assertRaises(ValueError):
            exact_numeric("0." + "0" * 30 + "1")
        self.assertEqual(exact_numeric(Decimal("-12.25")), Decimal("-12.25"))


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1", "Use scripts/run-db-tests.py")
class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[3]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.engine = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        cls.operator = create_engine(os.environ["NI_TEST_OPERATOR_URL"], poolclass=NullPool,
                                     hide_parameters=True)
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"], poolclass=NullPool,
                                  hide_parameters=True)
        command.upgrade(cls.config, "head")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        cls.operator.dispose()
        cls.admin.dispose()

    def setUp(self):
        self.alice, self.bob = uuid4(), uuid4()
        for subject, name in ((self.alice, "Synthetic Alice"), (self.bob, "Synthetic Bob")):
            with user_transaction(self.engine, subject) as connection:
                connection.execute(text("INSERT INTO app.users(id) VALUES (:id)"), {"id": subject})
                connection.execute(text("""INSERT INTO app.user_profiles(user_id, display_name)
                                          VALUES (:id, :name)"""), {"id": subject, "name": name})

    def test_01_upgrade_down_upgrade_and_metadata(self):
        command.downgrade(self.config, "base")
        with self.admin.connect() as connection:
            self.assertIsNone(connection.scalar(text("SELECT to_regclass('app.users')")))
        command.upgrade(self.config, "head")
        command.check(self.config)
        with self.admin.connect() as connection:
            tables = connection.execute(text("""
                SELECT relname, relrowsecurity, relforcerowsecurity, pg_get_userbyid(relowner)
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'app' AND relname IN ('users', 'user_profiles')
            """)).all()
        self.assertEqual(len(tables), 2)
        self.assertTrue(all(row[1:] == (True, True, "near_migrator") for row in tables))

    def test_two_user_rls_read_update_delete_and_owner_forgery(self):
        with user_transaction(self.engine, None) as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.users")), 0)
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.user_profiles")), 0)
        with user_transaction(self.engine, self.alice) as connection:
            self.assertEqual(connection.scalars(text("SELECT id FROM app.users")).all(), [self.alice])
            self.assertEqual(connection.scalars(text("SELECT user_id FROM app.user_profiles")).all(),
                             [self.alice])
            self.assertEqual(connection.execute(text("""UPDATE app.user_profiles SET display_name='x'
                                                    WHERE user_id=:id"""), {"id": self.bob}).rowcount, 0)
            self.assertEqual(connection.execute(text("DELETE FROM app.user_profiles WHERE user_id=:id"),
                                                {"id": self.bob}).rowcount, 0)
        for statement, params in (
            ("INSERT INTO app.users(id) VALUES (:id)", {"id": uuid4()}),
            ("INSERT INTO app.user_profiles(user_id) VALUES (:id)", {"id": self.bob}),
            ("UPDATE app.user_profiles SET user_id=:id", {"id": self.bob}),
            ("UPDATE app.users SET disabled_at=now()", {}),
        ):
            with self.subTest(statement=statement), self.assertRaises(DBAPIError) as raised:
                with user_transaction(self.engine, self.alice) as connection:
                    connection.execute(text(statement), params)
            self.assertEqual(raised.exception.orig.sqlstate, "42501")
        with user_transaction(self.engine, self.bob) as connection:
            self.assertEqual(connection.scalar(text("SELECT display_name FROM app.user_profiles")),
                             "Synthetic Bob")

    def test_runtime_cannot_bypass_rls_or_create_objects(self):
        for statement in ("SET ROLE near_migrator", "SET ROLE near_operator",
                          "ALTER TABLE app.users DISABLE ROW LEVEL SECURITY",
                          "TRUNCATE app.users CASCADE", "CREATE TABLE app.forbidden(id int)",
                          "CREATE TABLE public.forbidden(id int)", "SELECT * FROM pg_authid"):
            with self.subTest(statement=statement), self.assertRaises(DBAPIError) as raised:
                with user_transaction(self.engine, self.alice) as connection:
                    connection.execute(text(statement))
            self.assertEqual(raised.exception.orig.sqlstate, "42501")
        with self.assertRaises(DBAPIError) as raised:
            with user_transaction(self.engine, self.alice) as connection:
                connection.execute(text("SET LOCAL row_security=off"))
                connection.execute(text("SELECT * FROM app.users"))
        self.assertEqual(raised.exception.orig.sqlstate, "42501")
        with self.admin.connect() as connection:
            rows = connection.execute(text("""
                SELECT rolname, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication
                FROM pg_roles WHERE rolname IN ('near_app', 'near_operator', 'near_migrator')
            """)).all()
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(not any(row[1:]) for row in rows))

    def test_pool_identity_cleared_after_commit_rollback_and_session_leak(self):
        with user_transaction(self.engine, self.alice) as connection:
            backend = connection.scalar(text("SELECT pg_backend_pid()"))
            self.assertEqual(connection.scalar(text("SELECT app.current_user_id()")), self.alice)
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT pg_backend_pid()")), backend)
            self.assertIsNone(connection.scalar(text("SELECT app.current_user_id()")))
        with self.assertRaisesRegex(RuntimeError, "synthetic rollback"):
            with user_transaction(self.engine, self.alice) as connection:
                connection.execute(text("UPDATE app.user_profiles SET display_name='rolled back'"))
                raise RuntimeError("synthetic rollback")
        with user_transaction(self.engine, self.bob) as connection:
            self.assertEqual(connection.scalar(text("SELECT pg_backend_pid()")), backend)
            self.assertEqual(connection.scalar(text("SELECT app.current_user_id()")), self.bob)
        with self.engine.begin() as connection:
            connection.execute(text("SELECT set_config('app.user_id', :id, false)"),
                               {"id": str(self.alice)})
        with self.engine.connect() as connection:
            self.assertIsNone(connection.scalar(text("SELECT app.current_user_id()")))
        with user_transaction(self.engine, self.alice) as connection:
            self.assertEqual(connection.scalar(text("SELECT display_name FROM app.user_profiles")),
                             "Synthetic Alice")

    def test_constraints_timezone_fk_and_real_numeric_overflow_rollback(self):
        with self.assertRaises(DBAPIError) as raised:
            with self.operator.begin() as connection:
                connection.execute(text("INSERT INTO app.user_profiles(user_id) VALUES (:id)"),
                                   {"id": uuid4()})
        self.assertEqual(raised.exception.orig.sqlstate, "23503")
        for name, zone, state in (("x" * 81, "UTC", "22001"),
                                  ("Synthetic", "Imaginary/Not_A_Zone", "23514")):
            with self.assertRaises(DBAPIError) as raised:
                with user_transaction(self.engine, self.alice) as connection:
                    connection.execute(text("""UPDATE app.user_profiles SET display_name=:name,
                                              display_timezone=:zone"""), {"name": name, "zone": zone})
            self.assertEqual(raised.exception.orig.sqlstate, state)
        with user_transaction(self.engine, self.alice) as connection:
            previous = connection.scalar(text("SELECT updated_at FROM app.user_profiles"))
            connection.execute(text("UPDATE app.user_profiles SET display_timezone='Europe/Moscow'"))
            self.assertGreaterEqual(connection.scalar(text("SELECT updated_at FROM app.user_profiles")),
                                    previous)
            self.assertEqual(str(connection.scalar(text("SELECT CAST(:amount AS NUMERIC(78,0))"),
                                                   {"amount": "9" * 78})), "9" * 78)
        subject = uuid4()
        with self.assertRaises(DBAPIError) as raised:
            with user_transaction(self.engine, subject) as connection:
                connection.execute(text("INSERT INTO app.users(id) VALUES (:id)"), {"id": subject})
                connection.execute(text("SELECT CAST(:amount AS NUMERIC(78,0))"),
                                   {"amount": "1" + "0" * 78})
        self.assertEqual(raised.exception.orig.sqlstate, "22003")
        with user_transaction(self.engine, subject) as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.users")), 0)

    def test_operator_disables_user_without_runtime_escalation(self):
        with self.operator.begin() as connection:
            connection.execute(text("UPDATE app.users SET disabled_at=now() WHERE id=:id"),
                               {"id": self.alice})
        with user_transaction(self.engine, self.alice) as connection:
            self.assertIsNotNone(connection.scalar(text("SELECT disabled_at FROM app.users")))
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.user_profiles")), 0)
            self.assertEqual(connection.execute(text("UPDATE app.user_profiles SET display_name='x'"))
                             .rowcount, 0)

    def test_unsafe_credentials_memberships_and_identity_are_rejected(self):
        for value in ("not a URL", os.environ["MIGRATION_DATABASE_URL"],
                      "postgresql+psycopg://near_app:REPLACE_PASSWORD@localhost/db"):
            with self.assertRaises(DatabaseConfigurationError):
                create_runtime_engine(value)
        with self.assertRaises(ValueError):
            with user_transaction(self.engine, "unverified-user-id"):
                self.fail("must not yield")
        for enable, disable in (("ALTER ROLE near_app BYPASSRLS", "ALTER ROLE near_app NOBYPASSRLS"),
                                ("ALTER ROLE near_app REPLICATION", "ALTER ROLE near_app NOREPLICATION"),
                                ("GRANT near_operator TO near_app", "REVOKE near_operator FROM near_app")):
            try:
                with self.admin.begin() as connection:
                    connection.execute(text(enable))
                with self.assertRaises(DatabaseConfigurationError):
                    with user_transaction(self.engine, self.alice):
                        self.fail("unsafe role must not yield")
            finally:
                with self.admin.begin() as connection:
                    connection.execute(text(disable))


if __name__ == "__main__":
    unittest.main()
