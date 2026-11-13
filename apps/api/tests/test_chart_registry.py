"""NI-031 tests: versioned chart/metric registry integrity.

Offline classes run everywhere; DB classes need scripts/run-db-tests.py.
A skip is never integration evidence. All chart bindings resolve against the
real NI-029 metric registry; no observation data is involved here.
"""

import os
import unittest
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from near_api.charts import registry as chart_registry
from near_api.charts.registry import (
    CHARTS,
    CHART_REGISTRY_NAMESPACE,
    CATEGORIES,
    ChartDefinition,
    ChartRegistryError,
    ChartSeries,
    FILTER_PROVIDER_SOURCES,
    FILTER_TREASURY_RECIPIENTS,
    MAX_RANGE_DAYS,
    RENDERER_VERSION,
    SERIES_ROLES,
    chart_by_chart_id,
    register_charts,
    validate_registry,
    view_contract,
)
from near_api.db.session import user_transaction
from near_api.metrics.registry import DEFINITIONS as METRIC_DEFINITIONS
from near_api.metrics.registry import definition_by_metric_id, definition_by_metric_id_version

import uuid as uuid_module

METRICS = {definition.metric_id: definition for definition in METRIC_DEFINITIONS}
GATED_METRIC_IDS = {"protocol_revenue_usd", "protocol_capture_rate", "fee_funded_buybacks_near"}


def doctored(chart_id: str, **changes) -> ChartDefinition:
    """A copy of a registered definition with field-level changes applied.

    Frozen dataclasses are rebuilt from their fields, so every registry
    invariant is testable against a doctored variant.
    """
    base = chart_by_chart_id(chart_id)
    fields = {name: getattr(base, name) for name in base.__dataclass_fields__}
    fields.update(changes)
    return ChartDefinition(**fields)


def validate_single(chart: ChartDefinition) -> None:
    """Validate one (possibly doctored) definition against the real metrics."""
    seen: set[UUID] = set()
    chart_registry._validate_chart(chart, METRICS, seen)


