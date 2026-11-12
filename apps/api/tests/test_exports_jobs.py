"""NI-058 tests, database part: the export job lifecycle end to end.

Needs scripts/run-db-tests.py (a disposable loopback PostgreSQL cluster);
direct discovery skips the class — a skip is never successful integration
evidence. Covered guarantees (all fixtures visibly synthetic):

- full export: create -> claim -> render (the REAL pinned Node renderer) ->
  poll -> download -> unzip -> every manifest hash and research.md link
  validates, and the manifest pins the exact revision (revision number,
  content hash, title);
- idempotent create: same-key replay returns the SAME job, same-key
  different-body is a 409, malformed key is 422, a new key creates a new
  job;
- superseded revision refusal (typed 409 REVISION_NOT_ACKNOWLEDGED) and the
  edit-during-export guarantee: a new revision after job creation leaves
  the frozen plan byte-identical and the bundle's revision pins unchanged;
- crash/retry idempotency: an expired lease re-claims the SAME job
  (attempts 2) and the retry commits exactly one succeeded job; the attempt
  cap turns a zombie into a typed failed row;
- TTL: a past-TTL job reads ``expired`` at poll time, downloads as typed
  410 EXPORT_EXPIRED, is never claimed, and the sweep persists the state
  and clears the bytes;
- typed download refusals for queued/running (409) and failed (409 with
  the error code);
- owner matrix: Bob cannot create, poll or download Alice's export (one
  generic 404) at the HTTP layer with the real dependency chain, for both
  documented formats;
- the PDF format success path (NI-059): create -> worker render -> download
  streams application/pdf with the server-controlled filename, and the
  same-key different-format idempotency conflict stays typed 409;
- a corrupted stored plan fails the worker typed;
- migration 0012 + 0016 downgrade/upgrade round trip with the model mirror.
"""

import copy
import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from datetime import date
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from near_api.auth import principal as principal_module
from near_api.auth.principal import Principal
from near_api.db.session import create_runtime_engine, user_transaction
from near_api.documents import service
from near_api.exports.worker import claim_job, process_one, sweep_expired
from near_api.main import app
from near_api.schemas.common import ErrorResponse
import test_chart_blocks as chart_fixtures
import test_delivery_apis as data_fixture
import test_documents as document_fixtures
from test_documents import _StubVerifier, _verified

SHA256 = "a" * 64
TS = "2026-11-09T12:00:00Z"


