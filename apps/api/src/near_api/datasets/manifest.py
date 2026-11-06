"""Strict prepared-manifest parsing for dataset staging (NI-028).

A prepared manifest is the operator-authored, hash-pinned description of one
dataset version: its header (key, frequency, half-open UTC window, pipeline
provenance), its member metrics, its input bindings (each pointing at a local
file copied into content-addressed storage or at a file of an already verified
NI-027 import batch) and its observations.  Every observation row carries an
exact decimal value or an explicit missing/unavailable quality with a reason,
half-open UTC ``[period_start, period_end)`` and canonical dimensions.

The parser is deliberately strict: unknown fields, duplicate keys, floats,
oversized payloads and inconsistent quality/bound combinations are contract
errors, because anything silently ignored here would break the claim that the
``content_sha256`` digest covers the complete semantic input.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from near_api.datasets.canonical import (
    CanonicalFormatError,
    canonical_timestamp,
    canonical_value,
    decimal_string,
    dump_canonical,
    load_json_strict,
    parse_date,
    parse_decimal,
    parse_timestamp,
    sha256_hex,
)

MAX_MANIFEST_BYTES = 128 * 1024 * 1024
MAX_BINDING_BYTES = 1024 * 1024
MAX_INPUT_FILE_BYTES = 256 * 1024 * 1024
MAX_OBSERVATIONS = 500_000
MAX_INPUTS = 100
MAX_METRICS = 500
MAX_DIMENSION_BYTES = 4096
MAX_OBSERVATION_QUALITY_BYTES = 4096
MAX_VERSION_QUALITY_BYTES = 16384
MAX_TEXT = 200

DATASET_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,38}(\.[a-z0-9][a-z0-9-]{0,38}){0,2}$")
SOURCE_ID_PATTERN = re.compile(r"^SRC-[A-Z]+(-[A-Z]+)*$")
CODE_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{7,64}$")

FREQUENCIES = ("daily", "weekly", "monthly", "snapshot")
INPUT_ROLES = ("raw", "normalized", "price", "sql", "config")
QUALITY_STATUSES = ("verified", "missing", "unavailable")
BOUND_KINDS = ("exact", "estimate", "lower", "upper")
LICENSE_STATUSES = ("unknown", "unverified", "verified", "prohibited")

# media_type recorded on the artifact row for each input role; deterministic,
# therefore excluded from the content hash.
ROLE_MEDIA_TYPES = {
    "raw": "application/octet-stream",
    "normalized": "application/json",
    "price": "application/json",
    "sql": "text/plain",
    "config": "application/json",
}

MANIFEST_FIELDS = (
    "schema_version", "dataset_key", "frequency", "window", "pipeline_version",
    "code_commit", "config_hash", "dependency_lock_hash", "source_as_of",
    "retrieved_at", "quality", "member_metrics", "inputs", "observations",
)
BINDING_FIELDS = (
    "schema_version", "dataset_key", "frequency", "window", "pipeline_version",
    "code_commit", "config_hash", "dependency_lock_hash", "source_as_of",
    "retrieved_at", "quality", "member_metrics", "inputs", "aggregate_record_format",
)
AGGREGATE_RECORD_FORMAT = "observations_json"
WINDOW_FIELDS = ("start", "end_exclusive")
INPUT_FIELDS = ("kind", "path", "batch_manifest_sha256", "relative_path", "role",
                "source_id", "query_hash", "license_status")
OBSERVATION_FIELDS = ("metric_definition_id", "period_start", "period_end", "dimensions",
                      "value", "quality_status", "bound_kind", "source_record_ref", "quality")


class ManifestFormatError(ValueError):
    """The prepared manifest violates the strict schema (CLI exit 4)."""


@dataclass(frozen=True)
class InputBinding:
    """One declared input: a local file, or a file of a verified import batch."""

    kind: str  # "file" or "imported"
    role: str
    path: Path | None = None
    batch_manifest_sha256: str | None = None
    relative_path: str | None = None
    source_id: str | None = None
    query_hash: str | None = None
    license_status: str = "unverified"


@dataclass(frozen=True)
class Observation:
    metric_definition_id: UUID
    period_start: dt.datetime
    period_end: dt.datetime
    dimensions: dict
    dimensions_hash: str
    value: str | None  # canonical decimal string; None for missing/unavailable
    quality_status: str
    bound_kind: str | None
    source_record_ref: str | None
    quality: dict


@dataclass(frozen=True)
class PreparedManifest:
    schema_version: int
    dataset_key: str
    frequency: str
    window_start: dt.date
    window_end_exclusive: dt.date
    pipeline_version: str
    code_commit: str | None
    config_hash: str | None
    dependency_lock_hash: str | None
    source_as_of: dt.datetime | None
    retrieved_at: dt.datetime | None
    quality: dict
    member_metrics: tuple[UUID, ...]
    inputs: tuple[InputBinding, ...]
    observations: tuple[Observation, ...]


def _fail(message: str) -> None:
    raise ManifestFormatError(message)


def _strict_fields(obj: object, allowed: tuple[str, ...], context: str) -> dict:
    if not isinstance(obj, dict):
        _fail(f"{context}: expected a JSON object")
    unknown = sorted(set(obj) - set(allowed))
    if unknown:
        _fail(f"{context}: unknown fields {unknown}")
    missing = [field for field in allowed if field not in obj]
    if missing:
        _fail(f"{context}: missing fields {missing}")
    return obj


def _bounded_str(value: object, limit: int, context: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not value and not allow_empty) or len(value) > limit:
        _fail(f"{context}: expected a non-empty string of at most {limit} characters")
    return value


def _optional_str(value: object, limit: int, context: str) -> str | None:
    if value is None:
        return None
    return _bounded_str(value, limit, context)


def _optional_hash(value: object, context: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not canonical_sha_pattern.match(value):
        _fail(f"{context}: expected a lowercase SHA-256 hex string or null")
    return value


canonical_sha_pattern = re.compile(r"^[0-9a-f]{64}$")


def _json_bytes_size(value: object, context: str, limit: int) -> int:
    size = len(dump_canonical(value))
    if size > limit:
        _fail(f"{context}: canonical size {size} exceeds the {limit} byte limit")
    return size


def parse_observation_record(obj: object, *, context: str) -> Observation:
    record = _strict_fields(obj, OBSERVATION_FIELDS, context)
    metric_field = record["metric_definition_id"]
    try:
        metric = UUID(metric_field) if isinstance(metric_field, str) else None
    except ValueError:
        metric = None
    if metric is None:
        _fail(f"{context}: metric_definition_id must be a UUID string")
    period_start = parse_timestamp(record["period_start"], context=f"{context}.period_start")
    period_end = parse_timestamp(record["period_end"], context=f"{context}.period_end")
    if period_end <= period_start:
        _fail(f"{context}: period_end must be after period_start (half-open [start,end))")
    dimensions = record["dimensions"]
    if not isinstance(dimensions, dict):
        _fail(f"{context}: dimensions must be an object")
    _json_bytes_size(dimensions, f"{context}.dimensions", MAX_DIMENSION_BYTES)
    dimensions_hash = sha256_hex(dump_canonical(dimensions))
    quality = record["quality"]
    if not isinstance(quality, dict):
        _fail(f"{context}: quality must be an object")
    _json_bytes_size(quality, f"{context}.quality", MAX_OBSERVATION_QUALITY_BYTES)
    quality_status = record["quality_status"]
    if quality_status not in QUALITY_STATUSES:
        _fail(f"{context}: quality_status must be one of {QUALITY_STATUSES}")
    bound_kind = record["bound_kind"]
    if bound_kind is not None and bound_kind not in BOUND_KINDS:
        _fail(f"{context}: bound_kind must be one of {BOUND_KINDS} or null")
    raw_value = record["value"]
    if raw_value is None:
        value = None
    else:
        try:
            value = decimal_string(parse_decimal(raw_value, context=f"{context}.value"))
        except CanonicalFormatError as error:
            _fail(str(error))
    if (quality_status in ("missing", "unavailable")) != (value is None):
        _fail(f"{context}: missing/unavailable quality implies a null value and vice versa")
    if (bound_kind is None) != (value is None):
        _fail(f"{context}: bound_kind is required exactly when a value is present")
    if value is None and "reason" not in quality:
        _fail(f"{context}: a null value requires a reason in the quality metadata")
    return Observation(
        metric_definition_id=metric,
        period_start=period_start,
        period_end=period_end,
        dimensions=dimensions,
        dimensions_hash=dimensions_hash,
        value=value,
        quality_status=quality_status,
        bound_kind=bound_kind,
        source_record_ref=_optional_str(record["source_record_ref"], MAX_TEXT,
                                        f"{context}.source_record_ref"),
        quality=quality,
    )


def _parse_window(document: dict, context: str) -> tuple[dt.date, dt.date]:
    window = _strict_fields(document.get("window"), WINDOW_FIELDS, f"{context}.window")
    start = parse_date(window["start"], context=f"{context}.window.start")
    end = parse_date(window["end_exclusive"], context=f"{context}.window.end_exclusive")
    if end <= start:
        _fail(f"{context}: window end_exclusive must be after start (half-open [start,end))")
    return start, end


def _parse_header(document: dict, *, context: str, fields: tuple[str, ...]) -> dict:
    header = _strict_fields(document, fields, context)
    if header["schema_version"] != 1:
        _fail(f"{context}: unsupported manifest schema_version {header['schema_version']!r}")
    dataset_key = header["dataset_key"]
    if not isinstance(dataset_key, str) or not DATASET_KEY_PATTERN.match(dataset_key):
        _fail(f"{context}: dataset_key must match {DATASET_KEY_PATTERN.pattern}")
    if header["frequency"] not in FREQUENCIES:
        _fail(f"{context}: frequency must be one of {FREQUENCIES}")
    parsed = {
        "dataset_key": dataset_key,
        "frequency": header["frequency"],
        "pipeline_version": _bounded_str(header["pipeline_version"], 80,
                                         f"{context}.pipeline_version"),
        "code_commit": None,
        "config_hash": _optional_hash(header["config_hash"], f"{context}.config_hash"),
        "dependency_lock_hash": _optional_hash(header["dependency_lock_hash"],
                                               f"{context}.dependency_lock_hash"),
        "source_as_of": None,
        "retrieved_at": None,
    }
    if header["code_commit"] is not None:
        if not isinstance(header["code_commit"], str) \
                or not CODE_COMMIT_PATTERN.match(header["code_commit"]):
            _fail(f"{context}: code_commit must match {CODE_COMMIT_PATTERN.pattern} or null")
        parsed["code_commit"] = header["code_commit"]
    if header["source_as_of"] is not None:
        parsed["source_as_of"] = parse_timestamp(header["source_as_of"],
                                                 context=f"{context}.source_as_of")
    if header["retrieved_at"] is not None:
        parsed["retrieved_at"] = parse_timestamp(header["retrieved_at"],
                                                 context=f"{context}.retrieved_at")
    quality = header["quality"]
    if not isinstance(quality, dict):
        _fail(f"{context}: quality must be an object")
    _json_bytes_size(quality, f"{context}.quality", MAX_VERSION_QUALITY_BYTES)
    parsed["quality"] = quality
    member_metrics = header["member_metrics"]
    if not isinstance(member_metrics, list) or not 1 <= len(member_metrics) <= MAX_METRICS:
        _fail(f"{context}: member_metrics must be a list of 1..{MAX_METRICS} metric UUIDs")
    members: list[UUID] = []
    for index, raw in enumerate(member_metrics):
        try:
            members.append(UUID(raw) if isinstance(raw, str) else None)
        except ValueError:
            members.append(None)
        if members[-1] is None:
            _fail(f"{context}.member_metrics[{index}]: metric IDs must be UUID strings")
    if len(set(members)) != len(members):
        _fail(f"{context}: member_metrics contains duplicates")
    parsed["member_metrics"] = tuple(sorted(members))
    return parsed


def _parse_input(obj: object, context: str) -> InputBinding:
    entry = _strict_fields(obj, INPUT_FIELDS, context)
    kind = entry["kind"]
    if kind not in ("file", "imported"):
        _fail(f"{context}: kind must be 'file' or 'imported'")
    role = entry["role"]
    if role not in INPUT_ROLES:
        _fail(f"{context}: role must be one of {INPUT_ROLES}")
    source_id = _optional_str(entry["source_id"], 40, f"{context}.source_id")
    if source_id is not None and not SOURCE_ID_PATTERN.match(source_id):
        _fail(f"{context}: source_id must match {SOURCE_ID_PATTERN.pattern}")
    license_status = entry["license_status"]
    if license_status is None:
        license_status = "unverified"
    if license_status not in LICENSE_STATUSES:
        _fail(f"{context}: license_status must be one of {LICENSE_STATUSES}")
    query_hash = _optional_hash(entry["query_hash"], f"{context}.query_hash")
    if kind == "file":
        path_value = entry["path"]
        if entry["batch_manifest_sha256"] is not None or entry["relative_path"] is not None:
            _fail(f"{context}: file inputs declare path only")
        if not isinstance(path_value, str) or not path_value:
            _fail(f"{context}: file inputs require a path string")
        return InputBinding(kind=kind, role=role, path=Path(path_value), source_id=source_id,
                            query_hash=query_hash, license_status=license_status)
    if entry["path"] is not None:
        _fail(f"{context}: imported inputs declare batch_manifest_sha256/relative_path only")
    batch = entry["batch_manifest_sha256"]
    if not isinstance(batch, str) or not canonical_sha_pattern.match(batch):
        _fail(f"{context}: imported inputs require the batch manifest SHA-256")
    relative = entry["relative_path"]
    if not isinstance(relative, str) or not relative or len(relative) > 1024 \
            or relative.startswith("/") or re.search(r"(^|/)\.\.(/|$)", relative):
        _fail(f"{context}: relative_path must be a bounded archive-relative path")
    return InputBinding(kind=kind, role=role, batch_manifest_sha256=batch, relative_path=relative,
                        source_id=source_id, query_hash=query_hash, license_status=license_status)


def parse_manifest_document(document: object, *, context: str) -> PreparedManifest:
    """Parse and validate one prepared manifest document (strict schema v1)."""
    header = _parse_header(document, context=context, fields=MANIFEST_FIELDS)
    window_start, window_end = _parse_window(document, context)
    raw_inputs = document["inputs"]
    if not isinstance(raw_inputs, list) or len(raw_inputs) > MAX_INPUTS:
        _fail(f"{context}: inputs must be a list of at most {MAX_INPUTS} bindings")
    inputs = tuple(_parse_input(item, context=f"{context}.inputs[{index}]")
                   for index, item in enumerate(raw_inputs))
    raw_observations = document["observations"]
    if not isinstance(raw_observations, list) or len(raw_observations) > MAX_OBSERVATIONS:
        _fail(f"{context}: observations must be a list of at most {MAX_OBSERVATIONS} records")
    observations: list[Observation] = []
    seen: set[tuple[str, str, str]] = set()
    for index, item in enumerate(raw_observations):
        observation = parse_observation_record(item, context=f"{context}.observations[{index}]")
        identity = (str(observation.metric_definition_id),
                    canonical_timestamp(observation.period_start), observation.dimensions_hash)
        if identity in seen:
            _fail(f"{context}.observations[{index}]: duplicate observation identity")
        seen.add(identity)
        observations.append(observation)
    return PreparedManifest(
        schema_version=1,
        dataset_key=header["dataset_key"],
        frequency=header["frequency"],
        window_start=window_start,
        window_end_exclusive=window_end,
        pipeline_version=header["pipeline_version"],
        code_commit=header["code_commit"],
        config_hash=header["config_hash"],
        dependency_lock_hash=header["dependency_lock_hash"],
        source_as_of=header["source_as_of"],
        retrieved_at=header["retrieved_at"],
        quality=header["quality"],
        member_metrics=header["member_metrics"],
        inputs=inputs,
        observations=tuple(observations),
    )


def load_manifest(path: Path) -> PreparedManifest:
    """Read and parse a prepared manifest file from disk (bounded size)."""
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ManifestFormatError(f"Cannot read manifest {path}: {error}") from None
    if len(data) > MAX_MANIFEST_BYTES:
        raise ManifestFormatError(f"Manifest exceeds the {MAX_MANIFEST_BYTES} byte limit")
    try:
        document = load_json_strict(data, context="manifest")
    except CanonicalFormatError as error:
        raise ManifestFormatError(str(error)) from None
    return parse_manifest_document(document, context="manifest")


def parse_binding_document(document: object, *, context: str) -> PreparedManifest:
    """Parse a stage-from-import binding (header only; records come from files)."""
    header = _parse_header(document, context=context, fields=BINDING_FIELDS)
    if document["aggregate_record_format"] != AGGREGATE_RECORD_FORMAT:
        _fail(f"{context}: aggregate_record_format must be {AGGREGATE_RECORD_FORMAT!r}")
    window_start, window_end = _parse_window(document, context)
    raw_inputs = document["inputs"]
    if not isinstance(raw_inputs, list) or not raw_inputs or len(raw_inputs) > MAX_INPUTS:
        _fail(f"{context}: inputs must be a list of 1..{MAX_INPUTS} imported bindings")
    inputs = tuple(_parse_input(item, context=f"{context}.inputs[{index}]")
                   for index, item in enumerate(raw_inputs))
    return PreparedManifest(
        schema_version=1,
        dataset_key=header["dataset_key"],
        frequency=header["frequency"],
        window_start=window_start,
        window_end_exclusive=window_end,
        pipeline_version=header["pipeline_version"],
        code_commit=header["code_commit"],
        config_hash=header["config_hash"],
        dependency_lock_hash=header["dependency_lock_hash"],
        source_as_of=header["source_as_of"],
        retrieved_at=header["retrieved_at"],
        quality=header["quality"],
        member_metrics=header["member_metrics"],
        inputs=inputs,
        observations=(),
    )


def canonical_input_entry(resolved) -> dict:
    """Canonical hash input for one resolved artifact binding."""
    return {
        "storage_key": resolved.storage_key,
        "sha256": resolved.sha256,
        "role": resolved.role,
        "source_id": resolved.source_id,
        "query_hash": resolved.query_hash,
        "license_status": resolved.license_status,
    }


def observation_entry(observation: Observation) -> dict:
    """Canonical hash input for one observation row."""
    return {
        "metric_definition_id": str(observation.metric_definition_id),
        "period_start": canonical_timestamp(observation.period_start),
        "period_end": canonical_timestamp(observation.period_end),
        "dimensions": canonical_value(observation.dimensions, context="dimensions"),
        "dimensions_hash": observation.dimensions_hash,
        "value": observation.value,
        "quality_status": observation.quality_status,
        "bound_kind": observation.bound_kind,
        "source_record_ref": observation.source_record_ref,
        "quality": observation.quality,
    }


def manifest_document(manifest: PreparedManifest, resolved_inputs) -> dict:
    """Assemble the canonical document whose SHA-256 is the dataset content hash.

    Inputs contribute their content identity (storage key, digest, role,
    source, query hash, license), never local paths, so re-staging the same
    semantic input from another location deduplicates to the same version.
    """
    inputs = sorted((canonical_input_entry(item) for item in resolved_inputs),
                    key=lambda entry: (entry["storage_key"], entry["role"]))
    observations = sorted((observation_entry(item) for item in manifest.observations),
                          key=lambda entry: (entry["metric_definition_id"],
                                             entry["period_start"], entry["dimensions_hash"]))
    return {
        "schema_version": 1,
        "dataset_key": manifest.dataset_key,
        "frequency": manifest.frequency,
        "window": {"start": manifest.window_start.isoformat(),
                   "end_exclusive": manifest.window_end_exclusive.isoformat()},
        "pipeline_version": manifest.pipeline_version,
        "code_commit": manifest.code_commit,
        "config_hash": manifest.config_hash,
        "dependency_lock_hash": manifest.dependency_lock_hash,
        "source_as_of": canonical_timestamp(manifest.source_as_of)
                        if manifest.source_as_of is not None else None,
        "retrieved_at": canonical_timestamp(manifest.retrieved_at)
                        if manifest.retrieved_at is not None else None,
        "quality": manifest.quality,
        "inputs": inputs,
        "member_metrics": [str(metric) for metric in manifest.member_metrics],
        "observations": observations,
    }


def content_digest(manifest: PreparedManifest, resolved_inputs) -> tuple[bytes, str]:
    """Canonical manifest bytes and their SHA-256 (the dedup/integrity key)."""
    document = manifest_document(manifest, resolved_inputs)
    data = dump_canonical(document)
    return data, sha256_hex(data)
