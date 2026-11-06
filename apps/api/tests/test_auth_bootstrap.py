"""NI-018 principal bootstrap against real PostgreSQL roles (NI-003).

Use scripts/run-db-tests.py; direct discovery skips DB cases without its
explicit isolated-cluster environment. A skip is never successful integration
evidence. All identities are synthetic test fixtures.
"""

import os
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from near_api.auth.principal import Principal, UserDisabled, bootstrap_principal
from near_api.auth.verification import VerifiedToken
from near_api.db.session import create_runtime_engine, user_transaction


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1", "Use scripts/run-db-tests.py")
class BootstrapTests(unittest.TestCase):
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
        with self.operator.begin() as connection:
            connection.execute(text("DELETE FROM app.users"))

    @staticmethod
    def verified(subject):
        return VerifiedToken(subject=subject, expires_at=datetime.now(UTC) + timedelta(minutes=5),
                             issued_at=datetime.now(UTC))

    def test_01_bootstrap_is_idempotent_and_writes_only_the_verified_subject(self):
        alice = uuid4()
        first = bootstrap_principal(self.engine, self.verified(alice))
        second = bootstrap_principal(self.engine, self.verified(alice))
        self.assertEqual(first, Principal(id=alice, display_name="", display_timezone="UTC"))
        self.assertEqual(second, first)
        with self.admin.connect() as connection:
            users = connection.execute(text("""
                SELECT id, auth_provider, disabled_at IS NULL FROM app.users ORDER BY id
            """)).all()
            profiles = connection.execute(text("""
                SELECT user_id, display_name, display_timezone FROM app.user_profiles
            """)).all()
        self.assertEqual(users, [(alice, "supabase", True)])
        self.assertEqual(profiles, [(alice, "", "UTC")])
        other, arbitrary = uuid4(), uuid4()
        bootstrap_principal(self.engine, self.verified(other))
        with self.admin.connect() as connection:
            ids = {row[0] for row in connection.execute(text("SELECT id FROM app.users"))}
        self.assertEqual(ids, {alice, other})
        self.assertNotIn(arbitrary, ids)

    def test_runtime_cannot_insert_another_subject_during_bootstrap_context(self):
        alice, bob = uuid4(), uuid4()
        with self.assertRaises(DBAPIError) as raised:
            with user_transaction(self.engine, alice) as connection:
                connection.execute(text("INSERT INTO app.users(id) VALUES (:id)"), {"id": bob})
        self.assertEqual(raised.exception.orig.sqlstate, "42501")
        with self.admin.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.users")), 0)

    def test_disabled_user_is_rejected_fail_closed(self):
        alice = uuid4()
        bootstrap_principal(self.engine, self.verified(alice))
        with self.operator.begin() as connection:
            connection.execute(text("UPDATE app.users SET disabled_at=now() WHERE id=:id"),
                               {"id": alice})
        with self.assertRaises(UserDisabled):
            bootstrap_principal(self.engine, self.verified(alice))
        with self.operator.connect() as connection:
            self.assertEqual(connection.scalar(text("""
                SELECT display_name FROM app.user_profiles WHERE user_id=:id
            """), {"id": alice}), "")
        # The rejection is state-dependent: restoring the account works again.
        with self.operator.begin() as connection:
            connection.execute(text("UPDATE app.users SET disabled_at=NULL WHERE id=:id"),
                               {"id": alice})
        self.assertEqual(bootstrap_principal(self.engine, self.verified(alice)).id, alice)
        # A rejection leaves the engine usable for the next verified subject.
        bob = uuid4()
        self.assertEqual(bootstrap_principal(self.engine, self.verified(bob)).id, bob)

    def test_pooled_identity_never_retains_another_user(self):
        alice, bob = uuid4(), uuid4()
        bootstrap_principal(self.engine, self.verified(alice))
        with user_transaction(self.engine, alice) as connection:
            backend = connection.scalar(text("SELECT pg_backend_pid()"))
        bootstrap_principal(self.engine, self.verified(bob))
        with self.engine.connect() as connection:
            self.assertIsNone(connection.scalar(text("SELECT app.current_user_id()")))
        with user_transaction(self.engine, bob) as connection:
            self.assertEqual(connection.scalar(text("SELECT pg_backend_pid()")), backend)
            self.assertEqual(connection.scalars(text("SELECT id FROM app.users")).all(), [bob])
            self.assertEqual(connection.scalars(text("SELECT user_id FROM app.user_profiles")).all(),
                             [bob])
        with user_transaction(self.engine, None) as connection:
            self.assertIsNone(connection.scalar(text("SELECT app.current_user_id()")))
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.users")), 0)


if __name__ == "__main__":
    unittest.main()
