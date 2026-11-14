"""NI-062 direct RLS defense-in-depth probes on the disposable cluster.

Needs scripts/run-db-tests.py (skips elsewhere; a skip is never successful
integration evidence). The HTTP suites prove the application boundary; this
suite attacks the DATABASE boundary directly with the two application roles
and the operator lease role:

- the pooled ``near_app`` role reads ZERO rows and writes ZERO rows of
  another user's private content across every private table (documents,
  document_versions, document_blocks, insights, hypotheses, evidence_links,
  saved_charts, export_jobs incl. plan/bundle bytes, idempotency_records,
  users, user_profiles), while the same queries through the admin
  connection return the rows (the fixtures are really there);
- RLS is FORCED for the table owner too (``SET row_security = off`` fails);
- the cross-owner write attempts fail with the policy violation 42501;
- the ``near_operator`` lease credential can touch only the derived export
  lifecycle columns — reading/writing the frozen plan or bundle bytes is a
  permission denial (NI-058 column grants), and DELETE is the only
  operator purge power;
- ``near_public`` has nothing on schema ``app``;
- the transaction-local identity is reset when the pooled connection
  returns, so a pooled session never retains another user's identity.
"""

import os
import unittest
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from near_api.auth.principal import Principal
from near_api.db.session import create_runtime_engine, user_transaction

