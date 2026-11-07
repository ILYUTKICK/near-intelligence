"""NI-030 tests for the bounded scheduled finalized-header refresh adapter.

Offline classes use synthetic mock transports only — no provider request is
made and no research archive is read. Database classes run under
scripts/run-db-tests.py in the disposable loopback cluster (direct discovery
skips them without the isolated-cluster environment; a skip is never
integration evidence). The one-request live smoke lives in
``test_refresh_live_smoke.py`` and is excluded from CI discovery on purpose.
"""

import datetime as dt
import gzip
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock
from uuid import UUID

import httpx
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from near_api.datasets.canonical import decimal_string
from near_api.datasets.service import create_dataset_operator_engine
from near_api.db.session import create_runtime_engine
from near_api.ingestion.providers.finalized_header import (
    DATASET_KEY,
    MAX_REQUESTS_PER_DAY,
    MAX_RESPONSE_BYTES,
    MIN_REQUEST_INTERVAL,
    REFRESH_LOCK_NAMESPACE,
    SOURCE_ID,
    FinalizedHeaderRefresh,
    RefreshFailed,
    RefreshRefused,
    evaluate_budget,
    exact_supply_near,
    validate_header_response,
)

BASE58_HASH = "q" * 43
SUPPLY_YOCTO = "1311012246333893718750000181969746"
SUPPLY_NEAR = "1311012246.333893718750000181969746"
FIXED_NOW = dt.datetime(2026, 11, 7, 3, 15, 0, tzinfo=dt.timezone.utc)


def block_hash_for(height: int) -> str:
    """Deterministic base58-safe (no 0/O/I/l) 43-character block hash."""
    return ("f" + str(height).replace("0", "g")).ljust(43, "x")


def header_body(height: int, *, timestamp_ns: str | None = None,
                total_supply: str = SUPPLY_YOCTO, block_hash: str | None = None,
                rpc_id: str = "ni-030") -> bytes:
    block_hash = block_hash or block_hash_for(height)
    timestamp_ns = timestamp_ns or str(1_794_000_000_000_000_000 + height * 60_000_000_000)
    return json.dumps({
        "jsonrpc": "2.0", "id": rpc_id,
        "result": {"header": {"height": height, "hash": block_hash,
                              "timestamp_nanosec": timestamp_ns,
                              "total_supply": total_supply}},
    }, separators=(",", ":")).encode("utf-8")


def success_transport(calls: list, body: bytes):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=body,
                              headers={"Content-Type": "application/json"})
    return httpx.MockTransport(handler)


def status_transport(calls: list, status: int):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, json={"synthetic": "provider error body"})
    return httpx.MockTransport(handler)


class BudgetDecisionTests(unittest.TestCase):
    """Pure OQ-03 budget logic: 1 request/minute, <=1440 requests/day."""

    def test_minute_budget_refuses_inside_interval_and_allows_after(self):
        last = FIXED_NOW - dt.timedelta(seconds=30)
        self.assertEqual(evaluate_budget(last_request_at=last, requests_used_today=0,
                                         now=FIXED_NOW), "minute_budget_exhausted")
        boundary = FIXED_NOW - MIN_REQUEST_INTERVAL  # exactly 60 s: request may go out
        self.assertIsNone(evaluate_budget(last_request_at=boundary, requests_used_today=0,
                                          now=FIXED_NOW))
        self.assertIsNone(evaluate_budget(last_request_at=None, requests_used_today=0,
                                          now=FIXED_NOW))

    def test_daily_budget_refuses_only_when_exhausted(self):
        self.assertIsNone(evaluate_budget(last_request_at=None,
                                          requests_used_today=MAX_REQUESTS_PER_DAY - 1,
                                          now=FIXED_NOW))
        self.assertEqual(evaluate_budget(last_request_at=None,
                                         requests_used_today=MAX_REQUESTS_PER_DAY,
                                         now=FIXED_NOW), "daily_budget_exhausted")

    def test_minute_budget_takes_precedence_when_both_exhausted(self):
        last = FIXED_NOW - dt.timedelta(seconds=5)
        self.assertEqual(evaluate_budget(last_request_at=last,
                                         requests_used_today=MAX_REQUESTS_PER_DAY,
                                         now=FIXED_NOW), "minute_budget_exhausted")


