"""NI-032 tests: public delivery APIs for metrics, chart views, datasets, sources.

Offline classes run everywhere (contract shape, filter fuzz, quality mapping,
bounded cache behavior); DB classes need scripts/run-db-tests.py. A skip is
never integration evidence. All dataset keys, values and identities are
synthetic fixtures staged through the real NI-028 pipeline; no provider,
archive or network access happens anywhere.
"""

import datetime as dt
import json
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from near_api.auth.principal import get_runtime_engine
from near_api.charts.registry import chart_by_chart_id
from near_api.datasets import delivery
from near_api.datasets.delivery import (
    AMBIGUOUS_VARIANT_REASON,
    LatestPointerCache,
    VersionContentCache,
    aggregate_quality,
    parse_filters_document,
    validate_filters_against_schema,
)
from near_api.datasets.service import publish, stage
from near_api.datasets.storage import ArtifactStorage
from near_api.main import app
from near_api.metrics.registry import definition_by_metric_id
from near_api.pagination import decode_page_cursor, encode_page_cursor
from near_api.schemas.delivery import (
    ChartDefinitionResponse,
    ChartViewResponse,
    DataSourceResponse,
    DatasetResponse,
    MetricResponse,
    ResolvedSelection,
    SeriesResponse,
)
from near_api.db.session import create_runtime_engine

WINDOW = ("2026-01-01", "2026-01-06")
DAILY_PERIODS = 5

METRIC_PURCHASES = definition_by_metric_id("observed_near_purchases").id
METRIC_CONVERSIONS = definition_by_metric_id("conversion_count").id
METRIC_VOLUME = definition_by_metric_id("provider_intents_volume_usd").id
METRIC_FEES = definition_by_metric_id("provider_gross_fees_usd").id
METRIC_PAYOUTS = definition_by_metric_id("treasury_payouts_near").id
METRIC_PAYOUT_COUNT = definition_by_metric_id("treasury_payout_count").id

SOURCE_IDS = {"SRC-BQ": "BigQuery export", "SRC-PRICE": "Saved price snapshots",
              "SRC-LLAMA": "DefiLlama saved snapshots",
              "SRC-DASHBOARD": "Public dashboard saved snapshots",
              "SRC-FASTNEAR": "FastNear indexed blocks",
              "SRC-NEAR-RPC": "NEAR public RPC",
              "SRC-SECRET-PROVIDER": "Synthetic gated provider"}


def observation(metric: UUID, day: dt.date, *, value: str | None = "10.5",
                dimensions: dict | None = None, quality: dict | None = None,
                bound_kind: str | None = "exact", status: str | None = None,
                period_start: dt.datetime | None = None) -> dict:
    start = period_start or dt.datetime.combine(day, dt.time.min, tzinfo=dt.timezone.utc)
    end = start + dt.timedelta(days=1)
    return {
        "metric_definition_id": str(metric),
        "period_start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "period_end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dimensions": dimensions or {},
        "value": value,
        "quality_status": status or ("verified" if value is not None else "missing"),
        "bound_kind": bound_kind if value is not None else None,
        "source_record_ref": None,
        "quality": quality if quality is not None else (
            {} if value is not None else {"reason": "synthetic source gap"}),
    }


def manifest_document(dataset_key: str, observations: list[dict], *,
                      member_metrics: list[UUID], window: tuple[str, str] = WINDOW,
                      frequency: str = "daily") -> dict:
    return {
        "schema_version": 1,
        "dataset_key": dataset_key,
        "frequency": frequency,
        "window": {"start": window[0], "end_exclusive": window[1]},
        "pipeline_version": "ni032-test",
        "code_commit": None, "config_hash": None, "dependency_lock_hash": None,
        "source_as_of": None, "retrieved_at": None,
        "quality": {"notes": "synthetic ni032 fixture"},
        "member_metrics": [str(metric) for metric in member_metrics],
        "inputs": [],
        "observations": observations,
    }


class ResolvedSelectionContractTests(unittest.TestCase):
    """Offline response-contract checks for the delivery schemas."""

    def test_resolved_selection_carries_validated_filters(self):
        selection = ResolvedSelection(start="2026-01-01", end="2026-01-31",
                                      frequency="day", filters={"source": "SRC-LLAMA"})
        self.assertEqual(selection.filters.model_dump(), {"source": "SRC-LLAMA"})
        for changes in ({"end": "2024-01-01"}, {"end": "2026-01-01"},
                        {"frequency": "week"}, {"owner_id": "synthetic"},
                        {"start": "2025-01-01", "end": "2027-01-01"}):
            with self.subTest(changes=changes):
                with self.assertRaises(Exception):
                    ResolvedSelection.model_validate({"start": "2026-01-01",
                                                      "end": "2026-01-31",
                                                      "frequency": "day", "filters": {},
                                                      **changes})

    def test_unavailable_chart_responses_carry_reason_and_available_do_not(self):
        from near_api.schemas.delivery import AvailableRanges
        base = {"id": str(uuid4()), "chart_id": "synthetic", "version": 1,
                "title": "Synthetic", "description": "Synthetic description",
                "category": "fees", "metric_definition_ids": [],
                "visualization_type": "bar", "units": {}, "filter_schema": {},
                "available_ranges": {"presets_days": [7], "max_days": 366},
                "renderer_version": "synthetic@1", "update_frequency": "daily",
                "source_lineage": {"sources": [], "note": "synthetic"}}
        with self.assertRaises(Exception):
            ChartDefinitionResponse.model_validate({**base, "data_status": "available",
                                                    "unavailable_reason": "should not be"})
        with self.assertRaises(Exception):
            ChartDefinitionResponse.model_validate({**base, "data_status": "unavailable"})
        honest = ChartDefinitionResponse.model_validate({**base, "data_status":
                                                         "unavailable",
                                                         "unavailable_reason": "gated"})
        self.assertEqual(honest.data_status, "unavailable")

    def test_range_presets_exceeding_max_are_rejected(self):
        from near_api.schemas.delivery import AvailableRanges
        with self.assertRaises(Exception):
            AvailableRanges(presets_days=(400,), max_days=366)


