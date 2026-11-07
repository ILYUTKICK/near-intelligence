"""One bounded scheduled finalized-header refresh adapter (NI-030).

Implements the operator-approved (OQ-03 RESOLVED, docs/OPEN_QUESTIONS.md)
refresh of the public NEAR mainnet finalized chain head:

- exactly ONE JSON-RPC ``block`` request with ``finality: "final"`` per
  invocation against the endpoint recorded in the database source registry
  (``app.sources``) — never in code — for a source whose ``access_status`` is
  ``approved``; budget 0, no account, no key, no credential;
- persistent budgets (OQ-03: 1 request/minute, <=1440 requests/day) enforced
  BEFORE any network I/O from database state (``app.ingestion_checkpoints`` /
  ``app.ingestion_daily_counters``), so process restarts cannot reset them;
- a persisted block-height checkpoint: a refresh resumes from the last
  committed finalized height (never from zero), a lower advertised height is a
  regression failure and an unchanged height publishes nothing;
- validation (monotonic height, base58 block hash, digit-string timestamp and
  total supply, 65536-byte response cap, identity encoding) before any write;
- stage + publish of dataset ``near-finalized-headers`` through the NI-028
  immutable dataset pipeline in ONE transaction that also advances the
  checkpoint and counters — any failure leaves the previous approved version
  as the active "last good" pointer;
- honest failure reporting: a 429/auth failure/outage is recorded on the
  checkpoint row (``last_failure_at``/``last_failure_kind``/
  ``consecutive_failures``) and the last good data is retained. There is no
  retry: one attempt per invocation, the host scheduler decides the next run.

This is NOT the single-use NI-026 probe (``capabilities.probe``); it is the
scheduled adapter, but it reuses the probe's sanitized ``FinalizedHeader``
model so both paths publish the identical sanitized field set. The adapter is
invoked only through the explicit operator CLI
(``python -m near_api.ingestion.refresh --once``); no application startup path
imports or runs it, and legacy collectors stay stopped
(``STOP_PUBLIC_COLLECTION`` markers are honored here exactly as in the probe).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import SQLAlchemyError

from near_api.datasets.canonical import (
    CanonicalFormatError,
    canonical_timestamp,
    decimal_string,
    load_json_strict,
    sha256_hex,
)
from near_api.datasets.manifest import ManifestFormatError, parse_manifest_document
from near_api.datasets.service import (
    DatasetContractError,
    DatasetLookupError,
    DatasetVerificationError,
    PublishRefused,
    _assert_operator,
    _load_version,
    _lock_dataset_key,
    _publish_locked,
    _stage_locked,
    content_digest,
    resolve_inputs,
)
from near_api.datasets.storage import ArtifactStorage, StorageError
from near_api.ingestion.archive import OperatorDatabaseError
from near_api.ingestion.capabilities.probe import FinalizedHeader
from near_api.metrics.registry import definition_by_metric_id

# The adapter carries source *identifiers* only; the approved endpoint lives in
# the app.sources registry row and the budgets in the recorded OQ-03 approval.
SOURCE_ID = "SRC-NEAR-RPC"
DATASET_KEY = "near-finalized-headers"
SUPPLY_METRIC_ID = "total_supply_near"
PIPELINE_VERSION = "ni030-refresh-v1"

# OQ-03 operator approval (2026-11-06): 1 request/minute, <=1440/day, budget 0.
REQUESTS_PER_MINUTE = 1
MIN_REQUEST_INTERVAL = dt.timedelta(seconds=60)
MAX_REQUESTS_PER_DAY = 1440
# Header-only responses with the probe's implemented byte cap (OQ-03).
MAX_RESPONSE_BYTES = 65_536
REQUEST_TIMEOUT_SECONDS = 10
JSON_RPC_ID = "ni-030"

# Session-level advisory lock class for refresh runs ('NR'); distinct from the
# dataset staging/publication lock class so both can be held together.
REFRESH_LOCK_NAMESPACE = 20040

REQUEST_BODY: dict[str, Any] = {
    "jsonrpc": "2.0", "id": JSON_RPC_ID, "method": "block",
    "params": {"finality": "final"},
}


class RefreshRefused(RuntimeError):
    """The run was refused BEFORE any network request (CLI exit 3)."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