class SupplyConversionTests(unittest.TestCase):
    def test_exact_power_of_ten_conversion_never_rounds(self):
        # 34 significant digits must survive exactly, whatever ambient decimal
        # context the process happens to have (default contexts are 28-digit).
        from decimal import localcontext
        self.assertEqual(exact_supply_near(SUPPLY_YOCTO), SUPPLY_NEAR)
        self.assertEqual(exact_supply_near("0"), "0")
        self.assertEqual(exact_supply_near("1" + "0" * 24), "1")
        with localcontext() as context:
            context.prec = 5
            self.assertEqual(exact_supply_near(SUPPLY_YOCTO), SUPPLY_NEAR)


class HeaderValidationTests(unittest.TestCase):
    """Controlled schema tests; the provider is never contacted."""

    def test_valid_header_is_sanitized(self):
        raw = header_body(223_400_000, total_supply=SUPPLY_YOCTO)
        header = validate_header_response(raw, retrieved_at=FIXED_NOW)
        self.assertEqual(header["height"], 223_400_000)
        self.assertEqual(header["block_hash"], block_hash_for(223_400_000))
        self.assertEqual(header["timestamp_nanosec"],
                         str(1_794_000_000_000_000_000 + 223_400_000 * 60_000_000_000))
        self.assertEqual(header["total_supply_yocto"], SUPPLY_YOCTO)
        self.assertEqual(header["response_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(header["response_bytes"], len(raw))

    def test_schema_deviations_fail_without_exposing_payload(self):
        cases = {
            "jsonrpc error": json.dumps({"jsonrpc": "2.0", "id": "ni-030",
                                         "error": {"code": -32000,
                                                   "message": "synthetic"}}).encode(),
            "wrong id": json.dumps({"jsonrpc": "2.0", "id": "other", "result": {
                "header": {"height": 1, "hash": BASE58_HASH,
                           "timestamp_nanosec": "1", "total_supply": "1"}}}).encode(),
            "missing header": json.dumps({"jsonrpc": "2.0", "id": "ni-030",
                                          "result": {}}).encode(),
            "bad height": header_body(-1),
            "bad hash": header_body(5, block_hash="0OIl" + "a" * 39),
            "bad timestamp": header_body(5, timestamp_ns="17x"),
            "bad supply": header_body(5, total_supply="12.5"),
            "float body": json.dumps({"jsonrpc": "2.0", "id": "ni-030", "result": {
                "header": {"height": 1.5, "hash": BASE58_HASH,
                           "timestamp_nanosec": "1", "total_supply": "1"}}}).encode(),
            "not json": b"<html>gateway error</html>",
        }
        for name, raw in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(RefreshFailed) as caught:
                    validate_header_response(raw, retrieved_at=FIXED_NOW)
                self.assertEqual(caught.exception.kind, "schema_invalid")
                self.assertNotIn("synthetic", str(caught.exception))


class FetchFailureTests(unittest.TestCase):
    """Controlled HTTP failure tests on a mock transport: one attempt, no retry."""

    def setUp(self):
        self.refresh = FinalizedHeaderRefresh(
            engine=mock.Mock(), storage_root=Path("/nonexistent-storage"),
            repo_root=Path("/nonexistent-repo"))
        self.calls: list = []

    def test_http_429_fails_once_without_retry(self):
        with self.assertRaises(RefreshFailed) as caught:
            self.refresh._fetch("https://rpc.example.invalid",
                                transport=status_transport(self.calls, 429))
        self.assertEqual(caught.exception.kind, "http_429")
        self.assertEqual(len(self.calls), 1)

    def test_auth_failures_fail_once(self):
        for status in (401, 403):
            with self.subTest(status=status):
                self.calls.clear()
                with self.assertRaises(RefreshFailed) as caught:
                    self.refresh._fetch("https://rpc.example.invalid",
                                        transport=status_transport(self.calls, status))
                self.assertEqual(caught.exception.kind, f"http_{status}")
                self.assertEqual(len(self.calls), 1)

    def test_oversized_body_aborts_within_byte_cap(self):
        oversized = header_body(1) + b" " * (MAX_RESPONSE_BYTES + 1)

        def handler(request):
            self.calls.append(request)
            return httpx.Response(200, content=oversized)

        with self.assertRaises(RefreshFailed) as caught:
            self.refresh._fetch("https://rpc.example.invalid",
                                transport=httpx.MockTransport(handler))
        self.assertEqual(caught.exception.kind, "response_too_large")
        self.assertEqual(len(self.calls), 1)

    def test_encoded_response_rejected(self):
        def handler(request):
            self.calls.append(request)
            # A genuinely encoded body: the adapter must reject it on headers
            # before consuming any bytes.
            return httpx.Response(200, content=gzip.compress(header_body(1)),
                                  headers={"Content-Encoding": "gzip"})

        with self.assertRaises(RefreshFailed) as caught:
            self.refresh._fetch("https://rpc.example.invalid",
                                transport=httpx.MockTransport(handler))
        self.assertEqual(caught.exception.kind, "encoded_response")
        self.assertEqual(len(self.calls), 1)

    def test_transport_error_fails_once(self):
        def handler(request):
            self.calls.append(request)
            raise httpx.ConnectError("synthetic outage")

        with self.assertRaises(RefreshFailed) as caught:
            self.refresh._fetch("https://rpc.example.invalid",
                                transport=httpx.MockTransport(handler))
        self.assertEqual(caught.exception.kind, "transport_error")
        self.assertEqual(len(self.calls), 1)

    def test_request_shape_is_the_approved_json_rpc_block_query(self):
        self.refresh._fetch("https://rpc.example.invalid",
                            transport=success_transport(self.calls, header_body(1)))
        self.assertEqual(len(self.calls), 1)
        request = self.calls[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(str(request.url), "https://rpc.example.invalid")
        payload = json.loads(request.content)
        self.assertEqual(payload["method"], "block")
        self.assertEqual(payload["params"], {"finality": "final"})
        self.assertEqual(payload["id"], "ni-030")
        # This adapter is single-request by contract: there is no pagination,
        # cursor or follow-up request behavior to exercise.
        self.assertNotIn("cursor", payload)


class StopMarkerTests(unittest.TestCase):
    """Legacy collectors remain stopped: markers gate the adapter identically."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name)

    def test_root_stop_marker_refuses(self):
        (self.repo / "STOP_PUBLIC_COLLECTION").write_text("stopped", encoding="utf-8")
        refresh = FinalizedHeaderRefresh(engine=mock.Mock(),
                                         storage_root=self.repo / "storage",
                                         repo_root=self.repo)
        with self.assertRaises(RefreshRefused) as caught:
            refresh._check_stop_markers()
        self.assertEqual(caught.exception.kind, "stop_marker_present")

    def test_research_stop_marker_refuses(self):
        nested = self.repo / "research" / "near-x"
        nested.mkdir(parents=True)
        (nested / "STOP_PUBLIC_COLLECTION").write_text("stopped", encoding="utf-8")
        refresh = FinalizedHeaderRefresh(engine=mock.Mock(),
                                         storage_root=self.repo / "storage",
                                         repo_root=self.repo)
        with self.assertRaises(RefreshRefused) as caught:
            refresh._check_stop_markers()
        self.assertEqual(caught.exception.kind, "stop_marker_present")

    def test_missing_repo_root_refuses(self):
        refresh = FinalizedHeaderRefresh(engine=mock.Mock(),
                                         storage_root=self.repo / "storage",
                                         repo_root=self.repo / "missing")
        with self.assertRaises(RefreshRefused) as caught:
            refresh._check_stop_markers()
        self.assertEqual(caught.exception.kind, "repo_root_unavailable")

    def test_clean_repo_passes_markers(self):
        (self.repo / "research").mkdir()
        FinalizedHeaderRefresh(engine=mock.Mock(),
                               storage_root=self.repo / "storage",
                               repo_root=self.repo)._check_stop_markers()


class StubSourceRow:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class StubConnection:
    """Offline stand-in for _approved_endpoint's single registry lookup."""

    def __init__(self, row):
        self._row = row

    def execute(self, *_args, **_kwargs):
        return StubSourceRow(self._row)


class AllowlistTests(unittest.TestCase):
    """The endpoint lives in the database registry; the code only carries IDs."""

    def refresh(self):
        return FinalizedHeaderRefresh(engine=mock.Mock(),
                                      storage_root=Path("/nonexistent"),
                                      repo_root=Path("/nonexistent"))

    def test_approved_row_yields_endpoint(self):
        connection = StubConnection({"access_status": "approved",
                                     "base_url": "https://rpc.mainnet.near.org"})
        self.assertEqual(self.refresh()._approved_endpoint(connection),
                         "https://rpc.mainnet.near.org")

    def test_unapproved_or_missing_rows_refuse(self):
        for row, reason in (
                ({"access_status": "documented", "base_url": "https://rpc.mainnet.near.org"},
                 "documented"),
                ({"access_status": "disabled", "base_url": "https://rpc.mainnet.near.org"},
                 "disabled"),
                ({"access_status": "approved", "base_url": None}, "no endpoint"),
                (None, "missing row")):
            with self.subTest(reason=reason):
                with self.assertRaises(RefreshRefused) as caught:
                    self.refresh()._approved_endpoint(StubConnection(row))
                self.assertEqual(caught.exception.kind, "source_not_approved")

    def test_unsafe_endpoints_refuse(self):
        for endpoint in ("http://rpc.mainnet.near.org",
                         "https://user:pass@rpc.mainnet.near.org",
                         "https://rpc.mainnet.near.org/?x=1",
                         "not a url"):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(RefreshRefused) as caught:
                    self.refresh()._approved_endpoint(StubConnection(
                        {"access_status": "approved", "base_url": endpoint}))
                self.assertEqual(caught.exception.kind, "source_not_approved")


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1",
                     "Use scripts/run-db-tests.py")
class RefreshAdapterDatabaseTests(unittest.TestCase):
    """Real PostgreSQL tests: checkpoints, counters, locks, last-good retention."""

    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[3]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.operator = create_dataset_operator_engine(os.environ["NI_TEST_OPERATOR_URL"])
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"], poolclass=NullPool,
                                  hide_parameters=True)
        cls.runtime = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        command.upgrade(cls.config, "head")
        from near_api.metrics import register_definitions
        with cls.operator.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.sources(id, name, docs_url, base_url, access_status,
                                        license_status)
                VALUES ('SRC-NEAR-RPC', 'NEAR public RPC',
                        'https://docs.near.org/api/rpc/providers',
                        'https://rpc.mainnet.near.org', 'documented', 'unverified')
                ON CONFLICT (id) DO UPDATE SET base_url = EXCLUDED.base_url
            """))
            register_definitions(connection)

    @classmethod
    def tearDownClass(cls):
        cls.operator.dispose()
        cls.admin.dispose()
        cls.runtime.dispose()

    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix="refresh-",
                                               dir=os.environ["NI_TEST_TMP_DIR"]))
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.storage_root = self.directory / "storage"
        self.repo_root = self.directory / "repo"
        self.repo_root.mkdir()
        self.calls: list = []
        self.clock = FIXED_NOW  # every run() call advances past the minute budget
        # Every test starts from the documented (not approved) allowlist state:
        # the fresh-environment default is an empty effective allowlist.
        with self.operator.begin() as connection:
            connection.execute(text(
                "UPDATE app.sources SET access_status = 'documented' WHERE id = :id"),
                {"id": SOURCE_ID})

    def tearDown(self):
        with self.admin.begin() as connection:
            connection.execute(text(
                "DELETE FROM app.ingestion_daily_counters WHERE source_id = :id"),
                {"id": SOURCE_ID})
            connection.execute(text(
                "DELETE FROM app.ingestion_checkpoints WHERE source_id = :id"),
                {"id": SOURCE_ID})
            connection.execute(text(
                "DELETE FROM app.active_datasets WHERE dataset_key = :key"),
                {"key": DATASET_KEY})
            connection.execute(text(
                "DELETE FROM app.metric_observations WHERE dataset_version_id IN "
                "(SELECT id FROM app.dataset_versions WHERE dataset_key = :key)"),
                {"key": DATASET_KEY})
            connection.execute(text(
                "DELETE FROM app.dataset_inputs WHERE dataset_version_id IN "
                "(SELECT id FROM app.dataset_versions WHERE dataset_key = :key)"),
                {"key": DATASET_KEY})
            connection.execute(text(
                "DELETE FROM app.dataset_metrics WHERE dataset_version_id IN "
                "(SELECT id FROM app.dataset_versions WHERE dataset_key = :key)"),
                {"key": DATASET_KEY})
            connection.execute(text(
                "DELETE FROM app.dataset_versions WHERE dataset_key = :key"),
                {"key": DATASET_KEY})

    # -- helpers ------------------------------------------------------------ #

    def approve_source(self):
        with self.operator.begin() as connection:
            connection.execute(text(
                "UPDATE app.sources SET access_status = 'approved' WHERE id = :id"),
                {"id": SOURCE_ID})

    def attempt(self, body: bytes | None = None, *, status: int | None = None,
                now: dt.datetime | None = None):
        """One refresh attempt; the run clock advances past the minute budget."""
        if now is None:
            now, self.clock = self.clock, self.clock + dt.timedelta(seconds=61)
        self.calls.clear()
        transport = (status_transport(self.calls, status) if status is not None
                     else success_transport(self.calls, body))
        return FinalizedHeaderRefresh(self.operator, self.storage_root,
                                      self.repo_root).run_once(transport=transport,
                                                               now=now)

    def checkpoint(self):
        with self.admin.connect() as connection:
            row = connection.execute(text(
                "SELECT * FROM app.ingestion_checkpoints WHERE source_id = :id"),
                {"id": SOURCE_ID}).mappings().first()
            return dict(row) if row is not None else None

    def counter(self):
        with self.admin.connect() as connection:
            row = connection.execute(text(
                "SELECT request_count, success_count FROM app.ingestion_daily_counters "
                "WHERE source_id = :id AND day = :day"),
                {"id": SOURCE_ID, "day": FIXED_NOW.date()}).mappings().first()
            return dict(row) if row is not None else None

    def active_version(self):
        with self.admin.connect() as connection:
            return connection.execute(text("""
                SELECT v.version, v.status, v.content_sha256, v.id
                FROM app.active_datasets a JOIN app.dataset_versions v
                     ON v.id = a.dataset_version_id
                WHERE a.dataset_key = :key
            """), {"key": DATASET_KEY}).mappings().first()

    def version_count(self):
        with self.admin.connect() as connection:
            return connection.scalar(text(
                "SELECT count(*) FROM app.dataset_versions WHERE dataset_key = :key"),
                {"key": DATASET_KEY})

    # -- lifecycle ----------------------------------------------------------- #

    def test_01_full_refresh_publishes_and_checkpoints(self):
        self.approve_source()
        report = self.attempt(header_body(223_400_000))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(report["status"], "published")
        self.assertEqual(report["height"], 223_400_000)
        self.assertEqual(report["checkpoint_height_before"], None)
        self.assertEqual(report["request_count_today"], 1)
        active = self.active_version()
        self.assertEqual(active["status"], "approved")
        self.assertEqual(active["version"], 1)
        self.assertEqual(report["dataset_version_id"], str(active["id"]))
        point = self.checkpoint()
        self.assertEqual(point["last_height"], 223_400_000)
        self.assertEqual(point["last_failure_kind"], None)
        self.assertEqual(point["consecutive_failures"], 0)
        self.assertIsNotNone(point["last_success_at"])
        self.assertIsNotNone(point["last_request_at"])
        self.assertEqual(self.counter(), {"request_count": 1, "success_count": 1})
        # The observation carries the exact supply value and pinned block identity.
        with self.admin.connect() as connection:
            row = connection.execute(text("""
                SELECT o.value::text AS value, o.bound_kind, o.quality_status,
                       o.source_record_ref, o.quality
                FROM app.metric_observations o
                JOIN app.dataset_versions v ON v.id = o.dataset_version_id
                WHERE v.dataset_key = :key
            """), {"key": DATASET_KEY}).mappings().one()
        self.assertEqual(decimal_string(Decimal(row["value"])), SUPPLY_NEAR)
        self.assertEqual((row["bound_kind"], row["quality_status"]), ("exact", "verified"))
        self.assertIn("block 223400000", row["source_record_ref"])
        self.assertEqual(row["quality"]["block_hash"], block_hash_for(223_400_000))
        self.assertEqual(row["quality"]["source_id"], SOURCE_ID)
        # The raw response is preserved as a source-qualified input artifact.
        with self.admin.connect() as connection:
            inputs = connection.execute(text("""
                SELECT i.source_id, i.query_hash, i.role, a.sha256, a.byte_size
                FROM app.dataset_inputs i JOIN app.artifacts a ON a.id = i.artifact_id
                JOIN app.dataset_versions v ON v.id = i.dataset_version_id
                WHERE v.dataset_key = :key
            """), {"key": DATASET_KEY}).mappings().all()
        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0]["source_id"], SOURCE_ID)
        self.assertEqual(inputs[0]["role"], "raw")
        self.assertEqual(inputs[0]["sha256"], hashlib.sha256(
            header_body(223_400_000)).hexdigest())
        stored = self.storage_root / "raw" / (
            f"finalized-header-223400000-{inputs[0]['sha256'][:16]}.json")
        self.assertEqual(stored.read_bytes(), header_body(223_400_000))

    def test_02_higher_height_supersedes_with_revision_delta(self):
        self.approve_source()
        first = self.attempt(header_body(223_400_000))
        next_day_ns = str(int((dt.datetime(2026, 11, 8, 0, 1, tzinfo=dt.timezone.utc)
                               ).timestamp() * 1_000_000_000))
        second = self.attempt(header_body(223_400_120, timestamp_ns=next_day_ns))
        self.assertEqual(second["status"], "published")
        self.assertEqual(second["checkpoint_height_before"], 223_400_000)
        self.assertNotEqual(second["content_sha256"], first["content_sha256"])
        active = self.active_version()
        self.assertEqual(active["version"], 2)
        self.assertEqual(self.checkpoint()["last_height"], 223_400_120)
        with self.admin.connect() as connection:
            revision = connection.execute(text(
                "SELECT quality->'revision' AS revision FROM app.dataset_versions "
                "WHERE id = :id"), {"id": UUID(second["dataset_version_id"])}
            ).scalar_one()
        self.assertEqual(revision["added"], 1)
        self.assertEqual(revision["previous_version_id"], first["dataset_version_id"])

    def test_02b_same_day_higher_height_supersedes_with_changed_observation(self):
        self.approve_source()
        first = self.attempt(header_body(223_400_000))
        # The production cadence case: the next scheduled attempt (61 s later on
        # the run clock) sees the finalized head advanced WITHIN the same UTC
        # day. The observation identity (metric, period_start, dimensions) is
        # unchanged, so the revision delta records a change of the day's
        # observation instead of a new date, and the pointer still moves forward.
        second = self.attempt(header_body(223_400_005))
        self.assertEqual(second["status"], "published")
        self.assertEqual(second["checkpoint_height_before"], 223_400_000)
        self.assertNotEqual(second["content_sha256"], first["content_sha256"])
        active = self.active_version()
        self.assertEqual(active["version"], 2)
        self.assertEqual(self.checkpoint()["last_height"], 223_400_005)
        with self.admin.connect() as connection:
            revision = connection.execute(text(
                "SELECT quality->'revision' AS revision FROM app.dataset_versions "
                "WHERE id = :id"), {"id": UUID(second["dataset_version_id"])}
            ).scalar_one()
        self.assertEqual(revision["previous_version_id"], first["dataset_version_id"])
        self.assertEqual(revision["changed"], 1)
        self.assertEqual(revision["added"], 0)
        self.assertEqual(revision["removed"], 0)

    def test_03_unchanged_height_publishes_nothing(self):
        self.approve_source()
        first = self.attempt(header_body(223_400_000))
        report = self.attempt(header_body(223_400_000))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(report["status"], "unchanged")
        self.assertEqual(self.version_count(), 1)
        self.assertEqual(self.active_version()["id"], UUID(first["dataset_version_id"]))
        self.assertEqual(self.counter()["success_count"], 2)

    def test_04_height_regression_retains_last_good(self):
        self.approve_source()
        good = self.attempt(header_body(223_400_120))
        with self.assertRaises(RefreshFailed) as caught:
            self.attempt(header_body(223_400_000))
        self.assertEqual(caught.exception.kind, "height_regression")
        active = self.active_version()
        self.assertEqual(active["id"], UUID(good["dataset_version_id"]))
        point = self.checkpoint()
        self.assertEqual(point["last_height"], 223_400_120)
        self.assertEqual(point["last_failure_kind"], "height_regression")
        self.assertEqual(point["consecutive_failures"], 1)
        self.assertEqual(self.counter(), {"request_count": 2, "success_count": 1})

    def test_05_http_429_retains_last_good_and_honestly_records(self):
        self.approve_source()
        good = self.attempt(header_body(223_400_000))
        with self.assertRaises(RefreshFailed) as caught:
            self.attempt(status=429)
        self.assertEqual(caught.exception.kind, "http_429")
        self.assertEqual(self.active_version()["id"], UUID(good["dataset_version_id"]))
        self.assertEqual(self.version_count(), 1)
        point = self.checkpoint()
        self.assertEqual(point["last_failure_kind"], "http_429")
        self.assertEqual(point["last_height"], 223_400_000)
        self.assertEqual(self.counter(), {"request_count": 2, "success_count": 1})
        # A successful later run clears the failure state.
        report = self.attempt(header_body(223_400_005))
        self.assertEqual(report["status"], "published")
        cleared = self.checkpoint()
        self.assertIsNone(cleared["last_failure_kind"])
        self.assertEqual(cleared["consecutive_failures"], 0)

    def test_06_auth_failure_retains_last_good(self):
        self.approve_source()
        good = self.attempt(header_body(223_400_000))
        for status in (401, 403):
            with self.subTest(status=status):
                with self.assertRaises(RefreshFailed) as caught:
                    self.attempt(status=status)
                self.assertEqual(caught.exception.kind, f"http_{status}")
        self.assertEqual(self.active_version()["id"], UUID(good["dataset_version_id"]))
        self.assertEqual(self.checkpoint()["last_failure_kind"], "http_403")
        self.assertEqual(self.counter(), {"request_count": 3, "success_count": 1})

    def test_07_schema_error_creates_no_dataset_rows(self):
        self.approve_source()
        with self.assertRaises(RefreshFailed) as caught:
            self.attempt(b'{"jsonrpc": "2.0", "id": "ni-030", '
                     b'"error": {"code": -32000, "message": "synthetic"}}')
        self.assertEqual(caught.exception.kind, "schema_invalid")
        self.assertEqual(self.version_count(), 0)
        self.assertIsNone(self.active_version())
        self.assertEqual(self.checkpoint()["last_failure_kind"], "schema_invalid")

    def test_08_daily_budget_refused_before_any_request(self):
        self.approve_source()
        with self.admin.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.ingestion_daily_counters(source_id, day, request_count,
                                                         success_count)
                VALUES (:id, :day, 1440, 1440)
            """), {"id": SOURCE_ID, "day": FIXED_NOW.date()})
        with self.assertRaises(RefreshRefused) as caught:
            self.attempt(header_body(223_400_000))
        self.assertEqual(caught.exception.kind, "daily_budget_exhausted")
        self.assertEqual(self.calls, [])
        # Refusals consume nothing and record no failure: no request was made.
        self.assertIsNone(self.checkpoint())

    def test_09_minute_budget_refused_before_any_request(self):
        self.approve_source()
        with self.admin.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.ingestion_checkpoints(source_id, last_height,
                    last_block_hash, last_request_at, last_success_at)
                VALUES (:id, 223400000, :hash, :requested, :requested)
            """), {"id": SOURCE_ID, "hash": BASE58_HASH,
                   "requested": FIXED_NOW - dt.timedelta(seconds=45)})
        with self.assertRaises(RefreshRefused) as caught:
            self.attempt(header_body(223_400_005))
        self.assertEqual(caught.exception.kind, "minute_budget_exhausted")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.checkpoint()["last_height"], 223_400_000)

    def test_10_unapproved_source_refused_before_any_request(self):
        # access_status stays 'documented' (fresh-environment default).
        with self.assertRaises(RefreshRefused) as caught:
            self.attempt(header_body(223_400_000))
        self.assertEqual(caught.exception.kind, "source_not_approved")
        self.assertEqual(self.calls, [])
        self.assertIsNone(self.checkpoint())

    def test_11_checkpoint_resume_across_process_restart(self):
        self.approve_source()
        # A previous process committed a checkpoint at height 223_400_000.
        with self.admin.begin() as connection:
            connection.execute(text("""
                INSERT INTO app.ingestion_checkpoints(source_id, last_height,
                    last_block_hash, last_request_at, last_success_at)
                VALUES (:id, 223400000, :hash, :requested, :requested)
            """), {"id": SOURCE_ID, "hash": BASE58_HASH,
                   "requested": FIXED_NOW - dt.timedelta(minutes=5)})
        report = self.attempt(header_body(223_400_070))
        self.assertEqual(report["status"], "published")
        self.assertEqual(report["checkpoint_height_before"], 223_400_000)
        self.assertEqual(self.checkpoint()["last_height"], 223_400_070)

    def test_12_scheduler_overlap_is_refused_by_the_advisory_lock(self):
        self.approve_source()
        holder = self.admin.connect()
        holder.execute(text("SELECT pg_advisory_lock(:ns, hashtext(:key))"),
                       {"ns": REFRESH_LOCK_NAMESPACE, "key": SOURCE_ID})
        try:
            with self.assertRaises(RefreshRefused) as caught:
                self.attempt(header_body(223_400_000))
            self.assertEqual(caught.exception.kind, "overlap_lock_held")
            self.assertEqual(self.calls, [])
        finally:
            holder.execute(text("SELECT pg_advisory_unlock(:ns, hashtext(:key))"),
                           {"ns": REFRESH_LOCK_NAMESPACE, "key": SOURCE_ID})
            holder.close()
        report = self.attempt(header_body(223_400_000))
        self.assertEqual(report["status"], "published")

    def test_13_two_user_boundary_app_reads_operator_state_only(self):
        self.approve_source()
        self.attempt(header_body(223_400_000))
        with self.runtime.connect() as connection:
            rows = connection.execute(text(
                "SELECT last_height FROM app.ingestion_checkpoints")).all()
            self.assertEqual(len(rows), 1)
        # Each denial needs its own connection: a denied statement aborts the
        # surrounding transaction.
        with self.runtime.connect() as connection:
            with self.assertRaises(Exception) as caught:
                connection.execute(text(
                    "UPDATE app.ingestion_checkpoints SET consecutive_failures = 5"))
            self.assertIn("permission denied", str(caught.exception))
        with self.runtime.connect() as connection:
            with self.assertRaises(Exception) as caught:
                connection.execute(text(
                    "INSERT INTO app.ingestion_daily_counters(source_id, day) "
                    "VALUES ('SRC-NEAR-RPC', '2026-11-07')"))
            self.assertIn("permission denied", str(caught.exception))

    def test_14_checkpoint_reset_restages_the_same_block_honestly(self):
        self.approve_source()
        first = self.attempt(header_body(223_400_000))
        # Operator resets the checkpoint (simulated lost state): the same
        # finalized block is re-fetched and restaged as a NEW immutable version
        # (the fresh retrieval instant is part of the semantic manifest), the
        # pointer moves forward and history never moves backwards.
        with self.admin.begin() as connection:
            connection.execute(text(
                "UPDATE app.ingestion_checkpoints SET last_height = NULL, "
                "last_block_hash = NULL WHERE source_id = :id"), {"id": SOURCE_ID})
        report = self.attempt(header_body(223_400_000))
        self.assertEqual(report["status"], "published")
        self.assertNotEqual(report["content_sha256"], first["content_sha256"])
        self.assertEqual(self.version_count(), 2)
        self.assertEqual(self.active_version()["version"], 2)
        self.assertEqual(self.checkpoint()["last_height"], 223_400_000)

    def test_15_migration_round_trip_for_checkpoint_zone(self):
        command.downgrade(self.config, "0007_metric_chart_registries")
        with self.admin.connect() as connection:
            for table in ("ingestion_checkpoints", "ingestion_daily_counters"):
                self.assertIsNone(connection.scalar(
                    text(f"SELECT to_regclass('app.{table}')")))
        command.upgrade(self.config, "head")
        command.check(self.config)


if __name__ == "__main__":
    unittest.main()
