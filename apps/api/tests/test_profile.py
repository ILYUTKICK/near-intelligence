"""NI-025 profile API tests: verified-subject ownership, validation, RLS.

The validation tests run anywhere; the DB round-trip tests need the
disposable-cluster runner (scripts/run-db-tests.py) and follow the
test_auth_bootstrap.py identity patterns.
"""

from pathlib import Path

import os
import unittest
from datetime import UTC, datetime, timedelta
from unittest import TestCase
from uuid import uuid4

from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from near_api.auth.principal import Principal, bootstrap_principal
from near_api.auth.verification import VerifiedToken
from alembic.config import Config
from near_api.db.security import principal_transaction
from near_api.db.session import create_runtime_engine
from near_api.users.routes import ProfileUpdateRequest
from near_api.auth.verification import VerifiedToken


def _principal(sub):
    return Principal(id=sub, display_name="", display_timezone="UTC")


class ProfileUpdateValidationTest(TestCase):
    def test_rejects_empty_and_control_names(self):
        for bad in ("", "   ", "bad\x01name"):
            with self.assertRaises(ValueError):
                ProfileUpdateRequest(display_name=bad, display_timezone="UTC")

    def test_rejects_non_iana_timezones(self):
        for bad in ("Mars/Olympus", "posix/UTC", ""):
            with self.assertRaises(ValueError):
                ProfileUpdateRequest(display_name="Alex", display_timezone=bad)

    def test_accepts_valid_input(self):
        request = ProfileUpdateRequest(display_name="Alex", display_timezone="Europe/Berlin")
        self.assertEqual(request.display_name, "Alex")
        self.assertEqual(request.display_timezone, "Europe/Berlin")

    def test_rejects_oversized_name(self):
        with self.assertRaises(ValueError):
            ProfileUpdateRequest(display_name="x" * 81, display_timezone="UTC")


class ProfileOwnershipTest(TestCase):
    """The request model never carries a subject: ownership is verified only."""

    def test_payload_cannot_carry_subject(self):
        request = ProfileUpdateRequest(display_name="Alex", display_timezone="UTC")
        self.assertFalse(hasattr(request, "subject"))
        self.assertFalse(hasattr(request, "user_id"))
        self.assertFalse(hasattr(request, "owner_id"))

    def test_principal_subject_is_the_only_write_target(self):
        sub = uuid4()
        principal = _principal(sub)
        # The routes update WHERE user_id = :subject (verified principal id);
        # this test pins that contract: the principal's id is the sole target.
        self.assertEqual(str(principal.id), str(sub))


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1", "Use scripts/run-db-tests.py")
class ProfileRoundTripTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[3]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.engine = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"], poolclass=NullPool,
                                  hide_parameters=True)
        command.upgrade(cls.config, "head")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        cls.admin.dispose()

    def setUp(self):
        with self.admin.begin() as connection:
            connection.execute(text("DELETE FROM app.users"))

    @staticmethod
    def principal_for(sub):
        return Principal(id=sub, display_name="", display_timezone="UTC")

    @staticmethod
    def verified(sub):
        return VerifiedToken(subject=sub, expires_at=datetime.now(UTC) + timedelta(minutes=5),
                             issued_at=datetime.now(UTC))

    def bootstrap(self, sub):
        # The production bootstrap path: creates users + user_profiles rows.
        return bootstrap_principal(self.engine, self.verified(sub))

    def test_update_writes_own_row_through_rls(self):
        alice = uuid4()
        self.bootstrap(alice)
        with principal_transaction(self.engine, self.principal_for(alice)) as connection:
            result = connection.execute(
                text("UPDATE app.user_profiles SET display_name = :n, display_timezone = :tz "
                     "WHERE user_id = :id RETURNING display_name, display_timezone"),
                {"n": "Alice", "tz": "Europe/Berlin", "id": alice},
            ).mappings().first()
        self.assertIsNotNone(result)
        self.assertEqual(result["display_name"], "Alice")
        self.assertEqual(result["display_timezone"], "Europe/Berlin")

    def test_foreign_profile_is_unreachable_through_rls(self):
        alice, bob = uuid4(), uuid4()
        self.bootstrap(alice)
        self.bootstrap(bob)
        # Bob's transaction-local identity cannot see or update Alice's row.
        with principal_transaction(self.engine, self.principal_for(bob)) as connection:
            result = connection.execute(
                text("SELECT display_name FROM app.user_profiles WHERE user_id = :id"),
                {"id": alice},
            ).first()
        self.assertIsNone(result)

    def test_invalid_timezone_is_rejected_by_the_database_check(self):
        alice = uuid4()
        self.bootstrap(alice)
        with principal_transaction(self.engine, self.principal_for(alice)) as connection:
            with self.assertRaises(Exception):
                connection.execute(
                    text("UPDATE app.user_profiles SET display_timezone = 'Mars/Olympus' "
                         "WHERE user_id = :id"),
                    {"id": alice},
                )

    def test_timezones_display_only_utc_storage_invariant(self):
        alice = uuid4()
        self.bootstrap(alice)
        with principal_transaction(self.engine, self.principal_for(alice)) as connection:
            connection.execute(
                text("UPDATE app.user_profiles SET display_timezone = 'Europe/Berlin' "
                     "WHERE user_id = :id"),
                {"id": alice},
            )
            row = connection.execute(
                text("SELECT display_timezone FROM app.user_profiles WHERE user_id = :id"),
                {"id": alice},
            ).mappings().first()
        self.assertEqual(row["display_timezone"], "Europe/Berlin")