class FilterAndQualityUnitTests(unittest.TestCase):
    """Filter parsing/validation and quality-mapping behavior (no database)."""

    def test_filter_parsing_canonicalizes_and_rejects_fuzz(self):
        self.assertEqual(parse_filters_document(None), {})
        self.assertEqual(parse_filters_document(""), {})
        self.assertEqual(parse_filters_document('{"b":"2","a":"1"}'), {"a": "1", "b": "2"})
        for raw in ("{", "[1,2]", '"x"', "null", '{"a": 1}', '{"a": {"b": "c"}}',
                    '{"": "x"}', '{"a": null}', '{"k%s": "v"}' .replace("%s", "e" * 200)):
            with self.subTest(raw=raw[:20]), self.assertRaises(delivery.DeliveryInvalidFilter):
                parse_filters_document(raw)

    def test_chart_filter_schema_validation_is_closed(self):
        schema = chart_by_chart_id("intents-volume").filter_schema
        self.assertEqual(validate_filters_against_schema(
            {"source": "SRC-LLAMA"}, schema), {"source": "SRC-LLAMA"})
        for filters in ({"wallet": "x"}, {"source": "SRC-NOPE"}, {"source": 1}):
            with self.subTest(filters=filters), \
                    self.assertRaises(delivery.DeliveryInvalidFilter):
                validate_filters_against_schema(filters, schema)
        with self.assertRaises(delivery.DeliveryInvalidFilter):
            validate_filters_against_schema({}, {"type": "object"})

    def test_row_quality_maps_verified_missing_and_unavailable(self):
        verified = delivery._row_quality({"quality_status": "verified",
                                          "bound_kind": "lower", "quality": {}})
        self.assertEqual((verified.status, verified.bound_kind, verified.reasons),
                         ("ok", "lower", ()))
        self.assertEqual(verified.coverage.observed, 1)
        missing = delivery._row_quality({"quality_status": "missing", "bound_kind": None,
                                         "quality": {"reason": "x" * 500}})
        self.assertEqual((missing.status, missing.bound_kind), ("missing", None))
        self.assertEqual(missing.reasons, ("x" * 200,))
        self.assertEqual(missing.coverage.observed, 0)
        unavailable = delivery._row_quality({"quality_status": "unavailable",
                                             "bound_kind": "exact", "quality": {}})
        self.assertEqual(unavailable.status, "unavailable")
        self.assertIsNone(unavailable.bound_kind)

    def test_point_building_and_missing_points(self):
        row = {"period_start": dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc),
               "period_end": dt.datetime(2026, 1, 3, tzinfo=dt.timezone.utc),
               "value": "10.5", "quality_status": "verified", "bound_kind": "exact",
               "quality": {}}
        point = delivery._point_from_row(row)
        self.assertEqual(point["value"], "10.5")
        gap = delivery._missing_point(row["period_start"], row["period_end"],
                                      delivery.OUTSIDE_COVERAGE_REASON)
        self.assertEqual(gap["quality"]["status"], "missing")
        ambiguous = delivery._unavailable_point(row["period_start"], row["period_end"],
                                                AMBIGUOUS_VARIANT_REASON)
        self.assertEqual(ambiguous["quality"]["status"], "unavailable")
        self.assertIsNone(ambiguous["value"])

    def test_quality_aggregation_is_deterministic_worst_of(self):
        ok_point = {"quality": {"status": "ok", "reasons": [],
                                "coverage": {"observed": 1, "expected": 1}}}
        missing_point = {"quality": {"status": "missing", "reasons": ("gap",),
                                     "coverage": {"observed": 0, "expected": 1}}}
        unavailable_point = {"quality": {"status": "unavailable", "reasons": ("gate",),
                                         "coverage": {"observed": 0, "expected": 1}}}
        self.assertEqual(aggregate_quality([ok_point, ok_point]).status, "ok")
        partial = aggregate_quality([ok_point, missing_point])
        self.assertEqual((partial.status, partial.coverage.observed, partial.coverage.expected),
                         ("partial", 1, 2))
        self.assertEqual(aggregate_quality([missing_point, missing_point]).status, "missing")
        self.assertEqual(aggregate_quality([missing_point, unavailable_point]).status,
                         "unavailable")
        empty = aggregate_quality([])
        self.assertEqual((empty.status, empty.reasons, empty.coverage.expected),
                         ("unavailable", (delivery.NO_SELECTION_INTERSECTION_REASON,), 0))

    def test_series_points_daily_grid_gaps_and_ambiguity(self):
        version = {"frequency": "daily", "start_date": dt.date(2026, 1, 1),
                   "end_date": dt.date(2026, 1, 6)}
        metric = uuid4()
        utc = dt.timezone.utc
        content = {"observations": {
            metric: (
                {"period_start": dt.datetime(2026, 1, 1, tzinfo=utc),
                 "period_end": dt.datetime(2026, 1, 2, tzinfo=utc),
                 "dimensions": {"source": "SRC-A"}, "dimensions_hash": "0" * 64,
                 "value": "1.0", "quality_status": "verified",
                 "bound_kind": "exact", "quality": {}},
                # 01-02: two dimension variants -> ambiguous without a filter
                {"period_start": dt.datetime(2026, 1, 2, tzinfo=utc),
                 "period_end": dt.datetime(2026, 1, 3, tzinfo=utc),
                 "dimensions": {"source": "SRC-A"}, "dimensions_hash": "1" * 64,
                 "value": "2.0", "quality_status": "verified", "bound_kind": "exact",
                 "quality": {}},
                {"period_start": dt.datetime(2026, 1, 2, tzinfo=utc),
                 "period_end": dt.datetime(2026, 1, 3, tzinfo=utc),
                 "dimensions": {"source": "SRC-B"}, "dimensions_hash": "2" * 64,
                 "value": "3.0", "quality_status": "verified", "bound_kind": "exact",
                 "quality": {}},
                # 01-03: a stored missing observation with its reason
                {"period_start": dt.datetime(2026, 1, 3, tzinfo=utc),
                 "period_end": dt.datetime(2026, 1, 4, tzinfo=utc), "dimensions": {},
                 "dimensions_hash": "3" * 64, "value": None, "quality_status": "missing",
                 "bound_kind": None, "quality": {"reason": "gap"}},
                # 01-05 outside the requested selection below
                {"period_start": dt.datetime(2026, 1, 5, tzinfo=utc),
                 "period_end": dt.datetime(2026, 1, 6, tzinfo=utc), "dimensions": {},
                 "dimensions_hash": "4" * 64, "value": "5.0",
                 "quality_status": "verified", "bound_kind": "exact", "quality": {}},
            )}}
        points = delivery.build_series_points(version, content, metric,
                                              dt.date(2026, 1, 1), dt.date(2026, 1, 5), {})
        self.assertEqual([point["quality"]["status"] for point in points],
                         ["ok", "unavailable", "missing", "missing"])
        self.assertIn(AMBIGUOUS_VARIANT_REASON, points[1]["quality"]["reasons"])
        self.assertEqual(points[2]["value"], None)
        # 01-04 is inside the dataset window but holds no row at all
        self.assertEqual(points[3]["quality"]["reasons"],
                         (delivery.NO_OBSERVATION_REASON,))
        # a selection reaching past the dataset window explains the overlap
        extended = delivery.build_series_points(version, content, metric,
                                                dt.date(2026, 1, 5), dt.date(2026, 1, 8),
                                                {})
        self.assertEqual([point["quality"]["status"] for point in extended],
                         ["ok", "missing", "missing"])
        self.assertEqual(extended[1]["quality"]["reasons"],
                         (delivery.OUTSIDE_COVERAGE_REASON,))
        self.assertEqual(extended[2]["quality"]["reasons"],
                         (delivery.OUTSIDE_COVERAGE_REASON,))
        # a filter matching one variant disambiguates; the other variant day
        # still exists, so 01-02 keeps exactly one matching row
        filtered = delivery.build_series_points(version, content, metric,
                                                dt.date(2026, 1, 1), dt.date(2026, 1, 3),
                                                {"source": "SRC-A"})
        self.assertEqual([point["value"] for point in filtered], ["1.0", "2.0"])

    def test_series_points_boundary_anchored_frequencies_surface_rows(self):
        metric = uuid4()
        utc = dt.timezone.utc
        version = {"frequency": "snapshot", "start_date": dt.date(2026, 1, 1),
                   "end_date": dt.date(2026, 1, 31)}
        content = {"observations": {metric: (
            {"period_start": dt.datetime(2026, 1, 2, 6, tzinfo=utc),
             "period_end": dt.datetime(2026, 1, 2, 7, tzinfo=utc), "dimensions": {},
             "dimensions_hash": "a" * 64, "value": "9.0", "quality_status": "verified",
             "bound_kind": "exact", "quality": {}},
            {"period_start": dt.datetime(2026, 1, 9, 6, tzinfo=utc),
             "period_end": dt.datetime(2026, 1, 9, 7, tzinfo=utc), "dimensions": {},
             "dimensions_hash": "b" * 64, "value": None, "quality_status": "unavailable",
             "bound_kind": None, "quality": {"reason": "gated"}},)}}
        points = delivery.build_series_points(version, content, metric,
                                              dt.date(2026, 1, 1), dt.date(2026, 1, 31), {})
        self.assertEqual([point["value"] for point in points], ["9.0", None])
        self.assertEqual(points[0]["start"].hour, 6)

    def test_dataset_quality_aggregates_content(self):
        empty = delivery.dataset_quality({"total_count": 0, "verified_count": 0,
                                          "reasons": ()})
        self.assertEqual(empty.status, "unavailable")
        full = delivery.dataset_quality({"total_count": 4, "verified_count": 4,
                                         "reasons": ()})
        self.assertEqual(full.status, "ok")
        partial = delivery.dataset_quality({"total_count": 4, "verified_count": 3,
                                            "reasons": ("synthetic source gap",)})
        self.assertEqual((partial.status, partial.coverage.observed), ("partial", 3))

    def test_docs_url_and_lineage_redaction(self):
        self.assertEqual(delivery._safe_docs_url("https://docs.example.test/a"), 
                         "https://docs.example.test/a")
        for url in ("https://user:secret@example.test/a", "http://", "ftp://example.test",
                    "not a url", None, ""):
            with self.subTest(url=url):
                self.assertIsNone(delivery._safe_docs_url(url))
        lineage = delivery._sanitize_lineage(["kept", "  ", "x" * 500, 42, "last"])
        self.assertEqual(len(lineage), 3)
        self.assertEqual(lineage[1], "x" * 200)


