"""Transactional dataset staging, validation and publication (NI-028).

All dataset writes run as the unprivileged ``near_operator`` role (the same
boundary as the NI-027 archive import) and serialize per dataset key on
transaction-level PostgreSQL advisory locks.  The invariants:

- **Staging** (``stage``) resolves input artifacts (copying file bytes into
  content-addressed storage before the transaction, verifying imported archive
  bytes against their NI-027 ``imported_files`` digests), assembles the
  canonical manifest, computes the ``content_sha256`` digest and persists the
  version, its member metrics, inputs and observations in ONE transaction
  together with validation: the committed status is ``validated`` or
  ``rejected``, never silently ``staged``.  A contract or verification failure
  aborts the whole transaction and leaves zero rows.
- **Deduplication**: ``UNIQUE(dataset_key, content_sha256)`` plus an explicit
  digest lookup under the advisory lock make identical semantic input resolve
  to the existing version without any write.
- **Validation** (``validate``) re-derives the canonical manifest from the
  persisted rows and compares digests, then checks membership (every
  observation references a member metric and every member has observations),
  window containment, frequency-grid alignment and period coverage.  A failed
  validation commits the version as ``rejected`` with a bounded report in the
  row quality metadata and never touches the active pointer.
- **Publication** (``publish``) is a single transaction: advisory lock,
  digest re-verification, status guard ``validated -> approved``, revision
  delta against the currently active version, then the ``active_datasets``
  pointer switch (a trigger requires an approved version of the same key).
  Any failure rolls back and the previous pointer and its approved version are
  retained untouched.  Approved history is immutable (trigger-frozen rows and
  no UPDATE/DELETE grants), so old versions and hashes stay queryable forever.
"""

from __future__ import annotations

import calendar
import datetime as dt
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, text
from sqlalchemy import event as sa_event

from near_api.datasets.canonical import (
    canonical_timestamp,
    canonical_value,
    decimal_string,
    load_json_strict,
    sha256_hex,
)
from near_api.datasets.manifest import (
    MAX_INPUT_FILE_BYTES,
    InputBinding,
    Observation,
    PreparedManifest,
    ROLE_MEDIA_TYPES,
    content_digest,
    load_manifest,
)
from near_api.datasets.storage import ArtifactStorage
# The operator boundary is shared with the NI-027 archive import on purpose:
# one definition of "what may write the scientific data zone".
from near_api.ingestion.archive import _assert_operator, create_operator_engine

ADVISORY_LOCK_NAMESPACE = 20036  # dataset staging/publication lock class ('ND')

MAX_REPORT_ENTRIES = 20
MAX_QUERY_PAGE = 1000

# Imported archive files may only feed dataset input roles whose provenance
# they can honestly represent (NI-027 file_role -> dataset_inputs.role).
IMPORTED_FILE_ROLE_COMPATIBILITY = {
    "raw": {"raw"},
    "aggregate": {"normalized", "price"},
    "script": {"sql", "config"},
    "provenance": {"sql", "config"},
}


class DatasetContractError(ValueError):
    """Operator input violates the manifest/binding contract (CLI exit 4)."""


class DatasetVerificationError(RuntimeError):
    """Stored or on-disk data diverges from its recorded identity (CLI exit 3)."""


class DatasetLookupError(LookupError):
    """The requested dataset version or key does not exist (CLI exit 3)."""


class PublishRefused(DatasetVerificationError):
    """Publication was refused by a status/consistency gate (CLI exit 3)."""


@dataclass(frozen=True)
class ResolvedInput:
    """One input artifact ready to be referenced by a dataset version."""

    storage_key: str
    sha256: str
    byte_size: int
    media_type: str
    role: str
    source_id: str | None
    query_hash: str | None
    license_status: str


@dataclass(frozen=True)
class ImportedFileFact:
    """NI-027 import metadata for one archive file feeding a dataset input."""

    batch_id: UUID
    archive_root: str
    sha256: str
    byte_size: int
    file_role: str
    coverage_start: dt.date | None
    coverage_end_exclusive: dt.date | None
    source_id: str | None
    license_status: str


@dataclass(frozen=True)
class StagedVersion:
    dataset_version_id: UUID
    dataset_key: str
    version: int
    content_sha256: str
    status: str
    deduplicated: bool
    observation_count: int
    input_count: int
    validation: dict | None