class RegistryIntegrityTests(unittest.TestCase):
    def test_registry_validates_against_registered_metrics(self):
        validate_registry(METRICS)

    def test_definitions_are_complete_and_deterministic(self):
        seen_ids: set[UUID] = set()
        latest_by_id: dict[str, ChartDefinition] = {}
        for chart in CHARTS:
            with self.subTest(chart=chart.chart_id):
                expected = uuid_module.uuid5(CHART_REGISTRY_NAMESPACE,
                                             f"{chart.chart_id}:v{chart.version}")
                self.assertEqual(chart.id, expected)
                # the chart_id map resolves the latest registered version;
                # superseded versions coexist in the registry tuple
                previous = latest_by_id.get(chart.chart_id)
                if previous is None or previous.version < chart.version:
                    latest_by_id[chart.chart_id] = chart
                self.assertNotIn(chart.id, seen_ids)
                seen_ids.add(chart.id)
                self.assertTrue(chart.title and chart.description)
                self.assertIn(chart.category, CATEGORIES)
                self.assertEqual(chart.renderer_version, RENDERER_VERSION)
        for chart_id, latest in latest_by_id.items():
            self.assertIs(chart_by_chart_id(chart_id), latest)

    def test_all_chart_metrics_resolve_with_matching_units_and_ids(self):
        for chart in CHARTS:
            with self.subTest(chart=chart.chart_id):
                row = chart.row(METRICS)
                resolved = sorted(str(chart_registry.resolve_binding(METRICS, binding).id)
                                  for binding in chart.series)
                self.assertEqual(row["metric_definition_ids"], resolved)
                for binding in chart.series:
                    metric = chart_registry.resolve_binding(METRICS, binding)
                    self.assertIn(binding.series_role, SERIES_ROLES)
                    self.assertEqual(chart.unit_schema[binding.series_role], metric.unit)
                junction = chart.junction_rows(METRICS)
                self.assertEqual(len(junction), len(chart.series))
                for binding_row, binding in zip(junction, chart.series):
                    self.assertEqual(binding_row["metric_definition_id"],
                                     chart_registry.resolve_binding(METRICS, binding).id)
                # a binding pins an exact metric definition version: the v1
                # aggregate chart keeps binding v1 after v2 supersedes it
                if chart.chart_id == "treasury-payouts":
                    expected = ("treasury_payouts_near", chart.version)
                    self.assertEqual((binding.metric_id, 0) and
                                     (chart.series[0].metric_id,
                                      chart.series[0].metric_version),
                                     (expected[0], expected[1]))

    def test_initial_catalog_covers_available_and_gated_charts(self):
        available = {chart.chart_id for chart in CHARTS if chart.data_status == "available"}
        unavailable = {chart.chart_id for chart in CHARTS
                       if chart.data_status == "unavailable"}
        # The CHART_SYSTEM initial catalog, resolved against real NI-029 inputs:
        # the seven metric-driven charts are available; the gated revenue
        # charts and the model-artifact chart are registered honestly
        # unavailable.
        self.assertEqual(available, {"intents-volume", "gross-fees", "observed-conversions",
                                     "treasury-payouts", "quantity-usd-sensitivity",
                                     "supply-context", "fee-volume-association"})
        self.assertEqual(unavailable, {"model-diagnostics", "protocol-revenue",
                                       "capture-rate", "fee-funded-buybacks"})

    def test_unavailable_metrics_are_never_advertised_as_live(self):
        for chart in CHARTS:
            with self.subTest(chart=chart.chart_id):
                gated = [binding.metric_id for binding in chart.series
                         if chart_registry.resolve_binding(METRICS, binding)
                         .definition["availability"] == "G"]
                contract = view_contract(chart, METRICS)
                if gated or not chart.series:
                    # gated bindings or a non-metric driver (model artifact)
                    # are never advertised as live
                    self.assertEqual(chart.data_status, "unavailable")
                    self.assertTrue(chart.unavailable_reason)
                    self.assertEqual(contract["data_status"], "unavailable")
                else:
                    self.assertEqual(chart.data_status, "available")
                    self.assertIsNone(chart.unavailable_reason)
                    self.assertEqual(contract["data_status"], "available")
        # the gated bindings are exactly the three OQ-gated metric definitions;
        # the model-artifact chart binds nothing and stays unavailable
        self.assertEqual({binding.metric_id for chart in CHARTS for binding in chart.series
                          if chart_registry.resolve_binding(METRICS, binding)
                          .definition["availability"] == "G"},
                         GATED_METRIC_IDS)
        self.assertIn("model run", chart_by_chart_id("model-diagnostics").unavailable_reason)

    def test_filters_are_closed_string_enums_from_approved_mappings(self):
        for chart in CHARTS:
            with self.subTest(chart=chart.chart_id):
                schema = chart.filter_schema
                self.assertEqual(schema["type"], "object")
                self.assertIs(schema["additionalProperties"], False)
                for bound in schema["properties"].values():
                    self.assertEqual(bound["type"], "string")
                    self.assertTrue(bound["enum"])
        self.assertEqual(
            chart_by_chart_id("treasury-payouts").filter_schema["properties"]["recipient"]["enum"],
            list(chart_registry.FILTER_TREASURY_RECIPIENTS))
        for chart_id in ("intents-volume", "gross-fees", "fee-volume-association"):
            self.assertEqual(
                chart_by_chart_id(chart_id).filter_schema["properties"]["source"]["enum"],
                list(chart_registry.FILTER_PROVIDER_SOURCES))
        self.assertEqual(
            chart_by_chart_id("quantity-usd-sensitivity")
            .filter_schema["properties"]["price_basis"]["enum"],
            list(chart_registry.FILTER_PRICE_BASES))

    def test_allowed_ranges_stay_within_the_documented_bound(self):
        for chart in CHARTS:
            with self.subTest(chart=chart.chart_id):
                ranges = chart.allowed_ranges
                self.assertLessEqual(ranges["max_days"], MAX_RANGE_DAYS)
                self.assertTrue(ranges["presets_days"])
                for preset in ranges["presets_days"]:
                    self.assertLessEqual(preset, ranges["max_days"])

    def test_view_contract_is_fully_registry_driven(self):
        for chart in CHARTS:
            contract = view_contract(chart, METRICS)
            with self.subTest(chart=chart.chart_id):
                self.assertEqual(contract["chart_definition_id"], str(chart.id))
                self.assertEqual(contract["visualization_type"], chart.visualization_type)
                self.assertEqual(len(contract["series"]), len(chart.series))
                for entry, binding in zip(contract["series"], chart.series):
                    metric = chart_registry.resolve_binding(METRICS, binding)
                    self.assertEqual(entry["series_role"], binding.series_role)
                    self.assertEqual(entry["metric_definition_id"], str(metric.id))
                    self.assertEqual(entry["unit"], metric.unit)
                    self.assertIn(entry["availability"], ("A", "P", "B", "G"))
                # renderer + lineage travel with the contract; no page-specific keys
                self.assertEqual(contract["renderer_version"], chart.renderer_version)
                self.assertEqual(contract["source_lineage"], chart.source_lineage)


