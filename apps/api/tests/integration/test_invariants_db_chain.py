"""NI-061 database invariant tests on the disposable PostgreSQL cluster.

The same synthetic raw bundle used by the offline oracle tests flows through
the real pipeline — NI-029 emission, NI-028 staging/publication on real
PostgreSQL, NI-032 delivery APIs, NI-036 revision projections, NI-041/NI-043
frozen chart contexts and the NI-049 evidence graph — and every delivered
value is compared EXACTLY (Decimal equality; amounts re-scaled to yoctoNEAR
integers) against the independent oracle recomputed from the raw extract.
Publishing a new latest version must never change a pinned reconstruction,
and a mutated approved row must fail that reconstruction closed instead of
serving changed values.

Database cases need scripts/run-db-tests.py (they skip elsewhere; a skip is
never integration evidence). All accounts are synthetic (``users`` is reset
per test, Alice/Bob); every dataset key, document and amount is invented
fixture data labeled ``synthetic``; nothing touches archives, collectors,
providers or the network.
"""

import datetime as dt
import json
import os
import shutil
import unittest
import uuid as uuid_module
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from integration import invariant_fixtures as fixtures
from integration.oracles import YOCTO_PER_NEAR

from near_api.auth.principal import Principal, get_runtime_engine
from near_api.charts.registry import chart_by_chart_id
from near_api.datasets.service import (
    create_dataset_operator_engine,
    publish,
    stage,
)
from near_api.db.security import ResourceNotFound
from near_api.db.session import create_runtime_engine, user_transaction
from near_api.documents import service as documents
from near_api.documents.context_resolver import (
    ReconstructionError,
    build_resolved_context,
    load_chart_definition,
    reconstruct_revision_chart,
)
from near_api.documents.schema import DocumentSchemaError, parse_document
from near_api.main import app
from near_api.metrics.emit import DatasetSpec, ManifestInputSpec, build_all_manifests
from near_api.metrics.registry import (TreasuryAccounts, definition_by_metric_id,
                                       definition_by_metric_id_version)
from near_api.repositories.documents import get_version as get_version_row
from near_api.schemas.chart_selection import ChartSelection

YOCTO = Decimal(YOCTO_PER_NEAR)
ONE_DAY = dt.timedelta(days=1)
D1, D2, D3 = fixtures.DAYS
D4 = fixtures.WINDOW_END_EXCLUSIVE
CONVERSIONS_CHART = chart_by_chart_id("observed-conversions")

SOURCE_IDS = {"SRC-BQ": "BigQuery export", "SRC-PRICE": "Saved price snapshots",
              "SRC-LLAMA": "DefiLlama saved snapshots",
              "SRC-DASHBOARD": "Public dashboard saved snapshots",
              "SRC-FASTNEAR": "FastNear indexed blocks",
              "SRC-NEAR-RPC": "NEAR public RPC"}

ROLE_BY_INPUT = {"flows": "raw", "daily": "price", "supply": "normalized",
                 "treasury": "normalized"}

DOCUMENT_TABLES = ("document_versions", "document_blocks", "insights",
                   "hypotheses", "evidence_links")


def unique_key(stem: str) -> str:
    return f"metrics.{stem}.synthetic-{uuid_module.uuid4().hex[:10]}"


def write_manifest_document(directory: Path, name: str, document: dict) -> Path:
    # a dedicated subdirectory: the raw saved-input files live in the bundle
    # root and must never be overwritten by the emitted manifest documents
    manifests = directory / "manifests"
    manifests.mkdir(exist_ok=True)
    path = manifests / f"{name}-synthetic.json"
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return path


