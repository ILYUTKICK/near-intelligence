"""NI-041 chart-block insertion tests: one confirmation, one valid block.

Offline classes run everywhere (request contract, route contract); the
database class needs scripts/run-db-tests.py — a skip is never successful
integration evidence. Covered guarantees:

- one confirmation appends exactly ONE valid liveChart block as ONE new
  revision through the canonical flow (projections included);
- ownership is the verified principal's (Alice/Bob matrix at HTTP level);
- the inspected evidence is frozen: the pinned dataset version and the
  ResolvedContext survive source changes verbatim, and a whole-document save
  can neither re-pin nor inject/alter a chart block without its context;
- duplicate retries with an Idempotency-Key replay the original result
  (timeout-after-commit) and concurrent submits admit exactly one block;
- reference failures (unknown/unavailable definition, unapproved dataset,
  missing required metrics, snapshot mode, dangling anchor) are typed 422s
  that leave zero rows.

All chart definitions come from the NI-031 code registry; every dataset,
document and identity is a synthetic fixture — no research data, no
provider access.
"""

import copy
import datetime as dt
import os
import threading
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from near_api.auth import principal as principal_module
from near_api.auth.principal import Principal
from near_api.auth.verification import VerifiedToken
from near_api.charts.registry import chart_by_chart_id
from near_api.datasets.delivery import _context_hash
from near_api.db.session import create_runtime_engine, user_transaction
from near_api.documents import service
from near_api.documents.chart_blocks import (
    ChartDefinitionRow,
    validate_selection_against_definition,
)
from near_api.documents.schema import canonical_context_json, parse_document
from near_api.insights.schemas import ResolvedContext
from near_api.main import app
from near_api.metrics.registry import definition_by_metric_id
from near_api.schemas.chart_blocks import ChartBlockInsertRequest
from near_api.schemas.common import ErrorResponse
from near_api.schemas.delivery import ResolvedSelection

CHART = chart_by_chart_id("intents-volume")
CHART_ID = CHART.id
UNAVAILABLE_CHART_ID = chart_by_chart_id("model-diagnostics").id
METRIC_ID = definition_by_metric_id("provider_intents_volume_usd").id
DATASET_WINDOW = ("2026-01-01", "2026-02-01")
SHA256 = "a" * 64


def selection(start: str = "2026-01-01", end: str = "2026-01-08") -> dict:
    return {"start": start, "end": end, "frequency": "day", "filters": {}}


def insert_payload(**changes) -> dict:
    payload = {
        "chart_definition_version_id": str(CHART_ID),
        "selection": selection(),
        "mode": "live",
        "dataset_version_id": str(uuid4()),
    }
    payload.update(changes)
    return payload


def text_paragraph(text: str) -> dict:
    return {"type": "paragraph",
            "attrs": {"block_id": str(uuid4())},
            "content": [{"type": "text", "text": text}]}


def document_with(paragraph_count: int) -> dict:
    return {"schema_version": 1, "type": "doc",
            "content": [text_paragraph(f"Synthetic paragraph {index}")
                        for index in range(paragraph_count)]}