class RegistryRejectionTests(unittest.TestCase):
    def test_unknown_metric_reference_is_rejected(self):
        for chart_id in ("intents-volume", "treasury-payouts"):
            chart = doctored(chart_id, series=(ChartSeries(str(uuid4()), "required_primary"),))
            with self.subTest(chart=chart_id), self.assertRaisesRegex(
                    ChartRegistryError, "not a registered metric definition"):
                validate_single(chart)

    def test_unit_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ChartRegistryError, "declares unit"):
            validate_single(doctored("intents-volume",
                                     unit_schema={"required_primary": "NEAR"}))

    def test_unit_schema_missing_role_is_rejected(self):
        with self.assertRaisesRegex(ChartRegistryError, "exactly the bound series roles"):
            validate_single(doctored("observed-conversions",
                                     unit_schema={"required_primary": "NEAR"}))

    def test_gated_metric_in_available_chart_is_rejected(self):
        chart = doctored("intents-volume",
                         series=(ChartSeries("protocol_revenue_usd", "required_primary"),),
                         unit_schema={"required_primary": "USD"},
                         source_lineage={"sources": [], "note": "gated binding"})
        with self.assertRaisesRegex(ChartRegistryError, "must not be advertised as live"):
            validate_single(chart)

    def test_unavailable_chart_without_reason_is_rejected(self):
        with self.assertRaisesRegex(ChartRegistryError, "carries a reason"):
            validate_single(doctored("protocol-revenue", unavailable_reason=None))

    def test_available_chart_marked_unavailable_is_rejected(self):
        with self.assertRaisesRegex(ChartRegistryError, "all of its bound metrics"):
            validate_single(doctored("intents-volume", data_status="unavailable",
                                     unavailable_reason="doctored"))

    def test_invalid_ranges_are_rejected(self):
        cases = (
            ({"presets_days": [7, 30, 90], "max_days": MAX_RANGE_DAYS + 1}, "max_days"),
            ({"presets_days": [7, 400], "max_days": 366}, "exceeds max_days"),
            ({"presets_days": [30, 7], "max_days": 366}, "unique and ascending"),
            ({"presets_days": [], "max_days": 366}, "positive integers"),
            ({"presets_days": [7, 30, 90]}, "exactly presets_days/max_days"),
        )
        for ranges, fragment in cases:
            with self.subTest(ranges=ranges):
                with self.assertRaisesRegex(ChartRegistryError, fragment):
                    validate_single(doctored("intents-volume", allowed_ranges=ranges))

    def test_invalid_filters_are_rejected(self):
        open_schema = {"type": "object", "properties": {}, "additionalProperties": True}
        empty_enum = {"type": "object",
                      "properties": {"source": {"type": "string", "enum": []}},
                      "additionalProperties": False}
        not_string = {"type": "object",
                      "properties": {"source": {"type": "integer", "enum": [1]}},
                      "additionalProperties": False}
        extra_key = {"type": "object",
                     "properties": {"source": {"type": "string", "enum": ["SRC-LLAMA"],
                                               "pattern": "x"}},
                     "additionalProperties": False}
        unknown_top = {"type": "object", "properties": {}, "additionalProperties": False,
                       "required": []}
        for schema, fragment in ((open_schema, "additionalProperties"),
                                 (empty_enum, "unique nonempty strings"),
                                 (not_string, "must be a string enum"),
                                 (extra_key, "must be a string enum"),
                                 (unknown_top, "exactly type/properties")):
            with self.subTest(schema=schema):
                with self.assertRaisesRegex(ChartRegistryError, fragment):
                    validate_single(doctored("intents-volume", filter_schema=schema))

    def test_source_lineage_must_match_bound_definitions(self):
        with self.assertRaisesRegex(ChartRegistryError, "no bound metric"):
            validate_single(doctored("intents-volume",
                                     source_lineage={"sources": ["SRC-FASTNEAR"],
                                                     "note": "doctored"}))
        with self.assertRaisesRegex(ChartRegistryError, "qualification note"):
            validate_single(doctored("intents-volume",
                                     source_lineage={"sources": ["SRC-LLAMA"], "note": ""}))

    def test_update_frequency_must_match_a_bound_metric(self):
        with self.assertRaisesRegex(ChartRegistryError, "matches no bound metric"):
            validate_single(doctored("intents-volume", update_frequency="snapshot"))

    def test_unsupported_category_visualization_and_role_are_rejected(self):
        with self.assertRaisesRegex(ChartRegistryError, "unsupported category"):
            validate_single(doctored("intents-volume", category="hype"))
        with self.assertRaisesRegex(ChartRegistryError, "unsupported visualization_type"):
            validate_single(doctored("intents-volume", visualization_type="hologram"))
        with self.assertRaisesRegex(ChartRegistryError, "unsupported series role"):
            validate_single(doctored(
                "intents-volume",
                series=(ChartSeries("provider_intents_volume_usd", "required_axis"),)))

    def test_duplicate_metric_binding_is_rejected(self):
        with self.assertRaisesRegex(ChartRegistryError, "bound more than once"):
            validate_single(doctored(
                "intents-volume",
                series=(ChartSeries("provider_intents_volume_usd", "required_primary"),
                        ChartSeries("provider_intents_volume_usd", "optional_overlay")),
                unit_schema={"required_primary": "USD", "optional_overlay": "USD"}))

    def test_ni071_comparison_markers_are_validated(self):
        from near_api.charts.filter_registry import FILTER_DIMENSIONS

        # the registered v2 recipient schema validates and carries the markers
        v2 = next(chart for chart in CHARTS
                  if chart.chart_id == "treasury-payouts" and chart.version == 2)
        validate_single(v2)
        self.assertIs(v2.filter_schema["properties"]["recipient"]["multi_value"], True)
        self.assertEqual(FILTER_DIMENSIONS["recipient"].reconciliation,
                         v2.filter_schema["properties"]["recipient"]["reconciliation"])
        # only registered multi-value dimensions may carry the marker
        with self.assertRaisesRegex(ChartRegistryError, "not a registered multi-value"):
            validate_single(doctored("intents-volume", filter_schema={
                "type": "object",
                "properties": {"source": {"type": "string",
                                          "enum": list(FILTER_PROVIDER_SOURCES),
                                          "multi_value": True}},
                "additionalProperties": False}))
        with self.assertRaisesRegex(ChartRegistryError, "must be true when present"):
            validate_single(doctored("treasury-payouts", version=9, filter_schema={
                "type": "object",
                "properties": {"recipient": {"type": "string",
                                             "enum": list(FILTER_TREASURY_RECIPIENTS),
                                             "multi_value": False}},
                "additionalProperties": False}))

    def test_ni071_reconciliation_declarations_are_validated(self):
        recipient_property = {
            "type": "string", "enum": list(FILTER_TREASURY_RECIPIENTS),
            "multi_value": True,
            "reconciliation": {"aggregate_metric_id": "treasury_payouts_near",
                               "aggregate_metric_version": 1,
                               "universe_note": "the three named treasuries"}}
        # a full valid declaration validates on a single-binding chart
        validate_single(doctored("treasury-payouts", version=8, title="x",
                                 description="x", filter_schema={
                                     "type": "object",
                                     "properties": {"recipient": recipient_property},
                                     "additionalProperties": False}))
        # a reconciliation marker without multi_value is not even a valid
        # property shape (fail closed on the declared key set)
        with self.assertRaisesRegex(ChartRegistryError, "must be a string enum"):
            validate_single(doctored("treasury-payouts", version=9, title="x",
                                     description="x", filter_schema={
                                         "type": "object",
                                         "properties": {"recipient": {
                                             "type": "string",
                                             "enum": list(FILTER_TREASURY_RECIPIENTS),
                                             "reconciliation": recipient_property[
                                                 "reconciliation"]}},
                                         "additionalProperties": False}))
        # the aggregate must be an exact registered (metric_id, version)
        for changes in ({"aggregate_metric_id": "not_a_metric"},
                        {"aggregate_metric_version": 7}):
            bad = {**recipient_property,
                   "reconciliation": {**recipient_property["reconciliation"], **changes}}
            with self.subTest(changes=changes), self.assertRaisesRegex(
                    ChartRegistryError, "not a registered metric definition version"):
                validate_single(doctored("treasury-payouts", version=10, title="x",
                                         description="x", filter_schema={
                                             "type": "object",
                                             "properties": {"recipient": bad},
                                             "additionalProperties": False}))
        # a gated aggregate can never back a reconciliation identity
        gated = {**recipient_property,
                 "reconciliation": {"aggregate_metric_id": "protocol_revenue_usd",
                                    "aggregate_metric_version": 1,
                                    "universe_note": "gated"}}
        with self.assertRaisesRegex(ChartRegistryError, "must not be a gated metric"):
            validate_single(doctored("treasury-payouts", version=11, title="x",
                                     description="x",
                                     unit_schema={"required_primary": "USD"},
                                     filter_schema={
                                         "type": "object",
                                         "properties": {"recipient": gated},
                                         "additionalProperties": False}))
        # a reconcilable dimension requires exactly one bound metric
        two_bindings = doctored("observed-conversions", filter_schema={
            "type": "object",
            "properties": {"recipient": recipient_property},
            "additionalProperties": False})
        with self.assertRaisesRegex(ChartRegistryError, "exactly one bound metric"):
            validate_single(two_bindings)

    def test_filter_enum_must_match_the_filter_registry(self):
        with self.assertRaisesRegex(ChartRegistryError, "disagree with the filter"):
            chart_registry._filter_enum("source", ("SRC-OTHER",))

    def test_recipient_is_the_only_multi_value_dimension(self):
        from near_api.charts.filter_registry import FILTER_DIMENSIONS
        self.assertTrue(FILTER_DIMENSIONS["recipient"].multi_value)
        self.assertIsNone(FILTER_DIMENSIONS["source"].reconciliation)
        self.assertFalse(FILTER_DIMENSIONS["source"].multi_value)
        self.assertFalse(FILTER_DIMENSIONS["price_basis"].multi_value)

    def test_version_increment_adds_a_new_definition_without_touching_v1(self):
        first = chart_by_chart_id("intents-volume")
        second = doctored("intents-volume", version=2, title="Intents volume (revised)")
        validate_single(second)
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.version, 1)
        self.assertEqual(first.title, "Provider-reported Intents gross volume")
        # immutability is structural: a registered definition cannot be edited
        with self.assertRaises(Exception):
            first.title = "rewritten"
        # the deterministic identity of v1 is unchanged by the v2 registration
        self.assertEqual(first.id, chart_by_chart_id("intents-volume").id)