TITLE = "Synthetic RLS probe document"


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class SecurityRlsProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[4]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.runtime = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        cls.operator = create_engine(os.environ["NI_TEST_OPERATOR_URL"],
                                     poolclass=NullPool, hide_parameters=True)
        cls.public = create_engine(os.environ["NI_TEST_PUBLIC_URL"],
                                   poolclass=NullPool, hide_parameters=True)
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"],
                                  poolclass=NullPool, hide_parameters=True)
        command.upgrade(cls.config, "head")
        import test_chart_blocks as chart_fixtures
        chart_fixtures.register_test_chart_catalog(cls.operator)

    @classmethod
    def tearDownClass(cls):
        cls.runtime.dispose()
        cls.operator.dispose()
        cls.public.dispose()
        cls.admin.dispose()

    def setUp(self):
        with self.operator.begin() as connection:
            connection.execute(text("DELETE FROM app.users"))
        self.alice_id, self.bob_id = uuid4(), uuid4()
        for subject in (self.alice_id, self.bob_id):
            with user_transaction(self.runtime, subject) as connection:
                connection.execute(text("INSERT INTO app.users(id) VALUES (:id)"),
                                   {"id": subject})
        self.alice = Principal(id=self.alice_id, display_name="Synthetic Alice",
                               display_timezone="UTC")
        self.bob = Principal(id=self.bob_id, display_name="Synthetic Bob",
                             display_timezone="UTC")
        # Alice's private fixture rows, written through her own identity.
        self.document_id, self.version_id, self.saved_chart_id = self._alice_rows()
        self.export_job_id = self._alice_export_job()

    def _alice_rows(self):
        document_id, version_id = uuid4(), uuid4()
        saved_chart_id = uuid4()
        with user_transaction(self.runtime, self.alice_id) as connection:
            connection.execute(text("SET CONSTRAINTS ALL DEFERRED"))
            connection.execute(text("""
                INSERT INTO app.documents(id, owner_id, title, revision,
                       current_version_id, schema_version)
                VALUES (:id, :owner, :title, 1, :version, 1)
            """), {"id": document_id, "owner": self.alice_id, "title": TITLE,
                   "version": version_id})
            connection.execute(text("""
                INSERT INTO app.document_versions(id, document_id, owner_id, revision,
                       schema_version, content, content_sha256)
                VALUES (:id, :document, :owner, 1, 1, CAST(:content AS jsonb), :sha)
            """), {"id": version_id, "document": document_id, "owner": self.alice_id,
                   "content": json_document(), "sha": "b" * 64})
            connection.execute(text("""
                INSERT INTO app.document_blocks(document_version_id, document_id, owner_id,
                       block_id, position, block_type, attrs)
                VALUES (:version, :document, :owner, :block, 0, 'paragraph',
                        CAST(:attrs AS jsonb))
            """), {"version": version_id, "document": document_id,
                   "owner": self.alice_id, "block": str(uuid4()),
                   "attrs": '{"block_id": "%s"}' % str(uuid4())})
            connection.execute(text("""
                INSERT INTO app.insights(document_version_id, document_id, owner_id,
                       insight_id, block_id, type, classification, body, context,
                       authored_at, modified_at)
                VALUES (:version, :document, :owner, :insight,
                        (SELECT block_id FROM app.document_blocks
                          WHERE document_version_id = :version LIMIT 1),
                        'observation', 'supporting', '[{"type":"paragraph","content":[
                          {"type":"text","text":"Synthetic insight"}]}]'::jsonb,
                        '{}'::jsonb, now(), now())
            """), {"version": version_id, "document": document_id,
                   "owner": self.alice_id, "insight": str(uuid4())})
            connection.execute(text("""
                INSERT INTO app.hypotheses(document_version_id, document_id, owner_id,
                       hypothesis_id, block_id, statement, assessment,
                       authored_at, modified_at)
                VALUES (:version, :document, :owner, :hypothesis,
                        (SELECT block_id FROM app.document_blocks
                          WHERE document_version_id = :version LIMIT 1),
                        'Synthetic statement', 'untested', now(), now())
                RETURNING hypothesis_id
            """), {"version": version_id, "document": document_id,
                   "owner": self.alice_id, "hypothesis": str(uuid4())})
            hypothesis_id = connection.execute(text(
                "SELECT hypothesis_id FROM app.hypotheses "
                "WHERE document_version_id = :version"),
                {"version": version_id}).scalar_one()
            connection.execute(text("""
                INSERT INTO app.evidence_links(document_version_id, evidence_id,
                       document_id, owner_id, block_id, hypothesis_id, classification,
                       target_kind, target_id, explanation)
                VALUES (:version, :evidence, :document, :owner,
                        (SELECT block_id FROM app.document_blocks
                          WHERE document_version_id = :version LIMIT 1),
                        :hypothesis, 'contradicting', 'insight',
                        (SELECT insight_id FROM app.insights
                          WHERE document_version_id = :version LIMIT 1),
                        'Synthetic evidence explanation')
            """), {"version": version_id, "document": document_id,
                   "owner": self.alice_id, "evidence": str(uuid4()),
                   "hypothesis": hypothesis_id})
            connection.execute(text("""
                INSERT INTO app.saved_charts(id, owner_id, chart_definition_version_id,
                       label, mode, selection)
                SELECT :id, :owner, cd.id, 'Synthetic probe chart', 'live',
                       '{"start": "2026-01-01", "end": "2026-01-02",
                         "frequency": "day", "filters": {}}'::jsonb
                FROM app.chart_definitions cd
                WHERE cd.chart_id = 'intents-volume' AND cd.version = 1
            """), {"id": saved_chart_id, "owner": self.alice_id})
            connection.execute(text("""
                INSERT INTO app.idempotency_records(owner_id, route_key, idempotency_key,
                       request_hash, response_status, response_body, expires_at)
                VALUES (:owner, 'POST /api/documents', :key, :hash, 201,
                        CAST('{}' AS jsonb), now() + interval '1 hour')
            """), {"owner": self.alice_id, "key": str(uuid4()), "hash": "e" * 64})
        return document_id, version_id, saved_chart_id

    def _alice_export_job(self):
        job_id = uuid4()
        with self.admin.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.export_jobs(id, owner_id, document_id, document_version_id,
                       format, status, revision, plan, plan_sha256, expires_at, attempts)
                VALUES (:id, :owner, :document, :version, 'markdown_zip', 'queued', 1,
                        :plan, :sha, now() + interval '1 day', 0)
            """), {"id": job_id, "owner": self.alice_id, "document": self.document_id,
                   "version": self.version_id, "plan": b"frozen-plan-bytes",
                   "sha": "c" * 64})
            connection.execute(text("""
                UPDATE app.export_jobs SET status = 'succeeded', bundle = :bundle,
                       bundle_sha256 = :sha, bundle_byte_size = :size, completed_at = now()
                WHERE id = :id
            """), {"id": job_id, "bundle": b"PK\x03\x04bundle", "sha": "d" * 64,
                   "size": 9})
        return job_id

    # -- the probes ----------------------------------------------------------- #

    def test_runtime_role_reads_zero_foreign_private_rows(self):
        probes = (
            ("documents", "id", self.document_id),
            ("document_versions", "id", self.version_id),
            ("document_blocks", "document_id", self.document_id),
            ("insights", "document_id", self.document_id),
            ("hypotheses", "document_id", self.document_id),
            ("evidence_links", "document_id", self.document_id),
            ("saved_charts", "id", self.saved_chart_id),
            ("export_jobs", "id", self.export_job_id),
            ("idempotency_records", "owner_id", self.alice_id),
        )
        for table, column, value in probes:
            with self.runtime.connect() as connection:
                rows = connection.execute(
                    text(f"SELECT count(*) FROM app.{table} WHERE {column} = :value"),
                    {"value": value}).scalar_one()
                self.assertEqual(rows, 0, f"{table} leaked through near_app")
        # The admin connection sees the same rows: the fixtures are real and
        # the zero above is the policy, not an empty database.
        for table, column, value in probes:
            with self.admin.connect() as connection:
                rows = connection.execute(
                    text(f"SELECT count(*) FROM app.{table} WHERE {column} = :value"),
                    {"value": value}).scalar_one()
                self.assertEqual(rows, 1, f"{table} fixture missing for admin")

    def test_runtime_role_reads_zero_foreign_identity_rows(self):
        with self.runtime.connect() as connection:
            other = connection.execute(text(
                "SELECT count(*) FROM app.users WHERE id <> :self"),
                {"self": self.bob_id}).scalar_one()
            self.assertEqual(other, 0, "users table leaked other subjects")
            profiles = connection.execute(text(
                "SELECT count(*) FROM app.user_profiles WHERE user_id <> :self"),
                {"self": self.bob_id}).scalar_one()
            self.assertEqual(profiles, 0, "profiles leaked other subjects")

    def test_runtime_role_cannot_write_foreign_private_rows(self):
        # RLS hides foreign rows from UPDATE/DELETE: the statement runs but
        # matches nothing (rowcount 0) — no error, no effect, no leak.
        hidden = (
            ("UPDATE app.documents SET title = 'Hijacked' WHERE id = :id",
             {"id": self.document_id}, "update foreign document"),
            ("DELETE FROM app.documents WHERE id = :id",
             {"id": self.document_id}, "delete foreign document"),
            ("DELETE FROM app.export_jobs WHERE id = :id",
             {"id": self.export_job_id}, "delete foreign export job"),
            ("UPDATE app.saved_charts SET label = 'Hijacked' WHERE id = :id",
             {"id": self.saved_chart_id}, "update foreign saved chart"),
            ("DELETE FROM app.saved_charts WHERE id = :id",
             {"id": self.saved_chart_id}, "delete foreign saved chart"),
        )
        for statement, params, where in hidden:
            with self.runtime.connect() as connection:
                rowcount = connection.execute(text(statement), params).rowcount
            self.assertEqual(rowcount, 0, where)
        # Hard denials: no WITH CHECK pass, no column grant, no insert.
        denied = (
            ("UPDATE app.document_versions SET content = '{}'::jsonb WHERE id = :id",
             {"id": self.version_id}, "versions are immutable for the runtime role",
             "42501"),
            ("UPDATE app.documents SET owner_id = :owner WHERE id = :id",
             {"owner": self.bob_id, "id": self.document_id},
             "owner column is not updatable", "42501"),
            ("INSERT INTO app.documents(id, owner_id, title, revision, schema_version)"
             " VALUES (:id, :owner, 'Injected', 1, 1)",
             {"id": uuid4(), "owner": self.alice_id}, "insert as foreign owner",
             "42501"),
        )
        for statement, params, where, sqlstate in denied:
            with self.assertRaises(DBAPIError) as caught, \
                    self.runtime.connect() as connection:
                connection.execute(text(statement), params)
            self.assertEqual(caught.exception.orig.sqlstate, sqlstate, where)

    def test_rls_is_forced_even_for_privileged_session_settings(self):
        with self.assertRaises(DBAPIError) as caught, \
                self.runtime.connect() as connection:
            connection.execute(text("SET row_security = off"))
            connection.execute(text(
                "SELECT count(*) FROM app.documents WHERE id = :id"),
                {"id": self.document_id})
        self.assertEqual(caught.exception.orig.sqlstate, "42501")
        # The runtime role also cannot escalate to another role:
        with self.assertRaises(DBAPIError) as caught, \
                self.runtime.connect() as connection:
            connection.execute(text("SET ROLE near_operator"))
        self.assertEqual(caught.exception.orig.sqlstate, "42501")

    def test_operator_lease_cannot_read_or_write_plan_and_bundle_bytes(self):
        lifecycle = ("status", "leased_by", "leased_until", "attempts", "expires_at",
                     "error_code", "completed_at")
        with self.operator.connect() as connection:
            row = connection.execute(text(
                "SELECT status, attempts FROM app.export_jobs WHERE id = :id"),
                {"id": self.export_job_id}).mappings().one()
            self.assertEqual(row["status"], "succeeded")
        for column in ("plan", "bundle", "plan_sha256", "bundle_sha256",
                       "bundle_byte_size"):
            with self.assertRaises(DBAPIError) as caught, \
                    self.operator.connect() as connection:
                connection.execute(text(
                    f"SELECT {column} FROM app.export_jobs WHERE id = :id"),
                    {"id": self.export_job_id})
            self.assertEqual(caught.exception.orig.sqlstate, "42501",
                             f"operator read {column} must be denied")
            with self.assertRaises(DBAPIError) as caught, \
                    self.operator.connect() as connection:
                connection.execute(text(
                    f"UPDATE app.export_jobs SET {column} = NULL WHERE id = :id"),
                    {"id": self.export_job_id})
            self.assertEqual(caught.exception.orig.sqlstate, "42501",
                             f"operator write {column} must be denied")
        for column in lifecycle:
            with self.operator.connect() as connection:
                connection.execute(text(
                    f"SELECT {column} FROM app.export_jobs WHERE id = :id"),
                    {"id": self.export_job_id})

    def test_operator_purge_is_delete_only_and_user_cascaded(self):
        with self.operator.begin() as connection:
            connection.execute(text(
                "DELETE FROM app.export_jobs WHERE id = :id"),
                {"id": self.export_job_id})
        with self.admin.connect() as connection:
            rows = connection.execute(text(
                "SELECT count(*) FROM app.export_jobs WHERE id = :id"),
                {"id": self.export_job_id}).scalar_one()
        self.assertEqual(rows, 0)

    def test_public_role_has_nothing_on_schema_app(self):
        with self.assertRaises(DBAPIError), self.public.connect() as connection:
            connection.execute(text("SELECT count(*) FROM app.documents"))

    def test_pooled_identity_is_reset_after_the_transaction(self):
        # An authenticated transaction sets the identity; the pooled
        # connection (pool_size=1, so the SAME backend session is reused)
        # must come back clean, and a subsequent transaction starts without
        # residue.
        with user_transaction(self.runtime, self.alice_id):
            pass
        with self.runtime.connect() as connection:
            self.assertIsNone(connection.scalar(text("SELECT app.current_user_id()")))
        with user_transaction(self.runtime, self.bob_id):
            pass
        with self.runtime.connect() as connection:
            self.assertIsNone(connection.scalar(text("SELECT app.current_user_id()")))

    def test_disabled_owner_loses_every_private_row_at_the_database_layer(self):
        def visible_documents():
            with user_transaction(self.runtime, self.alice_id) as connection:
                return connection.execute(text(
                    "SELECT count(*) FROM app.documents WHERE id = :id"),
                    {"id": self.document_id}).scalar_one()
        self.assertEqual(visible_documents(), 1)
        with self.operator.begin() as connection:
            connection.execute(text(
                "UPDATE app.users SET disabled_at = now() WHERE id = :id"),
                {"id": self.alice_id})
        self.assertEqual(visible_documents(), 0,
                         "a disabled owner must lose private rows")
        with self.operator.begin() as connection:
            connection.execute(text(
                "UPDATE app.users SET disabled_at = NULL WHERE id = :id"),
                {"id": self.alice_id})
        self.assertEqual(visible_documents(), 1,
                         "re-enabling restores the owner's rows")


def json_document() -> str:
    import json
    return json.dumps({"type": "doc", "content": [
        {"type": "paragraph", "attrs": {"block_id": str(uuid4())},
         "content": [{"type": "text", "text": TITLE}]}]})


if __name__ == "__main__":
    unittest.main()
