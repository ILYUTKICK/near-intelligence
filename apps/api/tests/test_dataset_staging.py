"""NI-028 real PostgreSQL tests for immutable dataset staging and publication.

All dataset keys, metrics, amounts and archive bytes are synthetic. Use
scripts/run-db-tests.py; direct discovery skips DB cases without its explicit
isolated-cluster environment. A skip is never integration evidence.
"""

import datetime as dt
import hashlib
import io
import json
import os
import shutil
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from archive_fixture import REGISTRY, write_registry

from near_api.datasets.from_import import stage_from_import
from near_api.datasets.manifest import (
    ManifestFormatError,
    content_digest,
    parse_manifest_document,
)
from near_api.datasets.service import (
    DatasetVerificationError,
    PublishRefused,
    _expected_periods,
    _lock_dataset_key,
    _stage_locked,
    _assert_operator,
    active_version,
    create_dataset_operator_engine,
    get_version,
    list_inputs,
    list_observations,
    publish,
    stage,
    validate,
    version_history,
)
from near_api.datasets.storage import ArtifactStorage
from near_api.db.session import create_runtime_engine, user_transaction
from near_api.ingestion import archive
from near_api.metrics.registry import definition_by_metric_id

# NI-031 contract change: dataset_metrics.metric_definition_id carries a
# referential FK to app.metric_definitions, so staging fixtures bind
# registered metric definitions instead of opaque identifiers.
METRIC_A = definition_by_metric_id("observed_near_purchases").id
METRIC_B = definition_by_metric_id("treasury_payouts_near").id
FROM_IMPORT_METRIC = definition_by_metric_id("conversion_count").id
WINDOW = ("2026-01-01", "2026-01-31")
DAILY_PERIODS = 30

DATASET_TABLES = ("artifacts", "dataset_versions", "dataset_metrics", "dataset_inputs",
                  "metric_observations", "active_datasets")


def observation(metric: UUID, day: dt.date, *, value: str | None = "10.5",
                days: int = 1, dimensions: dict | None = None,
                quality: dict | None = None, bound_kind: str | None = "exact",
                status: str | None = None) -> dict:
    start = dt.datetime.combine(day, dt.time.min, tzinfo=dt.timezone.utc)
    end = start + dt.timedelta(days=days)
    record = {
        "metric_definition_id": str(metric),
        "period_start": start.strftime("%Y-%m-%dT00:00:00Z"),
        "period_end": end.strftime("%Y-%m-%dT00:00:00Z"),
        "dimensions": dimensions or {},
        "value": value,
        "quality_status": status or ("verified" if value is not None else "missing"),
        "bound_kind": bound_kind if value is not None else None,
        "source_record_ref": None,
        "quality": quality if quality is not None else (
            {} if value is not None else {"reason": "synthetic source gap"}),
    }
    return record


def daily_observations(metric: UUID, *, start: str = WINDOW[0], count: int = DAILY_PERIODS,
                       value_fn=None) -> list[dict]:
    first = dt.date.fromisoformat(start)
    return [observation(metric, first + dt.timedelta(days=index),
                        value="10.5" if value_fn is None else value_fn(index))
            for index in range(count)]


def manifest_document(dataset_key: str, observations: list[dict], *,
                      member_metrics: list[UUID] | None = None,
                      inputs: list[dict] | None = None,
                      window: tuple[str, str] = WINDOW,
                      frequency: str = "daily", quality: dict | None = None,
                      pipeline_version: str = "ni028-test") -> dict:
    return {
        "schema_version": 1,
        "dataset_key": dataset_key,
        "frequency": frequency,
        "window": {"start": window[0], "end_exclusive": window[1]},
        "pipeline_version": pipeline_version,
        "code_commit": None,
        "config_hash": None,
        "dependency_lock_hash": None,
        "source_as_of": None,
        "retrieved_at": None,
        "quality": quality if quality is not None else {"notes": "synthetic"},
        "member_metrics": [str(metric) for metric in
                           (member_metrics if member_metrics is not None else [METRIC_A])],
        "inputs": inputs if inputs is not None else [],
        "observations": observations,
    }


def write_json(path: Path, document: dict, *, sort_keys: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=sort_keys) + "\n",
                    encoding="utf-8")
    return path