def create_dataset_operator_engine(database_url: str) -> Engine:
    """Operator engine with exact JSONB decoding (Decimal, no float drift)."""
    engine = create_operator_engine(database_url)

    @sa_event.listens_for(engine, "connect")
    def _configure_json(dbapi_connection, connection_record):
        from psycopg.types.json import set_json_loads

        set_json_loads(lambda raw: load_json_strict(raw, context="stored jsonb"),
                       dbapi_connection)

    return engine


def _lock_dataset_key(connection: Connection, dataset_key: str) -> None:
    """Serialize staging/publication per dataset key for this transaction."""
    connection.execute(text("SELECT pg_advisory_xact_lock(:namespace, hashtext(:key))"),
                       {"namespace": ADVISORY_LOCK_NAMESPACE, "key": dataset_key})


def _dumps_canonical(value) -> str:
    """Deterministic JSONB text: decimals become their canonical strings first."""
    return json.dumps(canonical_value(value, context="jsonb payload"), ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"))


# --------------------------------------------------------------------------- #
# Input resolution (byte writes happen before the staging transaction opens)
# --------------------------------------------------------------------------- #


def _read_file_input(binding: InputBinding, storage: ArtifactStorage) -> ResolvedInput:
    try:
        data = binding.path.read_bytes()
    except OSError as error:
        raise DatasetContractError(f"Cannot read input file {binding.path}: {error}") from None
    if len(data) > MAX_INPUT_FILE_BYTES:
        raise DatasetContractError(
            f"Input file {binding.path} exceeds the {MAX_INPUT_FILE_BYTES} byte limit")
    digest = sha256_hex(data)
    key = storage.store("blobs", digest, data)
    return ResolvedInput(storage_key=key, sha256=digest, byte_size=len(data),
                         media_type=ROLE_MEDIA_TYPES[binding.role], role=binding.role,
                         source_id=binding.source_id, query_hash=binding.query_hash,
                         license_status=binding.license_status)


def lookup_imported_file(connection: Connection, batch_manifest_sha256: str,
                         relative_path: str) -> ImportedFileFact:
    row = connection.execute(text("""
        SELECT b.id AS batch_id, b.archive_root, f.sha256, f.byte_size, f.file_role,
               f.coverage_start, f.coverage_end_exclusive, f.source_id, f.license_status
        FROM app.import_batches b
        JOIN app.imported_files f ON f.batch_id = b.id
        WHERE b.manifest_sha256 = :batch AND f.relative_path = :path
    """), {"batch": batch_manifest_sha256, "path": relative_path}).mappings().first()
    if row is None:
        raise DatasetVerificationError(
            f"Import batch {batch_manifest_sha256} has no imported file {relative_path!r}; "
            "run the NI-027 archive import first")
    return ImportedFileFact(
        batch_id=row["batch_id"], archive_root=row["archive_root"], sha256=row["sha256"],
        byte_size=row["byte_size"], file_role=row["file_role"],
        coverage_start=row["coverage_start"],
        coverage_end_exclusive=row["coverage_end_exclusive"], source_id=row["source_id"],
        license_status=row["license_status"])


def read_imported_bytes(fact: ImportedFileFact, relative_path: str) -> bytes:
    """Read imported archive bytes from disk and re-verify the NI-027 digest."""
    root = Path(fact.archive_root)
    if not root.is_dir():
        raise DatasetVerificationError(
            f"Archive root {fact.archive_root!r} recorded by the import batch is not "
            "available on this machine; request an authorized data handoff")
    candidate = root / relative_path
    try:
        resolved = candidate.resolve()
        inside = resolved.is_relative_to(root.resolve())
    except OSError:
        inside = False
    if (not inside or candidate.is_symlink() or not candidate.is_file()):
        raise DatasetVerificationError(
            f"Imported file {relative_path!r} is missing, symlinked or escaped the "
            "archive root; refusing to stage from changed bytes")
    try:
        data = candidate.read_bytes()
    except OSError as error:
        raise DatasetVerificationError(
            f"Cannot read imported file {relative_path!r}: {error}") from None
    if sha256_hex(data) != fact.sha256 or len(data) != fact.byte_size:
        raise DatasetVerificationError(
            f"Imported file {relative_path!r} diverges from its verified NI-027 digest; "
            "the archive changed after import")
    return data


def _resolve_imported_input(connection: Connection, binding: InputBinding, *,
                            require_file_role: bool) -> tuple[ResolvedInput, ImportedFileFact]:
    fact = lookup_imported_file(connection, binding.batch_manifest_sha256,
                                binding.relative_path)
    if require_file_role and binding.role not in IMPORTED_FILE_ROLE_COMPATIBILITY.get(
            fact.file_role, set()):
        raise DatasetContractError(
            f"Imported file {binding.relative_path!r} has file_role {fact.file_role!r}, "
            f"which cannot honestly feed dataset input role {binding.role!r}")
    source_id = binding.source_id
    if source_id is None:
        source_id = fact.source_id
    elif fact.source_id is not None and fact.source_id != source_id:
        raise DatasetContractError(
            f"Input source_id {source_id!r} contradicts the imported metadata "
            f"{fact.source_id!r} for {binding.relative_path!r}")
    resolved = ResolvedInput(
        storage_key=f"imported/{fact.batch_id}/{fact.sha256}",
        sha256=fact.sha256, byte_size=fact.byte_size,
        media_type=ROLE_MEDIA_TYPES[binding.role], role=binding.role,
        source_id=source_id, query_hash=binding.query_hash,
        license_status=fact.license_status)
    return resolved, fact


def resolve_inputs(connection: Connection, manifest: PreparedManifest,
                   storage: ArtifactStorage) -> list[ResolvedInput]:
    """Resolve every declared input; file bytes hit storage before the transaction."""
    resolved: list[ResolvedInput] = []
    seen: set[tuple[str, str]] = set()
    for index, binding in enumerate(manifest.inputs):
        context = f"inputs[{index}]"
        if binding.kind == "file":
            item = _read_file_input(binding, storage)
        else:
            item, fact = _resolve_imported_input(connection, binding, require_file_role=True)
            read_imported_bytes(fact, binding.relative_path)
        identity = (item.storage_key, item.role)
        if identity in seen:
            raise DatasetContractError(
                f"{context}: duplicate input for storage key {item.storage_key} "
                f"and role {item.role}")
        seen.add(identity)
        resolved.append(item)
    return resolved


# --------------------------------------------------------------------------- #
# Staging (single transaction, advisory-locked per dataset key)
# --------------------------------------------------------------------------- #


def _ensure_artifact(connection: Connection, storage_key: str, digest: str, *,
                     byte_size: int, media_type: str, license_status: str) -> UUID:
    row = connection.execute(text(
        "SELECT id, sha256 FROM app.artifacts WHERE relative_storage_key = :key"),
        {"key": storage_key}).first()
    if row is not None:
        if row[1] != digest:
            raise DatasetVerificationError(
                f"Stored artifact {storage_key} diverges from the newly computed digest; "
                "refusing to mutate artifact history")
        return row[0]
    artifact_id = uuid4()
    connection.execute(text("""
        INSERT INTO app.artifacts(id, relative_storage_key, sha256, byte_size, media_type,
                                  scope, owner_id, license_status)
        VALUES (:id, :key, :sha256, :byte_size, :media_type, 'internal', NULL, :license)
    """), {"id": artifact_id, "key": storage_key, "sha256": digest, "byte_size": byte_size,
           "media_type": media_type, "license": license_status})
    return artifact_id


def _insert_observations(connection: Connection, version_id: UUID,
                         observations: tuple[Observation, ...]) -> None:
    if not observations:
        return
    statement = text("""
        INSERT INTO app.metric_observations(dataset_version_id, metric_definition_id,
            period_start, period_end, dimensions, dimensions_hash, value, quality_status,
            bound_kind, source_record_ref, quality)
        VALUES (:version_id, :metric, :period_start, :period_end,
                CAST(:dimensions AS jsonb), :dimensions_hash,
                CAST(:value AS numeric(78,30)), :quality_status, :bound_kind,
                :source_record_ref, CAST(:quality AS jsonb))
    """)
    batch: list[dict] = []
    for observation in observations:
        batch.append({
            "version_id": version_id,
            "metric": observation.metric_definition_id,
            "period_start": observation.period_start,
            "period_end": observation.period_end,
            "dimensions": _dumps_canonical(observation.dimensions),
            "dimensions_hash": observation.dimensions_hash,
            "value": observation.value,
            "quality_status": observation.quality_status,
            "bound_kind": observation.bound_kind,
            "source_record_ref": observation.source_record_ref,
            "quality": _dumps_canonical(observation.quality),
        })
    connection.execute(statement, batch)


def _canonical_inputs_from_rows(input_rows: list) -> list[ResolvedInput]:
    return [ResolvedInput(storage_key=row.storage_key, sha256=row.sha256,
                          byte_size=0, media_type="", role=row.role,
                          source_id=row.source_id, query_hash=row.query_hash,
                          license_status=row.license_status) for row in input_rows]


def _rebuild_manifest_from_rows(connection: Connection, version: dict) -> tuple[
        PreparedManifest, list[ResolvedInput]]:
    """Re-derive the exact canonical manifest from persisted rows."""
    input_rows = connection.execute(text("""
        SELECT i.role, i.source_id, i.query_hash, a.relative_storage_key AS storage_key,
               a.sha256, a.license_status
        FROM app.dataset_inputs i
        JOIN app.artifacts a ON a.id = i.artifact_id
        WHERE i.dataset_version_id = :id
        ORDER BY a.relative_storage_key, i.role
    """), {"id": version["id"]}).all()
    metric_rows = connection.execute(text("""
        SELECT metric_definition_id FROM app.dataset_metrics
        WHERE dataset_version_id = :id ORDER BY metric_definition_id
    """), {"id": version["id"]}).all()
    observation_rows = connection.execute(text("""
        SELECT metric_definition_id, period_start, period_end, dimensions, dimensions_hash,
               value::text AS value_text, quality_status, bound_kind, source_record_ref, quality
        FROM app.metric_observations WHERE dataset_version_id = :id
    """), {"id": version["id"]}).all()
    resolved = _canonical_inputs_from_rows(input_rows)
    observations = []
    for row in observation_rows:
        value = None
        if row.value_text is not None:
            value = decimal_string(Decimal(row.value_text))
        observations.append(Observation(
            metric_definition_id=row.metric_definition_id,
            period_start=row.period_start, period_end=row.period_end,
            dimensions=row.dimensions, dimensions_hash=row.dimensions_hash,
            value=value, quality_status=row.quality_status, bound_kind=row.bound_kind,
            source_record_ref=row.source_record_ref, quality=row.quality))
    manifest = PreparedManifest(
        schema_version=1,
        dataset_key=version["dataset_key"],
        frequency=version["frequency"],
        window_start=version["start_date"],
        window_end_exclusive=version["end_date"],
        pipeline_version=version["pipeline_version"],
        code_commit=version["code_commit"],
        config_hash=version["config_hash"],
        dependency_lock_hash=version["dependency_lock_hash"],
        source_as_of=version["source_as_of"],
        retrieved_at=version["retrieved_at"],
        quality=version["quality"].get("operator", {}),
        member_metrics=tuple(row.metric_definition_id for row in metric_rows),
        inputs=(),
        observations=tuple(observations),
    )
    return manifest, resolved


def _verify_stored_digest(connection: Connection, version: dict) -> None:
    manifest, resolved = _rebuild_manifest_from_rows(connection, version)
    _bytes, digest = content_digest(manifest, resolved)
    if digest != version["content_sha256"]:
        raise DatasetVerificationError(
            "Persisted dataset rows no longer hash to the recorded content_sha256; "
            "the version is corrupt and cannot be validated or published")


# --------------------------------------------------------------------------- #
# Validation gate
# --------------------------------------------------------------------------- #


def _add_months(day: dt.date, months: int) -> dt.date:
    total = day.month - 1 + months
    year = day.year + total // 12
    month = total % 12 + 1
    return dt.date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _expected_periods(manifest: PreparedManifest) -> list[tuple[dt.datetime, dt.datetime]]:
    """Half-open UTC periods tiling the declared window at the dataset frequency."""
    start_dt = dt.datetime.combine(manifest.window_start, dt.time.min, tzinfo=dt.timezone.utc)
    end_dt = dt.datetime.combine(manifest.window_end_exclusive, dt.time.min,
                                 tzinfo=dt.timezone.utc)
    periods: list[tuple[dt.datetime, dt.datetime]] = []
    if manifest.frequency == "snapshot":
        return periods
    step_months = manifest.frequency == "monthly"
    step = dt.timedelta(days=7 if manifest.frequency == "weekly" else 1)
    cursor = start_dt
    while cursor < end_dt:
        if step_months:
            following = _add_months(cursor.date(), 1)
            boundary = dt.datetime.combine(following, dt.time.min, tzinfo=dt.timezone.utc)
        else:
            boundary = cursor + step
        boundary = min(boundary, end_dt)
        periods.append((cursor, boundary))
        cursor = boundary
    return periods


def _validate_version_content(manifest: PreparedManifest, resolved_inputs) -> dict:
    """Run the membership/alignment/coverage gates (digest already verified)."""
    report: dict = {
        "ok": True,
        "content_verified": True,
        "observation_count": len(manifest.observations),
        "member_metric_count": len(manifest.member_metrics),
        "members_without_observations": [],
        "uncovered_periods": [],
        "errors": [],
        "errors_truncated": False,
    }
    errors: list[str] = report["errors"]

    def fail(message: str) -> None:
        if len(errors) < MAX_REPORT_ENTRIES:
            errors.append(message)
        else:
            report["errors_truncated"] = True
    observed_by_metric: dict[UUID, set[dt.datetime]] = {}
    aligned = manifest.frequency != "snapshot"
    expected = _expected_periods(manifest)
    expected_pairs = set(expected)
    for observation in manifest.observations:
        metric = observation.metric_definition_id
        if metric not in manifest.member_metrics:
            fail(f"Observation references non-member metric {metric}")
        if not (manifest.window_start <= observation.period_start.date()
                and observation.period_end.date() <= manifest.window_end_exclusive
                and observation.period_start < observation.period_end):
            fail(f"Observation period {canonical_timestamp(observation.period_start)}.."
                 f"{canonical_timestamp(observation.period_end)} is outside the declared "
                 "half-open window")
        elif aligned:
            start = observation.period_start.astimezone(dt.timezone.utc)
            end = observation.period_end.astimezone(dt.timezone.utc)
            if (start, end) not in expected_pairs:
                fail(f"Observation period {canonical_timestamp(start)}..{canonical_timestamp(end)}"
                     " does not align with the declared "
                     f"{manifest.frequency} grid")
        observed_by_metric.setdefault(metric, set()).add(observation.period_start)
    for metric in manifest.member_metrics:
        starts = observed_by_metric.get(metric)
        if not starts:
            fail(f"Member metric {metric} has no observations")
            continue
        missing = [period_start for period_start, _end in expected if period_start not in starts]
        if missing:
            fail(f"Member metric {metric} has {len(missing)} uncovered periods without an "
                 "explicit missing/unavailable observation")
            report["uncovered_periods"].append({
                "metric_definition_id": str(metric),
                "total_missing": len(missing),
                "first_missing": [canonical_timestamp(value) for value in
                                  sorted(missing)[:MAX_REPORT_ENTRIES]],
            })
    report["ok"] = not errors
    return report


def _validation_status_and_quality(version: dict, report: dict) -> tuple[str, dict]:
    quality = dict(version["quality"])
    quality["validation"] = report
    return ("validated" if report["ok"] else "rejected"), quality


def _load_version(connection: Connection, version_id: UUID) -> dict | None:
    row = connection.execute(text("""
        SELECT id, dataset_key, version, status, start_date, end_date, frequency,
               pipeline_version, code_commit, config_hash, dependency_lock_hash,
               manifest_artifact_id, content_sha256, source_as_of, retrieved_at,
               quality, supersedes_id, created_at
        FROM app.dataset_versions WHERE id = :id
    """), {"id": version_id}).mappings().first()
    return dict(row) if row is not None else None


def _validate_locked(connection: Connection, version: dict, *,
                     current_status: str) -> dict:
    """Run the validation gate and commit the resulting status (same transaction)."""
    manifest, resolved = _rebuild_manifest_from_rows(connection, version)
    _bytes, digest = content_digest(manifest, resolved)
    if digest != version["content_sha256"]:
        report = {"ok": False, "content_verified": False,
                  "errors": ["Persisted dataset rows no longer hash to the recorded "
                             "content_sha256; the version is corrupt"],
                  "errors_truncated": False}
    else:
        report = _validate_version_content(manifest, resolved)
    status, quality = _validation_status_and_quality(version, report)
    updated = connection.execute(text("""
        UPDATE app.dataset_versions SET status = :status, quality = CAST(:quality AS jsonb)
        WHERE id = :id AND status = :expected
    """), {"status": status, "quality": _dumps_canonical(quality),
           "id": version["id"], "expected": current_status})
    if updated.rowcount != 1:
        raise DatasetVerificationError(
            "Dataset version changed concurrently while validating; nothing was modified")
    return report


def validate(engine: Engine, dataset_version_id: UUID) -> dict:
    """Re-run the validation gate for a staged or validated version."""
    with engine.begin() as connection:
        _assert_operator(connection)
        version = _load_version(connection, dataset_version_id)
        if version is None:
            raise DatasetLookupError(f"Dataset version {dataset_version_id} does not exist")
        if version["status"] not in ("staged", "validated"):
            raise PublishRefused(
                f"Dataset version is {version['status']}; only staged or validated "
                "versions can be validated")
        _lock_dataset_key(connection, version["dataset_key"])
        version = _load_version(connection, dataset_version_id)
        return {"dataset_key": version["dataset_key"], "version": version["version"],
                "dataset_version_id": str(version["id"]),
                "validation": _validate_locked(connection, version,
                                               current_status=version["status"])}


# --------------------------------------------------------------------------- #
# Staging entry point
# --------------------------------------------------------------------------- #


def _stage_locked(connection: Connection, manifest: PreparedManifest,
                  resolved_inputs: list[ResolvedInput], manifest_key: str,
                  manifest_digest: str, manifest_bytes: bytes) -> StagedVersion:
    existing = connection.execute(text("""
        SELECT id, version, status FROM app.dataset_versions
        WHERE dataset_key = :key AND content_sha256 = :digest
    """), {"key": manifest.dataset_key, "digest": manifest_digest}).mappings().first()
    if existing is not None:
        return StagedVersion(
            dataset_version_id=existing["id"], dataset_key=manifest.dataset_key,
            version=existing["version"], content_sha256=manifest_digest,
            status=existing["status"], deduplicated=True,
            observation_count=len(manifest.observations), input_count=len(resolved_inputs),
            validation=None)
    manifest_artifact_id = _ensure_artifact(
        connection, manifest_key, manifest_digest, byte_size=len(manifest_bytes),
        media_type="application/json", license_status="unverified")
    artifact_ids: list[tuple[UUID, ResolvedInput]] = []
    for item in resolved_inputs:
        artifact_id = _ensure_artifact(
            connection, item.storage_key, item.sha256, byte_size=item.byte_size,
            media_type=item.media_type, license_status=item.license_status)
        artifact_ids.append((artifact_id, item))
    version_number = connection.execute(text("""
        SELECT COALESCE(MAX(version), 0) + 1 FROM app.dataset_versions
        WHERE dataset_key = :key
    """), {"key": manifest.dataset_key}).scalar_one()
    version_id = uuid4()
    quality = {"operator": manifest.quality}
    connection.execute(text("""
        INSERT INTO app.dataset_versions(id, dataset_key, version, status, start_date,
            end_date, frequency, pipeline_version, code_commit, config_hash,
            dependency_lock_hash, manifest_artifact_id, content_sha256, source_as_of,
            retrieved_at, quality)
        VALUES (:id, :key, :version, 'staged', :start_date, :end_date, :frequency,
                :pipeline_version, :code_commit, :config_hash, :dependency_lock_hash,
                :manifest_artifact_id, :content_sha256, :source_as_of, :retrieved_at,
                CAST(:quality AS jsonb))
    """), {
        "id": version_id, "key": manifest.dataset_key, "version": version_number,
        "start_date": manifest.window_start, "end_date": manifest.window_end_exclusive,
        "frequency": manifest.frequency, "pipeline_version": manifest.pipeline_version,
        "code_commit": manifest.code_commit, "config_hash": manifest.config_hash,
        "dependency_lock_hash": manifest.dependency_lock_hash,
        "manifest_artifact_id": manifest_artifact_id,
        "content_sha256": manifest_digest,
        "source_as_of": manifest.source_as_of, "retrieved_at": manifest.retrieved_at,
        "quality": _dumps_canonical(quality),
    })
    if manifest.member_metrics:
        connection.execute(text("""
            INSERT INTO app.dataset_metrics(dataset_version_id, metric_definition_id)
            VALUES (:version_id, :metric)
        """), [{"version_id": version_id, "metric": metric}
               for metric in manifest.member_metrics])
    if artifact_ids:
        connection.execute(text("""
            INSERT INTO app.dataset_inputs(dataset_version_id, artifact_id, role, source_id,
                                           ingestion_run_id, query_hash)
            VALUES (:version_id, :artifact_id, :role, :source_id, NULL, :query_hash)
        """), [{"version_id": version_id, "artifact_id": artifact_id, "role": item.role,
                "source_id": item.source_id, "query_hash": item.query_hash}
               for artifact_id, item in artifact_ids])
    _insert_observations(connection, version_id, manifest.observations)
    version = _load_version(connection, version_id)
    report = _validate_locked(connection, version, current_status="staged")
    return StagedVersion(
        dataset_version_id=version_id, dataset_key=manifest.dataset_key,
        version=version_number, content_sha256=manifest_digest,
        status="validated" if report["ok"] else "rejected", deduplicated=False,
        observation_count=len(manifest.observations), input_count=len(resolved_inputs),
        validation=report)


def stage(engine: Engine, manifest_path: Path, storage_root: Path) -> StagedVersion:
    """Stage and validate one prepared manifest as an immutable dataset version."""
    manifest = load_manifest(manifest_path)
    storage = ArtifactStorage(storage_root)
    with engine.connect() as connection:
        resolved = resolve_inputs(connection, manifest, storage)
    manifest_bytes, digest = content_digest(manifest, resolved)
    manifest_key = storage.store("manifests", digest, manifest_bytes, suffix=".json")
    with engine.begin() as connection:
        _assert_operator(connection)
        _lock_dataset_key(connection, manifest.dataset_key)
        return _stage_locked(connection, manifest, resolved, manifest_key, digest,
                             manifest_bytes)


# --------------------------------------------------------------------------- #
# Publication (single transaction: approve + atomic pointer switch)
# --------------------------------------------------------------------------- #


def _revision_delta(connection: Connection, previous_id: UUID | None,
                    new_id: UUID) -> dict:
    def snapshot(version_id: UUID) -> dict[tuple, tuple]:
        rows = connection.execute(text("""
            SELECT metric_definition_id, period_start, period_end, dimensions_hash,
                   value::text AS value_text, quality_status, bound_kind,
                   source_record_ref, quality
            FROM app.metric_observations WHERE dataset_version_id = :id
        """), {"id": version_id})
        state: dict[tuple, tuple] = {}
        for row in rows:
            value = None if row.value_text is None else decimal_string(Decimal(row.value_text))
            identity = (row.metric_definition_id, canonical_timestamp(row.period_start),
                        row.dimensions_hash)
            state[identity] = (canonical_timestamp(row.period_end), value,
                               row.quality_status, row.bound_kind, row.source_record_ref,
                               _dumps_canonical(row.quality))
        return state

    if previous_id is None:
        return {"previous_version_id": None, "added": None, "removed": 0, "changed": 0}
    before, after = snapshot(previous_id), snapshot(new_id)
    added = sum(1 for key in after if key not in before)
    removed = sum(1 for key in before if key not in after)
    changed = sum(1 for key in after if key in before and after[key] != before[key])
    return {"previous_version_id": str(previous_id), "added": added,
            "removed": removed, "changed": changed}


def _publish_locked(connection: Connection, version: dict) -> dict:
    _verify_stored_digest(connection, version)
    status = version["status"]
    if status == "approved":
        active = connection.execute(text(
            "SELECT dataset_version_id FROM app.active_datasets WHERE dataset_key = :key"),
            {"key": version["dataset_key"]}).scalar_one_or_none()
        if active == version["id"]:
            return {"dataset_key": version["dataset_key"], "version": version["version"],
                    "dataset_version_id": str(version["id"]),
                    "content_sha256": version["content_sha256"], "already_active": True}
        raise PublishRefused(
            "Refusing to re-publish a non-active approved version; history would move "
            "backwards. Stage the intended content as a new version instead")
    if status != "validated":
        raise PublishRefused(
            f"Only validated dataset versions can be published; this one is {status!r}")
    previous_id = connection.execute(text(
        "SELECT dataset_version_id FROM app.active_datasets WHERE dataset_key = :key"),
        {"key": version["dataset_key"]}).scalar_one_or_none()
    delta = _revision_delta(connection, previous_id, version["id"])
    quality = dict(version["quality"])
    quality["revision"] = delta
    updated = connection.execute(text("""
        UPDATE app.dataset_versions SET status = 'approved', supersedes_id = :previous,
               quality = CAST(:quality AS jsonb)
        WHERE id = :id AND status = 'validated'
    """), {"previous": previous_id, "quality": _dumps_canonical(quality),
           "id": version["id"]})
    if updated.rowcount != 1:
        raise DatasetVerificationError(
            "Dataset version changed concurrently while publishing; nothing was modified")
    pointer = connection.execute(text("""
        INSERT INTO app.active_datasets(dataset_key, dataset_version_id)
        VALUES (:key, :id)
        ON CONFLICT (dataset_key) DO UPDATE
        SET dataset_version_id = EXCLUDED.dataset_version_id, published_at = clock_timestamp()
        RETURNING published_at
    """), {"key": version["dataset_key"], "id": version["id"]}).scalar_one()
    return {"dataset_key": version["dataset_key"], "version": version["version"],
            "dataset_version_id": str(version["id"]),
            "content_sha256": version["content_sha256"],
            "previous_version_id": None if previous_id is None else str(previous_id),
            "revision": delta,
            "published_at": canonical_timestamp(pointer)}


def publish(engine: Engine, dataset_version_id: UUID) -> dict:
    """Approve a validated version and switch the active pointer atomically."""
    with engine.begin() as connection:
        _assert_operator(connection)
        version = _load_version(connection, dataset_version_id)
        if version is None:
            raise DatasetLookupError(f"Dataset version {dataset_version_id} does not exist")
        _lock_dataset_key(connection, version["dataset_key"])
        version = _load_version(connection, dataset_version_id)
        return _publish_locked(connection, version)


# --------------------------------------------------------------------------- #
# Query API (old versions and hashes remain queryable forever)
# --------------------------------------------------------------------------- #


def _json_safe(value):
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, Decimal):
        return decimal_string(value)
    if isinstance(value, dt.datetime):
        return canonical_timestamp(value)
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    raise TypeError(f"Value of type {type(value).__name__} is not JSON-serializable")