class CacheUnitTests(unittest.TestCase):
    """Bounded cache behavior: TTL, eviction and full-key collision checks."""

    def test_latest_pointer_cache_ttl_and_negative_is_never_cached(self):
        now = [100.0]
        cache = LatestPointerCache(ttl_seconds=60, clock=lambda: now[0])
        first, second = uuid4(), uuid4()
        self.assertIsNone(cache.get(frozenset({first})))
        cache.put(frozenset({first}), first)
        self.assertEqual(cache.get(frozenset({first})), first)
        # distinct required-metric sets never collide
        self.assertIsNone(cache.get(frozenset({second})))
        now[0] += 59.9
        self.assertEqual(cache.get(frozenset({first})), first)
        now[0] += 0.2
        self.assertIsNone(cache.get(frozenset({first})))

    def test_latest_pointer_cache_is_bounded(self):
        cache = LatestPointerCache(ttl_seconds=60, limit=2, clock=lambda: 0.0)
        keys = [uuid4() for _ in range(3)]
        for key in keys:
            cache.put(frozenset({key}), key)
        self.assertIsNone(cache.get(frozenset({keys[0]})))
        self.assertEqual(cache.get(frozenset({keys[2]})), keys[2])

    def test_version_cache_never_collides_distinct_versions(self):
        cache = VersionContentCache(limit=4)
        first, second = uuid4(), uuid4()
        cache.put(first, {"tag": "first"})
        cache.put(second, {"tag": "second"})
        self.assertEqual(cache.get(first), {"tag": "first"})
        self.assertEqual(cache.get(second), {"tag": "second"})
        cache.put(first, {"tag": "first-immutable"})
        self.assertEqual(cache.get(first), {"tag": "first-immutable"})
        self.assertEqual(cache.get(second), {"tag": "second"})

    def test_version_cache_evicts_least_recently_used(self):
        cache = VersionContentCache(limit=2)
        keys = [uuid4() for _ in range(3)]
        for index, key in enumerate(keys):
            cache.put(key, {"index": index})
        self.assertIsNone(cache.get(keys[0]))
        self.assertEqual(cache.get(keys[2]), {"index": 2})
        cache.put(keys[0], {"index": 0})
        self.assertIsNone(cache.get(keys[1]))

    def test_cursors_round_trip_and_reject_garbage(self):
        self.assertEqual(decode_page_cursor(None), 0)
        self.assertEqual(decode_page_cursor(encode_page_cursor(42)), 42)
        for cursor in ("%%%", "bm90LWhleA", encode_page_cursor(10**12), "-1"):
            with self.subTest(cursor=cursor):
                with self.assertRaises(HTTPException) as raised:
                    decode_page_cursor(cursor)
                self.assertEqual(raised.exception.status_code, 422)