def file_input(directory: Path, *, name: str = "input.json", role: str = "config",
               content: bytes = b'{"synthetic": true}\n') -> dict:
    target = directory / name
    target.write_bytes(content)
    return {"kind": "file", "path": str(target), "role": role, "source_id": None,
            "query_hash": None, "license_status": "unverified"}


class CanonicalManifestTests(unittest.TestCase):
    """Offline checks: canonical hashing, strict parsing, period grids, storage."""

    def test_identical_semantic_manifests_share_digest(self):
        plain = manifest_document("dedup.daily", daily_observations(METRIC_A))
        records = [json.loads(json.dumps(record)) for record in daily_observations(METRIC_A)]
        # same content, different JSON spelling: key order, decimal spelling,
        # timestamp offset form
        records[0]["value"] = "10.50"
        records[0]["period_start"] = "2026-01-01T03:00:00+03:00"
        records[1]["period_end"] = "2026-01-03T00:00:00.000000+00:00"
        reordered = {key: plain[key] for key in reversed(list(plain))}
        reordered["observations"] = records
        other = parse_manifest_document(reordered, context="reordered")
        base = parse_manifest_document(plain, context="plain")
        _bytes_a, digest_a = content_digest(base, [])
        _bytes_b, digest_b = content_digest(other, [])
        self.assertEqual(digest_a, digest_b)

    def test_different_content_changes_digest(self):
        base = parse_manifest_document(
            manifest_document("diff.daily", daily_observations(METRIC_A)), context="base")
        changed = parse_manifest_document(
            manifest_document("diff.daily",
                              daily_observations(METRIC_A, value_fn=lambda index: "11.0")),
            context="changed")
        _bytes_a, digest_a = content_digest(base, [])
        _bytes_b, digest_b = content_digest(changed, [])
        self.assertNotEqual(digest_a, digest_b)

    def test_strict_manifest_rejections(self):
        good = manifest_document("strict.daily", daily_observations(METRIC_A))

        def rejected(mutate, fragment):
            document = json.loads(json.dumps(good))
            mutate(document)
            with self.assertRaises(ManifestFormatError, msg=fragment):
                parse_manifest_document(document, context=fragment)

        rejected(lambda d: d.update(unexpected=1), "unknown field")
        rejected(lambda d: d["observations"][0].update(value=1.5), "float value")
        rejected(lambda d: d["observations"].append(d["observations"][0]), "duplicate record")
        rejected(lambda d: d["observations"][0].update(value=None, quality_status="missing",
                 quality={}), "null value without reason")
        rejected(lambda d: d["observations"][0].update(bound_kind=None), "value without bound")
        rejected(lambda d: d["observations"][0].update(
            period_end="2026-01-01T00:00:00Z"), "empty period")
        rejected(lambda d: d.update(dataset_key="Bad_Key"), "bad dataset key")
        rejected(lambda d: d["window"].update(end_exclusive="2026-01-01"), "empty window")
        rejected(lambda d: d.update(schema_version=2), "unknown schema version")
        rejected(lambda d: d.update(member_metrics=[str(METRIC_A), str(METRIC_A)]),
                 "duplicate member")
        rejected(lambda d: d.update(frequency="hourly"), "bad frequency")

    def test_decimal_bounds_and_canonicalization(self):
        from near_api.datasets.canonical import decimal_string, CanonicalFormatError, parse_decimal
        self.assertEqual(decimal_string(parse_decimal("123.450", context="x")), "123.45")
        self.assertEqual(decimal_string(parse_decimal("1.23e2", context="x")), "123")
        self.assertEqual(decimal_string(parse_decimal("-0.00", context="x")), "0")
        with self.assertRaises(CanonicalFormatError):
            parse_decimal("0." + "0" * 30 + "1", context="x")
        with self.assertRaises(CanonicalFormatError):
            parse_decimal("1" * 49, context="x")
        with self.assertRaises(CanonicalFormatError):
            parse_decimal(1.5, context="x")

    def test_expected_period_grids(self):
        from near_api.datasets.manifest import PreparedManifest

        def manifest(frequency, start, end):
            return PreparedManifest(
                schema_version=1, dataset_key="grid.test", frequency=frequency,
                window_start=dt.date.fromisoformat(start),
                window_end_exclusive=dt.date.fromisoformat(end),
                pipeline_version="t", code_commit=None, config_hash=None,
                dependency_lock_hash=None, source_as_of=None, retrieved_at=None,
                quality={}, member_metrics=(METRIC_A,), inputs=(), observations=())

        daily = _expected_periods(manifest("daily", "2026-01-01", "2026-01-04"))
        self.assertEqual([(a.date().isoformat(), b.date().isoformat()) for a, b in daily],
                         [("2026-01-01", "2026-01-02"), ("2026-01-02", "2026-01-03"),
                          ("2026-01-03", "2026-01-04")])
        weekly = _expected_periods(manifest("weekly", "2026-01-01", "2026-01-15"))
        self.assertEqual(len(weekly), 2)
        self.assertEqual(weekly[1][1].date().isoformat(), "2026-01-15")  # truncated final
        monthly = _expected_periods(manifest("monthly", "2026-01-01", "2026-03-01"))
        self.assertEqual([(a.date().isoformat(), b.date().isoformat()) for a, b in monthly],
                         [("2026-01-01", "2026-02-01"), ("2026-02-01", "2026-03-01")])
        self.assertEqual(_expected_periods(manifest("snapshot", "2026-01-01", "2026-01-31")), [])

    def test_storage_keys_and_atomic_write(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            storage = ArtifactStorage(Path(directory))
            digest = "ab" * 32
            key = storage.store("manifests", digest, b"payload", suffix=".json")
            self.assertEqual(key, f"manifests/ab/{digest}.json")
            self.assertEqual((Path(directory) / key).read_bytes(), b"payload")
            # content-addressed: re-store is a no-op, different digest gets another key
            self.assertEqual(storage.store("manifests", digest, b"payload", suffix=".json"), key)
            self.assertNotEqual(storage.store("blobs", "cd" * 32, b"other"),
                                key)
            with self.assertRaises(Exception):
                storage.key_for("nope", digest)
            with self.assertRaises(Exception):
                storage.path_for("../escape")


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1", "Use scripts/run-db-tests.py")
class DatasetStagingDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).resolve().parents[3]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.operator = create_dataset_operator_engine(os.environ["NI_TEST_OPERATOR_URL"])
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"], poolclass=NullPool,
                                  hide_parameters=True)
        cls.runtime = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=1)
        command.upgrade(cls.config, "head")
        # NI-031 contract change: dataset_metrics.member UUIDs are referentially
        # bound to the metric definition registry, so the fixtures' registered
        # definitions must exist before staging.
        from near_api.metrics import register_definitions

        sources = {"SRC-BQ": "BigQuery export", "SRC-PRICE": "Saved price snapshots",
                   "SRC-LLAMA": "DefiLlama saved snapshots",
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

    def setUp(self):
        # NOTE: keep every path segment's alphanumeric run below 40 chars —
        # the NI-027 lineage redactor replaces long secret-looking runs, and a
        # redacted archive root could not be re-read from disk.
        self.directory = Path(os.environ["NI_TEST_TMP_DIR"]) / f"datasets-{uuid4().hex[:8]}"
        self.directory.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.storage_root = self.directory / "storage"
        self.key = f"ni028-{uuid4().hex[:10]}"

    # -- helpers ------------------------------------------------------------ #

    def write_manifest(self, name: str, document: dict, **kwargs) -> Path:
        return write_json(self.directory / name, document, **kwargs)

    def happy_document(self, dataset_key: str | None = None, **kwargs) -> dict:
        inputs = kwargs.pop("inputs", None)
        if inputs is None:
            inputs = [file_input(self.directory)]
        return manifest_document(dataset_key or self.key, daily_observations(METRIC_A),
                                 inputs=inputs, **kwargs)

    def stage_happy(self, dataset_key: str | None = None, **kwargs):
        manifest_path = self.write_manifest("manifest.json", self.happy_document(dataset_key,
                                                                                **kwargs))
        return stage(self.operator, manifest_path, self.storage_root)

    def counts(self):
        with self.admin.connect() as connection:
            return {table: connection.scalar(text(f"SELECT count(*) FROM app.{table}"))
                    for table in DATASET_TABLES}

    def active_id(self, dataset_key: str | None = None) -> UUID | None:
        with self.admin.connect() as connection:
            return connection.scalar(text(
                "SELECT dataset_version_id FROM app.active_datasets WHERE dataset_key = :key"),
                {"key": dataset_key or self.key})

    # -- lifecycle ----------------------------------------------------------- #

    def test_01_stage_publish_activates_pointer(self):
        result = self.stage_happy()
        self.assertFalse(result.deduplicated)
        self.assertEqual(result.status, "validated")
        self.assertEqual(result.validation["ok"], True)
        self.assertEqual(result.observation_count, DAILY_PERIODS)
        self.assertEqual(result.version, 1)

        report = publish(self.operator, result.dataset_version_id)
        self.assertIsNone(report["previous_version_id"])
        self.assertEqual(report["published_at"].endswith("Z"), True)
        self.assertEqual(self.active_id(), result.dataset_version_id)

        with self.admin.connect() as connection:
            status, supersedes = connection.execute(text("""
                SELECT status, supersedes_id FROM app.dataset_versions WHERE id = :id
            """), {"id": result.dataset_version_id}).one()
        self.assertEqual(status, "approved")
        self.assertIsNone(supersedes)

        # near_app (runtime) can read the approved version and observations
        subject = uuid4()
        with user_transaction(self.runtime, subject) as connection:
            row = connection.execute(text("""
                SELECT dataset_key, status FROM app.dataset_versions WHERE id = :id
            """), {"id": result.dataset_version_id}).one()
            observed = connection.scalar(text("""
                SELECT count(*) FROM app.metric_observations
                WHERE dataset_version_id = :id
            """), {"id": result.dataset_version_id})
            self.assertGreater(connection.scalar(text(
                "SELECT count(*) FROM app.artifacts WHERE scope = 'internal'")), 0)
        self.assertEqual((row[0], row[1], observed), (self.key, "approved", DAILY_PERIODS))

    def test_02_identical_semantic_input_deduplicates(self):
        first = self.stage_happy()
        second = self.stage_happy()
        self.assertTrue(second.deduplicated)
        self.assertEqual(second.dataset_version_id, first.dataset_version_id)
        self.assertEqual(second.version, first.version)
        # same content, different JSON spelling (key order + decimal + offset)
        document = self.happy_document()
        document["observations"][0]["value"] = "10.50"
        document["observations"][0]["period_start"] = "2026-01-01T03:00:00+03:00"
        shuffled = self.write_manifest("manifest-shuffled.json",
                                       {key: document[key] for key in reversed(list(document))},
                                       sort_keys=False)
        third = stage(self.operator, shuffled, self.storage_root)
        self.assertTrue(third.deduplicated)
        self.assertEqual(third.dataset_version_id, first.dataset_version_id)
        with self.admin.connect() as connection:
            key_versions = connection.scalar(text(
                "SELECT count(*) FROM app.dataset_versions WHERE dataset_key = :key"),
                {"key": self.key})
        self.assertEqual(key_versions, 1)

        # identical bytes from a DIFFERENT local path also deduplicate
        copy_input = file_input(self.directory, name="input-copy.json")
        document = self.happy_document(inputs=[copy_input])
        copied = stage(self.operator,
                       self.write_manifest("manifest-copy.json", document), self.storage_root)
        self.assertTrue(copied.deduplicated)
        self.assertEqual(copied.dataset_version_id, first.dataset_version_id)

    def test_03_revision_creates_new_version_without_mutating_old(self):
        first = self.stage_happy()
        publish(self.operator, first.dataset_version_id)
        old_state = self._observations(first.dataset_version_id)
        old_version = self._version_row(first.dataset_version_id)

        document = self.happy_document()
        document["observations"][5]["value"] = "99.25"
        second = stage(self.operator, self.write_manifest("manifest-v2.json", document),
                       self.storage_root)
        self.assertFalse(second.deduplicated)
        self.assertEqual(second.version, 2)
        self.assertNotEqual(second.content_sha256, first.content_sha256)

        report = publish(self.operator, second.dataset_version_id)
        self.assertEqual(report["previous_version_id"], str(first.dataset_version_id))
        self.assertEqual(report["revision"]["changed"], 1)
        self.assertEqual(self.active_id(), second.dataset_version_id)

        # old version untouched, still approved and queryable with its own hash
        self.assertEqual(self._version_row(first.dataset_version_id), old_version)
        self.assertEqual(self._observations(first.dataset_version_id), old_state)
        with self.admin.connect() as connection:
            status = connection.scalar(text(
                "SELECT status FROM app.dataset_versions WHERE id = :id"),
                {"id": first.dataset_version_id})
        self.assertEqual(status, "approved")

        history = self._history()
        self.assertEqual([row["version"] for row in history], [1, 2])
        self.assertEqual(len({row["content_sha256"] for row in history}), 2)
        self.assertEqual(history[1]["supersedes_id"], str(first.dataset_version_id))

    def _version_row(self, version_id: UUID):
        with self.admin.connect() as connection:
            row = connection.execute(text("""
                SELECT id, version, status, content_sha256, supersedes_id
                FROM app.dataset_versions WHERE id = :id
            """), {"id": version_id}).one()
        return tuple(row)

    def _observations(self, version_id: UUID) -> list:
        with self.admin.connect() as connection:
            rows = connection.execute(text("""
                SELECT metric_definition_id, period_start, dimensions_hash, value::text
                FROM app.metric_observations WHERE dataset_version_id = :id
                ORDER BY period_start
            """), {"id": version_id}).all()
        return [tuple(row) for row in rows]

    def _history(self) -> list[dict]:
        with self.operator.connect() as connection:
            _assert_operator(connection)
            return version_history(connection, self.key)

    def test_04_failed_validation_cannot_change_active_data(self):
        first = self.stage_happy()
        publish(self.operator, first.dataset_version_id)

        document = self.happy_document()
        del document["observations"][7]  # unexplained gap inside the declared window
        result = stage(self.operator, self.write_manifest("manifest-gap.json", document),
                       self.storage_root)
        self.assertEqual(result.status, "rejected")
        self.assertFalse(result.validation["ok"])
        self.assertTrue(any("uncovered" in error for error in result.validation["errors"]))

        # active pointer untouched; the rejected version is frozen history
        self.assertEqual(self.active_id(), first.dataset_version_id)
        with self.assertRaises(PublishRefused):
            publish(self.operator, result.dataset_version_id)
        self.assertEqual(self.active_id(), first.dataset_version_id)
        with self.admin.connect() as connection:
            status = connection.scalar(text(
                "SELECT status FROM app.dataset_versions WHERE id = :id"),
                {"id": result.dataset_version_id})
        self.assertEqual(status, "rejected")
        # rejected rows are immutable for the operator role
        with self.assertRaises(DBAPIError) as raised:
            with self.operator.begin() as connection:
                connection.execute(text(
                    "UPDATE app.dataset_versions SET quality = '{}'::jsonb WHERE id = :id"),
                    {"id": result.dataset_version_id})
        self.assertEqual(raised.exception.orig.sqlstate, "P0001")

    def test_05_crash_before_publish_and_rollback_leaves_no_trace(self):
        before = self.counts()
        with mock.patch("near_api.datasets.service._validate_locked",
                        side_effect=RuntimeError("simulated crash during stage")):
            with self.assertRaises(RuntimeError):
                self.stage_happy()
        self.assertEqual(self.counts(), before)

        # publish: crash after every publish step but before commit
        first = self.stage_happy()
        publish(self.operator, first.dataset_version_id)
        document = self.happy_document()
        document["observations"][3]["value"] = "12.0"
        second = stage(self.operator, self.write_manifest("manifest-v2.json", document),
                       self.storage_root)
        with mock.patch("near_api.datasets.service._revision_delta",
                        side_effect=RuntimeError("simulated crash during publish")):
            with self.assertRaises(RuntimeError):
                publish(self.operator, second.dataset_version_id)
        self.assertEqual(self.active_id(), first.dataset_version_id)
        with self.admin.connect() as connection:
            status = connection.scalar(text(
                "SELECT status FROM app.dataset_versions WHERE id = :id"),
                {"id": second.dataset_version_id})
        self.assertEqual(status, "validated")

        # a caller-controlled transaction around the internal core leaves
        # nothing behind when it is rolled back instead of committed
        before = self.counts()
        document = self.happy_document(dataset_key=f"ni028-{uuid4().hex[:10]}")
        document["observations"][4]["value"] = "13.0"
        manifest = parse_manifest_document(document, context="rollback")
        storage = ArtifactStorage(self.storage_root)
        manifest_bytes, digest = content_digest(manifest, [])
        manifest_key = storage.store("manifests", digest, manifest_bytes, suffix=".json")
        with self.assertRaises(RuntimeError):
            with self.operator.begin() as connection:
                _assert_operator(connection)
                _lock_dataset_key(connection, manifest.dataset_key)
                staged = _stage_locked(connection, manifest, [], manifest_key, digest,
                                       manifest_bytes)
                self.assertFalse(staged.deduplicated)
                raise RuntimeError("simulated crash before commit")
        self.assertEqual(self.counts(), before)

    def test_06_concurrent_publish_is_serialized_by_advisory_lock(self):
        first = self.stage_happy()
        publish(self.operator, first.dataset_version_id)

        def revised(index: int):
            document = self.happy_document()
            document["observations"][index]["value"] = f"5{index}.5"
            return stage(self.operator,
                         self.write_manifest(f"manifest-c{index}.json", document),
                         self.storage_root)

        contenders = [revised(10), revised(20)]
        versions = [item.dataset_version_id for item in contenders]
        self.assertEqual([item.version for item in contenders], [2, 3])

        barrier = threading.Barrier(2)
        results: dict[int, dict | Exception] = {}
        engine_b = create_dataset_operator_engine(os.environ["NI_TEST_OPERATOR_URL"])

        def publish_worker(index: int, version_id: UUID, engine):
            barrier.wait()
            try:
                results[index] = publish(engine, version_id)
            except Exception as error:  # honest failure is acceptable, corruption is not
                results[index] = error

        threads = [threading.Thread(target=publish_worker, args=(0, versions[0], self.operator)),
                   threading.Thread(target=publish_worker, args=(1, versions[1], engine_b))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        engine_b.dispose()

        for index in (0, 1):
            self.assertNotIsInstance(results[index], Exception,
                                     f"worker {index} failed: {results[index]!r}")
        final = self.active_id()
        self.assertIn(final, versions)
        with self.admin.connect() as connection:
            statuses = dict(connection.execute(text("""
                SELECT id, status FROM app.dataset_versions WHERE dataset_key = :key
            """), {"key": self.key}).all())
        self.assertEqual(set(statuses.values()), {"approved"})
        self.assertEqual(len(statuses), 3)

    def test_07_history_is_immutable_and_role_scoped(self):
        result = self.stage_happy()
        version_id = result.dataset_version_id
        publish(self.operator, version_id)

        frozen = (
            ("UPDATE app.dataset_versions SET status = 'validated' WHERE id = :id",
             "status regression", "immutable"),
            ("UPDATE app.dataset_versions SET quality = '{}'::jsonb WHERE id = :id",
             "quality rewrite", "immutable"),
            # the column grant itself refuses identity rewrites before the trigger
            ("UPDATE app.dataset_versions SET content_sha256 = repeat('a', 64) WHERE id = :id",
             "hash rewrite", "permission denied"),
        )
        for statement, label, fragment in frozen:
            with self.subTest(label=label):
                with self.assertRaises(DBAPIError) as raised:
                    with self.operator.begin() as connection:
                        connection.execute(text(statement), {"id": version_id})
                self.assertIn(fragment, str(raised.exception.orig).lower())

        # no DELETE grant exists for scientific rows
        with self.assertRaises(DBAPIError) as raised:
            with self.operator.begin() as connection:
                connection.execute(text("DELETE FROM app.dataset_versions WHERE id = :id"),
                                   {"id": version_id})
        self.assertEqual(raised.exception.orig.sqlstate, "42501")

        # the runtime role can read but never write the scientific zone
        subject = uuid4()
        forbidden = (
            "INSERT INTO app.dataset_versions(id, dataset_key, version, start_date, end_date,"
            " frequency, pipeline_version, manifest_artifact_id, content_sha256)"
            " VALUES (gen_random_uuid(), 'evil.set', 1, '2026-01-01', '2026-01-02',"
            " 'daily', 'x', gen_random_uuid(), '" + "a" * 64 + "')",
            "INSERT INTO app.artifacts(id, relative_storage_key, sha256, byte_size, media_type)"
            " VALUES (gen_random_uuid(), 'blobs/aa/" + "b" * 62 + "', '" + "b" * 62 + "ab', 1,'x')",
            "INSERT INTO app.active_datasets(dataset_key, dataset_version_id)"
            " VALUES ('evil.set', gen_random_uuid())",
            "UPDATE app.metric_observations SET value = 0 WHERE dataset_version_id = gen_random_uuid()",
        )
        for statement in forbidden:
            with self.subTest(statement=statement[:50]):
                with self.assertRaises(DBAPIError) as raised:
                    with user_transaction(self.runtime, subject) as connection:
                        connection.execute(text(statement))
                self.assertEqual(raised.exception.orig.sqlstate, "42501")

        # a staged row must be driven through the whitelist: no validated -> staged
        document = self.happy_document(dataset_key=f"ni028-{uuid4().hex[:10]}")
        document["observations"] = document["observations"][:1]
        document["window"] = {"start": "2026-01-01", "end_exclusive": "2026-01-02"}
        staged = stage(self.operator, self.write_manifest("manifest-staged.json", document),
                       self.storage_root)
        self.assertEqual(staged.status, "validated")
        with self.assertRaises(DBAPIError) as raised:
            with self.operator.begin() as connection:
                connection.execute(text(
                    "UPDATE app.dataset_versions SET status = 'staged' WHERE id = :id"),
                    {"id": staged.dataset_version_id})
        self.assertIn("illegal", str(raised.exception.orig).lower())

    def test_08_stage_from_import_is_offline_and_deduplicates(self):
        records = daily_observations(FROM_IMPORT_METRIC, value_fn=lambda index: f"7.2{index}")
        root = self.directory / "handoff"
        root.mkdir()
        manifest_path = self._build_observations_archive(root, records)
        batch_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        registry_path = write_registry(self.directory, self._observations_registry())

        with redirect_stdout(io.StringIO()):
            code = archive.main(["--archive-root", str(root), "--manifest", str(manifest_path),
                                 "--cohorts", str(registry_path), "--database-url",
                                 os.environ["NI_TEST_OPERATOR_URL"]])
        self.assertEqual(code, archive.EXIT_OK)

        binding = {
            "schema_version": 1,
            "dataset_key": self.key,
            "frequency": "daily",
            "window": {"start": WINDOW[0], "end_exclusive": WINDOW[1]},
            "pipeline_version": "ni028-import-test",
            "code_commit": None, "config_hash": None, "dependency_lock_hash": None,
            "source_as_of": None, "retrieved_at": None,
            "quality": {"notes": "from synthetic archive"},
            "member_metrics": [str(FROM_IMPORT_METRIC)],
            "inputs": [{"kind": "imported", "batch_manifest_sha256": batch_sha,
                        "relative_path": "research/metrics-cohort/data/response.json",
                        "role": "normalized", "source_id": "SRC-EXAMPLE",
                        "query_hash": None, "license_status": None}],
            "aggregate_record_format": "observations_json",
        }
        binding_path = write_json(self.directory / "binding.json", binding)
        result = stage_from_import(self.operator, batch_sha, binding_path, self.storage_root)
        self.assertEqual(result.status, "validated")
        self.assertEqual(result.observation_count, DAILY_PERIODS)
        publish(self.operator, result.dataset_version_id)
        self.assertEqual(self.active_id(), result.dataset_version_id)

        with self.operator.connect() as connection:
            _assert_operator(connection)
            inputs = list_inputs(connection, result.dataset_version_id)
        self.assertEqual(inputs[0]["storage_key"].startswith("imported/"), True)
        self.assertEqual(inputs[0]["source_id"], "SRC-EXAMPLE")
        self.assertEqual(inputs[0]["role"], "normalized")

        again = stage_from_import(self.operator, batch_sha, binding_path, self.storage_root)
        self.assertTrue(again.deduplicated)
        self.assertEqual(again.dataset_version_id, result.dataset_version_id)

        # a changed archive file can never feed staging: bytes diverge from NI-027
        target = root / "research/metrics-cohort/data/response.json"
        target.write_text(target.read_text().replace("7.20", "9.99"))
        with self.assertRaises(DatasetVerificationError):
            stage_from_import(self.operator, batch_sha, binding_path, self.storage_root)

    def _observations_registry(self) -> dict:
        registry = json.loads(json.dumps(REGISTRY))
        registry["cohorts"] = {
            "metrics-cohort": {
                "window_start": WINDOW[0], "window_end_exclusive": WINDOW[1],
                "coverage_scope": "aggregate_window",
                "partial_audit": "Synthetic coverage note.",
                "license_status": "unverified", "sources": ["SRC-EXAMPLE"],
                "basis": "synthetic fixture",
            },
            # A second, manifest-less cohort keeps the common manifest prefix
            # at "research/" so the cohort directory survives classification.
            "notes-cohort": {
                "window_start": None, "window_end_exclusive": None,
                "coverage_scope": "point_in_time_snapshot",
                "partial_audit": "Synthetic manifest-less cohort.",
                "license_status": "unverified", "sources": ["SRC-EXAMPLE"],
                "basis": "synthetic fixture",
            },
        }
        return registry

    def _build_observations_archive(self, root: Path, records: list[dict]) -> Path:
        cohort = "metrics-cohort"
        response = (json.dumps({"observations": records}, indent=2, sort_keys=True)
                    + "\n").encode("utf-8")
        readme = b"Synthetic metrics cohort README.\n"
        cohort_manifest = {
            "window_utc_start": WINDOW[0],
            "window_utc_end_exclusive": WINDOW[1],
            # response.json is deliberately NOT documented as a saved HTTP
            # response, so the archive import classifies it as aggregate.
            "http_sources": {
                "README.md": {"url": "https://docs.example.test/synthetic",
                              "saved_at_utc": "2026-01-31T00:00:00Z", "http_status": 200},
            },
            "files": {
                "README.md": {"bytes": len(readme),
                              "sha256": hashlib.sha256(readme).hexdigest()},
                "data/response.json": {"bytes": len(response),
                                       "sha256": hashlib.sha256(response).hexdigest()},
            },
        }
        files = {
            f"research/{cohort}/README.md": readme,
            f"research/{cohort}/data/response.json": response,
            f"research/{cohort}/manifest.json": (
                json.dumps(cohort_manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            "research/notes-cohort/NOTES.md": b"Synthetic manifest-less notes cohort.\n",
        }
        for relative, data in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        lines = [f"{hashlib.sha256(data).hexdigest()}  {relative}"
                 for relative, data in sorted(files.items())]
        manifest_path = root.parent / "observations-manifest.sha256"
        manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return manifest_path

    def test_09_query_api_surfaces_history_hashes_and_pages(self):
        first = self.stage_happy()
        publish(self.operator, first.dataset_version_id)
        document = self.happy_document()
        document["observations"][2]["value"] = "42.0"
        second = stage(self.operator, self.write_manifest("manifest-v2.json", document),
                       self.storage_root)

        with self.operator.connect() as connection:
            _assert_operator(connection)
            history = version_history(connection, self.key)
            active = active_version(connection, self.key)
            page = list_observations(connection, second.dataset_version_id, limit=10, offset=5)
            inputs = list_inputs(connection, second.dataset_version_id)
            missing = get_version(connection, uuid4())
        self.assertEqual([row["version"] for row in history], [1, 2])
        self.assertEqual(history[0]["content_sha256"], first.content_sha256)
        # only the published version is active; the staged one is history-in-waiting
        self.assertEqual(active["id"], str(first.dataset_version_id))
        self.assertEqual(active["status"], "approved")
        self.assertEqual((page["total"], len(page["items"])), (DAILY_PERIODS, 10))
        self.assertEqual(inputs[0]["role"], "config")
        self.assertTrue(inputs[0]["storage_key"].startswith("blobs/"))
        self.assertIsNone(missing)

    def test_10_migration_round_trip_and_metadata_drift(self):
        command.downgrade(self.config, "0003_archive_import")
        with self.admin.connect() as connection:
            for table in DATASET_TABLES:
                self.assertIsNone(connection.scalar(text(
                    f"SELECT to_regclass('app.{table}')")))
        command.upgrade(self.config, "head")
        command.check(self.config)
        with self.admin.connect() as connection:
            rows = connection.execute(text("""
                SELECT relname, relrowsecurity, relforcerowsecurity, pg_get_userbyid(relowner)
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'app'
                  AND relname IN ('artifacts','dataset_versions','dataset_metrics',
                                  'dataset_inputs','metric_observations','active_datasets')
            """)).all()
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(row[1:] == (True, True, "near_migrator") for row in rows))


if __name__ == "__main__":
    unittest.main()