_VERSION_COLUMNS = """
    id, dataset_key, version, status, start_date, end_date, frequency, pipeline_version,
    code_commit, config_hash, dependency_lock_hash, manifest_artifact_id, content_sha256,
    source_as_of, retrieved_at, quality, supersedes_id, created_at
"""


def get_version(connection: Connection, dataset_version_id: UUID) -> dict | None:
    row = connection.execute(text(
        f"SELECT {_VERSION_COLUMNS} FROM app.dataset_versions WHERE id = :id"),
        {"id": dataset_version_id}).mappings().first()
    return _json_safe(dict(row)) if row is not None else None


def active_version(connection: Connection, dataset_key: str) -> dict | None:
    row = connection.execute(text(f"""
        SELECT v.id, v.dataset_key, v.version, v.status, v.start_date, v.end_date,
               v.frequency, v.pipeline_version, v.code_commit, v.config_hash,
               v.dependency_lock_hash, v.manifest_artifact_id, v.content_sha256,
               v.source_as_of, v.retrieved_at, v.quality, v.supersedes_id, v.created_at,
               a.published_at
        FROM app.active_datasets a
        JOIN app.dataset_versions v ON v.id = a.dataset_version_id
        WHERE a.dataset_key = :key
    """), {"key": dataset_key}).mappings().first()
    return _json_safe(dict(row)) if row is not None else None


