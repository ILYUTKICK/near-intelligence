"""NI-041 chart-block insertion tests: one confirmation, one valid block.

Offline classes run everywhere (request contract, route contract); the
database class needs scripts/run-db-tests.py — a skip is never successful
integration evidence. Covered guarantees:

- one confirmation appends exactly ONE valid liveChart block as ONE new
  revision through the canonical flow (projections included);
- ownership is the verified principal's (Alice/Bob matrix at HTTP level);
- the inspected evidence is frozen: the pinned dataset version and the
  ResolvedContext survive source changes verbatim, and a whole-document save
  carries unchanged contexts verbatim, while explicit NI-042 chart edits
  resolve new validated contexts from their inspected immutable dataset pins;
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
import csv
import datetime as dt
import json
import os
import tempfile
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
from near_api.datasets import delivery
from near_api.datasets.delivery import _context_hash
from near_api.db.session import create_runtime_engine, user_transaction
from near_api.documents import service
from near_api.documents.context_resolver import (
    ChartDefinitionRow,
    build_resolved_context,
    load_chart_definition,
    validate_selection_against_definition,
)
from near_api.documents.schema import canonical_context_json, parse_document
from near_api.insights.schemas import ResolvedContext
from near_api.main import app
from near_api.metrics.registry import definition_by_metric_id
from near_api.schemas.chart_blocks import ChartBlockInsertRequest
from near_api.schemas.chart_selection import ChartSelection
from near_api.schemas.common import ErrorResponse
from near_api.schemas.delivery import ResolvedSelection
import test_delivery_apis as data_fixture

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


def observed_context(view: dict) -> dict:
    return {
        "chart_definition_version_id": view["definition"]["id"],
        "dataset_version_id": view["dataset"]["id"],
        "selection": view["selection"],
        "context_hash": view["context_hash"],
        "renderer_version": view["definition"]["renderer_version"],
        "metric_definition_versions": view["definition"]["metric_definition_ids"],
        "resolved_at": view["resolved_at"],
    }


def volume_context(operator, dataset_id: UUID, *, selected: dict | None = None) -> dict:
    with operator.connect() as connection:
        definition = load_chart_definition(connection, CHART_ID, error_path="context")
    return build_resolved_context(
        definition, dataset_id, ChartSelection.model_validate(selected or selection()),
        resolved_at=dt.datetime.now(dt.UTC)).model_dump(mode="json")


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

    def test_historical_contract_has_no_selection_parameters(self):
        prefix = "/api/documents/{document_id}/versions/{version_id}/chart-blocks/{block_id}"
        routes = app.openapi()["paths"]
        for suffix in ("view", "csv"):
            path = f"{prefix}/{suffix}"
            operation = routes[path]["get"]
            self.assertEqual(
                {(p["name"], p["in"]) for p in operation["parameters"]},
                {("document_id", "path"), ("version_id", "path"), ("block_id", "path"),
                 ("authorization", "header")})
            self.assertIn("409", operation["responses"])
            response = self.client.get(
                f"/api/documents/{uuid4()}/versions/{uuid4()}/chart-blocks/{uuid4()}/{suffix}")
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(set(routes[prefix + "/csv"]["get"]["responses"]["200"]["content"]),
                         {"text/csv"})


def register_test_chart_catalog(operator) -> None:
    from near_api.charts.registry import register_charts
    from near_api.metrics.registry import register_definitions

    sources = {"SRC-LLAMA": "DefiLlama saved snapshots",
               "SRC-DASHBOARD": "NEAR Dashboard",
               "SRC-BQ": "BigQuery export", "SRC-PRICE": "Saved price snapshots",
               "SRC-FASTNEAR": "FastNear indexed blocks",
               "SRC-NEAR-RPC": "NEAR public RPC"}
    with operator.begin() as connection:
        for source_id, name in sources.items():
            connection.execute(text("""
                INSERT INTO app.sources(id, name, access_status, license_status)
                VALUES (:id, :name, 'documented', 'unverified')
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
            """), {"id": source_id, "name": name})
        register_definitions(connection)
        register_charts(connection)


class ChartBlockDatabaseFixture:
    """Registered chart, two accounts and disposable PostgreSQL connections."""

    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[3]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.engine = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        cls.engine_b = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        cls.operator = create_engine(os.environ["NI_TEST_OPERATOR_URL"], poolclass=NullPool,
                                     hide_parameters=True)
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"], poolclass=NullPool,
                                  hide_parameters=True)
        command.upgrade(cls.config, "head")
        register_test_chart_catalog(cls.operator)

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

    def publish_volume(self, key, value):
        if not hasattr(self, "directory"):
            tmp = tempfile.TemporaryDirectory(prefix="ni043-", dir=os.environ["NI_TEST_TMP_DIR"])
            self.addCleanup(tmp.cleanup)
            self.directory = Path(tmp.name)
            self.storage_root = self.directory / "storage"
        dimensions = {"source": "SRC-LLAMA"}
        return data_fixture.DeliveryDatabaseTests.stage_fixture(
            self, key,
            [data_fixture.observation(METRIC_ID, dt.date(2026, 1, 1), value=value,
                                      bound_kind="lower", dimensions=dimensions),
             data_fixture.observation(METRIC_ID, dt.date(2026, 1, 2), value=None,
                                      dimensions=dimensions)],
            [METRIC_ID], window=("2026-01-01", "2026-01-03"))

    def preview_volume(self, document_id, *, dataset_version="latest", start="2026-01-01",
                       end="2026-01-04"):
        with self.as_session(self.alice_id):
            response = self.client.get(
                f"/api/documents/{document_id}/chart-view",
                params={"chart_definition_version_id": str(CHART_ID), "start": start,
                        "end": end, "dataset_version": str(dataset_version),
                        "filters": json.dumps({"source": "SRC-LLAMA"})},
                headers={"Authorization": "Bearer t.alice"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def chart_document(self, preview):
        block_id = str(uuid4())
        return block_id, {"type": "doc", "schema_version": 1, "content": [
            {"type": "liveChart", "attrs": {
                "block_id": block_id, "mode": "live", "selection": preview["selection"],
                "chart_definition_version_id": preview["definition"]["id"],
                "observed_dataset_version_id": preview["dataset"]["id"],
            }},
        ]}


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class ChartBlockServiceDatabaseTests(ChartBlockDatabaseFixture, unittest.TestCase):
    """Insertion guarantees on the disposable PostgreSQL cluster."""

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

    def test_replay_is_scoped_to_the_concrete_destination(self):
        first_doc = self.create_document(self.alice, "Synthetic first")
        second_doc = self.create_document(self.alice, "Synthetic second")
        foreign = self.create_document(self.bob, "Synthetic Bob")
        dataset = self.insert_dataset_version(self.dataset_key("replay-destination"))
        payload = insert_payload(dataset_version_id=str(dataset))
        key = str(uuid4())
        first = self.add_chart(first_doc.document.id, payload, key=key)
        self.assertEqual(first.status_code, 201, first.text)
        # An owned replay may never satisfy a request targeting another owner.
        denied = self.add_chart(foreign.document.id, payload, key=key)
        self.assertEqual(denied.status_code, 404, denied.text)
        second = self.add_chart(second_doc.document.id, payload, key=key)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(second.json()["document"]["id"], str(second_doc.document.id))
        self.assertNotEqual(first.json()["value"]["block_id"], second.json()["value"]["block_id"])
        for document, result in ((first_doc, first), (second_doc, second)):
            replay = self.add_chart(document.document.id, payload, revision=2, key=key)
            self.assertEqual(replay.status_code, 201)
            self.assertEqual(replay.json(), result.json())
            self.assertEqual(self.table_counts(document.document.id),
                             {"document_versions": 2, "document_blocks": 1})

    def test_04_idempotent_concurrent_same_key_single_block(self):
        detail = self.create_document(self.alice)
        dataset_id = self.insert_dataset_version(self.dataset_key("intents"))
        payload = ChartBlockInsertRequest.model_validate(
            insert_payload(dataset_version_id=str(dataset_id)))
        from near_api.documents import idempotency
        from near_api.documents.chart_blocks import append_chart_block_in_transaction
        key = uuid4()
        route_key = idempotency.ROUTE_ADD_CHART_BLOCK.format(document_id=detail.document.id)
        fingerprint = idempotency.request_fingerprint(
            route_key, self.alice_id,
            insert_payload(dataset_version_id=str(dataset_id)))
        barrier = threading.Barrier(2)
        outcomes = {}

        def run(engine, tag):
            barrier.wait()
            outcomes[tag] = idempotency.execute_idempotent(
                engine, self.alice, route_key=route_key,
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

        # NI-042 explicit edits freeze the supplied inspected pin and selection;
        # this is not latest resolution (v2 exists, but v1 remains selected).
        changed = copy.deepcopy(revision_three["content"])
        selected = {**selection("2026-01-02", "2026-01-09"),
                    "filters": {"source": "SRC-LLAMA"}}
        changed["content"][0]["attrs"]["selection"] = selected
        changed_save = self.save_document(detail.document.id, changed, revision=3)
        self.assertEqual(changed_save.status_code, 201, changed_save.text)
        revision_four = self.stored_document(self.alice, detail.document.id)
        changed_context = revision_four["resolved_contexts"][block_id]
        self.assertEqual(changed_context["dataset_version_id"], str(dataset_v1))
        self.assertEqual(changed_context["selection"], selected)
        self.assertNotEqual(changed_context["context_hash"],
                            revision_three["resolved_contexts"][block_id]["context_hash"])
        self.assertEqual(changed_context["context_hash"], _context_hash(
            {"id": CHART_ID}, dataset_v1,
            ResolvedSelection.model_validate(selected), (METRIC_ID,)))

        # Refresh is also explicit: adopt the inspected v2 UUID; the saved
        # context hash must describe exactly that new pin, not the old view.
        refreshed = copy.deepcopy(revision_four["content"])
        refreshed["content"][0]["attrs"]["observed_dataset_version_id"] = str(dataset_v2)
        refreshed_save = self.save_document(detail.document.id, refreshed, revision=4)
        self.assertEqual(refreshed_save.status_code, 201, refreshed_save.text)
        revision_five = self.stored_document(self.alice, detail.document.id)
        self.assertEqual(revision_five["resolved_contexts"][block_id]["dataset_version_id"],
                         str(dataset_v2))
        # A stale concurrent chart edit cannot bypass the revision lock.
        stale = self.save_document(detail.document.id, changed, revision=4)
        self.assertEqual(stale.status_code, 409, stale.text)
        self.assertEqual(self.stored_document(self.alice, detail.document.id), revision_five)

        # Duplicated/new node attrs resolve independently under the same
        # canonical validation and frozen pin, without arbitrary contexts.
        duplicated = copy.deepcopy(revision_five["content"])
        new_node = copy.deepcopy(duplicated["content"][0])
        new_block_id = str(uuid4())
        new_node["attrs"]["block_id"] = new_block_id
        duplicated["content"].append(new_node)
        duplicate_save = self.save_document(detail.document.id, duplicated, revision=5)
        self.assertEqual(duplicate_save.status_code, 201, duplicate_save.text)
        revision_six = self.stored_document(self.alice, detail.document.id)
        self.assertEqual(set(revision_six["resolved_contexts"]), {block_id, new_block_id})
        self.assertEqual(revision_six["resolved_contexts"][new_block_id]["dataset_version_id"],
                         str(dataset_v2))
        self.assertEqual(revision_six["resolved_contexts"][block_id],
                         revision_five["resolved_contexts"][block_id])

        # Deleting chart blocks drops current contexts only. Historical
        # evidence is immutable despite edits, refresh, duplicates and deletion.
        without_chart = copy.deepcopy(revision_six["content"])
        without_chart["content"] = [node for node in without_chart["content"]
                                    if node["type"] != "liveChart"]
        deleted = self.save_document(detail.document.id, without_chart, revision=6)
        self.assertEqual(deleted.status_code, 201, deleted.text)
        self.assertEqual(self.stored_document(self.alice, detail.document.id)["resolved_contexts"], {})
        with user_transaction(self.engine, self.alice_id) as connection:
            historical = connection.execute(text("""
                SELECT content, resolved_contexts FROM app.document_versions
                WHERE document_id = :id AND revision = 3
            """), {"id": detail.document.id}).mappings().one()
        self.assertEqual(historical["content"], revision_three["content"])
        self.assertEqual(historical["resolved_contexts"], revision_three["resolved_contexts"])

    def save_document(self, document_id, content, *, revision, subject_id=None,
                      observed_contexts=None):
        subject = subject_id or self.alice_id
        with self.as_session(subject):
            return self.client.post(
                f"/api/documents/{document_id}/versions",
                json={"schema_version": 1, "content": content,
                      "observed_contexts": observed_contexts or []},
                headers={"Authorization": f"Bearer t.{subject}",
                         "If-Match": f'"{revision}"'})

    def test_explicit_chart_edits_validate_references_and_owner_atomically(self):
        detail = self.create_document(self.alice)
        dataset_id = self.insert_dataset_version(self.dataset_key("explicit-edit"))
        self.assertEqual(self.add_chart(detail.document.id,
            insert_payload(dataset_version_id=str(dataset_id))).status_code, 201)
        original = self.stored_document(self.alice, detail.document.id)
        staged = self.insert_dataset_version(self.dataset_key("staged-edit"), status="staged")
        cases = (
            {"chart_definition_version_id": str(uuid4())},
            {"chart_definition_version_id": str(UNAVAILABLE_CHART_ID)},
            {"observed_dataset_version_id": str(staged)},
            {"selection": {**selection(), "filters": {"source": "unapproved"}}},
            {"mode": "snapshot", "snapshot_id": str(uuid4())},
        )
        for attrs in cases:
            changed = copy.deepcopy(original["content"])
            changed["content"][0]["attrs"].update(attrs)
            response = self.save_document(detail.document.id, changed, revision=2)
            self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual(self.stored_document(self.alice, detail.document.id), original)
        changed = copy.deepcopy(original["content"])
        changed["content"][0]["attrs"]["selection"] = selection("2026-01-02", "2026-01-09")
        denied = self.save_document(detail.document.id, changed, revision=2,
                                    subject_id=self.bob_id)
        self.assertEqual(denied.status_code, 404)
        submitted_context = self.save_document(
            detail.document.id, changed, revision=2,
            observed_contexts=[original["resolved_contexts"][next(iter(original["resolved_contexts"]))]])
        self.assertEqual(submitted_context.status_code, 422, submitted_context.text)
        self.assertEqual(self.stored_document(self.alice, detail.document.id), original)

    def test_chart_view_auth_owner_and_explicit_dataset_choice(self):
        detail = self.create_document(self.alice)
        params = {"chart_definition_version_id": str(CHART_ID),
                  "start": "2026-01-01", "end": "2026-01-08",
                  "dataset_version": str(uuid4())}
        path = f"/api/documents/{detail.document.id}/chart-view"
        anonymous = self.client.get(path, params=params)
        self.assertEqual(anonymous.status_code, 401)
        with self.as_session(self.bob_id):
            foreign = self.client.get(path, params=params,
                                      headers={"Authorization": "Bearer t.bob"})
            missing = self.client.get(f"/api/documents/{uuid4()}/chart-view", params=params,
                                      headers={"Authorization": "Bearer t.bob"})
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(foreign.json()["error"]["message"], missing.json()["error"]["message"])
        self.assertEqual(foreign.headers["Cache-Control"], "no-store")
        with self.as_session(self.alice_id):
            no_choice = {key: value for key, value in params.items() if key != "dataset_version"}
            absent = self.client.get(path, params=no_choice,
                                     headers={"Authorization": "Bearer t.alice"})
            self.assertEqual(absent.status_code, 422)
            for changes in ({"dataset_version": "https://example.com/data"},
                            {"start": "2026-01-08", "end": "2026-01-01"},
                            {"start": "2025-01-01"},
                            {"filters": '{"source":"unapproved"}'},
                            {"chart_definition_version_id": str(UNAVAILABLE_CHART_ID)}):
                response = self.client.get(path, params={**params, **changes},
                                           headers={"Authorization": "Bearer t.alice"})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.headers["Cache-Control"], "no-store")

    def historical_chart(self, document_id, version_id, block_id, suffix="view", *,
                         subject=None, params=None):
        with self.as_session(subject or self.alice_id):
            return self.client.get(
                f"/api/documents/{document_id}/versions/{version_id}/chart-blocks/{block_id}/{suffix}",
                params=params, headers={"Authorization": "Bearer synthetic"})

    def test_frozen_chart_survives_publication_before_and_after_save(self):
        document_id = self.create_document(self.alice).document.id
        key = self.dataset_key("preview-save")
        value = "12.123456789012345678901234"
        first = self.publish_volume(key, value)
        inspected = self.preview_volume(document_id)
        self.assertEqual(inspected["dataset"]["id"], str(first.dataset_version_id))
        self.assertEqual(inspected["latest_approved_dataset_version_id"], inspected["dataset"]["id"])
        block_id, content = self.chart_document(inspected)

        # Re-publication between inspection and the CAS must not change the
        # selected evidence, but the working reader can surface the new pointer.
        second = self.publish_volume(key, "222")
        claim = {**observed_context(inspected), "resolved_at": "2000-01-01T00:00:00Z"}
        saved = self.save_document(document_id, content, revision=1, observed_contexts=[claim])
        self.assertEqual(saved.status_code, 201, saved.text)
        version = saved.json()["version"]
        frozen = version["resolved_contexts"][block_id]
        self.assertEqual({**frozen, "resolved_at": claim["resolved_at"]}, claim)
        self.assertNotEqual(frozen["resolved_at"], claim["resolved_at"])
        pinned = self.preview_volume(document_id, dataset_version=first.dataset_version_id)
        self.assertEqual(pinned["context_hash"], frozen["context_hash"])
        self.assertEqual(pinned["latest_approved_dataset_version_id"], str(second.dataset_version_id))
        self.assertEqual(pinned["dataset"]["id"], str(first.dataset_version_id))

        # Assert explicitly that the historical resolver never looks at the pointer.
        with patch.object(delivery, "resolve_latest_version", side_effect=AssertionError("latest queried")):
            before = self.historical_chart(document_id, version["id"], block_id)
            csv_before = self.historical_chart(document_id, version["id"], block_id, "csv")
        self.assertEqual(before.status_code, 200, before.text)
        self.assertEqual(csv_before.status_code, 200, csv_before.text)
        self.assertEqual(before.headers["Cache-Control"], "no-store")
        self.assertEqual(csv_before.headers["Cache-Control"], "no-store")
        self.assertTrue(csv_before.headers["Content-Type"].startswith("text/csv"))
        self.assertTrue(csv_before.headers["Content-Disposition"].startswith("attachment;"))
        self.assertEqual(before.json()["context_hash"], frozen["context_hash"])
        self.assertEqual(before.json()["resolved_at"], frozen["resolved_at"])
        rows = list(csv.DictReader(csv_before.text.splitlines()))
        self.assertEqual([row["value"] for row in rows], [value, "", ""])
        self.assertEqual([row["quality_status"] for row in rows], ["ok", "missing", "missing"])
        self.assertEqual([row["bound_kind"] for row in rows], ["lower", "", ""])
        self.assertEqual(rows[0]["metric_definition_version_id"], str(METRIC_ID))
        self.assertEqual(rows[0]["dataset_content_sha256"], first.content_sha256)
        self.assertEqual(json.loads(rows[0]["filters"]), inspected["selection"]["filters"])

        self.publish_volume(key, "333")
        removed = self.save_document(document_id, document_with(1), revision=2)
        self.assertEqual(removed.status_code, 201, removed.text)
        self.assertEqual(removed.json()["version"]["resolved_contexts"], {})
        with self.as_session(self.alice_id):
            saved_again = self.client.get(
                f"/api/documents/{document_id}/versions/{version['id']}",
                headers={"Authorization": "Bearer t.alice"})
        self.assertEqual(saved_again.json(), version)
        self.assertEqual(self.historical_chart(document_id, version["id"], block_id).json(),
                         before.json())
        self.assertEqual(self.historical_chart(document_id, version["id"], block_id, "csv").content,
                         csv_before.content)
        self.assertEqual(self.historical_chart(
            document_id, version["id"], block_id, params={"dataset_version": "latest"}
        ).status_code, 422)
        alice_other = self.create_document(self.alice).document.id
        for suffix in ("view", "csv"):
            for target, revision, block, subject in (
                (document_id, version["id"], block_id, self.bob_id),
                (alice_other, version["id"], block_id, self.alice_id),
                (document_id, version["id"], uuid4(), self.alice_id),
                (document_id, removed.json()["version"]["id"], block_id, self.alice_id),
            ):
                denied = self.historical_chart(target, revision, block, suffix, subject=subject)
                self.assertEqual(denied.status_code, 404, denied.text)
                self.assertEqual(denied.json()["error"]["code"], "NOT_FOUND")
                self.assertEqual(denied.headers["Cache-Control"], "no-store")

    def test_observed_context_version_mismatch_leaves_no_revision(self):
        detail = self.create_document(self.alice)
        dataset = self.publish_volume(self.dataset_key("observation-mismatch"), "15")
        inspected = self.preview_volume(detail.document.id, dataset_version=dataset.dataset_version_id)
        _, content = self.chart_document(inspected)
        claim = observed_context(inspected)
        for changes in (
            {"chart_definition_version_id": str(uuid4())},
            {"dataset_version_id": str(uuid4())},
            {"selection": selection("2026-01-02", "2026-01-04")},
            {"renderer_version": "synthetic-other-renderer"},
            {"metric_definition_versions": [str(uuid4())]},
            {"context_hash": "f" * 64},
        ):
            with self.subTest(changes=changes):
                response = self.save_document(
                    detail.document.id, content, revision=1, observed_contexts=[{**claim, **changes}])
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.json()["error"]["code"], "REFERENCE_INVALID")
        self.assertEqual(self.table_counts(detail.document.id),
                         {"document_versions": 1, "document_blocks": 0})

    def test_missing_or_inconsistent_historical_artifacts_fail_explicitly(self):
        document_id = self.create_document(self.alice).document.id
        dataset = self.publish_volume(self.dataset_key("lost-artifacts"), "5")
        # No observations fall in the selected range, a legitimate empty
        # result. The prepared artifact as a whole is still present.
        inspected = self.preview_volume(document_id, dataset_version=dataset.dataset_version_id,
                                        start="2026-01-07", end="2026-01-09")
        block_id, content = self.chart_document(inspected)
        saved = self.save_document(document_id, content, revision=1)
        self.assertEqual(saved.status_code, 201, saved.text)
        version = saved.json()["version"]
        version_id = version["id"]
        view = self.historical_chart(document_id, version_id, block_id)
        self.assertEqual(view.status_code, 200, view.text)
        self.assertEqual([point["value"] for point in view.json()["series"][0]["points"]],
                         [None, None])

        # Exercise the explicit error surface after a simulated damaged restore.
        for contexts, reason in (
            ({}, "missing_chart_context"),
            ({block_id: {**version["resolved_contexts"][block_id],
                         "renderer_version": "unavailable-renderer"}}, "chart_context_mismatch"),
        ):
            with self.admin.begin() as connection:
                connection.execute(text("""
                    UPDATE app.document_versions SET resolved_contexts = CAST(:contexts AS jsonb)
                    WHERE id = :id
                """), {"contexts": json.dumps(contexts), "id": version_id})
            self.assert_reconstruction_error(document_id, version_id, block_id, reason)

        with self.admin.begin() as connection:
            connection.execute(text("""
                UPDATE app.document_versions
                SET resolved_contexts = CAST(:contexts AS jsonb),
                    content = jsonb_set(content, '{content,0,attrs,selection,end}', '"2026-01-10"')
                WHERE id = :id
            """), {"contexts": json.dumps(version["resolved_contexts"]), "id": version_id})
        self.assert_reconstruction_error(
            document_id, version_id, block_id, "revision_content_hash_mismatch")

        with self.admin.begin() as connection:
            connection.execute(text("""
                UPDATE app.document_versions SET content = CAST(:content AS jsonb) WHERE id = :id
            """), {"content": json.dumps(version["content"]), "id": version_id})
            # One observation survives and the working read already warmed
            # the public version cache. Only digest verification catches this.
            connection.execute(text("""
                DELETE FROM app.metric_observations WHERE dataset_version_id = :id AND value IS NULL
            """), {"id": dataset.dataset_version_id})
        self.assert_reconstruction_error(
            document_id, version_id, block_id, "pinned_artifact_unavailable")
        self.assertEqual(self.historical_chart(
            document_id, version_id, block_id, subject=self.bob_id).status_code, 404)

    def assert_reconstruction_error(self, document_id, version_id, block_id, reason):
        for suffix in ("view", "csv"):
            response = self.historical_chart(document_id, version_id, block_id, suffix)
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(response.json()["error"]["code"], "RECONSTRUCTION_ERROR")
            self.assertEqual(response.json()["error"]["details"][0]["reason"], reason)
            self.assertEqual(response.headers["Cache-Control"], "no-store")

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