def selection() -> dict:
    return {"start": "2026-01-01", "end": "2026-01-08", "frequency": "day",
            "filters": {}}


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class ExportJobDatabaseTests(unittest.TestCase):
    """The owned export job lifecycle on the disposable cluster."""

    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[3]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.engine = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=2)
        cls.operator = create_engine(os.environ["NI_TEST_OPERATOR_URL"], poolclass=NullPool,
                                     hide_parameters=True)
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"], poolclass=NullPool,
                                  hide_parameters=True)
        command.upgrade(cls.config, "head")
        chart_fixtures.register_test_chart_catalog(cls.operator)
        cls.publish_synthetic_model_run()
        cls.citation_id = cls.insert_public_citation()

    @classmethod
    def publish_synthetic_model_run(cls):
        from near_api.research.publication import load_bundle, verify_bundle
        from near_api.research.publish_store import publish_run
        from test_models_publication import (
            MANIFEST_KEYS,
            bundle_dir,
            canonical_artifact_hash,
            derive_run_id,
            valid_bundle,
        )

        directory = Path(os.environ["NI_TEST_TMP_DIR"]) / "ni058-bundle"
        directory.mkdir(parents=True, exist_ok=True)
        cls.bundle_path = bundle_dir(directory, valid_bundle())
        bundle = load_bundle(cls.bundle_path)
        report = verify_bundle(bundle)
        cls.assertTrue(report.passed, "the synthetic bundle must pass the gate")
        hashes = {key: canonical_artifact_hash(json.loads(
            (cls.bundle_path / f"{key}.json").read_text("utf-8")))
            for key in MANIFEST_KEYS}
        cls.run_id = derive_run_id(hashes)
        publish_run(os.environ["NI_TEST_OPERATOR_URL"], bundle, cls.run_id)

    @classmethod
    def insert_public_citation(cls):
        artifact_id = uuid4()
        with cls.operator.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.artifacts(id, relative_storage_key, sha256,
                       byte_size, media_type, scope, owner_id, license_status)
                VALUES (:id, :key, :sha, 10, 'application/pdf', 'public', NULL,
                        'verified')
            """), {"id": artifact_id, "key": f"synthetic/{artifact_id}.pdf",
                   "sha": SHA256})
        return artifact_id

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        cls.operator.dispose()
        cls.admin.dispose()

    def setUp(self):
        with self.operator.begin() as connection:
            connection.execute(text("DELETE FROM app.users"))
        self.alice_id, self.bob_id = uuid4(), uuid4()
        for subject, name in ((self.alice_id, "Synthetic Alice"),
                              (self.bob_id, "Synthetic Bob")):
            with user_transaction(self.engine, subject) as connection:
                connection.execute(text("INSERT INTO app.users(id) VALUES (:id)"),
                                   {"id": subject})
                connection.execute(text("""INSERT INTO app.user_profiles(user_id, display_name)
                                          VALUES (:id, :name)"""), {"id": subject, "name": name})
        self.alice = Principal(id=self.alice_id, display_name="Synthetic Alice",
                               display_timezone="UTC")
        self.bob = Principal(id=self.bob_id, display_name="Synthetic Bob",
                             display_timezone="UTC")
        self.client = TestClient(app, raise_server_exceptions=False)

    # -- HTTP session helper (real dependency chain, stubbed verifier) ------- #

    def as_session(self, subject):
        verifier = _StubVerifier(_verified(subject))
        context = ExitStack()
        context.enter_context(patch.object(principal_module, "_get_verifier",
                                           return_value=verifier))
        context.enter_context(patch.object(principal_module, "_get_engine",
                                           return_value=self.engine))
        return context

    def bearer(self, subject) -> dict:
        return {"Authorization": f"Bearer t.{subject}"}

    # -- fixture helpers ----------------------------------------------------- #

    def dataset_key(self, name: str) -> str:
        return f"synthetic.{uuid4().hex[:8]}.{name}"

    def stage_volume(self, key: str, value: str) -> UUID:
        """One published synthetic dataset version for the chart."""
        if not hasattr(self, "directory"):
            tmp = tempfile.TemporaryDirectory(prefix="ni058-",
                                              dir=os.environ["NI_TEST_TMP_DIR"])
            self.addCleanup(tmp.cleanup)
            self.directory = Path(tmp.name)
            self.storage_root = self.directory / "storage"
        dimensions = {"source": "SRC-LLAMA"}
        result = data_fixture.DeliveryDatabaseTests.stage_fixture(
            self, key,
            [data_fixture.observation(chart_fixtures.METRIC_ID, date(2026, 1, 1),
                                      value=value, bound_kind="lower",
                                      dimensions=dimensions),
             data_fixture.observation(chart_fixtures.METRIC_ID, date(2026, 1, 2),
                                      value=None, dimensions=dimensions)],
            [chart_fixtures.METRIC_ID], window=("2026-01-01", "2026-01-03"))
        return result.dataset_version_id

    def insert_dataset_row(self, dataset_key: str) -> UUID:
        """A minimal synthetic approved dataset version row without observations."""
        dataset_id, artifact_id = uuid4(), uuid4()
        with self.operator.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.artifacts(id, relative_storage_key, sha256, byte_size,
                       media_type, scope, owner_id, license_status)
                VALUES (:id, :key, :sha, 10, 'application/json', 'internal', NULL,
                        'unverified')
            """), {"id": artifact_id, "key": f"synthetic/{dataset_id}.json",
                   "sha": SHA256})
            connection.execute(text("""
                INSERT INTO app.dataset_versions(id, dataset_key, version, status,
                       start_date, end_date, frequency, pipeline_version,
                       manifest_artifact_id, content_sha256)
                VALUES (:id, :key, 1, 'approved', '2025-01-01', '2025-02-01', 'daily',
                        'synthetic-pipeline-1', :artifact, :sha)
            """), {"id": dataset_id, "key": dataset_key,
                   "artifact": artifact_id, "sha": SHA256})
        return dataset_id

    def full_content(self, *, dataset_id: UUID, table_dataset_id: UUID) -> dict:
        """A synthetic document with chart, table, cards, evidence and prose."""
        insight_context = chart_fixtures.volume_context(self.operator, dataset_id)
        hypothesis = document_fixtures.hypothesis_attrs()
        hypothesis_id = hypothesis["attrs"]["hypothesis_id"]
        insight = document_fixtures.insight_attrs(
            hypothesis_id=hypothesis_id, context=copy.deepcopy(insight_context))
        chart_block_id = str(uuid4())
        chart = document_fixtures.block(
            "liveChart", chart_block_id, mode="live", selection=selection(),
            chart_definition_version_id=str(chart_fixtures.CHART_ID),
            observed_dataset_version_id=str(dataset_id))
        return {"schema_version": 1, "type": "doc", "content": [
            {"type": "paragraph", "attrs": {"block_id": str(uuid4())},
             "content": [document_fixtures.text_node("Synthetic intro ",
                                                     marks=[{"type": "bold"}]),
                         document_fixtures.text_node(
                             "with a source link",
                             marks=[{"type": "link",
                                     "attrs": {"href": "https://example.test/source"}}])]},
            {"type": "heading", "attrs": {"block_id": str(uuid4()), "level": 2},
             "content": [document_fixtures.text_node("Findings")]},
            document_fixtures.data_table_attrs(
                rows=[["fees", "12.5"], [None, True], [2, 12.5]]),
            document_fixtures.data_table_attrs(
                dataset_version_id=str(table_dataset_id)),
            hypothesis, insight,
            document_fixtures.evidence_attrs(hypothesis_id, "insight",
                                             insight["attrs"]["insight_id"]),
            document_fixtures.evidence_attrs(hypothesis_id, "citation",
                                             str(self.citation_id)),
            document_fixtures.risk_attrs(hypothesis_id),
            document_fixtures.block("divider"),
            chart,
        ]}

    def create_full_document(self, principal: Principal, *, dataset_id: UUID,
                             table_dataset_id: UUID,
                             title: str = "Synthetic export research (fixture)"):
        created = service.create_document(self.engine, principal, title=title)
        content = self.full_content(dataset_id=dataset_id,
                                    table_dataset_id=table_dataset_id)
        saved = service.save_revision(self.engine, principal, created.document.id,
                                      expected_revision=1, document_payload=content)
        return created, saved

    def create_job(self, document_id: UUID, version_id: UUID, *,
                   key: str | None = None, principal: Principal | None = None,
                   format: str = "markdown_zip"):
        from near_api.exports import service as export_service

        return export_service.create_export_job(
            self.engine, principal or self.alice, document_id, version_id,
            format=format, idempotency_key=key)

    def job_row(self, document_id: UUID, job_id: UUID):
        with self.admin.connect() as connection:
            row = connection.execute(text("""
                SELECT id, owner_id, document_id, document_version_id, status,
                       error_code, attempts, leased_by, leased_until,
                       bundle IS NOT NULL AS has_bundle, plan IS NOT NULL AS has_plan,
                       octet_length(plan) AS plan_bytes, expires_at
                  FROM app.export_jobs WHERE id = :id AND document_id = :doc
            """), {"id": job_id, "doc": document_id}).mappings().one()
        return dict(row)

    def expire(self, document_id: UUID, job_id: UUID, *, hours: float = -1.0):
        with self.admin.begin() as connection:
            connection.execute(text(
                "UPDATE app.export_jobs SET expires_at = now() + make_interval"
                "(secs => :secs) WHERE id = :id"),
                {"secs": hours * 3600, "id": job_id})

    # -- the lifecycle ------------------------------------------------------- #

    def test_01_full_export_unzip_and_validate_hashes_and_links(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "12.5")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        with self.as_session(self.alice_id):
            response = self.client.post(
                f"/api/documents/{created.document.id}/exports",
                headers=self.bearer(self.alice_id),
                json={"document_version_id": str(saved.version.id),
                      "format": "markdown_zip"})
        self.assertEqual(response.status_code, 202)
        job = response.json()
        self.assertEqual(job["status"], "queued")
        self.assertIsNone(job["download_path"])
        self.assertEqual(job["format"], "markdown_zip")
        self.assertIsNone(job["error_code"])

        processed = process_one(self.engine, self.operator, worker_id="ni058-test",
                                lease_seconds=300, timeout=60.0, node_bin=None,
                                renderer_script=None)
        self.assertTrue(processed)
        with self.as_session(self.alice_id):
            poll = self.client.get(
                f"/api/documents/{created.document.id}/exports/{job['id']}",
                headers=self.bearer(self.alice_id))
            self.assertEqual(poll.status_code, 200)
            self.assertEqual(poll.json()["status"], "succeeded")
            download_path = poll.json()["download_path"]
            self.assertTrue(download_path and
                            download_path.endswith(f"/exports/{job['id']}/download"))
            download = self.client.get(download_path,
                                       headers=self.bearer(self.alice_id))
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.headers["Content-Type"], "application/zip")
        self.assertIn("attachment", download.headers["Content-Disposition"])

        self.validate_bundle(download.content, created, saved, expected_revision=2,
                             expected_value="12.5")

    def validate_bundle(self, zip_bytes: bytes, created, saved, *,
                        expected_revision: int, expected_value: str,
                        expected_title: str = "Synthetic export research (fixture)"):
        from near_api.exports.bundle import (
            extract_bundle,
            verify_bundle,
            verify_research_links,
        )

        extracted = extract_bundle(zip_bytes)
        manifest = json.loads(extracted["manifest.json"])
        verify_bundle(manifest, extracted)
        verify_research_links(extracted["research.md"].decode("utf-8"), extracted)
        self.assertEqual(manifest["document"]["revision"], expected_revision)
        self.assertEqual(manifest["document"]["version_id"], str(saved.version.id))
        self.assertEqual(manifest["document"]["content_sha256"],
                         saved.version.content_sha256)
        self.assertEqual(manifest["document"]["title"], expected_title)
        self.assertEqual(manifest["document"]["author"]["owner_id"],
                         str(self.alice_id))
        research = extracted["research.md"].decode("utf-8")
        self.assertIn(f"# {expected_title}", research)
        self.assertIn(f"Exported revision {expected_revision} of document", research)
        # exact decimal strings and recorded reasons from the frozen chart CSV
        chart_csv = next(data for path, data in extracted.items()
                         if path.startswith("assets/") and path.endswith(".csv")).decode("utf-8")
        self.assertIn(f"{expected_value},lower,ok,", chart_csv)
        self.assertIn("synthetic source gap", chart_csv)
        # authored table cells as exact decimal strings; the dataset pin
        self.assertIn("| fees | 12.5 |", research)
        self.assertIn("Projected from approved dataset", research)
        # the pinned identity registries
        self.assertIn("## Sources", research)
        self.assertIn("SRC-LLAMA", research)
        self.assertIn("## Citations", research)
        self.assertIn(str(self.citation_id), research)
        # every chart asset name is derived from the safe-name rule
        for path in extracted:
            if path.startswith("assets/"):
                stem = Path(path).stem
                self.assertRegex(stem, r"^chart-[0-9a-f-]{36}$")
        return manifest

    def test_02_idempotent_create_replays_the_same_job(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "9")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        key = str(uuid4())
        first = self.create_job(created.document.id, saved.version.id, key=key)
        self.assertFalse(first.replay)
        second = self.create_job(created.document.id, saved.version.id, key=key)
        self.assertTrue(second.replay)
        self.assertEqual(first.job.id, second.job.id)
        with self.admin.connect() as connection:
            count = connection.scalar(text(
                "SELECT count(*) FROM app.export_jobs WHERE owner_id = :owner"),
                {"owner": self.alice_id})
        self.assertEqual(count, 1)
        # same key, different payload -> typed 409
        from near_api.documents.idempotency import IdempotencyConflict

        with self.assertRaises(IdempotencyConflict):
            self.create_job(created.document.id, uuid4(), key=key)
        # same key and revision, different FORMAT -> also a different request
        with self.assertRaises(IdempotencyConflict):
            self.create_job(created.document.id, saved.version.id, key=key,
                            format="pdf")
        # malformed key -> 422 at the route
        with self.as_session(self.alice_id):
            response = self.client.post(
                f"/api/documents/{created.document.id}/exports",
                headers={"Idempotency-Key": "not-a-uuid",
                         **self.bearer(self.alice_id)},
                json={"document_version_id": str(saved.version.id),
                      "format": "markdown_zip"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(ErrorResponse.model_validate(response.json()).error.code,
                         "VALIDATION_ERROR")
        # a fresh key creates a second, independent job
        third = self.create_job(created.document.id, saved.version.id, key=str(uuid4()))
        self.assertFalse(third.replay)
        self.assertNotEqual(first.job.id, third.job.id)

    def test_03_superseded_revision_refused_and_edit_during_export_frozen(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "7.25")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        outcome = self.create_job(created.document.id, saved.version.id)
        job_id = outcome.job.id
        with self.admin.connect() as connection:
            plan_before = connection.scalar(text(
                "SELECT plan FROM app.export_jobs WHERE id = :id"), {"id": job_id})

        # A rename and a new revision AFTER the job creation: the export is
        # frozen at revision 2 — the builder refuses the superseded version,
        # the queued job keeps its exact plan, and the bundle pins revision 2.
        renamed = service.rename_document(self.engine, self.alice,
                                          created.document.id, expected_revision=2,
                                          title="Synthetic export research v2 (fixture)")
        with self.as_session(self.alice_id):
            refused = self.client.post(
                f"/api/documents/{created.document.id}/exports",
                headers=self.bearer(self.alice_id),
                json={"document_version_id": str(saved.version.id),
                      "format": "markdown_zip"})
        self.assertEqual(refused.status_code, 409)
        error = ErrorResponse.model_validate(refused.json()).error
        self.assertEqual(error.code, "REVISION_NOT_ACKNOWLEDGED")
        self.assertIn(("version_id", "revision_not_acknowledged"),
                      [(item.path, item.reason) for item in error.details or []])

        processed = process_one(self.engine, self.operator, worker_id="ni058-test",
                                lease_seconds=300, timeout=60.0, node_bin=None,
                                renderer_script=None)
        self.assertTrue(processed)
        row = self.job_row(created.document.id, job_id)
        self.assertEqual(row["status"], "succeeded")
        with self.admin.connect() as connection:
            plan_after = connection.scalar(text(
                "SELECT plan FROM app.export_jobs WHERE id = :id"), {"id": job_id})
        self.assertEqual(bytes(plan_after), bytes(plan_before))  # frozen plan
        with self.as_session(self.alice_id):
            download = self.client.get(
                f"/api/documents/{created.document.id}/exports/{job_id}/download",
                headers=self.bearer(self.alice_id))
        self.assertEqual(download.status_code, 200)
        manifest = self.validate_bundle(download.content, created, saved,
                                        expected_revision=2, expected_value="7.25")
        self.assertEqual(manifest["document"]["title"],
                         "Synthetic export research (fixture)")  # not the new title
        # A new job for the NEW acknowledged revision carries the new title.
        outcome_v2 = self.create_job(created.document.id, renamed.version.id)
        process_one(self.engine, self.operator, worker_id="ni058-test",
                    lease_seconds=300, timeout=60.0, node_bin=None,
                    renderer_script=None)
        with self.as_session(self.alice_id):
            download_v2 = self.client.get(
                f"/api/documents/{created.document.id}"
                f"/exports/{outcome_v2.job.id}/download",
                headers=self.bearer(self.alice_id))
        manifest_v2 = self.validate_bundle(
            download_v2.content, created, renamed, expected_revision=3,
            expected_value="7.25",
            expected_title="Synthetic export research v2 (fixture)")
        self.assertNotEqual(manifest_v2["plan_sha256"], manifest["plan_sha256"])

    def test_04_crash_retry_is_idempotent_and_attempts_capped(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "3.5")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        outcome = self.create_job(created.document.id, saved.version.id)
        job_id = outcome.job.id

        # Crash after claim: the lease expires, the row stays running.
        claimed = claim_job(self.operator, "crashed-worker", lease_seconds=300)
        self.assertEqual(claimed.job_id, job_id)
        self.assertEqual(claimed.attempts, 1)
        with self.admin.begin() as connection:
            connection.execute(text(
                "UPDATE app.export_jobs SET leased_until = now() - interval '1s'"
                " WHERE id = :id"), {"id": job_id})

        # The next worker re-claims the SAME job through the expired lease
        # (attempts 2) and its render commits exactly once.
        processed = process_one(self.engine, self.operator, worker_id="retry-worker",
                                lease_seconds=300, timeout=60.0, node_bin=None,
                                renderer_script=None)
        self.assertTrue(processed)
        row = self.job_row(created.document.id, job_id)
        self.assertEqual(row["status"], "succeeded")
        self.assertEqual(row["leased_by"], "retry-worker")
        self.assertEqual(row["attempts"], 2)
        with self.admin.connect() as connection:
            count = connection.scalar(text(
                "SELECT count(*) FROM app.export_jobs WHERE document_id = :doc"),
                {"doc": created.document.id})
        self.assertEqual(count, 1)

        # A zombie past the attempt cap becomes a typed failed row on claim.
        outcome_b = self.create_job(created.document.id, saved.version.id,
                                    key=str(uuid4()))
        claim_job(self.operator, "zombie-worker", lease_seconds=300)
        with self.admin.begin() as connection:
            connection.execute(text(
                "UPDATE app.export_jobs SET leased_until = now() - interval '1s',"
                " attempts = 2 WHERE id = :id"), {"id": outcome_b.job.id})
        third = claim_job(self.operator, "zombie-worker", lease_seconds=300)
        row_b = self.job_row(created.document.id, outcome_b.job.id)
        self.assertEqual(row_b["status"], "failed")
        self.assertEqual(row_b["error_code"], "lease_attempts_exhausted")
        self.assertTrue(third is None or third.job_id != outcome_b.job.id)

    def test_05_ttl_expiry_typed_states_and_sweep(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "1.5")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        outcome = self.create_job(created.document.id, saved.version.id)
        job_id = outcome.job.id
        process_one(self.engine, self.operator, worker_id="ni058-test",
                    lease_seconds=300, timeout=60.0, node_bin=None,
                    renderer_script=None)

        # queued download refusal (409) before completion is checked in
        # test_06; here the succeeded artifact expires.
        self.expire(created.document.id, job_id, hours=-1)
        with self.as_session(self.alice_id):
            poll = self.client.get(
                f"/api/documents/{created.document.id}/exports/{job_id}",
                headers=self.bearer(self.alice_id))
            self.assertEqual(poll.status_code, 200)
            self.assertEqual(poll.json()["status"], "expired")
            self.assertIsNone(poll.json()["download_path"])
            download = self.client.get(
                f"/api/documents/{created.document.id}/exports/{job_id}/download",
                headers=self.bearer(self.alice_id))
        self.assertEqual(download.status_code, 410)
        self.assertEqual(ErrorResponse.model_validate(download.json()).error.code,
                         "EXPORT_EXPIRED")

        # A past-TTL job is never claimed.
        outcome_queued = self.create_job(created.document.id, saved.version.id,
                                         key=str(uuid4()))
        self.expire(created.document.id, outcome_queued.job.id, hours=-1)
        claimed = claim_job(self.operator, "ni058-test", lease_seconds=300)
        self.assertTrue(claimed is None or claimed.job_id != outcome_queued.job.id)

        # The sweep persists the typed state and clears the bytes.
        swept = sweep_expired(self.engine, self.operator)
        self.assertGreaterEqual(swept, 2)
        row = self.job_row(created.document.id, job_id)
        self.assertEqual(row["status"], "expired")
        self.assertFalse(row["has_bundle"])
        row_queued = self.job_row(created.document.id, outcome_queued.job.id)
        self.assertEqual(row_queued["status"], "expired")
        with self.as_session(self.alice_id):
            download = self.client.get(
                f"/api/documents/{created.document.id}/exports/{job_id}/download",
                headers=self.bearer(self.alice_id))
        self.assertEqual(download.status_code, 410)

    def test_06_download_not_ready_failed_and_pdf_success_path(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "5")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        outcome = self.create_job(created.document.id, saved.version.id)
        job_id = outcome.job.id
        with self.as_session(self.alice_id):
            queued = self.client.get(
                f"/api/documents/{created.document.id}/exports/{job_id}/download",
                headers=self.bearer(self.alice_id))
            self.assertEqual(queued.status_code, 409)
            self.assertEqual(ErrorResponse.model_validate(queued.json()).error.code,
                             "EXPORT_NOT_READY")
            # NI-059: the PDF format is a documented export now — the SAME
            # frozen-plan machinery, the PDF renderer on the worker.
            pdf = self.client.post(
                f"/api/documents/{created.document.id}/exports",
                headers=self.bearer(self.alice_id),
                json={"document_version_id": str(saved.version.id),
                      "format": "pdf"})
        self.assertEqual(pdf.status_code, 202)
        pdf_job = pdf.json()
        self.assertEqual(pdf_job["format"], "pdf")
        self.assertEqual(pdf_job["status"], "queued")
        self.assertIsNone(pdf_job["download_path"])

        # The worker renders both queued jobs (Markdown ZIP first by
        # creation order, then the PDF) from their frozen plans.
        self.assertTrue(process_one(self.engine, self.operator,
                                    worker_id="ni058-test", lease_seconds=300,
                                    timeout=60.0, node_bin=None,
                                    renderer_script=None))
        self.assertTrue(process_one(self.engine, self.operator,
                                    worker_id="ni058-test", lease_seconds=300,
                                    timeout=60.0, node_bin=None,
                                    renderer_script=None))
        with self.as_session(self.alice_id):
            zip_poll = self.client.get(
                f"/api/documents/{created.document.id}/exports/{job_id}",
                headers=self.bearer(self.alice_id))
            pdf_poll = self.client.get(
                f"/api/documents/{created.document.id}/exports/{pdf_job['id']}",
                headers=self.bearer(self.alice_id))
            zip_download = self.client.get(
                f"/api/documents/{created.document.id}/exports/{job_id}/download",
                headers=self.bearer(self.alice_id))
            pdf_download = self.client.get(
                f"/api/documents/{created.document.id}/exports/{pdf_job['id']}/download",
                headers=self.bearer(self.alice_id))
        self.assertEqual(zip_poll.json()["status"], "succeeded")
        self.assertEqual(pdf_poll.json()["status"], "succeeded")
        self.assertEqual(zip_poll.json()["format"], "markdown_zip")
        self.assertEqual(pdf_poll.json()["format"], "pdf")
        self.assertEqual(zip_download.status_code, 200)
        self.assertEqual(zip_download.headers["Content-Type"], "application/zip")
        self.assertIn(f"near-export-{job_id}.zip",
                      zip_download.headers["Content-Disposition"])
        self.assertEqual(pdf_download.status_code, 200)
        self.assertEqual(pdf_download.headers["Content-Type"], "application/pdf")
        self.assertIn(f"near-export-{pdf_job['id']}.pdf",
                      pdf_download.headers["Content-Disposition"])
        self.assertTrue(pdf_download.content.startswith(b"%PDF-"))
        # The stored PDF artifact matches its recorded identity (the
        # download route re-verifies the hash before streaming).
        row = self.job_row(created.document.id, UUID(pdf_job["id"]))
        self.assertEqual(row["status"], "succeeded")
        with self.as_session(self.bob_id):
            pdf_path = f"/api/documents/{created.document.id}/exports/{pdf_job['id']}"
            for path in (pdf_path, f"{pdf_path}/download"):
                denied = self.client.get(path, headers=self.bearer(self.bob_id))
                self.assertEqual(denied.status_code, 404)
                self.assertEqual(ErrorResponse.model_validate(denied.json()).error.code,
                                 "NOT_FOUND")

        # A typed worker refusal marks the job failed: one more job is
        # failed through the owner-scoped worker path (the renderer failure
        # path is exercised the same way by the boundary suite).
        third = self.create_job(created.document.id, saved.version.id)
        third_id = third.job.id
        claim_job(self.operator, "failing-worker", lease_seconds=300)
        from near_api.exports.worker import ClaimedJob, fail_job as fail_claimed

        with self.operator.connect() as connection:
            row = connection.execute(text(
                "SELECT id, owner_id, document_id, document_version_id, format,"
                " revision, attempts, leased_by FROM app.export_jobs"
                " WHERE id = :id"), {"id": third_id}).mappings().one()
        claimed = ClaimedJob(job_id=row["id"], owner_id=row["owner_id"],
                             document_id=row["document_id"],
                             document_version_id=row["document_version_id"],
                             format=row["format"],
                             revision=row["revision"], attempts=row["attempts"],
                             worker_id=row["leased_by"])
        self.assertTrue(fail_claimed(self.engine, claimed, "renderer_unavailable"))
        with self.as_session(self.alice_id):
            poll = self.client.get(
                f"/api/documents/{created.document.id}/exports/{third_id}",
                headers=self.bearer(self.alice_id))
            self.assertEqual(poll.json()["status"], "failed")
            self.assertEqual(poll.json()["error_code"], "renderer_unavailable")
            download = self.client.get(
                f"/api/documents/{created.document.id}/exports/{third_id}/download",
                headers=self.bearer(self.alice_id))
        self.assertEqual(download.status_code, 409)
        error = ErrorResponse.model_validate(download.json()).error
        self.assertEqual(error.code, "EXPORT_FAILED")
        self.assertIn(("job", "renderer_unavailable"),
                      [(item.path, item.reason) for item in error.details or []])

    def test_07_owner_matrix_bob_is_the_generic_404(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "2")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        outcome = self.create_job(created.document.id, saved.version.id)
        job_id = outcome.job.id
        with self.as_session(self.bob_id):
            create = self.client.post(
                f"/api/documents/{created.document.id}/exports",
                headers=self.bearer(self.bob_id),
                json={"document_version_id": str(saved.version.id),
                      "format": "markdown_zip"})
            create_pdf = self.client.post(
                f"/api/documents/{created.document.id}/exports",
                headers=self.bearer(self.bob_id),
                json={"document_version_id": str(saved.version.id),
                      "format": "pdf"})
            poll = self.client.get(
                f"/api/documents/{created.document.id}/exports/{job_id}",
                headers=self.bearer(self.bob_id))
            download = self.client.get(
                f"/api/documents/{created.document.id}/exports/{job_id}/download",
                headers=self.bearer(self.bob_id))
            cross_document = self.client.get(
                f"/api/documents/{uuid4()}/exports/{job_id}",
                headers=self.bearer(self.bob_id))
        for response in (create, create_pdf, poll, download, cross_document):
            self.assertEqual(response.status_code, 404)
            self.assertEqual(ErrorResponse.model_validate(response.json()).error.code,
                             "NOT_FOUND")
        # Bob's own document export works independently (both formats).
        bob_dataset = self.insert_dataset_row(self.dataset_key("bob-table"))
        bob_created, bob_saved = self.create_full_document(
            self.bob, dataset_id=self.stage_volume(self.dataset_key("bob-intents"), "4"),
            table_dataset_id=bob_dataset, title="Bob synthetic research (fixture)")
        with self.as_session(self.bob_id):
            bob_export = self.client.post(
                f"/api/documents/{bob_created.document.id}/exports",
                headers=self.bearer(self.bob_id),
                json={"document_version_id": str(bob_saved.version.id),
                      "format": "markdown_zip"})
            bob_pdf = self.client.post(
                f"/api/documents/{bob_created.document.id}/exports",
                headers=self.bearer(self.bob_id),
                json={"document_version_id": str(bob_saved.version.id),
                      "format": "pdf"})
        self.assertEqual(bob_export.status_code, 202)
        self.assertEqual(bob_export.json()["document_id"],
                         str(bob_created.document.id))
        self.assertEqual(bob_pdf.status_code, 202)
        self.assertEqual(bob_pdf.json()["format"], "pdf")

    def test_08_corrupted_plan_fails_typed(self):
        dataset_id = self.stage_volume(self.dataset_key("intents"), "6")
        created, saved = self.create_full_document(
            self.alice, dataset_id=dataset_id, table_dataset_id=dataset_id)
        outcome = self.create_job(created.document.id, saved.version.id)
        job_id = outcome.job.id
        # Corrupt one plan byte via admin SQL: the stored digest no longer
        # matches, so the worker refuses typed instead of rendering it.
        with self.admin.begin() as connection:
            connection.execute(text("""
                UPDATE app.export_jobs
                   SET plan = set_byte(plan, 0, (get_byte(plan, 0) + 1) % 256)
                 WHERE id = :id
            """), {"id": job_id})
        processed = process_one(self.engine, self.operator, worker_id="ni058-test",
                                lease_seconds=300, timeout=60.0, node_bin=None,
                                renderer_script=None)
        self.assertTrue(processed)
        row = self.job_row(created.document.id, job_id)
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["error_code"], "export_plan_hash_mismatch")

    def test_09_migration_round_trip_and_mirror(self):
        # Preserve the independent parents and both heads that precede the
        # final join. Upgrading each applies the missing schema changes.
        for parent in ("0014_document_organization", "0016_pdf_export_format",
                       "0015_publications", "0018_merge_pdf_organization"):
            with self.subTest(applied_parent=parent):
                command.downgrade(self.config, "0011_saved_charts")
                with self.admin.connect() as connection:
                    self.assertIsNone(connection.scalar(text(
                        "SELECT to_regclass('app.export_jobs')")))
                command.upgrade(self.config, parent)
                with self.admin.connect() as connection:
                    self.assertEqual(connection.scalar(text(
                        "SELECT version_num FROM app.alembic_version")), parent)
                command.upgrade(self.config, "head")
                command.check(self.config)
                with self.admin.connect() as connection:
                    self.assertEqual(connection.scalar(text(
                        "SELECT version_num FROM app.alembic_version")),
                        "0019_merge_pdf_publications")
                    self.assertIsNotNone(connection.scalar(text(
                        "SELECT to_regclass('app.document_organization')")))
                    self.assertIsNotNone(connection.scalar(text(
                        "SELECT to_regclass('app.research_publications')")))
                    format_check = connection.scalar(text(
                        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                        "WHERE conrelid = 'app.export_jobs'::regclass "
                        "AND conname = 'ck_export_jobs_format'"))
                self.assertIn("pdf", format_check)
        with self.admin.connect() as connection:
            columns = {row["column_name"] for row in connection.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='app' AND table_name='export_jobs'")).mappings()}
        self.assertEqual(columns, {
            "id", "owner_id", "document_id", "document_version_id", "format",
            "status", "idempotency_key", "revision", "plan", "plan_sha256",
            "bundle", "bundle_sha256", "bundle_byte_size", "error_code",
            "attempts", "leased_by", "leased_until", "expires_at", "created_at",
            "updated_at", "completed_at"})