class RefreshFailed(RuntimeError):
    """A request was made or validation failed; last good is retained (CLI exit 4)."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class RefreshOutcome:
    """Result of one ``--once`` run; serialized as the CLI JSON report."""

    status: str  # "published" | "unchanged"
    source_id: str
    dataset_key: str
    height: int
    block_hash: str
    block_timestamp_utc: str
    checkpoint_height_before: int | None
    dataset_version_id: str | None = None
    version: int | None = None
    content_sha256: str | None = None
    superseded_version_id: str | None = None
    request_count_today: int | None = None

    def report(self) -> dict:
        return dict(self.__dict__)


def exact_supply_near(total_supply_yocto: str) -> str:
    """Exact yoctoNEAR -> NEAR rendering (a power-of-ten division never rounds).

    Runs in a local context with at least the value's own digit count, exactly
    like ``datasets.canonical.decimal_string``: the ambient default precision
    (28) would silently round supplies of 29+ significant digits.
    """
    value = Decimal(total_supply_yocto)
    with localcontext() as context:
        context.prec = max(len(value.as_tuple().digits), context.prec)
        return decimal_string(context.divide(value, Decimal(10) ** 24))


def evaluate_budget(*, last_request_at: dt.datetime | None, requests_used_today: int,
                    now: dt.datetime) -> str | None:
    """Pure OQ-03 budget decision: a refusal kind, or None if a request may go out."""
    if last_request_at is not None and now - last_request_at < MIN_REQUEST_INTERVAL:
        return "minute_budget_exhausted"
    if requests_used_today >= MAX_REQUESTS_PER_DAY:
        return "daily_budget_exhausted"
    return None


def validate_header_response(raw: bytes, *, retrieved_at: dt.datetime) -> dict:
    """Strict parse + sanitization of one finalized-header JSON-RPC response.

    Returns the sanitized ``FinalizedHeader`` model dump. Every structural or
    schema deviation is one ``schema_invalid`` failure; provider payloads are
    never surfaced beyond the sanitized fields.
    """
    try:
        data = load_json_strict(raw, context="finalized header response")
        if not isinstance(data, dict):
            raise CanonicalFormatError("finalized header response: expected a JSON object")
    except CanonicalFormatError:
        raise RefreshFailed("schema_invalid",
                            "Finalized header response is not strict JSON") from None
    if data.get("jsonrpc") != "2.0" or data.get("id") != JSON_RPC_ID or "error" in data:
        raise RefreshFailed("schema_invalid", "Invalid JSON-RPC response envelope")
    header = data.get("result")
    if not isinstance(header, dict) or not isinstance(header.get("header"), dict):
        raise RefreshFailed("schema_invalid", "Response has no result.header object")
    try:
        sanitized = FinalizedHeader(
            height=header["header"].get("height"),
            block_hash=header["header"].get("hash"),
            timestamp_nanosec=header["header"].get("timestamp_nanosec"),
            total_supply_yocto=header["header"].get("total_supply"),
            retrieved_at=retrieved_at, response_bytes=len(raw),
            response_sha256=hashlib.sha256(raw).hexdigest(),
        )
    except Exception:
        raise RefreshFailed(
            "schema_invalid",
            "Finalized header response does not match the approved sanitized schema",
        ) from None
    return sanitized.model_dump()


class FinalizedHeaderRefresh:
    """Single-shot operator refresh: guard -> one request -> validate -> publish."""

    def __init__(self, engine: Engine, storage_root: Path, repo_root: Path, *,
                 source_id: str = SOURCE_ID, stop_paths: tuple[Path, ...] = ()):
        self.engine = engine
        self.storage_root = Path(storage_root).resolve()
        self.repo_root = Path(repo_root).resolve()
        self.source_id = source_id
        self.stop_paths = tuple(stop_paths)
        self._storage_instance: ArtifactStorage | None = None

    # -- guards (before any network I/O) ------------------------------------ #

    def _check_stop_markers(self) -> None:
        if not self.repo_root.is_dir():
            raise RefreshRefused("repo_root_unavailable",
                                 "Repository root is unavailable for stop-marker checks")
        markers = (
            self.repo_root / "STOP_PUBLIC_COLLECTION",
            *self.repo_root.glob("research/**/STOP_PUBLIC_COLLECTION"),
            *self.stop_paths,
        )
        if any(path.exists() for path in markers):
            raise RefreshRefused(
                "stop_marker_present",
                "Collection stop or pause marker is present; legacy collectors and "
                "new adapters stay stopped")

    def _approved_endpoint(self, connection: Connection) -> str:
        """Read the approved endpoint from the DB registry (never from code)."""
        row = connection.execute(text(
            "SELECT access_status, base_url FROM app.sources WHERE id = :id"),
            {"id": self.source_id}).mappings().first()
        if row is None:
            raise RefreshRefused(
                "source_not_approved",
                f"Source {self.source_id} is absent from the database source registry")
        if row["access_status"] != "approved":
            raise RefreshRefused(
                "source_not_approved",
                f"Source {self.source_id} access_status is {row['access_status']!r}; "
                "the effective allowlist is operator-managed in the database and "
                "starts empty")
        endpoint = row["base_url"]
        if not isinstance(endpoint, str) or not endpoint:
            raise RefreshRefused(
                "source_not_approved",
                f"Source {self.source_id} has no recorded base_url endpoint")
        parts = urlsplit(endpoint)
        if (parts.scheme != "https" or not parts.hostname or parts.username
                or parts.password or parts.query or parts.fragment):
            raise RefreshRefused(
                "source_not_approved",
                f"Source {self.source_id} endpoint is not a clean public HTTPS URL")
        return endpoint

    @staticmethod
    def _utc_day(now: dt.datetime) -> dt.date:
        return now.astimezone(dt.timezone.utc).date()

    # -- one network request ------------------------------------------------- #

    def _fetch(self, endpoint: str, *,
               transport: httpx.BaseTransport | None) -> bytes:
        # httpx can raise while closing a stream (for example a DecodingError on
        # a response that ignores Accept-Encoding: identity), which would mask a
        # pending failure. Failures are therefore recorded FIRST, the stream
        # context is always exited normally, and the recorded failure is raised
        # afterwards with its precise kind.
        failure: RefreshFailed | None = None
        raw = bytearray()

        def consume(response: httpx.Response) -> None:
            nonlocal failure
            if response.status_code != 200:
                failure = RefreshFailed(
                    f"http_{response.status_code}",
                    f"Refresh HTTP status {response.status_code}; no retry, "
                    "last good retained")
                return
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                failure = RefreshFailed("encoded_response",
                                        "Encoded refresh responses are not accepted")
                return
            for chunk in response.iter_bytes(chunk_size=65_536):
                if len(raw) + len(chunk) > MAX_RESPONSE_BYTES:
                    failure = RefreshFailed(
                        "response_too_large",
                        f"Refresh response exceeds the {MAX_RESPONSE_BYTES} byte "
                        "approved cap")
                    return
                raw.extend(chunk)

        try:
            with httpx.Client(transport=transport, timeout=REQUEST_TIMEOUT_SECONDS,
                              follow_redirects=False, trust_env=False) as client:
                with client.stream("POST", endpoint, json=REQUEST_BODY,
                                   headers={"Accept-Encoding": "identity"}) as response:
                    consume(response)
        except Exception as error:
            if failure is not None:
                raise failure from None
            # Provider exceptions can embed response bodies; never surface them.
            raise RefreshFailed(
                "transport_error",
                f"Refresh transport failed ({type(error).__name__}); no retry, "
                "last good retained") from None
        if failure is not None:
            raise failure
        return bytes(raw)

    # -- database state ------------------------------------------------------ #

    def _read_state(self, connection: Connection, today: dt.date) -> dict:
        checkpoint = connection.execute(text("""
            SELECT last_height, last_block_hash, last_request_at, last_success_at,
                   last_failure_at, last_failure_kind, consecutive_failures
            FROM app.ingestion_checkpoints WHERE source_id = :id
        """), {"id": self.source_id}).mappings().first()
        counter = connection.execute(text("""
            SELECT request_count FROM app.ingestion_daily_counters
            WHERE source_id = :id AND day = :day
        """), {"id": self.source_id, "day": today}).mappings().first()
        return {
            "checkpoint": dict(checkpoint) if checkpoint is not None else None,
            "requests_used_today": counter["request_count"] if counter is not None else 0,
        }

    def _record_success(self, connection: Connection, *, header: dict, now: dt.datetime,
                        day: dt.date) -> int:
        """Advance counters + checkpoint IN the publish transaction (atomic)."""
        connection.execute(text("""
            INSERT INTO app.ingestion_daily_counters(source_id, day, request_count, success_count)
            VALUES (:id, :day, 1, 1)
            ON CONFLICT (source_id, day) DO UPDATE SET
                request_count = app.ingestion_daily_counters.request_count + 1,
                success_count = app.ingestion_daily_counters.success_count + 1,
                updated_at = now()
        """), {"id": self.source_id, "day": day})
        connection.execute(text("""
            INSERT INTO app.ingestion_checkpoints(source_id, last_height, last_block_hash,
                last_header_at, last_request_at, last_success_at, consecutive_failures)
            VALUES (:id, :height, :hash, :header_at, :now, :now, 0)
            ON CONFLICT (source_id) DO UPDATE SET
                last_height = EXCLUDED.last_height,
                last_block_hash = EXCLUDED.last_block_hash,
                last_header_at = EXCLUDED.last_header_at,
                last_request_at = EXCLUDED.last_request_at,
                last_success_at = EXCLUDED.last_success_at,
                last_failure_at = NULL,
                last_failure_kind = NULL,
                consecutive_failures = 0,
                updated_at = now()
        """), {"id": self.source_id, "height": header["height"],
               "hash": header["block_hash"],
               "header_at": _ns_to_datetime(header["timestamp_nanosec"]), "now": now})
        return connection.execute(text("""
            SELECT request_count FROM app.ingestion_daily_counters
            WHERE source_id = :id AND day = :day
        """), {"id": self.source_id, "day": day}).scalar_one()

    def _record_failure(self, connection: Connection, *, kind: str,
                        now: dt.datetime, request_made: bool, day: dt.date) -> None:
        """Best-effort honest failure record; never masks the original error."""
        try:
            with connection.begin():
                if request_made:
                    connection.execute(text("""
                        INSERT INTO app.ingestion_daily_counters(source_id, day, request_count)
                        VALUES (:id, :day, 1)
                        ON CONFLICT (source_id, day) DO UPDATE SET
                            request_count = app.ingestion_daily_counters.request_count + 1,
                            updated_at = now()
                    """), {"id": self.source_id, "day": day})
                connection.execute(text("""
                    INSERT INTO app.ingestion_checkpoints(source_id, last_request_at,
                        last_failure_at, last_failure_kind, consecutive_failures)
                    VALUES (:id, :request_at, :now, :kind, 1)
                    ON CONFLICT (source_id) DO UPDATE SET
                        last_request_at = COALESCE(EXCLUDED.last_request_at,
                            app.ingestion_checkpoints.last_request_at),
                        last_failure_at = EXCLUDED.last_failure_at,
                        last_failure_kind = EXCLUDED.last_failure_kind,
                        consecutive_failures = app.ingestion_checkpoints.consecutive_failures + 1,
                        updated_at = now()
                """), {"id": self.source_id,
                       "request_at": now if request_made else None,
                       "now": now, "kind": kind})
        except Exception:
            pass

    # -- dataset publication (NI-028 pipeline) ------------------------------- #

    def _storage(self) -> ArtifactStorage:
        if self._storage_instance is None:
            self._storage_instance = ArtifactStorage(self.storage_root)
        return self._storage_instance

    def _manifest_document(self, header: dict, *, endpoint: str, raw_path: Path,
                           query_hash: str, now: dt.datetime) -> dict:
        header_day = _ns_to_datetime(header["timestamp_nanosec"]).date()
        next_day = header_day + dt.timedelta(days=1)
        supply_definition = definition_by_metric_id(SUPPLY_METRIC_ID)
        return {
            "schema_version": 1,
            "dataset_key": DATASET_KEY,
            "frequency": "snapshot",
            "window": {"start": header_day.isoformat(), "end_exclusive": next_day.isoformat()},
            "pipeline_version": PIPELINE_VERSION,
            "code_commit": None,
            "config_hash": None,
            "dependency_lock_hash": None,
            "source_as_of": canonical_timestamp(_ns_to_datetime(header["timestamp_nanosec"])),
            "retrieved_at": canonical_timestamp(now),
            "quality": {
                "adapter": "near_api.ingestion.providers.finalized_header",
                "pipeline_version": PIPELINE_VERSION,
                "source_id": self.source_id,
                "endpoint": endpoint,
                "finality": "final",
                "response_sha256": header["response_sha256"],
                "response_bytes": header["response_bytes"],
                "budget": {"requests_per_minute": REQUESTS_PER_MINUTE,
                           "max_requests_per_day": MAX_REQUESTS_PER_DAY},
                "input_license": "raw on-chain header data is public (OQ-03 approval)",
            },
            "member_metrics": [str(supply_definition.id)],
            "inputs": [{"kind": "file", "path": str(raw_path), "role": "raw",
                        "source_id": self.source_id, "query_hash": query_hash,
                        "license_status": "verified"}],
            "observations": [{
                "metric_definition_id": str(supply_definition.id),
                "period_start": f"{header_day.isoformat()}T00:00:00Z",
                "period_end": f"{next_day.isoformat()}T00:00:00Z",
                "dimensions": {},
                "value": exact_supply_near(header["total_supply_yocto"]),
                "quality_status": "verified",
                "bound_kind": "exact",
                "source_record_ref": f"block {header['height']} {header['block_hash']}",
                "quality": {
                    "block_height": header["height"],
                    "block_hash": header["block_hash"],
                    "block_timestamp_utc": canonical_timestamp(
                        _ns_to_datetime(header["timestamp_nanosec"])),
                    "timestamp_ns": header["timestamp_nanosec"],
                    "source_id": self.source_id,
                    "finality": "final",
                    "kind": "stock at the finalized chain head",
                },
            }],
        }

    def _write_raw_file(self, header: dict, raw: bytes) -> Path:
        """Persist the raw response bytes before any database write (stage-2 Preserve)."""
        directory = self.storage_root / "raw"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (
            f"finalized-header-{header['height']}-{header['response_sha256'][:16]}.json")
        path.write_bytes(raw)
        return path

    def _publish(self, connection: Connection, header: dict, *, endpoint: str,
                 raw_path: Path, query_hash: str, now: dt.datetime) -> dict:
        """Stage (+ publish) in the caller's transaction; returns the outcome parts."""
        document = self._manifest_document(header, endpoint=endpoint, raw_path=raw_path,
                                           query_hash=query_hash, now=now)
        try:
            manifest = parse_manifest_document(document, context="ni-030 refresh manifest")
        except ManifestFormatError as error:
            raise DatasetVerificationError(
                f"Adapter emitted an invalid manifest (adapter bug): {error}") from None
        storage = self._storage()
        # File inputs only: input bytes hit storage before any database write
        # (the same durability rule as the NI-028 stage()).
        resolved = resolve_inputs(connection, manifest, storage)
        manifest_bytes, digest = content_digest(manifest, resolved)
        manifest_key = storage.store("manifests", digest, manifest_bytes, suffix=".json")
        _lock_dataset_key(connection, DATASET_KEY)
        staged = _stage_locked(connection, manifest, resolved, manifest_key, digest,
                               manifest_bytes)
        version = _load_version(connection, staged.dataset_version_id)
        if staged.status == "validated":
            return {"outcome_status": "published", "staged": staged,
                    "report": _publish_locked(connection, version)}
        if staged.status == "approved":
            # Identical semantic content already exists as an approved version
            # (possible only after an operator checkpoint reset). Publishing it
            # again either confirms the active pointer (already_active) or is a
            # refused backwards move; either way no new version is created.
            return {"outcome_status": "unchanged", "staged": staged,
                    "report": _publish_locked(connection, version)}
        raise DatasetVerificationError(
            "Refreshed dataset version failed validation and was committed as "
            "rejected; the previous approved version stays active")

    # -- the single-shot run -------------------------------------------------- #

    def run_once(self, *, transport: httpx.BaseTransport | None = None,
                 now: dt.datetime | None = None) -> dict:
        """One guarded refresh attempt. Never retries; one request at most."""
        if now is None:
            now = dt.datetime.now(dt.timezone.utc)
        day = self._utc_day(now)
        with self.engine.connect() as lock_connection:
            with lock_connection.begin():
                acquired = lock_connection.execute(text(
                    "SELECT pg_try_advisory_lock(:namespace, hashtext(:key))"),
                    {"namespace": REFRESH_LOCK_NAMESPACE, "key": self.source_id},
                ).scalar_one()
            if not acquired:
                raise RefreshRefused(
                    "overlap_lock_held",
                    "Another refresh for this source holds the scheduler lock; "
                    "no overlap is permitted")
            try:
                return self._run_locked(lock_connection, transport=transport, now=now,
                                        day=day)
            finally:
                with lock_connection.begin():
                    lock_connection.execute(text(
                        "SELECT pg_advisory_unlock(:namespace, hashtext(:key))"),
                        {"namespace": REFRESH_LOCK_NAMESPACE, "key": self.source_id})

    def _run_locked(self, connection: Connection, *,
                    transport: httpx.BaseTransport | None, now: dt.datetime,
                    day: dt.date) -> dict:
        self._check_stop_markers()
        try:
            with connection.begin():
                # The begin() block owns the transaction; the helpers run on
                # the connection itself (SQLAlchemy 2.x: no proxy execute).
                _assert_operator(connection)
                endpoint = self._approved_endpoint(connection)
                state = self._read_state(connection, day)
            refusal = evaluate_budget(
                last_request_at=state["checkpoint"]["last_request_at"]
                if state["checkpoint"] is not None else None,
                requests_used_today=state["requests_used_today"], now=now)
            if refusal is not None:
                raise RefreshRefused(
                    refusal,
                    f"OQ-03 budget refused the request before any network I/O ({refusal})")
        except RefreshRefused:
            raise
        except (SQLAlchemyError, OperatorDatabaseError) as error:
            raise RefreshFailed("database_error",
                                f"Guard state could not be read: {type(error).__name__}"
                                ) from None

        try:
            raw = self._fetch(endpoint, transport=transport)
            header = validate_header_response(raw, retrieved_at=now)
        except RefreshFailed as failure:
            # The request was sent: the attempt is honestly consumed even when
            # the provider answered with a failure.
            self._record_failure(connection, kind=failure.kind, now=now,
                                 request_made=True, day=day)
            raise
        checkpoint_before = (state["checkpoint"] or {}).get("last_height")
        try:
            with connection.begin():
                last_height = (state["checkpoint"] or {}).get("last_height")
                if last_height is not None and header["height"] < last_height:
                    raise RefreshFailed(
                        "height_regression",
                        f"Advertised finalized height {header['height']} is below the "
                        f"checkpointed height {last_height}; refusing to publish")
                if last_height is not None and header["height"] == last_height:
                    request_count = self._record_success(connection, header=header,
                                                         now=now, day=day)
                    return RefreshOutcome(
                        status="unchanged", source_id=self.source_id,
                        dataset_key=DATASET_KEY, height=header["height"],
                        block_hash=header["block_hash"],
                        block_timestamp_utc=canonical_timestamp(
                            _ns_to_datetime(header["timestamp_nanosec"])),
                        checkpoint_height_before=last_height,
                        request_count_today=request_count).report()
                raw_path = self._write_raw_file(header, raw)
                query_hash = sha256_hex(_canonical_request_bytes())
                published = self._publish(connection, header, endpoint=endpoint,
                                          raw_path=raw_path, query_hash=query_hash,
                                          now=now)
                request_count = self._record_success(connection, header=header, now=now,
                                                     day=day)
                staged, report = published["staged"], published["report"]
                return RefreshOutcome(
                    status=published["outcome_status"], source_id=self.source_id,
                    dataset_key=DATASET_KEY, height=header["height"],
                    block_hash=header["block_hash"],
                    block_timestamp_utc=canonical_timestamp(
                        _ns_to_datetime(header["timestamp_nanosec"])),
                    checkpoint_height_before=checkpoint_before,
                    dataset_version_id=report["dataset_version_id"],
                    version=staged.version,
                    content_sha256=report["content_sha256"],
                    superseded_version_id=report.get("previous_version_id"),
                    request_count_today=request_count).report()
        except RefreshFailed as failure:
            self._record_failure(connection, kind=failure.kind, now=now,
                                 request_made=True, day=day)
            raise
        except (DatasetVerificationError, DatasetContractError, PublishRefused,
                DatasetLookupError, StorageError, ManifestFormatError) as error:
            self._record_failure(connection, kind="dataset_publish_error", now=now,
                                 request_made=True, day=day)
            raise RefreshFailed("dataset_publish_error",
                                f"Dataset publication failed: {type(error).__name__}"
                                ) from None
        except SQLAlchemyError:
            self._record_failure(connection, kind="database_error", now=now,
                                 request_made=True, day=day)
            raise RefreshFailed("database_error",
                                "Publish transaction failed; last good retained") from None


def _canonical_request_bytes() -> bytes:
    return json.dumps(REQUEST_BODY, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _ns_to_datetime(timestamp_nanosec: str) -> dt.datetime:
    seconds, remainder = divmod(int(timestamp_nanosec), 1_000_000_000)
    return dt.datetime.fromtimestamp(seconds, tz=dt.timezone.utc).replace(
        microsecond=remainder // 1_000)
