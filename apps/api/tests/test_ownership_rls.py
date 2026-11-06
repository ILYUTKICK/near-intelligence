"""NI-019 request-scoped ownership and RLS tests against real PostgreSQL.

Use scripts/run-db-tests.py; direct discovery skips DB cases without its
explicit isolated-cluster environment. A skip is never successful integration
evidence. All identities, titles and document contents are synthetic test
fixtures, never research data.
"""

import hashlib
import json
import os
import unittest
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from near_api.auth.principal import Principal
from near_api.db.security import (
    MAX_PAGE_LIMIT,
    OwnershipViolation,
    ResourceNotFound,
    principal_transaction,
    verified_owner_id,
)
from near_api.db.session import create_runtime_engine, user_transaction
from near_api.repositories import documents as documents_repo

DOCUMENT_CONTENT = {"type": "doc", "content": [{"type": "paragraph"}]}


def sha256_of(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1", "Use scripts/run-db-tests.py")
class OwnershipRlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[3]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.engine = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        cls.operator = create_engine(os.environ["NI_TEST_OPERATOR_URL"], poolclass=NullPool,
                                     hide_parameters=True)
        cls.public = create_engine(os.environ["NI_TEST_PUBLIC_URL"], poolclass=NullPool,
                                   hide_parameters=True)
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"], poolclass=NullPool,
                                  hide_parameters=True)
        command.upgrade(cls.config, "head")

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        cls.operator.dispose()
        cls.public.dispose()
        cls.admin.dispose()

    def setUp(self):
        # The cascade purge itself exercises the operator DELETE policies.
        with self.operator.begin() as connection:
            connection.execute(text("DELETE FROM app.users"))
        self.alice_id, self.bob_id = uuid4(), uuid4()
        for subject, name in ((self.alice_id, "Synthetic Alice"), (self.bob_id, "Synthetic Bob")):
            with user_transaction(self.engine, subject) as connection:
                connection.execute(text("INSERT INTO app.users(id) VALUES (:id)"), {"id": subject})
                connection.execute(text("""INSERT INTO app.user_profiles(user_id, display_name)
                                          VALUES (:id, :name)"""), {"id": subject, "name": name})

    def principal(self, subject: UUID) -> Principal:
        return Principal(id=subject, display_name="Synthetic", display_timezone="UTC")

    def alice(self) -> Principal:
        return self.principal(self.alice_id)

    def bob(self) -> Principal:
        return self.principal(self.bob_id)

    def create_document_fixture(self, principal: Principal, title: str, *, versions: int = 1):
        with principal_transaction(self.engine, principal) as connection:
            document_id = documents_repo.create_document(connection, principal, title=title,
                                                         schema_version=1)
            version_ids = [documents_repo.create_version(
                connection, principal, document_id, content=DOCUMENT_CONTENT,
                content_sha256=sha256_of(DOCUMENT_CONTENT)) for _ in range(versions)]
            return document_id, version_ids

    def test_01_private_tables_are_force_rls_with_expected_policies(self):
        with self.admin.connect() as connection:
            tables = connection.execute(text("""
                SELECT relname, relrowsecurity, relforcerowsecurity, pg_get_userbyid(relowner)
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'app'
                  AND relname IN ('documents', 'document_versions', 'document_blocks')
            """)).all()
            self.assertEqual(len(tables), 3)
            self.assertTrue(all(row[1:] == (True, True, "near_migrator") for row in tables))
            policies = connection.execute(text("""
                SELECT tablename, policyname, roles FROM pg_policies
                WHERE schemaname = 'app'
                  AND tablename IN ('documents', 'document_versions', 'document_blocks')
                ORDER BY tablename, policyname
            """)).all()
        expected = {(table, f"{table}_{action}") for table, actions in (
            ("documents", ("self_select", "self_insert", "self_update", "self_delete",
                           "operator_delete")),
            ("document_versions", ("self_select", "self_insert", "self_delete",
                                   "operator_delete")),
            ("document_blocks", ("self_select", "self_insert", "self_delete",
                                 "operator_delete")),
        ) for action in actions}
        self.assertEqual({(row[0], row[1]) for row in policies}, expected)
        for table, policy, roles in policies:
            with self.subTest(policy=policy):
                expected_role = "near_operator" if policy.endswith("operator_delete") else "near_app"
                self.assertIn(expected_role, roles)
        with self.admin.connect() as connection:
            self.assertTrue(connection.scalar(text(
                "SELECT has_function_privilege('near_app', 'app.identity_is_active()', 'EXECUTE')")))
            self.assertFalse(connection.scalar(text(
                "SELECT has_function_privilege('near_operator', 'app.identity_is_active()', 'EXECUTE')")))
            self.assertFalse(connection.scalar(text(
                "SELECT has_function_privilege('near_public', 'app.identity_is_active()', 'EXECUTE')")))

    def test_document_crud_is_isolated_between_two_users(self):
        alice, bob = self.alice(), self.bob()
        with principal_transaction(self.engine, alice) as connection:
            document_id = documents_repo.create_document(connection, alice,
                                                         title="Alice research", schema_version=1)
        with principal_transaction(self.engine, bob) as connection:
            # Reading, renaming, deleting and even listing Alice's data from
            # Bob's context yield the same empty result as a missing id.
            with self.assertRaises(ResourceNotFound):
                documents_repo.get_document(connection, bob, document_id)
            with self.assertRaises(ResourceNotFound):
                documents_repo.rename_document(connection, bob, document_id, title="hijacked")
            with self.assertRaises(ResourceNotFound):
                documents_repo.delete_document(connection, bob, document_id)
            self.assertEqual(documents_repo.list_documents(connection, bob).total, 0)
            bob_document = documents_repo.create_document(connection, bob, title="Bob research",
                                                          schema_version=1)
        with principal_transaction(self.engine, alice) as connection:
            page = documents_repo.list_documents(connection, alice)
            self.assertEqual(page.total, 1)
            self.assertEqual(page.items[0].id, document_id)
            self.assertEqual(page.items[0].owner_id, self.alice_id)
            self.assertEqual(documents_repo.get_document(connection, alice, document_id).title,
                             "Alice research")
            self.assertEqual(documents_repo.rename_document(
                connection, alice, document_id, title="Alice research v2").title, "Alice research v2")
        with principal_transaction(self.engine, bob) as connection:
            self.assertEqual(documents_repo.list_documents(connection, bob, search="Alice").total, 0)
            self.assertEqual(documents_repo.list_documents(connection, bob).total, 1)
            self.assertEqual(documents_repo.get_document(connection, bob, bob_document).owner_id,
                             self.bob_id)
        with principal_transaction(self.engine, alice) as connection:
            documents_repo.delete_document(connection, alice, document_id)
            with self.assertRaises(ResourceNotFound):
                documents_repo.get_document(connection, alice, document_id)
        with self.admin.connect() as connection:
            # The cascade removed the document's versions; Bob's row survives.
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.document_versions")), 0)
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.documents")), 1)

    def test_search_and_pagination_are_scoped_by_owner_before_limits(self):
        alice, bob = self.alice(), self.bob()
        with principal_transaction(self.engine, alice) as connection:
            for number in range(25):
                documents_repo.create_document(connection, alice, title=f"alpha-{number:02d}",
                                               schema_version=1)
            for number in range(3):
                documents_repo.create_document(connection, alice, title=f"beta-{number:02d}",
                                               schema_version=1)
        with principal_transaction(self.engine, bob) as connection:
            for number in range(2):
                documents_repo.create_document(connection, bob, title=f"alpha-Bob-{number}",
                                               schema_version=1)
        with principal_transaction(self.engine, alice) as connection:
            first = documents_repo.list_documents(connection, alice, search="alpha", limit=10)
            self.assertEqual((first.total, len(first.items), first.limit, first.offset),
                             (25, 10, 10, 0))
            self.assertTrue(all(item.owner_id == self.alice_id for item in first.items))
            second = documents_repo.list_documents(connection, alice, search="alpha", limit=10,
                                                   offset=10)
            third = documents_repo.list_documents(connection, alice, search="alpha", limit=10,
                                                  offset=20)
            self.assertEqual(len(third.items), 5)
            seen = {item.id for item in (*first.items, *second.items, *third.items)}
            self.assertEqual(len(seen), 25)
            self.assertEqual(documents_repo.list_documents(connection, alice).total, 28)
        with principal_transaction(self.engine, bob) as connection:
            scoped = documents_repo.list_documents(connection, bob, search="alpha", limit=10)
            self.assertEqual(scoped.total, 2)
            self.assertTrue(all(item.owner_id == self.bob_id for item in scoped.items))
            self.assertEqual(documents_repo.list_documents(connection, bob).total, 2)
        with principal_transaction(self.engine, alice) as connection:
            documents_repo.create_document(connection, alice, title="100%_literal", schema_version=1)
            # Wildcards in the search text match literally, not as patterns.
            self.assertEqual(documents_repo.list_documents(connection, alice,
                                                           search="100%_literal").total, 1)
            self.assertEqual(documents_repo.list_documents(connection, alice, search="%").total, 1)
            self.assertEqual(documents_repo.list_documents(connection, alice, search="_").total, 1)
        for limit, offset in ((0, 0), (MAX_PAGE_LIMIT + 1, 0), (10, -1), (True, 0), (None, -5)):
            with self.subTest(limit=limit, offset=offset), \
                    principal_transaction(self.engine, alice) as connection:
                with self.assertRaises(ValueError):
                    documents_repo.list_documents(connection, alice, search="alpha",
                                                  limit=limit, offset=offset)

    def test_nested_private_references_reject_cross_owner_access(self):
        alice, bob = self.alice(), self.bob()
        alice_document, alice_versions = self.create_document_fixture(alice, "Alice nested",
                                                                      versions=2)
        alice_version = alice_versions[0]
        with principal_transaction(self.engine, alice) as connection:
            documents_repo.add_block(connection, alice, alice_document, alice_version,
                                     block_id=uuid4(), block_type="paragraph", position=0)
        bob_document, bob_versions = self.create_document_fixture(bob, "Bob nested")
        with principal_transaction(self.engine, bob) as connection:
            with self.assertRaises(ResourceNotFound):
                documents_repo.get_version(connection, bob, alice_document, alice_version)
            with self.assertRaises(ResourceNotFound):
                documents_repo.list_versions(connection, bob, alice_document)
            with self.assertRaises(ResourceNotFound):
                documents_repo.get_block(connection, bob, alice_document, alice_version, uuid4())
            with self.assertRaises(ResourceNotFound):
                documents_repo.list_blocks(connection, bob, alice_document, alice_version)
            with self.assertRaises(ResourceNotFound):
                documents_repo.add_block(connection, bob, alice_document, alice_version,
                                         block_id=uuid4(), block_type="paragraph", position=0)
            # A version id from Bob's own document never resolves inside
            # Alice's document, and vice versa.
            with self.assertRaises(ResourceNotFound):
                documents_repo.get_version(connection, bob, alice_document, bob_versions[0])
        with principal_transaction(self.engine, alice) as connection:
            version = documents_repo.get_version(connection, alice, alice_document, alice_version)
            self.assertEqual(version.document_id, alice_document)
            self.assertEqual(version.owner_id, self.alice_id)
            self.assertEqual(documents_repo.list_blocks(
                connection, alice, alice_document, alice_version).total, 1)
            parent = documents_repo.add_block(connection, alice, alice_document,
                                              alice_versions[1], block_id=uuid4(),
                                              block_type="container", position=0)
            documents_repo.add_block(connection, alice, alice_document, alice_versions[1],
                                     block_id=uuid4(), block_type="paragraph", position=0,
                                     parent_block_id=parent)
            self.assertEqual(documents_repo.list_blocks(
                connection, alice, alice_document, alice_versions[1]).total, 2)
            self.assertEqual(documents_repo.list_versions(connection, alice,
                                                          alice_document).total, 2)

    def test_cross_owner_foreign_key_and_column_grant_probes(self):
        alice, bob = self.alice(), self.bob()
        alice_document, alice_versions = self.create_document_fixture(alice, "Alice probe",
                                                                      versions=2)
        bob_document, bob_versions = self.create_document_fixture(bob, "Bob probe")
        probes = (
            # RLS WITH CHECK rejects writing the foreign owner first...
            ("INSERT INTO app.document_versions(id, document_id, owner_id, revision, schema_version,"
             " content, content_sha256) VALUES (:id, :document, :owner, 424242, 1, CAST(:content AS jsonb), :sha)",
             {"id": uuid4(), "document": alice_document, "owner": self.bob_id,
              "content": json.dumps(DOCUMENT_CONTENT), "sha": sha256_of(DOCUMENT_CONTENT)},
             "42501"),
            # ...and the composite FK rejects the same-owner/foreign-document pair.
            ("INSERT INTO app.document_versions(id, document_id, owner_id, revision, schema_version,"
             " content, content_sha256) VALUES (:id, :document, :owner, 424242, 1, CAST(:content AS jsonb), :sha)",
             {"id": uuid4(), "document": bob_document, "owner": self.alice_id,
              "content": json.dumps(DOCUMENT_CONTENT), "sha": sha256_of(DOCUMENT_CONTENT)},
             "23503"),
            ("INSERT INTO app.document_blocks(document_version_id, document_id, owner_id, block_id,"
             " position, block_type) VALUES (:version, :document, :owner, :block, 0, 'paragraph')",
             {"version": alice_versions[0], "document": alice_document, "owner": self.bob_id,
              "block": uuid4()}, "42501"),
            ("INSERT INTO app.document_blocks(document_version_id, document_id, owner_id, block_id,"
             " position, block_type) VALUES (:version, :document, :owner, :block, 0, 'paragraph')",
             {"version": bob_versions[0], "document": alice_document, "owner": self.alice_id,
              "block": uuid4()}, "23503"),
        )
        for statement, params, state in probes:
            with self.subTest(state=state), self.assertRaises(DBAPIError) as raised:
                with user_transaction(self.engine, self.alice_id) as connection:
                    connection.execute(text(statement), params)
            self.assertEqual(raised.exception.orig.sqlstate, state)
        # A parent block from a different version of the same document is a
        # dangling reference: the parent FK covers (version, block) pairs.
        with principal_transaction(self.engine, alice) as connection:
            foreign_parent = documents_repo.add_block(connection, alice, alice_document,
                                                      alice_versions[1], block_id=uuid4(),
                                                      block_type="container", position=0)
        with self.assertRaises(DBAPIError) as raised:
            with user_transaction(self.engine, self.alice_id) as connection:
                connection.execute(text(
                    "INSERT INTO app.document_blocks(document_version_id, document_id, owner_id,"
                    " block_id, parent_block_id, position, block_type)"
                    " VALUES (:version, :document, :owner, :block, :parent, 1, 'paragraph')"),
                    {"version": alice_versions[0], "document": alice_document,
                     "owner": self.alice_id, "block": uuid4(), "parent": foreign_parent})
        self.assertEqual(raised.exception.orig.sqlstate, "23503")
        # The owner column is not in the runtime UPDATE grant list.
        with self.assertRaises(DBAPIError) as raised:
            with user_transaction(self.engine, self.alice_id) as connection:
                connection.execute(text("UPDATE app.documents SET owner_id=:bob WHERE id=:id"),
                                   {"bob": self.bob_id, "id": alice_document})
        self.assertEqual(raised.exception.orig.sqlstate, "42501")
        # Granted mutations still stop at the foreign rows (RLS USING).
        with user_transaction(self.engine, self.alice_id) as connection:
            self.assertEqual(connection.execute(
                text("UPDATE app.documents SET title='x' WHERE id=:id"),
                {"id": bob_document}).rowcount, 0)
            self.assertEqual(connection.execute(
                text("DELETE FROM app.document_versions WHERE id=:id"),
                {"id": bob_versions[0]}).rowcount, 0)
        # Versions are immutable for the runtime role: no UPDATE grant at all.
        with self.assertRaises(DBAPIError) as raised:
            with user_transaction(self.engine, self.alice_id) as connection:
                connection.execute(text("UPDATE app.document_versions SET content='{}'::jsonb"
                                        " WHERE id=:id"), {"id": alice_versions[0]})
        self.assertEqual(raised.exception.orig.sqlstate, "42501")
        # Payload ownership fields are rejected before any SQL runs.
        with self.assertRaises(OwnershipViolation):
            verified_owner_id(self.bob_id, self.alice_id)
        with principal_transaction(self.engine, alice) as connection:
            with self.assertRaises(OwnershipViolation):
                documents_repo.create_document(connection, alice, title="x", schema_version=1,
                                               owner_id=self.bob_id)
            with self.assertRaises(OwnershipViolation):
                documents_repo.create_version(connection, alice, alice_document, content={},
                                              content_sha256=sha256_of({}), owner_id=self.bob_id)
            with self.assertRaises(OwnershipViolation):
                documents_repo.add_block(connection, alice, alice_document, alice_versions[0],
                                         block_id=uuid4(), block_type="paragraph", position=0,
                                         owner_id=self.bob_id)
        # The rejected payload wrote nothing.
        with user_transaction(self.engine, self.alice_id) as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.documents")), 1)
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.document_versions")), 2)

    def test_pooled_identity_reset_between_users_for_private_tables(self):
        alice, bob = self.alice(), self.bob()
        alice_document, _ = self.create_document_fixture(alice, "Alice pooled")
        self.create_document_fixture(bob, "Bob pooled")
        with principal_transaction(self.engine, alice) as connection:
            backend = connection.scalar(text("SELECT pg_backend_pid()"))
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.documents")), 1)
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT pg_backend_pid()")), backend)
            self.assertIsNone(connection.scalar(text("SELECT app.current_user_id()")))
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.documents")), 0)
        with self.assertRaisesRegex(RuntimeError, "synthetic rollback"):
            with principal_transaction(self.engine, alice) as connection:
                documents_repo.create_document(connection, alice, title="aborted", schema_version=1)
                raise RuntimeError("synthetic rollback")
        with user_transaction(self.engine, self.bob_id) as connection:
            self.assertEqual(connection.scalar(text("SELECT pg_backend_pid()")), backend)
            self.assertEqual(connection.scalar(text("SELECT app.current_user_id()")), self.bob_id)
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.documents")), 1)
            self.assertEqual(connection.scalar(
                text("SELECT count(*) FROM app.documents WHERE id = :id"),
                {"id": alice_document}), 0)
        # A session-level identity leak outside the helper is cleared by the
        # pool reset, and the aborted insert left no row behind.
        with self.engine.begin() as connection:
            connection.execute(text("SELECT set_config('app.user_id', :id, false)"),
                               {"id": str(self.alice_id)})
        with self.engine.connect() as connection:
            self.assertIsNone(connection.scalar(text("SELECT app.current_user_id()")))
        with self.admin.connect() as connection:
            self.assertEqual(connection.scalar(
                text("SELECT count(*) FROM app.documents WHERE title = 'aborted'")), 0)
        with user_transaction(self.engine, None) as connection:
            self.assertIsNone(connection.scalar(text("SELECT app.current_user_id()")))
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.documents")), 0)

    def test_runtime_role_cannot_escalate_on_private_tables(self):
        for statement in ("SET ROLE near_operator", "SET ROLE near_migrator", "SET ROLE near_public",
                          "ALTER TABLE app.documents DISABLE ROW LEVEL SECURITY",
                          "TRUNCATE app.document_versions CASCADE",
                          "CREATE TABLE app.forbidden(id int)",
                          "DROP TABLE app.document_blocks"):
            with self.subTest(statement=statement), self.assertRaises(DBAPIError) as raised:
                with user_transaction(self.engine, self.alice_id) as connection:
                    connection.execute(text(statement))
            self.assertEqual(raised.exception.orig.sqlstate, "42501")
        with self.assertRaises(DBAPIError) as raised:
            with user_transaction(self.engine, self.alice_id) as connection:
                connection.execute(text("SET LOCAL row_security=off"))
                connection.execute(text("SELECT count(*) FROM app.documents"))
        self.assertEqual(raised.exception.orig.sqlstate, "42501")
        with self.admin.connect() as connection:
            rows = connection.execute(text("""
                SELECT rolname, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication
                FROM pg_roles
                WHERE rolname IN ('near_app', 'near_operator', 'near_migrator', 'near_public')
            """)).all()
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(not any(row[1:]) for row in rows))

    def test_operator_and_public_roles_cannot_touch_private_content(self):
        alice = self.alice()
        self.create_document_fixture(alice, "Alice operator")
        denied = (
            ("SELECT count(*) FROM app.documents", {}),
            ("INSERT INTO app.documents(id, owner_id, title, schema_version)"
             " VALUES (gen_random_uuid(), :owner, 'x', 1)", {"owner": self.alice_id}),
            ("UPDATE app.documents SET title = 'x'", {}),
            ("SELECT content FROM app.document_versions", {}),
            ("UPDATE app.document_versions SET content = '{}'::jsonb", {}),
            ("INSERT INTO app.document_blocks(document_version_id, document_id, owner_id, block_id,"
             " position, block_type) SELECT id, id, id, id, 0, 'x' FROM app.documents", {}),
        )
        for statement, params in denied:
            with self.subTest(statement=statement), self.assertRaises(DBAPIError) as raised:
                with self.operator.begin() as connection:
                    connection.execute(text(statement), params)
            self.assertEqual(raised.exception.orig.sqlstate, "42501")
        # The narrow operator power: purge by deletion, never by reading.
        with self.operator.begin() as connection:
            self.assertEqual(connection.execute(text("DELETE FROM app.documents")).rowcount, 1)
        with self.admin.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.document_versions")), 0)
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.document_blocks")), 0)
        self.create_document_fixture(alice, "Alice purge")
        with self.operator.begin() as connection:
            connection.execute(text("DELETE FROM app.users WHERE id = :id"), {"id": self.alice_id})
        with self.admin.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.documents")), 0)
        # The public query context connects but has nothing on schema app.
        with self.public.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT current_user")), "near_public")
        for statement in ("SELECT count(*) FROM app.documents",
                          "SELECT count(*) FROM app.users",
                          "SELECT count(*) FROM app.user_profiles"):
            with self.subTest(statement=statement), self.assertRaises(DBAPIError) as raised, \
                    self.public.connect() as connection:
                connection.execute(text(statement))
            self.assertEqual(raised.exception.orig.sqlstate, "42501")

    def test_disabled_owner_loses_private_access_fail_closed(self):
        alice = self.alice()
        alice_document, _ = self.create_document_fixture(alice, "Alice disabled")
        with self.operator.begin() as connection:
            connection.execute(text("UPDATE app.users SET disabled_at = now() WHERE id = :id"),
                               {"id": self.alice_id})
        with user_transaction(self.engine, self.alice_id) as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.documents")), 0)
            self.assertEqual(connection.execute(
                text("DELETE FROM app.documents WHERE id = :id"),
                {"id": alice_document}).rowcount, 0)
        with self.assertRaises(DBAPIError) as raised:
            with user_transaction(self.engine, self.alice_id) as connection:
                connection.execute(text("INSERT INTO app.documents(id, owner_id, title,"
                                        " schema_version) VALUES (:id, :owner, 'blocked', 1)"),
                                   {"id": uuid4(), "owner": self.alice_id})
        self.assertEqual(raised.exception.orig.sqlstate, "42501")
        # The rejection is state-dependent: restoring the account restores it.
        with self.operator.begin() as connection:
            connection.execute(text("UPDATE app.users SET disabled_at = NULL WHERE id = :id"),
                               {"id": self.alice_id})
        with principal_transaction(self.engine, alice) as connection:
            self.assertEqual(documents_repo.list_documents(connection, alice).total, 1)


if __name__ == "__main__":
    unittest.main()