def version_history(connection: Connection, dataset_key: str) -> list[dict]:
    rows = connection.execute(text(f"""
        SELECT {_VERSION_COLUMNS} FROM app.dataset_versions WHERE dataset_key = :key
        ORDER BY version
    """), {"key": dataset_key}).mappings().all()
    return [_json_safe(dict(row)) for row in rows]


def list_inputs(connection: Connection, dataset_version_id: UUID) -> list[dict]:
    rows = connection.execute(text("""
        SELECT i.role, i.source_id, i.query_hash, a.relative_storage_key AS storage_key,
               a.sha256, a.byte_size, a.media_type, a.license_status
        FROM app.dataset_inputs i
        JOIN app.artifacts a ON a.id = i.artifact_id
        WHERE i.dataset_version_id = :id
        ORDER BY a.relative_storage_key, i.role
    """), {"id": dataset_version_id}).mappings().all()
    return [_json_safe(dict(row)) for row in rows]


def list_observations(connection: Connection, dataset_version_id: UUID, *,
                      limit: int = 100, offset: int = 0) -> dict:
    limit = max(1, min(int(limit), MAX_QUERY_PAGE))
    offset = max(0, int(offset))
    total = connection.execute(text(
        "SELECT count(*) FROM app.metric_observations WHERE dataset_version_id = :id"),
        {"id": dataset_version_id}).scalar_one()
    rows = connection.execute(text("""
        SELECT metric_definition_id, period_start, period_end, dimensions, dimensions_hash,
               value::text AS value, quality_status, bound_kind, source_record_ref, quality
        FROM app.metric_observations WHERE dataset_version_id = :id
        ORDER BY metric_definition_id, period_start, dimensions_hash
        LIMIT :limit OFFSET :offset
    """), {"id": dataset_version_id, "limit": limit, "offset": offset}).mappings().all()
    return {"total": total, "limit": limit, "offset": offset,
            "items": [_json_safe(dict(row)) for row in rows]}