# --------------------------------------------------------------------------- #
# Real PostgreSQL integration (scripts/run-db-tests.py)
# --------------------------------------------------------------------------- #

@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1", "Use scripts/run-db-tests.py")
class ChartRegistryDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pathlib import Path

        from alembic import command
        from alembic.config import Config

        from near_api.metrics import register_definitions

        cls.repo = Path(__file__).resolve().parents[3]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.operator = create_engine(os.environ["NI_TEST_OPERATOR_URL"], poolclass=NullPool,
                                     hide_parameters=True)
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"], poolclass=NullPool,
                                  hide_parameters=True)
        cls.runtime = create_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        command.upgrade(cls.config, "head")
        sources = {"SRC-BQ": "BigQuery export", "SRC-PRICE": "Saved price snapshots",
                   "SRC-LLAMA": "DefiLlama saved snapshots", "SRC-DASHBOARD": "NEAR Dashboard",
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

    @classmethod
    def tearDownClass(cls):
        cls.operator.dispose()
        cls.admin.dispose()
        cls.runtime.dispose()

    def test_01_migration_round_trip_and_rls_flags(self):
        from alembic import command

        command.downgrade(self.config, "0006_document_projections")
        with self.admin.connect() as connection:
            self.assertIsNone(connection.scalar(text(
                "SELECT to_regclass('app.chart_definitions')")))
            self.assertIsNone(connection.scalar(text("""
                SELECT conname FROM pg_constraint
                WHERE conname = 'fk_dataset_metrics_metric_definition'
            """)))
        command.upgrade(self.config, "head")
        command.check(self.config)
        with self.admin.connect() as connection:
            rows = connection.execute(text("""
                SELECT relname, relrowsecurity, relforcerowsecurity, pg_get_userbyid(relowner)
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'app' AND relname IN ('chart_definitions', 'chart_metrics')
            """)).all()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row[1:] == (True, True, "near_migrator") for row in rows))
        with self.admin.connect() as connection:
            fk = connection.execute(text("""
                SELECT conrelid::regclass::text, confdeltype FROM pg_constraint
                WHERE conname = 'fk_dataset_metrics_metric_definition'
            """)).one()
        self.assertEqual(tuple(fk), ("app.dataset_metrics", "r"))

    def test_02_registration_is_idempotent_and_content_verified(self):
        with self.operator.begin() as connection:
            summary = register_charts(connection)
        self.assertEqual(summary["registered"], len(CHARTS))
        with self.operator.begin() as connection:
            again = register_charts(connection)
        self.assertEqual(again["registered"], 0)
        self.assertEqual(again["existing"], len(CHARTS))
        with self.operator.begin() as connection:
            row = connection.execute(text("""
                SELECT id, chart_id, version, title, data_status, unavailable_reason,
                       metric_definition_ids, unit_schema, filter_schema, renderer_version
                FROM app.chart_definitions WHERE chart_id = 'treasury-payouts'
                ORDER BY version
            """)).all()
            self.assertEqual([item.version for item in row], [1, 2])
            stored_v1, stored_v2 = row
            junctions = {item.id: connection.execute(text("""
                SELECT metric_definition_id, series_role FROM app.chart_metrics
                WHERE chart_definition_version_id = :id
            """), {"id": item.id}).all() for item in row}
        definition = chart_by_chart_id("treasury-payouts")
        self.assertIs(definition.version, 2)
        # v1 stays registered unchanged against the v1 aggregate definition
        self.assertEqual(stored_v1.metric_definition_ids,
                         [str(definition_by_metric_id_version(
                             "treasury_payouts_near", 1).id)])
        self.assertEqual(stored_v1.filter_schema["properties"]["recipient"],
                         {"type": "string",
                          "enum": list(chart_registry.FILTER_TREASURY_RECIPIENTS)})
        self.assertEqual(sorted(junctions[stored_v1.id]),
                         [(definition_by_metric_id_version(
                             "treasury_payouts_near", 1).id, "required_primary")])
        # v2 binds the per-recipient definition and carries the NI-071
        # multi-value/reconciliation filter schema
        self.assertEqual(stored_v2.id, definition.id)
        self.assertEqual(stored_v2.metric_definition_ids,
                         [str(definition_by_metric_id("treasury_payouts_near").id)])
        self.assertEqual(stored_v2.unit_schema, {"required_primary": "NEAR"})
        self.assertEqual(stored_v2.data_status, "available")
        self.assertIsNone(stored_v2.unavailable_reason)
        self.assertTrue(stored_v2.filter_schema["properties"]["recipient"]["multi_value"])
        self.assertEqual(sorted(junctions[stored_v2.id]),
                         [(definition_by_metric_id("treasury_payouts_near").id,
                           "required_primary")])

    def test_03_diverging_stored_chart_is_rejected_never_rewritten(self):
        with self.operator.begin() as connection:
            register_charts(connection)
        original = chart_by_chart_id("gross-fees").title

        def restore():
            with self.admin.begin() as connection:
                connection.execute(text("""
                    UPDATE app.chart_definitions SET title = :title
                    WHERE chart_id = 'gross-fees' AND version = 1
                """), {"title": original})
        self.addCleanup(restore)
        with self.admin.begin() as connection:
            connection.execute(text("""
                UPDATE app.chart_definitions SET title = 'tampered'
                WHERE chart_id = 'gross-fees' AND version = 1
            """))
        with self.assertRaisesRegex(ChartRegistryError, "diverges from"):
            with self.operator.begin() as connection:
                register_charts(connection)

    def test_04_registries_are_readable_but_append_only(self):
        with self.operator.begin() as connection:
            register_charts(connection)
        # two runtime users read the public scientific definitions, including
        # the honestly unavailable ones
        for subject in (uuid4(), uuid4()):
            with user_transaction(self.runtime, subject) as connection:
                count = connection.scalar(text("SELECT count(*) FROM app.chart_definitions"))
                gated = connection.execute(text("""
                    SELECT data_status, unavailable_reason FROM app.chart_definitions
                    WHERE chart_id = 'protocol-revenue'
                """)).one()
            self.assertEqual(count, len(CHARTS))
            self.assertEqual(gated.data_status, "unavailable")
            self.assertIn("OQ-01", gated.unavailable_reason)
        runtime_forbidden = (
            "INSERT INTO app.chart_definitions(id, chart_id, version, title, description,"
            " category, visualization_type, data_status, update_frequency,"
            " allowed_ranges, filter_schema, unit_schema, metric_definition_ids,"
            " source_lineage, renderer_version)"
            " VALUES (gen_random_uuid(), 'evil-chart', 1, 'x', 'x', 'model', 'bar',"
            " 'available', 'daily', '{}', '{}', '{}', '[]', '{}', 'x')",
            "INSERT INTO app.chart_metrics(chart_definition_version_id,"
            " metric_definition_id, series_role)"
            " VALUES (gen_random_uuid(), gen_random_uuid(), 'required_primary')",
        )
        operator_forbidden = (
            "UPDATE app.chart_definitions SET title = 'x' WHERE chart_id = 'gross-fees'",
            "DELETE FROM app.chart_definitions WHERE chart_id = 'gross-fees'",
            "UPDATE app.chart_metrics SET series_role = 'optional_context'",
            "DELETE FROM app.chart_metrics",
        )
        for statement in runtime_forbidden:
            with self.subTest(statement=statement[:60]):
                with self.assertRaises(DBAPIError) as raised:
                    with user_transaction(self.runtime, uuid4()) as connection:
                        connection.execute(text(statement))
                self.assertEqual(raised.exception.orig.sqlstate, "42501")
        for statement in operator_forbidden:
            with self.subTest(statement=statement[:60]):
                with self.assertRaises(DBAPIError) as raised:
                    with self.operator.begin() as connection:
                        connection.execute(text(statement))
                self.assertEqual(raised.exception.orig.sqlstate, "42501")

    def test_05_dataset_metric_bindings_resolve_registered_definitions(self):
        """The documented NI-031 contract change: staging members are FK-bound."""
        with self.operator.begin() as connection:
            register_charts(connection)
            sha = uuid4().hex * 2
            artifact = connection.execute(text("""
                INSERT INTO app.artifacts(id, relative_storage_key, sha256, byte_size,
                                          media_type, scope)
                VALUES (gen_random_uuid(), :key, :sha, 2, 'application/json', 'internal')
                RETURNING id
            """), {"key": f"manifests/aa/{sha}.json", "sha": sha}).scalar_one()
            version = connection.execute(text("""
                INSERT INTO app.dataset_versions(id, dataset_key, version, status,
                    start_date, end_date, frequency, pipeline_version,
                    manifest_artifact_id, content_sha256)
                VALUES (gen_random_uuid(), 'ni031-fk.test', 1, 'staged', '2026-01-01',
                        '2026-01-02', 'daily', 'ni031-test', :artifact, :sha)
                RETURNING id
            """), {"artifact": artifact, "sha": uuid4().hex * 2}).scalar_one()
            # a registered definition binds fine
            connection.execute(text("""
                INSERT INTO app.dataset_metrics(dataset_version_id, metric_definition_id)
                VALUES (:version, :metric)
            """), {"version": version,
                   "metric": definition_by_metric_id("observed_near_purchases").id})

        def restore():
            with self.admin.begin() as connection:
                connection.execute(text(
                    "DELETE FROM app.dataset_metrics WHERE dataset_version_id = :v"),
                    {"v": version})
                connection.execute(text(
                    "DELETE FROM app.dataset_versions WHERE id = :v"), {"v": version})
                connection.execute(text(
                    "DELETE FROM app.artifacts WHERE id = :a"), {"a": artifact})
        self.addCleanup(restore)

        # an unregistered metric uuid is refused by the referential FK (each
        # probe in its own transaction: a failed statement aborts the rest)
        with self.assertRaises(DBAPIError) as raised:
            with self.operator.begin() as connection:
                connection.execute(text("""
                    INSERT INTO app.dataset_metrics(dataset_version_id, metric_definition_id)
                    VALUES (:version, :metric)
                """), {"version": version, "metric": uuid4()})
        self.assertEqual(raised.exception.orig.sqlstate, "23503")
        # the chart junction refuses an unregistered metric uuid too
        definition = chart_by_chart_id("intents-volume")
        with self.assertRaises(DBAPIError) as raised:
            with self.operator.begin() as connection:
                connection.execute(text("""
                    INSERT INTO app.chart_metrics(chart_definition_version_id,
                        metric_definition_id, series_role)
                    VALUES (:id, :metric, 'optional_context')
                """), {"id": definition.id, "metric": uuid4()})
        self.assertEqual(raised.exception.orig.sqlstate, "23503")


if __name__ == "__main__":
    unittest.main()