class ChartBlockContractTests(unittest.TestCase):
    """Offline request/route contract: no database required."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_01_request_contract_rejects_inconsistent_snapshot_mode(self):
        with self.assertRaises(ValidationError):
            ChartBlockInsertRequest.model_validate(insert_payload(mode="snapshot"))
        with self.assertRaises(ValidationError):
            ChartBlockInsertRequest.model_validate(
                insert_payload(snapshot_id=str(uuid4())))
        snapshot = ChartBlockInsertRequest.model_validate(
            insert_payload(mode="snapshot", snapshot_id=str(uuid4())))
        self.assertEqual(snapshot.mode, "snapshot")

    def test_02_request_contract_bounds_and_unknown_fields(self):
        with self.assertRaises(ValidationError):
            ChartBlockInsertRequest.model_validate(
                insert_payload(selection=selection("2025-01-01", "2026-03-01")))
        with self.assertRaises(ValidationError):
            ChartBlockInsertRequest.model_validate(
                insert_payload(selection={"start": "2026-01-08", "end": "2026-01-01",
                                          "frequency": "day", "filters": {}}))
        with self.assertRaises(ValidationError):
            ChartBlockInsertRequest.model_validate(
                insert_payload(selection={"start": "2026-01-01", "end": "2026-01-08",
                                          "frequency": "week", "filters": {}}))
        with self.assertRaises(ValidationError):
            ChartBlockInsertRequest.model_validate(
                insert_payload(selection={"start": "2026-01-01", "end": "2026-01-08",
                                          "frequency": "day",
                                          "filters": {"source": ["SRC-LLAMA"]}}))
        with self.assertRaises(ValidationError):
            ChartBlockInsertRequest.model_validate(
                insert_payload(block_id=str(uuid4()), owner_id=str(uuid4())))

    def test_03_range_rule_matches_the_public_view_rule(self):
        """The insertion range rule IS the NI-032 view rule for one version."""
        definition = ChartDefinitionRow(
            id=CHART_ID, chart_id="synthetic", version=1, data_status="available",
            unavailable_reason=None, renderer_version="echarts-modular-svg@1",
            max_days=30, filter_schema=CHART.filter_schema,
            metric_definition_versions=(METRIC_ID,),
            required_metric_versions=(METRIC_ID,))
        validate_selection_against_definition(
            definition, dt.date(2026, 1, 1), dt.date(2026, 1, 31), {})
        with self.assertRaisesRegex(Exception, "allowed maximum"):
            validate_selection_against_definition(
                definition, dt.date(2026, 1, 1), dt.date(2026, 2, 15), {})

    def test_04_insertion_route_requires_a_verified_session(self):
        response = self.client.post(f"/api/documents/{uuid4()}/chart-blocks",
                                    json=insert_payload())
        self.assertEqual(response.status_code, 401)
        failure = ErrorResponse.model_validate(response.json())
        self.assertEqual(failure.error.code, "AUTHENTICATION_REQUIRED")
        self.assertEqual(response.headers["Cache-Control"], "no-store")


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class ChartBlockServiceDatabaseTests(unittest.TestCase):
    """Insertion guarantees on the disposable PostgreSQL cluster."""

    @classmethod
    def setUpClass(cls):
        from near_api.charts.registry import register_charts
        from near_api.metrics.registry import register_definitions

        cls.repo = Path(__file__).resolve().parents[3]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.engine = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        cls.engine_b = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        cls.operator = create_engine(os.environ["NI_TEST_OPERATOR_URL"], poolclass=NullPool,
                                     hide_parameters=True)
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"], poolclass=NullPool,
                                  hide_parameters=True)
        command.upgrade(cls.config, "head")
        sources = {"SRC-LLAMA": "DefiLlama saved snapshots",
                   "SRC-DASHBOARD": "NEAR Dashboard",
                   "SRC-BQ": "BigQuery export", "SRC-PRICE": "Saved price snapshots",
                   "SRC-FASTNEAR": "FastNear indexed blocks",
                   "SRC-NEAR-RPC": "NEAR public RPC"}
        with cls.operator.begin() as connection:
            for source_id, name in sources.items():
                connection.execute(text("""
                    INSERT INTO app.sources(id, name, access_status, license_status)
                    VALUES (:id, :name, 'documented', 'unverified')
                    ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """), {"id": source_id, "name": name})
            register_definitions(connection)
            register_charts(connection)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()
        cls.engine_b.dispose()
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

    # -- fixture helpers ----------------------------------------------------- #

    def as_session(self, subject):
        verifier = _StubVerifier(_verified(subject))
        context = ExitStack()
        context.enter_context(patch.object(principal_module, "_get_verifier",
                                           return_value=verifier))
        context.enter_context(patch.object(principal_module, "_get_engine",
                                           return_value=self.engine))
        return context

    def create_document(self, principal: Principal, title: str = "Synthetic research"):
        return service.create_document(self.engine, principal, title=title)

    def dataset_key(self, name: str) -> str:
        """A unique synthetic dataset key: dataset_versions are shared
        scientific rows that survive between tests in the disposable cluster
        (only app.users is reset in setUp)."""
        return f"synthetic.{uuid4().hex[:8]}.{name}"

    def insert_dataset_version(self, dataset_key: str, *, version: int = 1,
                               status: str = "approved", with_metric: bool = True,
                               with_observation: bool = True,
                               sha: str = SHA256) -> UUID:
        """Synthetic dataset version fixture (no research data, no pipeline)."""
        dataset_id = uuid4()
        artifact_id = uuid4()
        with self.operator.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.artifacts(id, relative_storage_key, sha256, byte_size,
                       media_type, scope, owner_id, license_status)
                VALUES (:id, :key, :sha, 10, 'application/json', 'internal', NULL,
                        'unverified')
            """), {"id": artifact_id, "key": f"synthetic/{dataset_id}.json",
                   "sha": sha})
            connection.execute(text("""
                INSERT INTO app.dataset_versions(id, dataset_key, version, status,
                       start_date, end_date, frequency, pipeline_version,
                       manifest_artifact_id, content_sha256)
                VALUES (:id, :key, :version, :status, :start, :end, 'daily',
                        'synthetic-pipeline-1', :artifact, :sha)
            """), {"id": dataset_id, "key": dataset_key, "version": version,
                   "status": status, "start": DATASET_WINDOW[0],
                   "end": DATASET_WINDOW[1], "artifact": artifact_id, "sha": sha})
            if with_metric:
                connection.execute(text("""
                    INSERT INTO app.dataset_metrics(dataset_version_id,
                           metric_definition_id)
                    VALUES (:id, :metric)
                """), {"id": dataset_id, "metric": METRIC_ID})
            if with_observation:
                connection.execute(text("""
                    INSERT INTO app.metric_observations(dataset_version_id,
                           metric_definition_id, period_start, dimensions_hash,
                           period_end, dimensions, value, quality_status, bound_kind)
                    VALUES (:id, :metric, :period, :hash, :period_end,
                            CAST('{}' AS jsonb), 12.5, 'verified', 'exact')
                """), {"id": dataset_id, "metric": METRIC_ID,
                       "period": dt.datetime(2026, 1, 2, tzinfo=dt.UTC),
                       "period_end": dt.datetime(2026, 1, 3, tzinfo=dt.UTC),
                       "hash": SHA256})
        return dataset_id

    def table_counts(self, document_id: UUID) -> dict:
        with self.admin.connect() as connection:
            return {
                table: connection.scalar(text(
                    f"SELECT count(*) FROM app.{table} WHERE document_id = :id"),
                    {"id": document_id})
                for table in ("document_versions", "document_blocks")
            }

    def stored_document(self, principal: Principal, document_id: UUID) -> dict:
        with user_transaction(self.engine, principal.id) as connection:
            row = connection.execute(text("""
                SELECT v.id, v.revision, v.content, v.resolved_contexts
                FROM app.document_versions v
                WHERE v.document_id = :id
                ORDER BY v.revision DESC LIMIT 1
            """), {"id": document_id}).mappings().one()
        return dict(row)

    def add_chart(self, document_id: UUID, payload: dict, *, revision: int = 1,
                  subject_id: UUID | None = None,
                  key: str | None = None) -> object:
        subject = subject_id or self.alice_id
        headers = {"Authorization": f"Bearer t.{subject}",
                   "If-Match": f'"{revision}"'}
        if key is not None:
            headers["Idempotency-Key"] = key
        with self.as_session(subject):
            return self.client.post(f"/api/documents/{document_id}/chart-blocks",
                                    json=payload, headers=headers)

    # -- lifecycle ------------------------------------------------------------ #

    def test_01_one_confirmation_appends_one_valid_block(self):
        detail = self.create_document(self.alice)
        dataset_id = self.insert_dataset_version(self.dataset_key("intents"))
        response = self.add_chart(detail.document.id,
                                  insert_payload(dataset_version_id=str(dataset_id)))
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["ETag"], '"2"')
        body = response.json()
        self.assertEqual(body["document"]["revision"], 2)
        block_id = UUID(body["value"]["block_id"])

        stored = self.stored_document(self.alice, detail.document.id)
        self.assertEqual(stored["revision"], 2)
        parsed = parse_document(stored["content"])
        self.assertEqual([item.block_type for item in parsed.blocks], ["liveChart"])
        chart = parsed.live_charts[0]
        self.assertEqual(chart.block_id, block_id)
        self.assertEqual(chart.chart_definition_version_id, CHART_ID)
        self.assertEqual(chart.mode, "live")
        self.assertEqual(chart.selection, selection())
        self.assertEqual(chart.observed_dataset_version_id, dataset_id)
        self.assertIsNone(chart.snapshot_id)
        # One frozen context, keyed by the server-allocated block id.
        contexts = stored["resolved_contexts"]
        self.assertEqual(sorted(contexts), [str(block_id)])
        context = canonical_context_json(contexts[str(block_id)],
                                         path="resolved_contexts")
        published = ResolvedContext.model_validate(contexts[str(block_id)])
        self.assertEqual(str(published.chart_definition_version_id), str(CHART_ID))
        self.assertEqual(str(published.dataset_version_id), str(dataset_id))
        # The hash is the NI-032 ChartView hash of the same inspection.
        expected_hash = _context_hash(
            {"id": CHART_ID}, dataset_id,
            ResolvedSelection(start=dt.date(2026, 1, 1), end=dt.date(2026, 1, 8),
                              frequency="day", filters={}),
            (METRIC_ID,))
        self.assertEqual(context["context_hash"], expected_hash)
        self.assertEqual(published.renderer_version, CHART.renderer_version)
        # Exactly one new revision with one projection row; the old revision
        # (the empty document) is byte-for-byte intact.
        counts = self.table_counts(detail.document.id)
        self.assertEqual(counts, {"document_versions": 2, "document_blocks": 1})
        with user_transaction(self.engine, self.alice_id) as connection:
            rows = connection.execute(text("""
                SELECT revision, content FROM app.document_versions
                WHERE document_id = :id ORDER BY revision
            """), {"id": detail.document.id}).all()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][1], {"schema_version": 1, "type": "doc", "content": []})
        self.assertEqual(rows[1][0], 2)

    def test_source_filter_is_persisted_and_unsupported_values_are_rejected(self):
        detail = self.create_document(self.alice)
        dataset_id = self.insert_dataset_version(self.dataset_key("filtered"))
        selected = {**selection(), "filters": {"source": "SRC-LLAMA"}}
        payload = insert_payload(dataset_version_id=str(dataset_id), selection=selected)
        response = self.add_chart(detail.document.id, payload)
        self.assertEqual(response.status_code, 201, response.text)
        stored = self.stored_document(self.alice, detail.document.id)
        block_id = response.json()["value"]["block_id"]
        self.assertEqual(stored["content"]["content"][0]["attrs"]["selection"], selected)
        context = stored["resolved_contexts"][block_id]
        self.assertEqual(context["selection"], selected)
        ResolvedContext.model_validate(context)
        changed = {**payload, "selection": {**selected, "filters": {"source": "unapproved"}}}
        denied = self.add_chart(detail.document.id, changed, revision=2)
        self.assertEqual(denied.status_code, 422)
        self.assertEqual(denied.json()["error"]["code"], "FILTER_UNSUPPORTED")
        self.assertEqual(self.stored_document(self.alice, detail.document.id)["revision"], 2)

    def test_02_owner_validated_between_alice_and_bob(self):
        alice_document = self.create_document(self.alice).document.id
        dataset_id = self.insert_dataset_version(self.dataset_key("intents"))
        # Bob sees Alice's document as absent and cannot append to it.
        response = self.add_chart(alice_document,
                                  insert_payload(dataset_version_id=str(dataset_id)),
                                  subject_id=self.bob_id)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ErrorResponse.model_validate(response.json()).error.code,
                         "NOT_FOUND")
        self.assertEqual(self.table_counts(alice_document),
                         {"document_versions": 1, "document_blocks": 0})
        # Knowing the reference ids grants nothing: the references are public
        # scientific data, the DOCUMENT ownership is the gate. Bob appends to
        # his own document with the same ids.
        bob_document = self.create_document(self.bob).document.id
        own = self.add_chart(bob_document,
                             insert_payload(dataset_version_id=str(dataset_id)),
                             subject_id=self.bob_id)
        self.assertEqual(own.status_code, 201, own.text)
        # And Alice cannot read Bob's document afterwards.
        with self.as_session(self.alice_id):
            leaked = self.client.get(f"/api/documents/{bob_document}",
                                     headers={"Authorization": "Bearer t.alice"})
        self.assertEqual(leaked.status_code, 404)

    def test_03_duplicate_retry_is_idempotent(self):
        detail = self.create_document(self.alice)
        dataset_id = self.insert_dataset_version(self.dataset_key("intents"))
        payload = insert_payload(dataset_version_id=str(dataset_id))
        key = str(uuid4())
        first = self.add_chart(detail.document.id, payload, key=key)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.headers["ETag"], '"2"')
        # Timeout-after-commit retry: the identical request replays the
        # ORIGINAL 201 — same revision, no second block.
        retry = self.add_chart(detail.document.id, payload, key=key)
        self.assertEqual(retry.status_code, 201)
        self.assertEqual(retry.json(), first.json())
        self.assertEqual(retry.headers["ETag"], '"2"')
        self.assertEqual(self.table_counts(detail.document.id),
                         {"document_versions": 2, "document_blocks": 1})
        # The same key with a different body is a collision, not a replay.
        conflict = self.add_chart(detail.document.id,
                                  insert_payload(dataset_version_id=str(uuid4())),
                                  key=key)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(ErrorResponse.model_validate(conflict.json()).error.code,
                         "IDEMPOTENCY_CONFLICT")
        # A failed attempt stores nothing and the key stays retryable.
        failed_key = str(uuid4())
        failed = self.add_chart(detail.document.id,
                                insert_payload(chart_definition_version_id=str(uuid4())),
                                revision=2, key=failed_key)
        self.assertEqual(failed.status_code, 422)
        recovered = self.add_chart(detail.document.id, payload, revision=2,
                                   key=failed_key)
        self.assertEqual(recovered.status_code, 201)
        self.assertEqual(recovered.headers["ETag"], '"3"')
        # A different key never replays: plain CAS is now stale (honest 409).
        stale = self.add_chart(detail.document.id, payload, revision=2,
                               key=str(uuid4()))
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(ErrorResponse.model_validate(stale.json()).error.code,
                         "REVISION_CONFLICT")
        # Successful writes: the first insertion (rev 2) and the recovered
        # one (rev 3): projections contain 1 + 2 blocks across immutable revisions;
        # every replay/conflict/failure stored nothing extra.
        self.assertEqual(self.table_counts(detail.document.id),
                         {"document_versions": 3, "document_blocks": 3})

    def test_04_idempotent_concurrent_same_key_single_block(self):
        detail = self.create_document(self.alice)
        dataset_id = self.insert_dataset_version(self.dataset_key("intents"))
        payload = ChartBlockInsertRequest.model_validate(
            insert_payload(dataset_version_id=str(dataset_id)))
        from near_api.documents import idempotency
        from near_api.documents.chart_blocks import append_chart_block_in_transaction
        key = uuid4()
        fingerprint = idempotency.request_fingerprint(
            idempotency.ROUTE_ADD_CHART_BLOCK, self.alice_id,
            insert_payload(dataset_version_id=str(dataset_id)))
        barrier = threading.Barrier(2)
        outcomes = {}

        def run(engine, tag):
            barrier.wait()
            outcomes[tag] = idempotency.execute_idempotent(
                engine, self.alice, route_key=idempotency.ROUTE_ADD_CHART_BLOCK,
                idempotency_key=key, request_hash=fingerprint,
                operation=lambda connection: (201, {
                    "block_id": str(append_chart_block_in_transaction(
                        connection, self.alice, detail.document.id,
                        expected_revision=1, payload=payload).block_id)}))

        threads = [threading.Thread(target=run, args=(self.engine, "a")),
                   threading.Thread(target=run, args=(self.engine_b, "b"))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        self.assertEqual({outcome.status for outcome in outcomes.values()}, {201})
        self.assertEqual({outcome.body["block_id"] for outcome in outcomes.values()},
                         {outcomes["a"].body["block_id"]})
        self.assertTrue(outcomes["a"].replay != outcomes["b"].replay)
        counts = self.table_counts(detail.document.id)
        self.assertEqual(counts, {"document_versions": 2, "document_blocks": 1})

    def test_05_concurrent_cas_double_submit_admits_one_block(self):
        from near_api.documents.chart_blocks import append_chart_block

        detail = self.create_document(self.alice)
        dataset_id = self.insert_dataset_version(self.dataset_key("intents"))
        payload = ChartBlockInsertRequest.model_validate(
            insert_payload(dataset_version_id=str(dataset_id)))
        barrier = threading.Barrier(2)
        results: dict[int, object] = {}

        def worker(index: int, engine):
            barrier.wait()
            try:
                results[index] = append_chart_block(
                    engine, self.alice, detail.document.id,
                    expected_revision=1, payload=payload)
            except Exception as error:  # honest failure is the expected 409 path
                results[index] = error

        threads = [threading.Thread(target=worker, args=(0, self.engine)),
                   threading.Thread(target=worker, args=(1, self.engine_b))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        outcomes = list(results.values())
        conflicts = [item for item in outcomes
                     if isinstance(item, service.RevisionConflict)]
        wins = [item for item in outcomes if not isinstance(item, Exception)]
        self.assertEqual(len(conflicts), 1, f"exactly one loser: {outcomes!r}")
        self.assertEqual(len(wins), 1, f"exactly one winner: {outcomes!r}")
        self.assertEqual(conflicts[0].current_revision, 2)
        counts = self.table_counts(detail.document.id)
        self.assertEqual(counts, {"document_versions": 2, "document_blocks": 1})

    def test_06_http_conflict_and_precondition_matrix(self):
        detail = self.create_document(self.alice)
        dataset_id = self.insert_dataset_version(self.dataset_key("intents"))
        payload = insert_payload(dataset_version_id=str(dataset_id))
        with self.as_session(self.alice_id):
            headers = {"Authorization": "Bearer t.alice"}
            missing = self.client.post(
                f"/api/documents/{detail.document.id}/chart-blocks",
                json=payload, headers=headers)
            self.assertEqual(missing.status_code, 428)
            self.assertEqual(
                ErrorResponse.model_validate(missing.json()).error.code,
                "PRECONDITION_REQUIRED")
            for malformed in ('1', 'W/"1"', '"abc"', '""'):
                weak = self.client.post(
                    f"/api/documents/{detail.document.id}/chart-blocks",
                    json=payload, headers={**headers, "If-Match": malformed})
                self.assertEqual(weak.status_code, 428, malformed)
        self.assertEqual(self.table_counts(detail.document.id),
                         {"document_versions": 1, "document_blocks": 0})
        # A stale revision is a typed 409 carrying the current revision.
        self.add_chart(detail.document.id, payload)  # revision 2
        stale = self.add_chart(detail.document.id, payload, revision=1)
        self.assertEqual(stale.status_code, 409)
        error = ErrorResponse.model_validate(stale.json()).error
        self.assertEqual(error.code, "REVISION_CONFLICT")
        self.assertIn("current_revision:2",
                      str([detail.reason for detail in (error.details or ())]))

    def test_07_reference_failures_are_typed_and_leave_zero_rows(self):
        detail = self.create_document(self.alice)
        staged = self.insert_dataset_version(self.dataset_key("staged"), status="staged")
        approved_empty = self.insert_dataset_version(self.dataset_key("empty"),
                                                     with_metric=False,
                                                     with_observation=False)
        cases = (
            ("unknown chart definition",
             insert_payload(chart_definition_version_id=str(uuid4())),
             "REFERENCE_INVALID", "dangling_chart_definition"),
            ("unavailable chart",
             insert_payload(chart_definition_version_id=str(UNAVAILABLE_CHART_ID)),
             "REFERENCE_INVALID", "chart_unavailable"),
            ("staged dataset is not public",
             insert_payload(dataset_version_id=str(staged)),
             "REFERENCE_INVALID", "dangling_dataset_reference"),
            ("dataset without the required metric",
             insert_payload(dataset_version_id=str(approved_empty)),
             "REFERENCE_INVALID", "dataset_missing_required_metrics"),
            ("snapshot mode is gated on NI-035",
             insert_payload(mode="snapshot", snapshot_id=str(uuid4())),
             "REFERENCE_INVALID", "reference_unavailable"),
            ("dangling insertion anchor",
             insert_payload(after_block_id=str(uuid4())),
             "REFERENCE_INVALID", "dangling_after_block_reference"),
        )
        for name, payload, code, reason in cases:
            with self.subTest(case=name):
                response = self.add_chart(detail.document.id, payload)
                self.assertEqual(response.status_code, 422, response.text)
                error = ErrorResponse.model_validate(response.json()).error
                self.assertEqual(error.code, code)
                self.assertIn(reason,
                              str([detail.reason for detail in (error.details or ())]))
                self.assertEqual(self.table_counts(detail.document.id),
                                 {"document_versions": 1, "document_blocks": 0})
        # A non-empty filters object never reaches the service: the shared
        # Selection contract rejects it (the P0 filter domain is empty).
        with self.as_session(self.alice_id):
            filtered = self.client.post(
                f"/api/documents/{detail.document.id}/chart-blocks",
                json=insert_payload(selection={"start": "2026-01-01",
                                               "end": "2026-01-08",
                                               "frequency": "day",
                                               "filters": {"source": ["SRC-LLAMA"]}}),
                headers={"Authorization": "Bearer t.alice", "If-Match": '"1"'})
        self.assertEqual(filtered.status_code, 422)
        self.assertEqual(ErrorResponse.model_validate(filtered.json()).error.code,
                         "VALIDATION_ERROR")

    def test_08_inspected_evidence_survives_source_changes(self):
        detail = self.create_document(self.alice)
        source_key = self.dataset_key("intents")
        dataset_v1 = self.insert_dataset_version(source_key, version=1)
        inserted = self.add_chart(detail.document.id,
                                  insert_payload(dataset_version_id=str(dataset_v1)))
        self.assertEqual(inserted.status_code, 201, inserted.text)
        block_id = inserted.json()["value"]["block_id"]
        revision_two = self.stored_document(self.alice, detail.document.id)

        # A "source change": a newer approved dataset version of the same key
        # (different content hash — the (key, sha) dedup pair is immutable).
        dataset_v2 = self.insert_dataset_version(source_key, version=2,
                                                 sha="b" * 64)
        self.assertNotEqual(dataset_v1, dataset_v2)

        # The old revision is untouched — no silent re-pin, no hash drift.
        after = self.stored_document(self.alice, detail.document.id)
        self.assertEqual(after["content"], revision_two["content"])
        self.assertEqual(after["resolved_contexts"], revision_two["resolved_contexts"])
        self.assertEqual(after["resolved_contexts"][block_id]["dataset_version_id"],
                         str(dataset_v1))

        # A whole-document save with an unchanged chart block carries the
        # frozen context forward VERBATIM (text edit elsewhere).
        content = copy.deepcopy(revision_two["content"])
        content["content"].append(text_paragraph("A later note"))
        with self.as_session(self.alice_id):
            saved = self.client.post(
                f"/api/documents/{detail.document.id}/versions",
                json={"schema_version": 1, "content": content},
                headers={"Authorization": "Bearer t.alice", "If-Match": '"2"'})
        self.assertEqual(saved.status_code, 201, saved.text)
        revision_three = self.stored_document(self.alice, detail.document.id)
        self.assertEqual(revision_three["revision"], 3)
        self.assertEqual(revision_three["resolved_contexts"],
                         revision_two["resolved_contexts"])

        # Changing the chart selection through a raw save is rejected: the
        # inspected context would no longer describe the block (the explicit
        # re-resolution flow arrives with NI-042/NI-043).
        changed = copy.deepcopy(revision_three["content"])
        for node in changed["content"]:
            if node["type"] == "liveChart":
                node["attrs"]["selection"] = selection("2026-01-02", "2026-01-09")
        with self.as_session(self.alice_id):
            rejected = self.client.post(
                f"/api/documents/{detail.document.id}/versions",
                json={"schema_version": 1, "content": changed},
                headers={"Authorization": "Bearer t.alice", "If-Match": '"3"'})
        self.assertEqual(rejected.status_code, 422)
        error = ErrorResponse.model_validate(rejected.json()).error
        self.assertEqual(error.code, "REFERENCE_INVALID")
        self.assertIn("chart_context_unresolved",
                      str([detail.reason for detail in (error.details or ())]))

        # Injecting a NEW chart block through a raw save is equally rejected.
        injected = copy.deepcopy(revision_three["content"])
        injected["content"].append({
            "type": "liveChart",
            "attrs": {"block_id": str(uuid4()),
                      "chart_definition_version_id": str(CHART_ID),
                      "mode": "live", "selection": selection(),
                      "observed_dataset_version_id": str(dataset_v1)},
        })
        with self.as_session(self.alice_id):
            rejected_new = self.client.post(
                f"/api/documents/{detail.document.id}/versions",
                json={"schema_version": 1, "content": injected},
                headers={"Authorization": "Bearer t.alice", "If-Match": '"3"'})
        self.assertEqual(rejected_new.status_code, 422)

        # Deleting the chart block drops its context with the block; the
        # document remains savable and a fresh insertion works again.
        without_chart = copy.deepcopy(revision_three["content"])
        without_chart["content"] = [node for node in without_chart["content"]
                                    if node["type"] != "liveChart"]
        with self.as_session(self.alice_id):
            deleted = self.client.post(
                f"/api/documents/{detail.document.id}/versions",
                json={"schema_version": 1, "content": without_chart},
                headers={"Authorization": "Bearer t.alice", "If-Match": '"3"'})
        self.assertEqual(deleted.status_code, 201, deleted.text)
        revision_four = self.stored_document(self.alice, detail.document.id)
        self.assertEqual(revision_four["resolved_contexts"], {})
        again = self.add_chart(detail.document.id,
                               insert_payload(dataset_version_id=str(dataset_v2)),
                               revision=4)
        self.assertEqual(again.status_code, 201, again.text)
        # The new block pins what the user inspected THIS time (v2), and the
        # removed block's v1 context is gone — history keeps rev 3 as it was.
        final = self.stored_document(self.alice, detail.document.id)
        new_block_id = again.json()["value"]["block_id"]
        self.assertEqual(final["resolved_contexts"][new_block_id]["dataset_version_id"],
                         str(dataset_v2))
        with user_transaction(self.engine, self.alice_id) as connection:
            historical = connection.execute(text("""
                SELECT resolved_contexts FROM app.document_versions
                WHERE document_id = :id AND revision = 3
            """), {"id": detail.document.id}).mappings().one()
        self.assertEqual(historical["resolved_contexts"][block_id]["dataset_version_id"],
                         str(dataset_v1))

    def test_09_insertion_position_control(self):
        detail = self.create_document(self.alice)
        base = document_with(2)
        with self.as_session(self.alice_id):
            saved = self.client.post(
                f"/api/documents/{detail.document.id}/versions",
                json={"schema_version": 1, "content": base},
                headers={"Authorization": "Bearer t.alice", "If-Match": '"1"'})
        self.assertEqual(saved.status_code, 201, saved.text)
        dataset_id = self.insert_dataset_version(self.dataset_key("intents"))
        first_block = base["content"][0]["attrs"]["block_id"]
        anchored = self.add_chart(
            detail.document.id,
            insert_payload(dataset_version_id=str(dataset_id),
                           after_block_id=first_block),
            revision=2)
        self.assertEqual(anchored.status_code, 201, anchored.text)
        stored = self.stored_document(self.alice, detail.document.id)
        types = [node["type"] for node in stored["content"]["content"]]
        self.assertEqual(types, ["paragraph", "liveChart", "paragraph"])
        appended = self.add_chart(detail.document.id,
                                  insert_payload(dataset_version_id=str(dataset_id)),
                                  revision=3)
        self.assertEqual(appended.status_code, 201, appended.text)
        stored = self.stored_document(self.alice, detail.document.id)
        types = [node["type"] for node in stored["content"]["content"]]
        self.assertEqual(types, ["paragraph", "liveChart", "paragraph", "liveChart"])

    def test_10_block_limit_is_enforced_by_the_canonical_flow(self):
        detail = self.create_document(self.alice)
        with self.as_session(self.alice_id):
            saved = self.client.post(
                f"/api/documents/{detail.document.id}/versions",
                json={"schema_version": 1, "content": document_with(199)},
                headers={"Authorization": "Bearer t.alice", "If-Match": '"1"'})
        self.assertEqual(saved.status_code, 201, saved.text)
        dataset_id = self.insert_dataset_version(self.dataset_key("intents"))
        full = self.add_chart(detail.document.id,
                              insert_payload(dataset_version_id=str(dataset_id)),
                              revision=2)
        self.assertEqual(full.status_code, 201, full.text)
        over = self.add_chart(detail.document.id,
                              insert_payload(dataset_version_id=str(dataset_id)),
                              revision=3)
        self.assertEqual(over.status_code, 413)
        self.assertEqual(ErrorResponse.model_validate(over.json()).error.code,
                         "PAYLOAD_TOO_LARGE")
        # Projections are per revision: 199 blocks (rev 2) + 200 (rev 3); the
        # rejected 413 insertion added no partial rows.
        self.assertEqual(self.table_counts(detail.document.id),
                         {"document_versions": 3, "document_blocks": 399})


# --------------------------------------------------------------------------- #
# Shared test shims
# --------------------------------------------------------------------------- #


class _StubVerifier:
    """Stubbed token verifier so no provider or JWKS is ever contacted."""

    def __init__(self, result):
        self.result = result

    def verify(self, token):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _verified(subject) -> VerifiedToken:
    return VerifiedToken(subject=subject,
                         expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(minutes=5),
                         issued_at=dt.datetime.now(dt.UTC))