class OfflineHttpValidationTests(unittest.TestCase):
    """HTTP failures answered before any database access (no cluster needed)."""

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_runtime_engine] = lambda: None
        cls.client = TestClient(app, raise_server_exceptions=False)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.pop(get_runtime_engine, None)

    def test_metric_catalog_rejects_unknown_filter_axes(self):
        for query, code in (({"category": "fees"}, "FILTER_UNSUPPORTED"),
                            ({"availability": "Z"}, "FILTER_UNSUPPORTED"),
                            ({"limit": "0"}, "VALIDATION_ERROR"),
                            ({"limit": "101"}, "VALIDATION_ERROR"),
                            ({"cursor": "%%%"}, "VALIDATION_ERROR")):
            with self.subTest(query=query):
                response = self.client.get("/api/metrics", params=query)
                self.assertEqual(response.status_code, 422)
                error = response.json()["error"]
                self.assertEqual(error["code"], code)
                self.assertFalse(error["retryable"])

    def test_chart_catalog_and_view_validation_gates(self):
        response = self.client.get("/api/charts", params={"category": "nope"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "FILTER_UNSUPPORTED")
        base = {"definition_version": "1", "start": "2026-01-01", "end": "2026-01-08"}
        for changes, code in (({"frequency": "week"}, "FILTER_UNSUPPORTED"),
                              ({"dataset_version": "not-a-uuid"}, "FILTER_UNSUPPORTED"),
                              ({"start": "2026-01-08", "end": "2026-01-01"},
                               "VALIDATION_ERROR"),
                              ({"start": "2024-01-01", "end": "2027-01-01"},
                               "VALIDATION_ERROR"),
                              ({"filters": "{bad json"}, "FILTER_UNSUPPORTED")):
            with self.subTest(changes=changes):
                response = self.client.get("/api/charts/intents-volume/view",
                                           params={**base, **changes})
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["error"]["code"], code)
        # Unknown filter keys are rejected against the resolved version's
        # allowlist in the database-backed classes below.


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class DeliveryDatabaseTests(unittest.TestCase):
    """Public delivery HTTP behavior on the disposable PostgreSQL cluster."""

    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[3]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.runtime = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        cls.operator = create_engine(os.environ["NI_TEST_OPERATOR_URL"], poolclass=NullPool,
                                     hide_parameters=True)
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"], poolclass=NullPool,
                                  hide_parameters=True)
        command.upgrade(cls.config, "head")
        from near_api.charts.registry import register_charts
        from near_api.metrics.registry import register_definitions

        with cls.operator.begin() as connection:
            for source_id, name in SOURCE_IDS.items():
                connection.execute(text("""
                    INSERT INTO app.sources(id, name, docs_url, base_url, access_status,
                                            license_status, lineage)
                    VALUES (:id, :name, :docs_url, :base_url, 'documented', 'unverified',
                            CAST(:lineage AS jsonb))
                    ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name,
                        docs_url = EXCLUDED.docs_url, base_url = EXCLUDED.base_url,
                        lineage = EXCLUDED.lineage
                """), {"id": source_id, "name": name,
                       "docs_url": ("https://user:pass@example.test/docs" if
                                    source_id == "SRC-SECRET-PROVIDER" else
                                    f"https://docs.example.test/{source_id.lower()}"),
                       "base_url": ("https://user:token-secret-123@api.example.test/v1"
                                    if source_id == "SRC-SECRET-PROVIDER" else None),
                       "lineage": '["synthetic lineage note", "  ", 42]'})
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
        delivery.reset_delivery_caches()
        self.directory = Path(os.environ["NI_TEST_TMP_DIR"]) / f"ni032-{uuid4().hex[:8]}"
        self.directory.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.storage_root = self.directory / "storage"

    # -- fixture helpers ----------------------------------------------------- #

    def stage_fixture(self, dataset_key: str, observations: list[dict],
                      member_metrics: list[UUID], *, window: tuple[str, str] = WINDOW,
                      frequency: str = "daily", do_publish: bool = True):
        document = manifest_document(dataset_key, observations, member_metrics=member_metrics,
                                     window=window, frequency=frequency)
        path = self.directory / f"{dataset_key.replace('.', '-')}.json"
        path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
        result = stage(self.operator, path, self.storage_root)
        self.assertEqual(result.status, "validated", result.validation)
        if do_publish:
            publish(self.operator, result.dataset_version_id)
        return result

    def main_dataset(self, dataset_key: str):
        """Purchases (one missing day), conversions, and provider variants."""
        days = [dt.date.fromisoformat(WINDOW[0]) + dt.timedelta(days=index)
                for index in range(DAILY_PERIODS)]
        observations = []
        for index, day in enumerate(days):
            value = None if index == 3 else f"{10 + index}.5"
            observations.append(observation(METRIC_PURCHASES, day, value=value))
            observations.append(observation(METRIC_CONVERSIONS, day,
                                            value=str(index + 1)))
            observations.append(observation(METRIC_VOLUME, day, value="100.5",
                                            dimensions={"source": "SRC-LLAMA"}))
            observations.append(observation(METRIC_VOLUME, day, value="120.75",
                                            dimensions={"source": "SRC-DASHBOARD"}))
            observations.append(observation(METRIC_FEES, day, value="2.5",
                                            dimensions={"source": "SRC-LLAMA"}))
        return self.stage_fixture(dataset_key, observations,
                                  [METRIC_PURCHASES, METRIC_CONVERSIONS, METRIC_VOLUME,
                                   METRIC_FEES])

    def get_json(self, path: str, **params):
        response = self.client.get(path, params=params)
        return response

    # -- catalog --------------------------------------------------------------#

    def test_01_metric_catalog_filters_and_paginates(self):
        response = self.get_json("/api/metrics")
        self.assertEqual(response.status_code, 200)
        page = response.json()
        metric_ids = {item["metric_id"] for item in page["items"]}
        self.assertIn("observed_near_purchases", metric_ids)
        self.assertIn("protocol_revenue_usd", metric_ids)
        for item in page["items"]:
            MetricResponse.model_validate(item)
        gated = next(item for item in page["items"]
                     if item["metric_id"] == "protocol_revenue_usd")
        self.assertEqual(gated["availability"], "G")
        self.assertTrue(gated["limitations"])
        purchases = next(item for item in page["items"]
                         if item["metric_id"] == "observed_near_purchases")
        self.assertEqual((purchases["version"], purchases["unit"], purchases["frequency"]),
                         (1, "NEAR", "daily"))
        self.assertEqual(purchases["formula"], "observed_near_purchases_v1")

        filtered = self.get_json("/api/metrics", availability="G")
        self.assertEqual(filtered.status_code, 200)
        self.assertTrue(filtered.json()["items"])
        self.assertTrue(all(item["availability"] == "G"
                            for item in filtered.json()["items"]))
        paged = self.get_json("/api/metrics", limit=3)
        self.assertEqual(len(paged.json()["items"]), 3)
        self.assertIsNotNone(paged.json()["next_cursor"])
        followed = self.get_json("/api/metrics", limit=3,
                                 cursor=paged.json()["next_cursor"])
        first_ids = {item["metric_id"] for item in paged.json()["items"]}
        second_ids = {item["metric_id"] for item in followed.json()["items"]}
        self.assertFalse(first_ids & second_ids)

    def test_02_metric_detail_unknown_and_version_404(self):
        response = self.get_json("/api/metrics/observed_near_purchases")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MetricResponse.model_validate(response.json()).metric_id,
                         "observed_near_purchases")
        unknown = self.get_json("/api/metrics/unknown_metric")
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(unknown.json()["error"]["code"], "NOT_FOUND")
        stale_version = self.get_json("/api/metrics/observed_near_purchases",
                                      version=99)
        self.assertEqual(stale_version.status_code, 404)
        self.assertEqual(stale_version.json()["error"]["code"], "NOT_FOUND")

    def test_03_chart_catalog_is_honest(self):
        response = self.get_json("/api/charts")
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        by_id = {item["chart_id"]: item for item in items}
        self.assertEqual(len(items), 11)
        for item in items:
            ChartDefinitionResponse.model_validate(item)
        available = {"intents-volume", "gross-fees", "observed-conversions",
                     "treasury-payouts", "quantity-usd-sensitivity", "supply-context",
                     "fee-volume-association"}
        for chart_id, item in by_id.items():
            if chart_id in available:
                self.assertEqual(item["data_status"], "available")
                self.assertIsNone(item["unavailable_reason"])
            else:
                self.assertEqual(item["data_status"], "unavailable")
                self.assertTrue(item["unavailable_reason"])
        self.assertEqual(by_id["intents-volume"]["units"], {"required_primary": "USD"})
        self.assertEqual(by_id["intents-volume"]["available_ranges"]["max_days"], 366)

        searched = self.get_json("/api/charts", q="fees")
        # the search covers title, description and chart_id, so the gated
        # fee/buyback charts (whose descriptions mention fees) match too
        self.assertEqual({item["chart_id"] for item in searched.json()["items"]},
                         {"gross-fees", "fee-volume-association", "protocol-revenue",
                          "fee-funded-buybacks"})
        categorized = self.get_json("/api/charts", category="treasury")
        self.assertEqual({item["chart_id"] for item in categorized.json()["items"]},
                         {"treasury-payouts", "fee-funded-buybacks"})
        self.assertEqual(self.get_json("/api/charts", category="nope").status_code, 422)
        self.assertEqual(self.get_json("/api/charts/unknown-chart").status_code, 404)

    # -- one approved dataset per request -------------------------------------#

    def test_04_latest_excludes_staged_and_serves_last_good(self):
        # Use a metric no other test publishes, so "no approved dataset" holds.
        key = f"ni032-lastgood-{uuid4().hex[:10]}"
        observations = [observation(METRIC_PAYOUTS, dt.date.fromisoformat(WINDOW[0])
                                    + dt.timedelta(days=index), value="4.25")
                        for index in range(DAILY_PERIODS)]
        staged = self.stage_fixture(key, observations, [METRIC_PAYOUTS],
                                    do_publish=False)
        for path, params in (
                ("/api/metrics/treasury_payouts_near/series",
                 {"definition_version": 1, "start": WINDOW[0], "end": WINDOW[1],
                  "dataset_version": "latest"}),
                (f"/api/datasets/{staged.dataset_version_id}", {}),
                (f"/api/datasets/{staged.dataset_version_id}/manifest", {})):
            with self.subTest(path=path):
                response = self.get_json(path, **params)
                self.assertEqual(response.status_code, 503 if "series" in path else 404)
                if response.status_code == 503:
                    error = response.json()["error"]
                    self.assertEqual(error["code"], "DATA_NOT_READY")
                    self.assertTrue(error["retryable"])
        publish(self.operator, staged.dataset_version_id)
        series = self.get_json("/api/metrics/treasury_payouts_near/series",
                               definition_version=1, start=WINDOW[0], end=WINDOW[1],
                               dataset_version="latest")
        self.assertEqual(series.status_code, 200)
        self.assertEqual(series.json()["dataset"]["id"], str(staged.dataset_version_id))
        # a staged newer version never becomes latest
        document = json.loads((self.directory /
                               f"{key.replace('.', '-')}.json").read_text())
        document["observations"][0]["value"] = "99.0"
        path_v2 = self.directory / "lastgood-v2.json"
        path_v2.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        second = stage(self.operator, path_v2, self.storage_root)
        self.assertEqual(second.version, 2)
        delivery.reset_delivery_caches()
        still_first = self.get_json("/api/metrics/treasury_payouts_near/series",
                                    definition_version=1, start=WINDOW[0],
                                    end=WINDOW[1], dataset_version="latest")
        self.assertEqual(still_first.json()["dataset"]["id"],
                         str(staged.dataset_version_id))
        self.assertEqual(self.get_json(f"/api/datasets/{second.dataset_version_id}")
                         .status_code, 404)
        publish(self.operator, second.dataset_version_id)
        delivery.reset_delivery_caches()
        moved = self.get_json("/api/metrics/treasury_payouts_near/series",
                              definition_version=1, start=WINDOW[0], end=WINDOW[1],
                              dataset_version="latest")
        self.assertEqual(moved.json()["dataset"]["id"], str(second.dataset_version_id))
        # history stays readable at its immutable version id
        self.assertEqual(self.get_json(f"/api/datasets/{staged.dataset_version_id}")
                         .status_code, 200)

    def test_05_series_contract_decimal_strings_quality_timestamps(self):
        staged = self.main_dataset(f"ni032-series-{uuid4().hex[:10]}")
        version_id = staged.dataset_version_id
        response = self.get_json("/api/metrics/observed_near_purchases/series",
                                 definition_version=1, start=WINDOW[0], end=WINDOW[1],
                                 dataset_version=str(version_id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"],
                         "public, max-age=31536000, immutable")
        series = SeriesResponse.model_validate_json(response.text)
        self.assertEqual(len(series.points), DAILY_PERIODS)
        missing = series.points[3]
        self.assertIsNone(missing.value)
        self.assertEqual(missing.quality.status, "missing")
        self.assertEqual(missing.quality.reasons, ("synthetic source gap",))
        ok = series.points[0]
        self.assertEqual((ok.value, ok.quality.bound_kind, ok.quality.status),
                         ("10.5", "exact", "ok"))
        self.assertTrue(ok.start.isoformat().endswith("+00:00"))
        payload = response.json()
        for point in payload["points"]:
            self.assertTrue(point["start"].endswith("Z"))
            self.assertTrue(point["end"].endswith("Z"))
        self.assertEqual(payload["dataset"]["id"], str(version_id))
        self.assertEqual(payload["dataset"]["status"], "approved")
        self.assertEqual(payload["metric"]["metric_id"], "observed_near_purchases")
        self.assertEqual(payload["selection"],
                         {"start": WINDOW[0], "end": WINDOW[1], "frequency": "day",
                          "filters": {}})
        # identical selections resolve consistently: byte-identical responses
        again = self.get_json("/api/metrics/observed_near_purchases/series",
                              definition_version=1, start=WINDOW[0], end=WINDOW[1],
                              dataset_version=str(version_id))
        self.assertEqual(again.json(), payload)
        # selection extending beyond the dataset window explains the overlap
        extended = self.get_json("/api/metrics/observed_near_purchases/series",
                                 definition_version=1, start=WINDOW[0], end="2026-01-08",
                                 dataset_version=str(version_id))
        points = extended.json()["points"]
        self.assertEqual(len(points), 7)
        self.assertEqual(points[5]["quality"]["reasons"],
                         [delivery.OUTSIDE_COVERAGE_REASON])
        # unknown metric slug and unknown version are the generic 404
        self.assertEqual(self.get_json("/api/metrics/no_such_metric/series",
                                       definition_version=1, start=WINDOW[0],
                                       end=WINDOW[1],
                                       dataset_version=str(version_id)).status_code, 404)
        # a non-member metric on an explicit version is a reference error
        other = self.get_json("/api/metrics/treasury_payout_count/series",
                              definition_version=1, start=WINDOW[0], end=WINDOW[1],
                              dataset_version=str(version_id))
        self.assertEqual(other.status_code, 422)
        self.assertEqual(other.json()["error"]["code"], "REFERENCE_INVALID")
        # a malformed dataset_version value is unsupported, never guessed
        bad = self.get_json("/api/metrics/observed_near_purchases/series",
                            definition_version=1, start=WINDOW[0], end=WINDOW[1],
                            dataset_version="not-a-uuid")
        self.assertEqual((bad.status_code, bad.json()["error"]["code"]),
                         (422, "FILTER_UNSUPPORTED"))

    def test_06_metric_series_rejects_filters_and_reports_ambiguity(self):
        staged = self.main_dataset(f"ni032-ambig-{uuid4().hex[:10]}")
        version_id = str(staged.dataset_version_id)
        filtered = self.get_json("/api/metrics/provider_intents_volume_usd/series",
                                 definition_version=1, start=WINDOW[0], end=WINDOW[1],
                                 dataset_version=version_id,
                                 filters=json.dumps({"source": "SRC-LLAMA"}))
        self.assertEqual((filtered.status_code, filtered.json()["error"]["code"]),
                         (422, "FILTER_UNSUPPORTED"))
        ambiguous = self.get_json("/api/metrics/provider_intents_volume_usd/series",
                                  definition_version=1, start=WINDOW[0], end=WINDOW[1],
                                  dataset_version=version_id)
        self.assertEqual(ambiguous.status_code, 200)
        points = ambiguous.json()["points"]
        self.assertTrue(points)
        for point in points:
            self.assertIsNone(point["value"])
            self.assertEqual(point["quality"]["status"], "unavailable")
            self.assertEqual(point["quality"]["reasons"],
                             [delivery.AMBIGUOUS_VARIANT_REASON])
        single = self.get_json("/api/metrics/provider_gross_fees_usd/series",
                               definition_version=1, start=WINDOW[0], end=WINDOW[1],
                               dataset_version=version_id)
        self.assertEqual([point["value"] for point in single.json()["points"]],
                         ["2.5"] * DAILY_PERIODS)

    # -- chart views -----------------------------------------------------------#

    def test_07_chart_view_contract_and_consistency(self):
        staged = self.main_dataset(f"ni032-view-{uuid4().hex[:10]}")
        version_id = str(staged.dataset_version_id)
        params = {"definition_version": 1, "start": WINDOW[0], "end": WINDOW[1],
                  "dataset_version": version_id}
        response = self.get_json("/api/charts/observed-conversions/view", **params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"],
                         "public, max-age=31536000, immutable")
        view = ChartViewResponse.model_validate_json(response.text)
        self.assertEqual(view.definition.chart_id, "observed-conversions")
        self.assertEqual([series.metric.metric_id for series in view.series],
                         ["observed_near_purchases", "conversion_count"])
        self.assertEqual(view.series[0].metric.unit, "NEAR")
        self.assertEqual(view.series[1].metric.unit, "events")
        self.assertEqual(len(view.context_hash), 64)
        self.assertEqual(view.dataset.id, UUID(version_id))
        # purchases hold one missing day, conversions are complete -> partial
        self.assertEqual(view.quality.status, "partial")
        self.assertEqual(view.quality.coverage.observed, 9)
        self.assertEqual(view.quality.coverage.expected, 10)
        self.assertIn("synthetic source gap", view.quality.reasons)
        payload = response.json()
        repeat = self.get_json("/api/charts/observed-conversions/view", **params)
        self.assertEqual(repeat.json()["context_hash"], payload["context_hash"])
        self.assertEqual(repeat.json()["series"], payload["series"])
        # latest pointer serves the same single approved dataset
        latest = self.get_json("/api/charts/observed-conversions/view",
                               definition_version=1, start=WINDOW[0], end=WINDOW[1],
                               dataset_version="latest")
        self.assertEqual(latest.json()["dataset"]["id"], version_id)
        self.assertEqual(latest.headers["Cache-Control"], "public, max-age=60")

    def test_08_chart_view_filters_range_and_gates(self):
        staged = self.main_dataset(f"ni032-filters-{uuid4().hex[:10]}")
        version_id = str(staged.dataset_version_id)
        base = {"definition_version": 1, "start": WINDOW[0], "end": WINDOW[1],
                "dataset_version": version_id}
        filtered = self.get_json("/api/charts/intents-volume/view",
                                 **{**base, "filters": json.dumps(
                                     {"source": "SRC-LLAMA"})})
        self.assertEqual(filtered.status_code, 200)
        view = ChartViewResponse.model_validate_json(filtered.text)
        self.assertEqual([point.value for point in view.series[0].points],
                         ["100.5"] * DAILY_PERIODS)
        self.assertEqual(view.quality.status, "ok")
        self.assertEqual(view.selection.filters.model_dump(), {"source": "SRC-LLAMA"})
        for filters, code in (({"wallet": "x"}, "FILTER_UNSUPPORTED"),
                              ({"source": "SRC-NOPE"}, "FILTER_UNSUPPORTED")):
            with self.subTest(filters=filters):
                response = self.get_json("/api/charts/intents-volume/view",
                                         **{**base, "filters": json.dumps(filters)})
                self.assertEqual((response.status_code, response.json()["error"]["code"]),
                                 (422, code))
        unfiltered = self.get_json("/api/charts/intents-volume/view", **base)
        self.assertEqual(unfiltered.status_code, 200)
        self.assertEqual(unfiltered.json()["quality"]["status"], "unavailable")
        self.assertIn(delivery.AMBIGUOUS_VARIANT_REASON,
                      unfiltered.json()["quality"]["reasons"])
        # range gates: the shared 366-day bound rejects a multi-year window
        long_range = self.get_json("/api/charts/intents-volume/view",
                                   definition_version=1, start="2024-01-01",
                                   end="2027-01-01", dataset_version=version_id)
        self.assertEqual(long_range.status_code, 422)
        # gated charts are never advertised as live: no approved dataset
        # carries their metrics, so latest is a typed not-ready answer
        for chart_id in ("protocol-revenue", "model-diagnostics"):
            with self.subTest(chart_id=chart_id):
                response = self.get_json(f"/api/charts/{chart_id}/view",
                                         definition_version=1, start=WINDOW[0],
                                         end=WINDOW[1], dataset_version="latest")
                self.assertEqual(response.status_code, 503)
                error = response.json()["error"]
                self.assertEqual((error["code"], error["retryable"]),
                                 ("DATA_NOT_READY", True))
        # an explicit version missing a required metric is a reference error
        provider_only = self.stage_fixture(
            f"ni032-provider-{uuid4().hex[:10]}",
            [observation(METRIC_VOLUME, dt.date.fromisoformat(WINDOW[0])
                         + dt.timedelta(days=index), value="50.0",
                         dimensions={"source": "SRC-LLAMA"})
             for index in range(DAILY_PERIODS)],
            [METRIC_VOLUME])
        mismatch = self.get_json("/api/charts/observed-conversions/view",
                                 definition_version=1, start=WINDOW[0], end=WINDOW[1],
                                 dataset_version=str(provider_only.dataset_version_id))
        self.assertEqual((mismatch.status_code, mismatch.json()["error"]["code"]),
                         (422, "REFERENCE_INVALID"))

    # -- sources ---------------------------------------------------------------#

    def test_09_source_projections_are_sanitized(self):
        response = self.get_json("/api/data-sources")
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertTrue(items)
        for item in items:
            DataSourceResponse.model_validate(item)
        self.assertNotIn("base_url", response.text)
        self.assertNotIn("token-secret-123", response.text)
        self.assertNotIn("user:pass", response.text)
        gated = next(item for item in items if item["id"] == "SRC-SECRET-PROVIDER")
        self.assertIsNone(gated["docs_url"])
        normal = next(item for item in items if item["id"] == "SRC-BQ")
        self.assertEqual(normal["docs_url"], "https://docs.example.test/src-bq")
        self.assertEqual(normal["lineage"], ["synthetic lineage note"])
        self.assertIsNone(normal["last_success_at"])
        detail = self.get_json("/api/data-sources/SRC-BQ")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(DataSourceResponse.model_validate(detail.json()).id, "SRC-BQ")
        self.assertEqual(self.get_json("/api/data-sources/SRC-UNKNOWN").status_code, 404)
        # the ingestion checkpoint zone feeds last_success_at once a refresh ran
        with self.operator.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.ingestion_checkpoints(source_id, last_height,
                    last_block_hash, last_success_at, consecutive_failures)
                VALUES ('SRC-BQ', 100, '2gYUDWbRFHSTUKnbmUiqTQcxSYMcp4QtpLgtJbveEZcN',
                        now(), 0)
                ON CONFLICT (source_id) DO UPDATE SET last_success_at = now()
            """))
        refreshed = self.get_json("/api/data-sources/SRC-BQ")
        self.assertIsNotNone(refreshed.json()["last_success_at"])
        self.assertIsNone(refreshed.json()["expected_update_frequency"])

    # -- datasets and manifest --------------------------------------------------#

    def test_10_dataset_detail_and_manifest_sanitization(self):
        staged = self.main_dataset(f"ni032-dataset-{uuid4().hex[:10]}")
        version_id = staged.dataset_version_id
        response = self.get_json(f"/api/datasets/{version_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["ETag"], f'"{staged.content_sha256}"')
        dataset = DatasetResponse.model_validate_json(response.text)
        self.assertEqual((dataset.status, dataset.dataset_key, dataset.version),
                         ("approved", staged.dataset_key, 1))
        self.assertEqual(dataset.quality.coverage.observed, 24)
        self.assertEqual(dataset.quality.coverage.expected, 25)
        self.assertEqual(dataset.manifest_url, f"/api/datasets/{version_id}/manifest")
        manifest_response = self.get_json(f"/api/datasets/{version_id}/manifest")
        self.assertEqual(manifest_response.status_code, 200)
        self.assertEqual(manifest_response.headers["ETag"], f'"{staged.content_sha256}"')
        manifest = manifest_response.json()
        self.assertEqual(manifest["dataset_key"], staged.dataset_key)
        self.assertEqual(len(manifest["observations"]), 25)
        canonical_values = {item["value"] for item in manifest["observations"]
                            if item["value"] is not None}
        self.assertIn("10.5", canonical_values)
        self.assertFalse(any("10.500000000000000000000000000000" == value
                             for value in canonical_values))
        for item in manifest["inputs"]:
            self.assertNotIn("path", item)
            self.assertIn("sha256", item)
            self.assertTrue(item["storage_key"].startswith("blobs/"))
        self.assertNotIn(str(self.directory), manifest_response.text)
        self.assertEqual(manifest["member_metrics"],
                         sorted(str(item) for item in
                                (METRIC_PURCHASES, METRIC_CONVERSIONS, METRIC_VOLUME,
                                 METRIC_FEES)))
        # a prohibited license makes the manifest unreachable, identical to absent
        with self.admin.begin() as connection:
            artifact_id = connection.scalar(text(
                "SELECT manifest_artifact_id FROM app.dataset_versions WHERE id = :id"),
                {"id": version_id})
            connection.execute(text(
                "UPDATE app.artifacts SET license_status = 'prohibited' WHERE id = :id"),
                {"id": artifact_id})
        try:
            blocked = self.get_json(f"/api/datasets/{version_id}/manifest")
            self.assertEqual(blocked.status_code, 404)
            self.assertEqual(blocked.json()["error"]["code"], "NOT_FOUND")
        finally:
            with self.admin.begin() as connection:
                connection.execute(text(
                    "UPDATE app.artifacts SET license_status = 'unverified' "
                    "WHERE id = :id"), {"id": artifact_id})
        self.assertEqual(self.get_json(f"/api/datasets/{uuid4()}").status_code, 404)

    # -- caching -----------------------------------------------------------------#

    def test_11_cache_keys_never_collide_and_latest_is_bounded(self):
        first = self.main_dataset(f"ni032-cache-{uuid4().hex[:10]}")
        v1 = str(first.dataset_version_id)
        params = {"definition_version": 1, "start": WINDOW[0], "end": WINDOW[1],
                  "dataset_version": v1}
        before = self.get_json("/api/metrics/observed_near_purchases/series", **params)
        self.assertEqual(before.json()["dataset"]["id"], v1)
        # a revised second version with different content must never collide
        document = json.loads((self.directory /
                               f"{first.dataset_key.replace('.', '-')}.json")
                              .read_text())
        document["observations"][0]["value"] = "77.25"
        path_v2 = self.directory / "cache-v2.json"
        path_v2.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        second = stage(self.operator, path_v2, self.storage_root)
        publish(self.operator, second.dataset_version_id)
        v2 = str(second.dataset_version_id)
        after = self.get_json("/api/metrics/observed_near_purchases/series", **params)
        self.assertEqual(after.json(), before.json())
        revised = self.get_json("/api/metrics/observed_near_purchases/series",
                                definition_version=1, start=WINDOW[0], end=WINDOW[1],
                                dataset_version=v2)
        self.assertEqual(revised.json()["points"][0]["value"], "77.25")
        # the latest pointer re-resolves after a cache reset and keeps
        # pointing at the newest approved version (the <=60s TTL itself is
        # pinned by the offline cache unit tests)
        delivery.reset_delivery_caches()
        series_latest = self.get_json("/api/metrics/observed_near_purchases/series",
                                      definition_version=1, start=WINDOW[0],
                                      end=WINDOW[1], dataset_version="latest")
        self.assertEqual(series_latest.json()["dataset"]["id"], v2)
        again = self.get_json("/api/metrics/observed_near_purchases/series",
                              definition_version=1, start=WINDOW[0], end=WINDOW[1],
                              dataset_version="latest")
        self.assertEqual(again.json()["dataset"]["id"], v2)

    def test_12_failed_publication_keeps_serving_last_good(self):
        key = f"ni032-outage-{uuid4().hex[:10]}"
        observations = [observation(METRIC_PAYOUT_COUNT, dt.date.fromisoformat(WINDOW[0])
                                    + dt.timedelta(days=index), value="2")
                        for index in range(DAILY_PERIODS)]
        first = self.stage_fixture(key, observations, [METRIC_PAYOUT_COUNT])
        document = json.loads((self.directory /
                               f"{key.replace('.', '-')}.json").read_text())
        document["observations"][0]["value"] = "5"
        path_v2 = self.directory / "outage-v2.json"
        path_v2.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        second = stage(self.operator, path_v2, self.storage_root)
        with patch("near_api.datasets.service._revision_delta",
                   side_effect=RuntimeError("simulated refresh outage")):
            with self.assertRaises(RuntimeError):
                publish(self.operator, second.dataset_version_id)
        delivery.reset_delivery_caches()
        series = self.get_json("/api/metrics/treasury_payout_count/series",
                               definition_version=1, start=WINDOW[0], end=WINDOW[1],
                               dataset_version="latest")
        self.assertEqual(series.status_code, 200)
        self.assertEqual(series.json()["dataset"]["id"], str(first.dataset_version_id))
        self.assertEqual([point["value"] for point in series.json()["points"]],
                         ["2"] * DAILY_PERIODS)


if __name__ == "__main__":
    unittest.main()