class InvariantDatabaseFixture:
    """Engines, registered catalogs, two synthetic accounts and the bundle."""

    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[4]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.operator = create_dataset_operator_engine(os.environ["NI_TEST_OPERATOR_URL"])
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"], poolclass=NullPool,
                                  hide_parameters=True)
        cls.runtime = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        command.upgrade(cls.config, "head")
        from near_api.charts.registry import register_charts
        from near_api.metrics import register_definitions

        with cls.operator.begin() as connection:
            for source_id, name in SOURCE_IDS.items():
                connection.execute(text("""
                    INSERT INTO app.sources(id, name, access_status, license_status)
                    VALUES (:id, :name, 'documented', 'unverified')
                    ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """), {"id": source_id, "name": name})
            register_definitions(connection)
            register_charts(connection)
        app.dependency_overrides[get_runtime_engine] = lambda: cls.runtime
        cls.client = TestClient(app, raise_server_exceptions=False)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.pop(get_runtime_engine, None)
        cls.runtime.dispose()
        cls.operator.dispose()
        cls.admin.dispose()

    def setUp(self):
        with self.operator.begin() as connection:
            connection.execute(text("DELETE FROM app.users"))
        self.alice_id, self.bob_id = uuid4(), uuid4()
        for subject, name in ((self.alice_id, "Synthetic Alice"),
                              (self.bob_id, "Synthetic Bob")):
            with user_transaction(self.runtime, subject) as connection:
                connection.execute(text("INSERT INTO app.users(id) VALUES (:id)"),
                                   {"id": subject})
                connection.execute(text("""INSERT INTO app.user_profiles(user_id,
                                          display_name) VALUES (:id, :name)"""),
                                   {"id": subject, "name": name})
        self.alice = Principal(id=self.alice_id, display_name="Synthetic Alice",
                               display_timezone="UTC")
        self.bob = Principal(id=self.bob_id, display_name="Synthetic Bob",
                             display_timezone="UTC")
        directory = Path(os.environ["NI_TEST_TMP_DIR"]) / f"ni061-{uuid4().hex[:8]}"
        directory.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
        self.directory = directory
        self.storage_root = directory / "storage"

    # -- bundle helpers ------------------------------------------------------ #

    def emit_and_stage(self, *, payout_override: str | None = None,
                       do_publish: bool = True) -> dict[str, dict]:
        """Emit both manifests from the synthetic bundle and stage them.

        ``payout_override`` replaces the last-day payout amount in the raw
        extract BEFORE loading, producing a genuinely different dataset
        version for the latest-pointer invariance test. The emitted dataset
        key is rewritten to a per-run unique synthetic key so runs cannot
        interfere; the observations are untouched.
        """
        paths = fixtures.write_bundle(self.directory)
        if payout_override is not None:
            extract = paths["flows"].read_text(encoding="utf-8")
            extract = extract.replace(fixtures.PAYOUT_LAST_DAY, payout_override)
            paths["flows"].write_text(extract, encoding="utf-8")
        inputs = fixtures.pipeline_inputs(paths)
        manifest_inputs = tuple(ManifestInputSpec(name=name, path=path,
                                                  role=ROLE_BY_INPUT[name])
                                for name, path in paths.items())
        manifests = build_all_manifests(
            inputs, dataset_spec=DatasetSpec(pipeline_version="ni061-synthetic",
                                             quality={"notes": "synthetic NI-061 fixture"}),
            manifest_inputs=manifest_inputs)
        staged: dict[str, dict] = {}
        for dataset_key, document in manifests.items():
            stem = dataset_key.split(".")[1]
            document["dataset_key"] = key = unique_key(stem)
            path = write_manifest_document(self.directory, stem, document)
            result = stage(self.operator, path, self.storage_root)
            self.assertEqual(result.status, "validated", result.validation)
            if do_publish:
                publish(self.operator, result.dataset_version_id)
            staged[dataset_key] = {"id": result.dataset_version_id,
                                   "dataset_key": key,
                                   "content_sha256": result.content_sha256}
        self.oracle, self.supply = fixtures.oracle_for(paths["flows"])
        self.paths = paths
        return staged

    # -- reading helpers ----------------------------------------------------- #

    def scalar(self, statement: str, **params):
        with self.admin.connect() as connection:
            return connection.scalar(text(statement), params)

    def scalar_rows(self, statement: str, **params) -> list[tuple]:
        with self.admin.connect() as connection:
            return connection.execute(text(statement), params).all()

    def observations(self, version_id: UUID) -> list[dict]:
        with self.admin.connect() as connection:
            rows = connection.execute(text("""
                SELECT metric_definition_id, period_start, value::text AS value,
                       quality_status, bound_kind
                FROM app.metric_observations
                WHERE dataset_version_id = :id
                ORDER BY metric_definition_id, period_start
            """), {"id": version_id}).mappings().all()
        return [dict(row) for row in rows]

    def document_counts(self, document_id: UUID) -> dict[str, int]:
        with self.admin.connect() as connection:
            return {table: connection.scalar(text(
                f"SELECT count(*) FROM app.{table} WHERE document_id = :id"),
                {"id": document_id}) for table in DOCUMENT_TABLES}

    def series(self, metric_id: str, start: dt.date, end: dt.date, version: UUID):
        # the delivery route resolves the definition by its registered
        # metric_id text, not by the registry UUID
        response = self.client.get(
            f"/api/metrics/{metric_id}/series",
            params={"start": start.isoformat(), "end": end.isoformat(),
                    "definition_version": 1, "dataset_version": str(version)})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def chart_view(self, version: UUID):
        response = self.client.get("/api/charts/observed-conversions/view",
                                   params={"start": D1.isoformat(),
                                           "end": D4.isoformat(),
                                           "definition_version": 1,
                                           "dataset_version": str(version)})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def series_yocto(self, response_json: dict) -> list[int]:
        """Delivered daily values as exact yoctoNEAR integers (Decimal path)."""
        return [int(Decimal(point["value"]) * YOCTO) for point in
                response_json["points"]]

    @staticmethod
    def series_shape(view) -> list:
        """(metric id, delivered values) pairs for an HTTP view or a model."""
        series_items = view["series"] if isinstance(view, dict) else view.series
        result = []
        for item in series_items:
            if isinstance(item, dict):
                metric_id = item["metric"]["id"]
                values = [point["value"] for point in item["points"]]
            else:
                metric_id = str(item.metric.id)
                values = [point.value for point in item.points]
            result.append((metric_id, values))
        return result


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class StagedDatasetInvariants(InvariantDatabaseFixture, unittest.TestCase):
    """Staged rows and delivered series carry exactly the oracle values."""

    def test_exact_sums_and_membership_in_storage(self):
        staged = self.emit_and_stage()
        flows_id = staged["metrics.flows.daily"]["id"]
        windows_id = staged["metrics.windows.snapshot"]["id"]

        for version_id in (flows_id, windows_id):
            members = {str(row[0]) for row in self.scalar_rows(
                "SELECT metric_definition_id FROM app.dataset_metrics "
                "WHERE dataset_version_id = :id", id=version_id)}
            observation_metrics = {str(row[0]) for row in self.scalar_rows(
                "SELECT DISTINCT metric_definition_id FROM app.metric_observations "
                "WHERE dataset_version_id = :id", id=version_id)}
            self.assertTrue(observation_metrics, "the version stages observations")
            self.assertLessEqual(observation_metrics, members,
                                 "an observation references a non-member metric")
            stored_sha = self.scalar(
                "SELECT content_sha256 FROM app.dataset_versions WHERE id = :id",
                id=version_id)
            self.assertEqual(stored_sha,
                             staged["metrics.flows.daily" if version_id == flows_id
                                    else "metrics.windows.snapshot"]["content_sha256"])

        # exact per-day sums recomputed from the raw extract
        stored = {}
        for row in self.observations(flows_id):
            stored[(str(row["metric_definition_id"]), row["period_start"].date())] = \
                row["value"]
        purchases = str(definition_by_metric_id("observed_near_purchases").id)
        # NI-071: the aggregate payout identity is the immutable v1
        # definition; the v2 per-recipient rows are a separate declared
        # universe and must reconcile with it (checked below).
        payouts = str(definition_by_metric_id_version("treasury_payouts_near", 1).id)
        payouts_v2 = str(definition_by_metric_id_version("treasury_payouts_near", 2).id)
        conversions = str(definition_by_metric_id("conversion_count").id)
        for day in fixtures.DAYS:
            self.assertEqual(Decimal(stored[(purchases, day)]) * YOCTO,
                             self.oracle.purchase_yocto_by_day.get(day, 0),
                             f"{day}: stored purchases diverge from the oracle")
            self.assertEqual(Decimal(stored[(payouts, day)]) * YOCTO,
                             self.oracle.payout_yocto_by_day.get(day, 0),
                             f"{day}: stored payouts diverge from the oracle")
            self.assertEqual(int(Decimal(stored[(conversions, day)])),
                             self.oracle.purchase_events_by_day.get(day, 0))
        # the duplicated rows were collapsed: the stored total counts each
        # canonical event exactly once
        stored_total = sum(Decimal(value) * YOCTO for (metric, _day), value in
                           stored.items() if metric == purchases)
        self.assertEqual(stored_total, self.oracle.purchase_total_yocto)

        # NI-071 reconciliation identity in storage: exactly one v2 row per
        # (day, named recipient), each carrying the verified recipient
        # dimension, and the three per-recipient values sum to the v1
        # aggregate row for the same day at exact Decimal precision.
        with self.admin.connect() as connection:
            recipient_rows = connection.execute(text("""
                SELECT period_start, value::text AS value, dimensions
                FROM app.metric_observations
                WHERE dataset_version_id = :id
                  AND metric_definition_id = :metric
            """), {"id": flows_id, "metric": UUID(payouts_v2)}).mappings().all()
        by_day: dict[dt.date, list[Decimal]] = {}
        for row in recipient_rows:
            dimensions = row["dimensions"] or {}
            self.assertIn(dimensions.get("recipient"), TreasuryAccounts,
                          "a v2 payout row carries a non-universe recipient")
            by_day.setdefault(row["period_start"].date(), []).append(
                Decimal(row["value"]))
        for day in fixtures.DAYS:
            self.assertEqual(len(by_day.get(day, [])), len(TreasuryAccounts),
                             f"{day}: the v2 payout rows are not one per recipient")
            self.assertEqual(sum(by_day.get(day, []), Decimal(0)) * YOCTO,
                             self.oracle.payout_yocto_by_day.get(day, 0),
                             f"{day}: per-recipient payout rows diverge from the "
                             "aggregate oracle")

    def test_delivery_series_match_oracle_exactly(self):
        staged = self.emit_and_stage()
        flows_id = staged["metrics.flows.daily"]["id"]
        purchases = self.series("observed_near_purchases", D1, D4, flows_id)
        self.assertEqual(self.series_yocto(purchases),
                         [self.oracle.purchase_yocto_by_day.get(day, 0)
                          for day in fixtures.DAYS])
        payouts = self.series("treasury_payouts_near", D1, D4, flows_id)
        self.assertEqual(self.series_yocto(payouts),
                         [self.oracle.payout_yocto_by_day.get(day, 0)
                          for day in fixtures.DAYS])
        # every point is exact, never a bound or estimate
        self.assertTrue(all(point["quality"]["bound_kind"] == "exact"
                            for point in payouts["points"]))
        # identical selections resolve to identical delivered values
        again = self.series("observed_near_purchases", D1, D4, flows_id)
        self.assertEqual([point["value"] for point in again["points"]],
                         [point["value"] for point in purchases["points"]])
        self.assertEqual(again["dataset"]["id"], str(flows_id))

    def test_missing_price_day_is_explicit_null_with_reason(self):
        staged = self.emit_and_stage()
        flows_id = staged["metrics.flows.daily"]["id"]
        # storage state: the unpriced day holds NULL observations with an
        # explicit missing reason — never a zero
        usd = str(definition_by_metric_id("estimated_purchase_usd").id)
        gap_rows = [row for row in self.observations(flows_id)
                    if str(row["metric_definition_id"]) == usd
                    and row["period_start"].date() == D2]
        self.assertEqual(len(gap_rows), 2)  # both price bases
        for row in gap_rows:
            self.assertIsNone(row["value"])
            self.assertEqual(row["quality_status"], "missing")
        priced_rows = [row for row in self.observations(flows_id)
                       if str(row["metric_definition_id"]) == usd
                       and row["period_start"].date() == D1]
        self.assertEqual({Decimal(row["value"]) for row in priced_rows},
                         {Decimal("6.5"), Decimal("6.2")})
        # delivered series: the metric carries two basis variants per day, so
        # an unfiltered selection surfaces EXPLICIT unavailable points (never
        # a silent average, never a picked variant)
        estimates = self.series("estimated_purchase_usd", D1, D4, flows_id)
        self.assertEqual(len(estimates["points"]), 3)
        for point in estimates["points"]:
            self.assertIsNone(point["value"])
            self.assertEqual(point["quality"]["status"], "unavailable")
            self.assertIn("multiple dimension variants",
                          point["quality"]["reasons"][0])

    def test_gated_metrics_deliver_nulls_with_reasons(self):
        staged = self.emit_and_stage()
        flows_id = staged["metrics.flows.daily"]["id"]
        revenue = self.series("protocol_revenue_usd", D1, D4, flows_id)
        self.assertEqual(len(revenue["points"]), 3)
        for point in revenue["points"]:
            self.assertIsNone(point["value"])
            self.assertEqual(point["quality"]["status"], "unavailable")
            self.assertIn("OQ-01", point["quality"]["reasons"][0])

    def test_bounds_survive_the_delivery_chain(self):
        staged = self.emit_and_stage()
        flows = staged["metrics.flows.daily"]["id"]
        windows = staged["metrics.windows.snapshot"]["id"]
        nets = self.series("net_supply_change_near", D1, D3, windows)
        delivered = {point["start"][:10]: point for point in nets["points"]}
        self.assertEqual(Decimal(delivered[D1.isoformat()]["value"]),
                         self.supply.net_change_by_window[(D1, D2)])
        self.assertEqual(Decimal(delivered[D2.isoformat()]["value"]),
                         self.supply.net_change_by_window[(D2, D3)])
        stocks = self.series("total_supply_near", D1 - ONE_DAY, D4, windows)
        delivered_stocks = {Decimal(point["value"]) for point in stocks["points"]}
        self.assertEqual(delivered_stocks, set(self.supply.stock_by_date.values()))
        # the delivered stocks are the pinned boundary stocks exactly; the
        # purchases series is delivered separately and nothing anywhere in
        # the delivered chain carries a supply value net of purchases
        purchases = self.series("observed_near_purchases", D1, D4, flows)
        purchase_total = sum(Decimal(point["value"]) for point in purchases["points"])
        self.assertEqual(purchase_total, Decimal(self.oracle.purchase_total_yocto)
                         / YOCTO)
        self.assertNotIn(purchase_total, delivered_stocks)
        ratios = self.series("purchases_to_issuance_upper_pct", D1, D3, windows)
        for point in ratios["points"]:
            self.assertEqual(point["quality"]["bound_kind"], "upper")

    def test_chart_view_delivers_the_oracle_values(self):
        staged = self.emit_and_stage()
        flows_id = staged["metrics.flows.daily"]["id"]
        view = self.chart_view(flows_id)
        self.assertEqual(view["dataset"]["id"], str(flows_id))
        purchase_series, conversion_series = view["series"][0], view["series"][1]
        self.assertEqual(self.series_yocto(purchase_series),
                         [self.oracle.purchase_yocto_by_day.get(day, 0)
                          for day in fixtures.DAYS])
        self.assertEqual([int(Decimal(point["value"]))
                          for point in conversion_series["points"]],
                         [self.oracle.purchase_events_by_day.get(day, 0)
                          for day in fixtures.DAYS])
        self.assertTrue(view["context_hash"])


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class FrozenRevisionContextInvariants(InvariantDatabaseFixture, unittest.TestCase):
    """Pinned reconstructions survive latest changes; mutation fails closed."""

    def save_chart_document(self, dataset_version: UUID) -> tuple[UUID, UUID, UUID]:
        """Alice saves one document with a liveChart pinned to the dataset."""
        detail = documents.create_document(self.runtime, self.alice,
                                           title="Synthetic invariant research")
        block_id = uuid4()
        content = {"schema_version": 1, "type": "doc", "content": [
            {"type": "liveChart", "attrs": {
                "block_id": str(block_id), "mode": "live", "snapshot_id": None,
                "chart_definition_version_id": str(CONVERSIONS_CHART.id),
                "selection": {"start": D1.isoformat(), "end": D4.isoformat(),
                              "frequency": "day", "filters": {}},
                "observed_dataset_version_id": str(dataset_version),
            }},
        ]}
        saved = documents.save_revision(self.runtime, self.alice, detail.document.id,
                                        expected_revision=1,
                                        document_payload=content)
        return detail.document.id, saved.version.id, block_id

    def reconstruct(self, document_id: UUID, version_id: UUID, block_id: UUID):
        with user_transaction(self.runtime, self.alice_id) as connection:
            version = get_version_row(connection, self.alice, document_id, version_id)
            return reconstruct_revision_chart(connection, version, block_id)

    def test_pinned_reconstruction_matches_the_direct_view_exactly(self):
        staged = self.emit_and_stage()
        flows_id = staged["metrics.flows.daily"]["id"]
        direct = self.chart_view(flows_id)
        document_id, version_id, block_id = self.save_chart_document(flows_id)
        reconstructed = self.reconstruct(document_id, version_id, block_id)
        self.assertEqual(reconstructed.context_hash, direct["context_hash"])
        self.assertEqual(self.series_shape(reconstructed),
                         self.series_shape(direct))
        # the frozen context pins the inspected dataset, never a latest pointer
        self.assertEqual(str(reconstructed.dataset.id), str(flows_id))

    def test_new_latest_version_never_changes_a_pinned_reconstruction(self):
        staged = self.emit_and_stage()
        flows = staged["metrics.flows.daily"]
        document_id, version_id, block_id = self.save_chart_document(flows["id"])
        before = self.reconstruct(document_id, version_id, block_id)

        override = str(int(fixtures.PAYOUT_LAST_DAY) + 10 ** 22)
        staged2 = self.emit_and_stage(payout_override=override)
        self.assertNotEqual(staged2["metrics.flows.daily"]["id"], flows["id"])
        # the active pointer moved to the new approved version
        self.assertEqual(self.scalar(
            "SELECT dataset_version_id FROM app.active_datasets WHERE dataset_key = :key",
            key=staged2["metrics.flows.daily"]["dataset_key"]),
            staged2["metrics.flows.daily"]["id"])

        after = self.reconstruct(document_id, version_id, block_id)
        self.assertEqual(after.context_hash, before.context_hash)
        self.assertEqual(after.dataset.id, before.dataset.id)
        self.assertEqual(self.series_shape(after), self.series_shape(before))
        # and the explicitly pinned direct view of the old version is the
        # same data the reconstruction serves (old versions never refresh)
        before_direct = self.chart_view(flows["id"])
        self.assertEqual(self.series_shape(before_direct), self.series_shape(after))

    def test_mutated_approved_row_fails_the_reconstruction_closed(self):
        staged = self.emit_and_stage()
        flows_id = staged["metrics.flows.daily"]["id"]
        document_id, version_id, block_id = self.save_chart_document(flows_id)
        working = self.reconstruct(document_id, version_id, block_id)
        self.assertEqual(str(working.dataset.id), str(flows_id))

        # simulate source mutation of the approved (immutable) rows: the
        # reconstruction must refuse instead of serving changed values
        purchases = definition_by_metric_id("observed_near_purchases").id
        day_start = datetime.combine(D1, dt.time.min, tzinfo=UTC)
        with self.admin.begin() as connection:
            mutated = connection.execute(text("""
                UPDATE app.metric_observations
                SET value = value + 0.5
                WHERE dataset_version_id = :id
                  AND metric_definition_id = :metric
                  AND period_start = :start
            """), {"id": flows_id, "metric": purchases, "start": day_start})
            self.assertEqual(mutated.rowcount, 1)
        with self.assertRaises(ReconstructionError):
            self.reconstruct(document_id, version_id, block_id)
        # restore the row: the reconstruction works again and is unchanged
        with self.admin.begin() as connection:
            connection.execute(text("""
                UPDATE app.metric_observations
                SET value = value - 0.5
                WHERE dataset_version_id = :id
                  AND metric_definition_id = :metric
                  AND period_start = :start
            """), {"id": flows_id, "metric": purchases, "start": day_start})
        restored = self.reconstruct(document_id, version_id, block_id)
        self.assertEqual(self.series_shape(restored), self.series_shape(working))


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class RevisionProjectionAndGraphInvariants(InvariantDatabaseFixture,
                                           unittest.TestCase):
    """Projections match canonical content; the graph and cleanup rules hold."""

    def resolved_context(self, dataset_version: UUID) -> dict:
        with self.admin.connect() as connection:
            definition = load_chart_definition(connection, CONVERSIONS_CHART.id,
                                               error_path="test")
        selection = ChartSelection(start=D1, end=D4, frequency="day", filters={})
        context = build_resolved_context(definition, dataset_version, selection,
                                         resolved_at=datetime.now(UTC))
        return context.model_dump(mode="json")

    def paragraph(self, text: str, block_id: UUID | None = None) -> dict:
        """A top-level block paragraph (attrs.block_id required)."""
        node = {"type": "paragraph", "attrs": {"block_id": str(block_id or uuid4())},
                "content": [{"type": "text", "text": text}]}
        return node

    def rich_paragraph(self, text: str) -> dict:
        """A rich-body paragraph (annotation body: type+content only)."""
        return {"type": "paragraph", "content": [{"type": "text", "text": text}]}

    def save_with_annotations(self, document_id: UUID, *, revision: int,
                              with_evidence: bool = True) -> documents.DocumentDetail:
        context = self.resolved_context(self.staged_flows_id)
        insight_block, hypothesis_block = uuid4(), uuid4()
        insight_id, hypothesis_id = uuid4(), uuid4()
        content = {"schema_version": 1, "type": "doc", "content": [
            self.paragraph("Synthetic prose before the annotations"),
            {"type": "insight", "attrs": {
                "block_id": str(insight_block), "insight_id": str(insight_id),
                "type": "observation", "classification": "supporting",
                "body": [self.rich_paragraph("Synthetic observation body")],
                "context": context, "authored_at": "2026-11-09T00:00:00Z",
                "modified_at": "2026-11-09T00:00:00Z"}},
            {"type": "hypothesis", "attrs": {
                "block_id": str(hypothesis_block),
                "hypothesis_id": str(hypothesis_id),
                "statement": "Synthetic claim under test", "assessment": "untested",
                "authored_at": "2026-11-09T00:00:00Z",
                "modified_at": "2026-11-09T00:00:00Z"}},
        ]}
        if with_evidence:
            content["content"].append({
                "type": "evidence", "attrs": {
                    "block_id": str(uuid4()), "evidence_id": str(uuid4()),
                    "hypothesis_id": str(hypothesis_id),
                    "classification": "supporting", "target_kind": "insight",
                    "target_id": str(insight_id),
                    "explanation": "Synthetic supporting explanation"}})
        return documents.save_revision(self.runtime, self.alice, document_id,
                                       expected_revision=revision,
                                       document_payload=content), content

    def setUp(self):
        super().setUp()
        staged = self.emit_and_stage()
        self.staged_flows_id = staged["metrics.flows.daily"]["id"]

    def test_projections_match_canonical_content_exactly(self):
        detail = documents.create_document(self.runtime, self.alice,
                                           title="Synthetic projection research")
        saved, content = self.save_with_annotations(detail.document.id, revision=1)
        version_id = saved.version.id
        # the stored canonical content re-parses to the recorded hash
        self.assertEqual(parse_document(saved.content).content_sha256,
                         saved.version.content_sha256)
        blocks = self.scalar_rows("""
            SELECT block_id, block_type, position FROM app.document_blocks
            WHERE document_version_id = :id ORDER BY position
        """, id=version_id)
        insights = self.scalar_rows("""
            SELECT insight_id, block_id, classification FROM app.insights
            WHERE document_version_id = :id
        """, id=version_id)
        hypotheses = self.scalar_rows("""
            SELECT hypothesis_id, statement, assessment FROM app.hypotheses
            WHERE document_version_id = :id
        """, id=version_id)
        links = self.scalar_rows("""
            SELECT evidence_id, hypothesis_id, target_kind, target_id
            FROM app.evidence_links WHERE document_version_id = :id
        """, id=version_id)
        self.assertEqual([str(row[0]) for row in blocks],
                         [node["attrs"]["block_id"] for node in content["content"]])
        self.assertEqual([row[1] for row in blocks],
                         [node["type"] for node in content["content"]])
        self.assertEqual([row[2] for row in blocks], list(range(len(blocks))))
        canonical_insight = next(node for node in content["content"]
                                 if node["type"] == "insight")
        canonical_hypothesis = next(node for node in content["content"]
                                    if node["type"] == "hypothesis")
        canonical_evidence = next(node for node in content["content"]
                                  if node["type"] == "evidence")
        self.assertEqual([(str(insights[0][0]), str(insights[0][1]), insights[0][2])],
                         [(canonical_insight["attrs"]["insight_id"],
                           canonical_insight["attrs"]["block_id"],
                           canonical_insight["attrs"]["classification"])])
        self.assertEqual(str(hypotheses[0][0]),
                         canonical_hypothesis["attrs"]["hypothesis_id"])
        self.assertEqual(hypotheses[0][1], canonical_hypothesis["attrs"]["statement"])
        self.assertEqual([(str(links[0][0]), str(links[0][1]), links[0][2],
                           str(links[0][3]))],
                         [(canonical_evidence["attrs"]["evidence_id"],
                           canonical_evidence["attrs"]["hypothesis_id"],
                           canonical_evidence["attrs"]["target_kind"],
                           canonical_evidence["attrs"]["target_id"])])
        # the evidence target resolves to a real projection row of the SAME
        # revision (no dangling polymorphic reference)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM app.insights WHERE document_version_id = :version "
            "AND insight_id = :target", version=version_id,
            target=canonical_evidence["attrs"]["target_id"]), 1)

        # a dangling target is refused and leaves zero rows
        before = self.document_counts(detail.document.id)
        dangling = json.loads(json.dumps(content))
        dangling["content"][-1]["attrs"]["evidence_id"] = str(uuid4())
        dangling["content"][-1]["attrs"]["target_id"] = str(uuid4())
        with self.assertRaises(Exception):
            documents.save_revision(self.runtime, self.alice, detail.document.id,
                                    expected_revision=saved.document.revision,
                                    document_payload=dangling)
        self.assertEqual(self.document_counts(detail.document.id), before)

    def test_cas_ownership_and_invalid_content_leave_zero_rows(self):
        detail = documents.create_document(self.runtime, self.alice,
                                           title="Synthetic CAS research")
        document_id = detail.document.id
        # one real save first: the document is now at revision 2
        saved, _content = self.save_with_annotations(document_id, revision=1)
        self.assertEqual(saved.document.revision, 2)
        before = self.document_counts(document_id)

        # stale CAS: the current revision is carried, nothing is written
        with self.assertRaises(documents.RevisionConflict) as conflict:
            documents.save_revision(self.runtime, self.alice, document_id,
                                    expected_revision=1,
                                    document_payload={"schema_version": 1,
                                                      "type": "doc", "content": []})
        self.assertEqual(conflict.exception.current_revision, 2)
        self.assertEqual(self.document_counts(document_id), before)

        # invalid canonical content: no partial revision
        with self.assertRaises(DocumentSchemaError):
            documents.save_revision(self.runtime, self.alice, document_id,
                                    expected_revision=2,
                                    document_payload={"schema_version": 1,
                                                      "type": "doc",
                                                      "content": [{"type": "marquee"}]})
        self.assertEqual(self.document_counts(document_id), before)

        # Bob is not the owner: one generic not-found, nothing written
        with self.assertRaises(ResourceNotFound):
            documents.save_revision(self.runtime, self.bob, document_id,
                                    expected_revision=2,
                                    document_payload={"schema_version": 1,
                                                      "type": "doc", "content": []})
        self.assertEqual(self.document_counts(document_id), before)

    def test_history_keeps_original_links_and_delete_cleans_up(self):
        detail = documents.create_document(self.runtime, self.alice,
                                           title="Synthetic history research")
        saved_v2, content_v2 = self.save_with_annotations(detail.document.id,
                                                          revision=1)
        datasets_before = self.scalar("SELECT count(*) FROM app.dataset_versions")
        artifacts_before = self.scalar("SELECT count(*) FROM app.artifacts")

        # revision 3 removes the evidence node
        content_v3 = {"schema_version": 1, "type": "doc",
                      "content": content_v2["content"][:3]}
        saved_v3 = documents.save_revision(self.runtime, self.alice,
                                           detail.document.id,
                                           expected_revision=saved_v2.document.revision,
                                           document_payload=content_v3)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM app.evidence_links WHERE document_version_id = :id",
            id=saved_v3.version.id), 0)
        # the historical revision keeps its original links
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM app.evidence_links WHERE document_version_id = :id",
            id=saved_v2.version.id), 1)
        historical = documents.get_document_version(self.runtime, self.alice,
                                                    detail.document.id,
                                                    saved_v2.version.id)
        historical_evidence = [UUID(node["attrs"]["evidence_id"])
                               for node in historical.content["content"]
                               if node["type"] == "evidence"]
        self.assertEqual(historical_evidence,
                         [UUID(content_v2["content"][3]["attrs"]["evidence_id"])])
        # Bob gets no historical revision and no cleanup rights
        with self.assertRaises(ResourceNotFound):
            documents.get_document_version(self.runtime, self.bob, detail.document.id,
                                           saved_v2.version.id)
        with self.assertRaises(ResourceNotFound):
            documents.delete_document(self.runtime, self.bob, detail.document.id,
                                      expected_revision=saved_v3.document.revision)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM app.documents WHERE id = :id",
            id=detail.document.id), 1)

        # owner delete: private children cascade, shared scientific data stays
        documents.delete_document(self.runtime, self.alice, detail.document.id,
                                  expected_revision=saved_v3.document.revision)
        for table in DOCUMENT_TABLES:
            self.assertEqual(self.scalar(
                f"SELECT count(*) FROM app.{table} WHERE document_id = :id",
                id=detail.document.id), 0, table)
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM app.documents WHERE id = :id",
            id=detail.document.id), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM app.dataset_versions"),
                         datasets_before)
        self.assertEqual(self.scalar("SELECT count(*) FROM app.artifacts"),
                         artifacts_before)
