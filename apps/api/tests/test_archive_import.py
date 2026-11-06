"""NI-027 real PostgreSQL tests for the read-only archive import.

All archive bytes, cohorts and providers are synthetic (see archive_fixture).
Use scripts/run-db-tests.py; direct discovery skips DB cases without its
explicit isolated-cluster environment. A skip is never integration evidence.
"""

import datetime as dt
import hashlib
import io
import json
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from archive_fixture import (
    ALPHA_COHORT,
    ALPHA_PAYLOAD,
    BETA_COHORT,
    SECRET_TOKEN,
    build_archive,
    tree_digest,
    write_registry,
)

from near_api.db.session import create_runtime_engine, user_transaction
from near_api.ingestion import archive


def run_import(root: Path, manifest: Path, registry: Path, database_url: str | None) -> dict:
    stdout = io.StringIO()
    arguments = ["--archive-root", str(root), "--manifest", str(manifest),
                 "--cohorts", str(registry)]
    if database_url is None:
        arguments.insert(0, "--dry-run")
    else:
        arguments += ["--database-url", database_url]
    with redirect_stdout(stdout):
        code = archive.main(arguments)
    assert code == archive.EXIT_OK, f"import failed with exit code {code}"
    return json.loads(stdout.getvalue())


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1", "Use scripts/run-db-tests.py")
class ArchiveImportDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[3]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.operator = create_engine(os.environ["NI_TEST_OPERATOR_URL"], poolclass=NullPool,
                                     hide_parameters=True)
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"], poolclass=NullPool,
                                  hide_parameters=True)
        cls.runtime = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        command.upgrade(cls.config, "head")

    @classmethod
    def tearDownClass(cls):
        cls.operator.dispose()
        cls.admin.dispose()
        cls.runtime.dispose()

    def setUp(self):
        self.directory_base = Path(os.environ["NI_TEST_TMP_DIR"])
        self.work = self.directory_base / f"archive-{uuid4().hex}"
        self.work.mkdir(parents=True)
        self.addCleanup(self._cleanup_work)
        self.root = self.work / "handoff"
        self.root.mkdir()
        self.manifest = build_archive(self.root)
        self.registry = write_registry(self.work)
        self.archive_root = self.root
        self.before_digest = tree_digest(self.root)
        self.database_url = os.environ["NI_TEST_OPERATOR_URL"]

    def _cleanup_work(self):
        import shutil
        shutil.rmtree(self.work, ignore_errors=True)

    def counts(self):
        with self.operator.connect() as connection:
            return {
                table: connection.scalar(text(f"SELECT count(*) FROM app.{table}"))
                for table in ("import_batches", "imported_files", "source_runs", "sources")
            }

    def table_state(self):
        with self.operator.connect() as connection:
            return {
                "import_batches": connection.execute(text(
                    "SELECT manifest_sha256, manifest_file_count, verified_bytes FROM app.import_batches"
                )).all(),
                "imported_files": connection.execute(text(
                    "SELECT relative_path, sha256, byte_size, file_role, coverage_scope FROM app.imported_files"
                )).all(),
                "source_runs": connection.execute(text(
                    "SELECT query_identity, retrieval_utc FROM app.source_runs")).all(),
            }

    def test_01_import_twice_is_idempotent(self):
        first = run_import(self.archive_root, self.manifest, self.registry, self.database_url)
        self.assertTrue(first["imported"])
        self.assertEqual(first["files"], 8)
        self.assertEqual(first["cohorts"], [ALPHA_COHORT, BETA_COHORT])
        state = self.table_state()
        counts = self.counts()
        self.assertEqual(counts["import_batches"], 1)
        self.assertEqual(counts["imported_files"], 8)
        self.assertGreaterEqual(counts["source_runs"], 2)

        second = run_import(self.archive_root, self.manifest, self.registry, self.database_url)
        self.assertFalse(second["imported"])
        self.assertEqual(second["changes"], 0)
        self.assertEqual(second["batch_id"], first["batch_id"])
        self.assertEqual(self.table_state(), state)
        self.assertEqual(self.counts(), counts)

    def test_02_bad_hash_rejects_the_whole_batch(self):
        before = self.counts()
        target = self.root / f"research/{ALPHA_COHORT}/data/response.json"
        target.write_text(target.read_text() + "corruption\n")
        code = archive.main(["--archive-root", str(self.root), "--manifest", str(self.manifest),
                             "--cohorts", str(self.registry), "--database-url", self.database_url])
        self.assertEqual(code, archive.EXIT_VERIFICATION)
        self.assertEqual(self.counts(), before)

    def test_03_missing_file_rejects_the_whole_batch(self):
        before = self.counts()
        (self.root / f"research/{BETA_COHORT}/data/snapshot.json").unlink()
        code = archive.main(["--archive-root", str(self.root), "--manifest", str(self.manifest),
                             "--cohorts", str(self.registry), "--database-url", self.database_url])
        self.assertEqual(code, archive.EXIT_VERIFICATION)
        self.assertEqual(self.counts(), before)

    def test_04_extra_file_inside_the_subtree_rejects_the_batch(self):
        before = self.counts()
        (self.root / f"research/{ALPHA_COHORT}/data/extra.json").write_text("{}\n")
        code = archive.main(["--archive-root", str(self.root), "--manifest", str(self.manifest),
                             "--cohorts", str(self.registry), "--database-url", self.database_url])
        self.assertEqual(code, archive.EXIT_VERIFICATION)
        self.assertEqual(self.counts(), before)

    def test_05_stored_metadata_matches_source_and_hides_credentials(self):
        summary = run_import(self.archive_root, self.manifest, self.registry, self.database_url)
        relative = f"research/{ALPHA_COHORT}/data/response.json"
        with self.operator.connect() as connection:
            row = connection.execute(text("""
                SELECT f.sha256, f.byte_size, f.file_role, f.coverage_scope, f.coverage_start,
                       f.coverage_end_exclusive, f.source_id, f.license_status, f.metadata
                FROM app.imported_files f
                WHERE f.relative_path = :path
            """), {"path": relative}).mappings().one()
            batch = connection.execute(text("""
                SELECT manifest_sha256, registry_sha256, manifest_file_count, verified_bytes,
                       cohort_count, source_count FROM app.import_batches
            """)).mappings().one()
            run_row = connection.execute(text("""
                SELECT source_id, query_identity, retrieval_utc, byte_count
                FROM app.source_runs WHERE query_identity LIKE 'https://api.example-provider.test%'
            """)).mappings().one()
        stored_bytes = (self.root / relative).read_bytes()
        self.assertEqual(row["sha256"], hashlib.sha256(stored_bytes).hexdigest())
        self.assertEqual(row["byte_size"], len(stored_bytes))
        # Source-vs-stored metadata: the cohort manifest documents the same
        # bytes/URL/saved_at that the import recorded.
        cohort_manifest = json.loads(
            (self.root / f"research/{ALPHA_COHORT}/manifest.json").read_text())
        documented = cohort_manifest["http_sources"]["data/response.json"]
        self.assertEqual(row["metadata"]["http"]["url"],
                         "https://api.example-provider.test/v1/data?api_key=[redacted]")
        self.assertEqual(dt.datetime.fromisoformat(row["metadata"]["http"]["saved_at_utc"]),
                         dt.datetime.fromisoformat(documented["saved_at_utc"]))
        self.assertEqual(row["metadata"]["http"]["http_status"], documented["http_status"])
        self.assertEqual(row["file_role"], "raw")
        self.assertEqual(row["coverage_scope"], "aggregate_window")
        self.assertEqual(row["coverage_start"].isoformat(), "2026-01-01")
        self.assertEqual(row["coverage_end_exclusive"].isoformat(), "2026-01-31")
        self.assertEqual(row["source_id"], "SRC-EXAMPLE")
        self.assertEqual(row["license_status"], "unverified")
        self.assertEqual(run_row["source_id"], "SRC-EXAMPLE")
        self.assertIsNotNone(run_row["retrieval_utc"])
        self.assertEqual(run_row["byte_count"], len(stored_bytes))
        self.assertEqual(batch["manifest_sha256"], summary["manifest_sha256"])
        self.assertEqual(batch["manifest_file_count"], 8)
        self.assertEqual(batch["cohort_count"], 2)
        self.assertEqual(batch["source_count"], 1)
        # No credential-bearing or raw content string anywhere in the DB.
        for needle in (SECRET_TOKEN, ALPHA_PAYLOAD):
            for table, column in (("import_batches", "manifest_path"), ("imported_files", "metadata"),
                                  ("imported_files", "relative_path"), ("source_runs", "metadata"),
                                  ("source_runs", "query_identity"), ("sources", "lineage")):
                hits = connection_hits(self.operator, table, column, needle)
                self.assertEqual(hits, 0, f"{needle!r} leaked into app.{table}.{column}")

    def test_06_archive_bytes_unchanged_after_both_imports(self):
        run_import(self.archive_root, self.manifest, self.registry, self.database_url)
        run_import(self.archive_root, self.manifest, self.registry, self.database_url)
        self.assertEqual(tree_digest(self.root), self.before_digest)

    def test_07_runtime_cannot_write_or_read_import_tables(self):
        run_import(self.archive_root, self.manifest, self.registry, self.database_url)
        subject = uuid4()
        with user_transaction(self.runtime, subject) as connection:
            connection.execute(text("INSERT INTO app.users(id) VALUES (:id)"), {"id": subject})
        with user_transaction(self.runtime, subject) as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM app.sources")), 1)
        forbidden = (
            "SELECT count(*) FROM app.import_batches",
            "SELECT count(*) FROM app.imported_files",
            "SELECT count(*) FROM app.source_runs",
            "INSERT INTO app.import_batches(id, manifest_sha256, registry_sha256, manifest_path,"
            " archive_root, manifest_file_count, verified_bytes, cohort_count, source_count,"
            " importer) VALUES (gen_random_uuid(), '" + "a" * 64 + "', '" + "b" * 64 +
            "', 'x', 'y', 1, 1, 1, 0, 'attacker')",
            "DELETE FROM app.sources",
        )
        for statement in forbidden:
            with self.subTest(statement=statement[:60]):
                with self.assertRaises(DBAPIError) as raised:
                    with user_transaction(self.runtime, subject) as connection:
                        connection.execute(text(statement))
                self.assertEqual(raised.exception.orig.sqlstate, "42501")

    def test_08_operator_credential_is_enforced(self):
        from near_api.ingestion.archive import OperatorDatabaseError
        with self.assertRaises(OperatorDatabaseError):
            archive.create_operator_engine(os.environ["NI_TEST_RUNTIME_URL"])
        with self.assertRaises(OperatorDatabaseError):
            archive.create_operator_engine(os.environ["MIGRATION_DATABASE_URL"])

    def test_09_migration_round_trip(self):
        command.downgrade(self.config, "0002_private_documents")
        with self.admin.connect() as connection:
            self.assertIsNone(connection.scalar(text("SELECT to_regclass('app.import_batches')")))
            self.assertIsNone(connection.scalar(text("SELECT to_regclass('app.sources')")))
        command.upgrade(self.config, "head")
        command.check(self.config)
        with self.admin.connect() as connection:
            tables = connection.execute(text("""
                SELECT relname, relrowsecurity, relforcerowsecurity, pg_get_userbyid(relowner)
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'app'
                  AND relname IN ('sources','import_batches','imported_files','source_runs')
            """)).all()
        self.assertEqual(len(tables), 4)
        self.assertTrue(all(row[1:] == (True, True, "near_migrator") for row in tables))


def connection_hits(engine, table: str, column: str, needle: str) -> int:
    with engine.connect() as connection:
        result = connection.execute(text(
            f"SELECT count(*) FROM app.{table} WHERE CAST({column} AS text) LIKE :needle"),
            {"needle": f"%{needle}%"})
        return result.scalar_one()


if __name__ == "__main__":
    unittest.main()
