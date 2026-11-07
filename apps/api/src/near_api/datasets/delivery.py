"""Public delivery service for metrics, chart views, datasets and sources (NI-032).

Stage-8 Deliver of docs/DATA_PIPELINE.md: the API resolves the exact immutable
dataset version once per request, serves units/source/quality alongside the
values and exposes the same service to public and private contexts. Every
route here is a read-only public endpoint answered through the unprivileged
``near_app`` runtime role (the scientific-zone SELECT policies of migrations
0004-0008); no route accepts or infers a user identity, and no operator
write path is reachable.

The invariants this module owns:

- **One approved dataset per request.** A series/chart view resolves exactly
  one dataset version: either the explicit ``dataset_version`` UUID (which
  must be ``approved`` — staged/validated/rejected versions are
  indistinguishable from absent, so their existence is never leaked) or the
  ``latest`` pointer, which selects among ``app.active_datasets`` rows whose
  approved version contains every required metric definition (most recent
  ``published_at``, then lowest ``dataset_key`` — a deterministic total order).
  Staged data can therefore never appear under latest, and a publication that
  fails before the pointer switch keeps serving the last good version.
- **Honest availability.** Chart definitions carry their stored
  ``data_status``; unavailable charts are never advertised as live, and a
  missing or ambiguous observation serializes as an explicit null point with
  a reason, never as zero or a fabricated bound.
- **Bounded version-keyed caching.** Approved dataset versions are immutable,
  so their loaded observation content is cached in a bounded LRU keyed by the
  full version UUID (no truncated/prefix keys, hence no cross-version
  collision). The ``latest`` pointer resolution is cached for at most 60 s
  (API_SPECIFICATION) keyed by the frozenset of required metric definitions;
  negative outcomes are never cached, so a fresh publication is picked up
  immediately.
- **Redaction.** Source projections never serialize the provider endpoint
  (``base_url``) or any credential-bearing value; ``docs_url`` is nulled
  unless it is a credential-free http(s) URL.
"""

from __future__ import annotations

import datetime as dt
import json
import threading
import time
from collections import OrderedDict
from decimal import Decimal
from typing import Callable, Mapping
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import Connection, text

from near_api.charts.registry import SERIES_ROLES
from near_api.datasets.canonical import (
    canonical_timestamp,
    decimal_string,
    dump_canonical,
    sha256_hex,
)
from near_api.datasets.service import list_inputs, list_observations
from near_api.schemas.common import DataQuality, Observation
from near_api.schemas.delivery import (
    AvailableRanges,
    ChartDefinitionResponse,
    ChartViewResponse,
    DataSourceResponse,
    DatasetResponse,
    MetricResponse,
    ResolvedSelection,
    SeriesResponse,
)

UTC = dt.timezone.utc

# Hard safety cap for one manifest payload (validated MVP datasets are far
# below this; the cap keeps a pathological catalog row from serializing
# unbounded data into a public response).
MAX_MANIFEST_ROWS = 100_000

MAX_REASON_LENGTH = 200
MAX_LINEAGE_ENTRIES = 20
MAX_LINEAGE_ENTRY_LENGTH = 200

_LATEST_TTL_SECONDS = 60.0
_LATEST_CACHE_LIMIT = 128
_VERSION_CACHE_LIMIT = 16


class DeliveryError(RuntimeError):
    """Base class for delivery failures mapped to the typed error envelope."""


class DeliveryNotFound(DeliveryError, LookupError):
    """The requested public artifact does not exist or is not publicly visible.

    Absent, staged, validated and rejected versions share this one outcome so
    non-approved data never leaks its existence.
    """


class DeliveryDataNotReady(DeliveryError):
    """No approved (last-good) dataset exists for the requested selection."""


class DeliveryInvalidFilter(DeliveryError, ValueError):
    """A filter or range value is unsupported by the resolved version."""


class DeliveryReferenceInvalid(DeliveryError, ValueError):
    """A resolved dataset does not contain the required metric definitions."""


class DeliveryPayloadTooLarge(DeliveryError):
    """The requested manifest exceeds the bounded public payload size."""


def delivery_error_shape(error: DeliveryError) -> tuple[int, str, str]:
    """Map a delivery failure to its (status, code, message) error envelope."""
    if isinstance(error, DeliveryNotFound):
        return 404, "NOT_FOUND", "Resource was not found"
    if isinstance(error, DeliveryInvalidFilter):
        return 422, "FILTER_UNSUPPORTED", "Filters or range are not supported by this version"
    if isinstance(error, DeliveryReferenceInvalid):
        return 422, "REFERENCE_INVALID", str(error)
    if isinstance(error, DeliveryPayloadTooLarge):
        return 413, "PAYLOAD_TOO_LARGE", str(error)
    if isinstance(error, DeliveryDataNotReady):
        return 503, "DATA_NOT_READY", str(error)
    return 500, "INTERNAL_ERROR", "An internal error occurred"


# --------------------------------------------------------------------------- #
# Bounded caches
# --------------------------------------------------------------------------- #


class LatestPointerCache:
    """TTL cache for public latest-pointer resolution (<= 60 s per spec).

    Keyed by the frozenset of required metric definition UUIDs; only
    successful resolutions are cached, so a dataset that becomes available is
    served immediately instead of staying behind a stale negative answer.
    """

    def __init__(self, *, ttl_seconds: float = _LATEST_TTL_SECONDS,
                 limit: int = _LATEST_CACHE_LIMIT,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl_seconds
        self._limit = limit
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: dict[frozenset[UUID], tuple[float, UUID]] = {}

    def get(self, required: frozenset[UUID]) -> UUID | None:
        now = self._clock()
        with self._lock:
            entry = self._entries.get(required)
            if entry is None or entry[0] <= now:
                self._entries.pop(required, None)
                return None
            return entry[1]

    def put(self, required: frozenset[UUID], version_id: UUID) -> None:
        now = self._clock()
        with self._lock:
            if len(self._entries) >= self._limit:
                for key in [key for key, (deadline, _value) in self._entries.items()
                            if deadline <= now]:
                    del self._entries[key]
                while len(self._entries) >= self._limit:
                    self._entries.pop(next(iter(self._entries)))
            self._entries[required] = (now + self._ttl, version_id)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class VersionContentCache:
    """Bounded LRU of immutable approved-version content keyed by full UUID.

    Approved dataset rows are trigger-frozen, so the loaded content of one
    version never changes; the cache is bounded and keyed by the complete
    version UUID object, so distinct versions can never collide.
    """

    def __init__(self, *, limit: int = _VERSION_CACHE_LIMIT) -> None:
        self._limit = limit
        self._lock = threading.Lock()
        self._entries: OrderedDict[UUID, dict] = OrderedDict()

    def get(self, version_id: UUID) -> dict | None:
        with self._lock:
            content = self._entries.get(version_id)
            if content is not None:
                self._entries.move_to_end(version_id)
            return content

    def put(self, version_id: UUID, content: dict) -> None:
        with self._lock:
            self._entries[version_id] = content
            self._entries.move_to_end(version_id)
            while len(self._entries) > self._limit:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_latest_cache = LatestPointerCache()
_version_cache = VersionContentCache()


def reset_delivery_caches() -> None:
    """Clear both delivery caches (test/operator aid; safe at any time)."""
    _latest_cache.clear()
    _version_cache.clear()


# --------------------------------------------------------------------------- #
# Selection, filters and quality helpers
# --------------------------------------------------------------------------- #


def parse_filters_document(raw: str | None) -> dict[str, str]:
    """Parse the urlencoded ``filters`` query parameter into a canonical dict.

    Accepts absent/empty (no filters) or a JSON object with non-empty string
    keys and string values; anything else is unsupported. The returned dict is
    sorted by key so identical selections canonicalize identically before any
    hash/cache computation.
    """
    if raw is None or raw == "":
        return {}
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        raise DeliveryInvalidFilter(
            "filters must be a JSON object of approved string values") from None
    if not isinstance(value, dict) or len(value) > 32:
        raise DeliveryInvalidFilter(
            "filters must be a JSON object of approved string values")
    canonical: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip() or len(key) > 120 \
                or not isinstance(item, str) or len(item) > 120:
            raise DeliveryInvalidFilter(
                "filters must be a JSON object of approved string values")
        canonical[key] = item
    return dict(sorted(canonical.items()))


def validate_filters_against_schema(filters: Mapping[str, str],
                                    filter_schema: Mapping) -> dict[str, str]:
    """Validate filters against one chart version's closed filter schema.

    The NI-031 registry stores a closed JSON-Schema object whose properties
    are string enums drawn from approved mappings. Unknown keys and unlisted
    values are rejected, never ignored; the canonicalized result is what the
    resolution, hashing and caching see.
    """
    properties = filter_schema.get("properties")
    if not isinstance(properties, dict):
        raise DeliveryInvalidFilter("this chart version declares no filter schema")
    canonical: dict[str, str] = {}
    for key, value in filters.items():
        bound = properties.get(key)
        if bound is None:
            raise DeliveryInvalidFilter(
                "filters must be a JSON object of approved string values")
        options = bound.get("enum") if isinstance(bound, dict) else None
        if not isinstance(options, list) or value not in options:
            raise DeliveryInvalidFilter(
                "filters must be a JSON object of approved string values")
        canonical[key] = value
    return dict(sorted(canonical.items()))


def _truncate_reason(value) -> str:
    text_value = str(value).strip()
    return text_value[:MAX_REASON_LENGTH] if text_value else "observation is not verified"


AMBIGUOUS_VARIANT_REASON = ("the period holds multiple dimension variants for this "
                            "metric; an approved filter value must disambiguate them")
OUTSIDE_COVERAGE_REASON = "outside the dataset coverage window"
NO_OBSERVATION_REASON = "no observation for the period"
NO_SELECTION_INTERSECTION_REASON = ("the selection does not intersect the dataset "
                                    "coverage window")


def _unavailable_point(start: dt.datetime, end: dt.datetime, reason: str) -> dict:
    return {"start": start, "end": end, "value": None,
            "quality": {"status": "unavailable", "bound_kind": None,
                        "reasons": (reason,), "coverage": {"observed": 0, "expected": 1},
                        "freshness_target_seconds": None}}


def _missing_point(start: dt.datetime, end: dt.datetime, reason: str) -> dict:
    return {"start": start, "end": end, "value": None,
            "quality": {"status": "missing", "bound_kind": None, "reasons": (reason,),
                        "coverage": {"observed": 0, "expected": 1},
                        "freshness_target_seconds": None}}


def _row_quality(row: Mapping) -> DataQuality:
    """Map one stored observation row to the shared DataQuality contract."""
    status = {"verified": "ok", "missing": "missing", "unavailable": "unavailable"}[
        row["quality_status"]]
    if status == "ok":
        reasons: tuple[str, ...] = ()
    else:
        reason = (row.get("quality") or {}).get("reason")
        reasons = (_truncate_reason(reason),)
    return DataQuality(
        status=status,  # type: ignore[arg-type]
        bound_kind=row["bound_kind"] if status == "ok" else None,
        reasons=reasons,
        coverage={"observed": 1 if status == "ok" else 0, "expected": 1},
        freshness_target_seconds=None)


def _point_from_row(row: Mapping) -> dict:
    return {"start": row["period_start"], "end": row["period_end"],
            "value": row["value"], "quality": _row_quality(row).model_dump(mode="json")}


def aggregate_quality(points: list[dict]) -> DataQuality:
    """Aggregate point qualities into one view-level DataQuality.

    Deterministic worst-of aggregation: ``ok`` only when every point is ok,
    ``partial`` when verified and non-verified points mix, ``missing`` /
    ``unavailable`` when no point is verified; reasons are the distinct sorted
    non-ok reasons (bounded). An empty point set is explicitly unavailable
    instead of silently empty.
    """
    reasons: set[str] = set()
    observed = expected = ok = missing = unavailable = 0
    for point in points:
        quality = point["quality"]
        coverage = quality["coverage"]
        observed += coverage["observed"]
        expected += coverage["expected"]
        if quality["status"] == "ok":
            ok += 1
        else:
            reasons.update(quality["reasons"])
            if quality["status"] == "missing":
                missing += 1
            else:
                unavailable += 1
    if not points:
        return DataQuality(status="unavailable", bound_kind=None,
                           reasons=(NO_SELECTION_INTERSECTION_REASON,),
                           coverage={"observed": 0, "expected": 0},
                           freshness_target_seconds=None)
    if ok and ok < len(points):
        status = "partial"
    elif ok:
        status = "ok"
    elif unavailable:
        status = "unavailable"
    else:
        status = "missing"
    return DataQuality(status=status,  # type: ignore[arg-type]
                       bound_kind=None, reasons=tuple(sorted(reasons)[:20]),
                       coverage={"observed": observed, "expected": expected},
                       freshness_target_seconds=None)


# --------------------------------------------------------------------------- #
# Approved-version loading (one approved dataset per request)
# --------------------------------------------------------------------------- #


def _load_version_content(connection: Connection, version_id: UUID) -> dict:
    rows = connection.execute(text("""
        SELECT metric_definition_id, period_start, period_end, dimensions, dimensions_hash,
               value, quality_status, bound_kind, source_record_ref, quality
        FROM app.metric_observations WHERE dataset_version_id = :id
        ORDER BY metric_definition_id, period_start, dimensions_hash
    """), {"id": version_id}).mappings().all()
    observations: dict[UUID, list[dict]] = {}
    verified = 0
    reasons: set[str] = set()
    for row in rows:
        value = None
        if row["value"] is not None:
            value = decimal_string(row["value"])
        record = {"metric_definition_id": row["metric_definition_id"],
                  "period_start": row["period_start"].astimezone(UTC),
                  "period_end": row["period_end"].astimezone(UTC),
                  "dimensions": dict(row["dimensions"] or {}),
                  "dimensions_hash": row["dimensions_hash"],
                  "value": value, "quality_status": row["quality_status"],
                  "bound_kind": row["bound_kind"],
                  "source_record_ref": row["source_record_ref"],
                  "quality": dict(row["quality"] or {})}
        observations.setdefault(row["metric_definition_id"], []).append(record)
        if row["quality_status"] == "verified":
            verified += 1
        else:
            reasons.add(_truncate_reason((row["quality"] or {}).get("reason")))
    input_source_ids = connection.execute(text("""
        SELECT DISTINCT source_id FROM app.dataset_inputs
        WHERE dataset_version_id = :id AND source_id IS NOT NULL
    """), {"id": version_id}).scalars().all()
    return {"observations": {metric: tuple(items)
                             for metric, items in observations.items()},
            "verified_count": verified, "total_count": len(rows),
            "reasons": tuple(sorted(reasons)[:20]),
            "input_source_ids": tuple(sorted(input_source_ids))}


def load_approved_dataset(connection: Connection, version_id: UUID) -> tuple[dict, dict]:
    """Return the approved version row and its (cached) observation content.

    Any version that is not ``approved`` — staged, validated, rejected or
    unknown — is indistinguishable from absent.
    """
    version = connection.execute(text("""
        SELECT id, dataset_key, version, status, start_date, end_date, frequency,
               pipeline_version, code_commit, config_hash, dependency_lock_hash,
               manifest_artifact_id, content_sha256, source_as_of, retrieved_at,
               quality, supersedes_id, created_at
        FROM app.dataset_versions WHERE id = :id
    """), {"id": version_id}).mappings().first()
    if version is None or version["status"] != "approved":
        raise DeliveryNotFound("approved dataset version was not found")
    content = _version_cache.get(version_id)
    if content is None:
        content = _load_version_content(connection, version_id)
        _version_cache.put(version_id, content)
    return dict(version), content


def resolve_latest_version(connection: Connection,
                           required_metric_ids: tuple[UUID, ...]) -> UUID:
    """Resolve the latest approved dataset version containing every metric.

    Deterministic total order: most recent ``published_at`` first, then the
    lowest ``dataset_key``. The outcome is cached for at most 60 s keyed by
    the exact required-metric set; no result means no approved dataset
    contains the requirement, which is a typed not-ready failure, never a
    substitution or a staged dataset.
    """
    if not required_metric_ids:
        raise DeliveryDataNotReady(
            "no approved dataset exists for this selection: the request binds no "
            "metric series that a prepared dataset could satisfy")
    key = frozenset(required_metric_ids)
    cached = _latest_cache.get(key)
    if cached is not None:
        return cached
    row = connection.execute(text("""
        SELECT a.dataset_version_id AS id
        FROM app.active_datasets a
        JOIN app.dataset_versions v ON v.id = a.dataset_version_id
            AND v.status = 'approved'
        JOIN app.dataset_metrics m ON m.dataset_version_id = a.dataset_version_id
            AND m.metric_definition_id = ANY(:ids)
        GROUP BY a.dataset_version_id, a.published_at, a.dataset_key
        HAVING count(DISTINCT m.metric_definition_id) = :count
        ORDER BY a.published_at DESC, a.dataset_key ASC
        LIMIT 1
    """), {"ids": list(required_metric_ids),
           "count": len(set(required_metric_ids))}).first()
    if row is None:
        raise DeliveryDataNotReady(
            "no approved dataset exists for this selection yet; the last good "
            "published dataset is served once publication completes")
    _latest_cache.put(key, row[0])
    return row[0]


# --------------------------------------------------------------------------- #
# Response projections
# --------------------------------------------------------------------------- #


def metric_response(row: Mapping) -> MetricResponse:
    definition = row["definition"] or {}
    limitations = definition.get("limitations") or ()
    return MetricResponse(
        id=row["id"], metric_id=row["metric_id"], version=row["version"],
        title=row["name"], definition=definition.get("description") or "",
        formula=row["formula_key"], unit=row["unit"], frequency=row["frequency"],
        source_id=row["source_id"], economic_scope=row["economic_scope"],
        availability=definition.get("availability"),
        limitations=tuple(str(item) for item in limitations))


def _safe_docs_url(value) -> str | None:
    """Null out any URL that is not a credential-free http(s) link."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    return value


def _sanitize_lineage(value) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    entries = []
    for item in value[:MAX_LINEAGE_ENTRIES]:
        if not isinstance(item, str):
            continue
        entry = item.strip()[:MAX_LINEAGE_ENTRY_LENGTH]
        if entry:
            entries.append(entry)
    return tuple(entries)


def source_response(row: Mapping) -> DataSourceResponse:
    """The sanitized public source projection (never the provider endpoint)."""
    return DataSourceResponse(
        id=row["id"], name=row["name"], docs_url=_safe_docs_url(row["docs_url"]),
        verified_at=row["verified_at"], license_status=row["license_status"],
        access_status=row["access_status"], lineage=_sanitize_lineage(row["lineage"]),
        # The catalog does not record an update frequency yet; null stays null
        # instead of a fabricated cadence promise.
        expected_update_frequency=None, last_success_at=row["last_success_at"])


def dataset_quality(content: Mapping) -> DataQuality:
    """Dataset-level quality aggregated over the loaded observation content."""
    total = content["total_count"]
    verified = content["verified_count"]
    if total == 0:
        return DataQuality(status="unavailable", bound_kind=None,
                           reasons=("the dataset holds no observations",),
                           coverage={"observed": 0, "expected": 0},
                           freshness_target_seconds=None)
    if verified == total:
        status = "ok"
    elif verified == 0:
        status = "missing"
    else:
        status = "partial"
    return DataQuality(status=status,  # type: ignore[arg-type]
                       bound_kind=None, reasons=content["reasons"],
                       coverage={"observed": verified, "expected": total},
                       freshness_target_seconds=None)


def dataset_response(version: Mapping, content: Mapping) -> DatasetResponse:
    start = version["start_date"]
    end = version["end_date"]
    if isinstance(start, str):
        start = dt.date.fromisoformat(start)
    if isinstance(end, str):
        end = dt.date.fromisoformat(end)
    return DatasetResponse(
        id=version["id"], dataset_key=version["dataset_key"],
        version=version["version"], status="approved", start=start, end=end,
        source_as_of=version["source_as_of"], retrieved_at=version["retrieved_at"],
        pipeline_version=version["pipeline_version"],
        content_sha256=version["content_sha256"],
        quality=dataset_quality(content),
        manifest_url=f"/api/datasets/{version['id']}/manifest",
        supersedes_id=version["supersedes_id"])


def chart_response(row: Mapping) -> ChartDefinitionResponse:
    return ChartDefinitionResponse(
        id=row["id"], chart_id=row["chart_id"], version=row["version"],
        title=row["title"], description=row["description"], category=row["category"],
        metric_definition_ids=tuple(UUID(item) for item in row["metric_definition_ids"]),
        visualization_type=row["visualization_type"],
        units={str(key): str(value) for key, value in (row["unit_schema"] or {}).items()},
        filter_schema=dict(row["filter_schema"] or {}),
        available_ranges=AvailableRanges(
            presets_days=tuple(row["allowed_ranges"]["presets_days"]),
            max_days=row["allowed_ranges"]["max_days"]),
        renderer_version=row["renderer_version"],
        update_frequency=row["update_frequency"], data_status=row["data_status"],
        unavailable_reason=row["unavailable_reason"],
        source_lineage=dict(row["source_lineage"] or {}))


# --------------------------------------------------------------------------- #
# Catalog queries
# --------------------------------------------------------------------------- #

_METRIC_COLUMNS = """id, metric_id, version, name, unit, frequency, economic_scope,
       formula_key, source_id, definition"""

_CHART_COLUMNS = """id, chart_id, version, title, description, category,
       visualization_type, data_status, unavailable_reason, update_frequency,
       allowed_ranges, filter_schema, unit_schema, metric_definition_ids,
       source_lineage, renderer_version"""

_SOURCE_COLUMNS = """s.id, s.name, s.docs_url, s.verified_at, s.license_status,
       s.access_status, s.lineage, cp.last_success_at"""


def list_metric_definitions(connection: Connection, *, availability: str | None,
                            limit: int,
                            offset: int) -> tuple[tuple[MetricResponse, ...], int]:
    """Latest registered version per metric, ordered by metric_id."""
    filters = ""
    params: dict = {"limit": limit, "offset": offset}
    if availability is not None:
        filters = "WHERE m.definition->>'availability' = :availability"
        params["availability"] = availability
    rows = connection.execute(text(f"""
        SELECT {_METRIC_COLUMNS}
        FROM app.metric_definitions m
        JOIN (SELECT metric_id, max(version) AS version FROM app.metric_definitions
              GROUP BY metric_id) latest
          ON latest.metric_id = m.metric_id AND latest.version = m.version
        {filters}
        ORDER BY m.metric_id
        LIMIT :limit OFFSET :offset
    """), params).mappings().all()
    total = connection.execute(text(f"""
        SELECT count(*) FROM app.metric_definitions m
        JOIN (SELECT metric_id, max(version) AS version FROM app.metric_definitions
              GROUP BY metric_id) latest
          ON latest.metric_id = m.metric_id AND latest.version = m.version
        {filters}
    """), params).scalar_one()
    return tuple(metric_response(row) for row in rows), total


def get_metric_definition(connection: Connection, metric_id: str,
                          version: int | None) -> MetricResponse:
    statement = f"""
        SELECT {_METRIC_COLUMNS} FROM app.metric_definitions
        WHERE metric_id = :metric_id {"AND version = :version" if version is not None else ""}
        ORDER BY version DESC LIMIT 1
    """
    params: dict = {"metric_id": metric_id}
    if version is not None:
        params["version"] = version
    row = connection.execute(text(statement), params).mappings().first()
    if row is None:
        raise DeliveryNotFound("metric definition was not found")
    return metric_response(row)


def list_chart_definitions(connection: Connection, *, search: str | None,
                           category: str | None, limit: int,
                           offset: int) -> tuple[tuple[ChartDefinitionResponse, ...], int]:
    """Latest registered version per chart, ordered by chart_id (public catalog)."""
    clauses = []
    params: dict = {"limit": limit, "offset": offset}
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params["pattern"] = f"%{escaped}%"
        clauses.append("(c.title ILIKE :pattern ESCAPE '\\' OR c.description ILIKE :pattern "
                       "ESCAPE '\\' OR c.chart_id ILIKE :pattern ESCAPE '\\')")
    if category is not None:
        params["category"] = category
        clauses.append("c.category = :category")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = connection.execute(text(f"""
        SELECT {_CHART_COLUMNS}
        FROM app.chart_definitions c
        JOIN (SELECT chart_id, max(version) AS version FROM app.chart_definitions
              GROUP BY chart_id) latest
          ON latest.chart_id = c.chart_id AND latest.version = c.version
        {where}
        ORDER BY c.chart_id
        LIMIT :limit OFFSET :offset
    """), params).mappings().all()
    total = connection.execute(text(f"""
        SELECT count(*) FROM app.chart_definitions c
        JOIN (SELECT chart_id, max(version) AS version FROM app.chart_definitions
              GROUP BY chart_id) latest
          ON latest.chart_id = c.chart_id AND latest.version = c.version
        {where}
    """), params).scalar_one()
    return tuple(chart_response(row) for row in rows), total


def load_chart_definition(connection: Connection, chart_id: str,
                          version: int | None) -> ChartDefinitionResponse:
    statement = f"""
        SELECT {_CHART_COLUMNS} FROM app.chart_definitions c
        WHERE c.chart_id = :chart_id {"AND c.version = :version" if version is not None else ""}
        ORDER BY c.version DESC LIMIT 1
    """
    params: dict = {"chart_id": chart_id}
    if version is not None:
        params["version"] = version
    row = connection.execute(text(statement), params).mappings().first()
    if row is None:
        raise DeliveryNotFound("chart definition was not found")
    return chart_response(row)


def load_chart_view_inputs(connection: Connection, chart_id: str, version: int | None,
                           ) -> tuple[Mapping, tuple[tuple[UUID, str], ...],
                                      dict[UUID, Mapping]]:
    """Chart row, its role-ordered series bindings and the bound metric rows."""
    statement = f"""
        SELECT {_CHART_COLUMNS} FROM app.chart_definitions c
        WHERE c.chart_id = :chart_id {"AND c.version = :version" if version is not None else ""}
        ORDER BY c.version DESC LIMIT 1
    """
    params: dict = {"chart_id": chart_id}
    if version is not None:
        params["version"] = version
    row = connection.execute(text(statement), params).mappings().first()
    if row is None:
        raise DeliveryNotFound("chart definition was not found")
    junction = connection.execute(text("""
        SELECT metric_definition_id, series_role FROM app.chart_metrics
        WHERE chart_definition_version_id = :id
    """), {"id": row["id"]}).all()
    bindings = sorted(((binding[0], binding[1]) for binding in junction),
                      key=lambda item: (SERIES_ROLES.index(item[1]), str(item[0])))
    metric_rows: dict[UUID, Mapping] = {}
    metric_ids = [metric_id for metric_id, _role in bindings]
    if metric_ids:
        for metric_row in connection.execute(text(f"""
                SELECT {_METRIC_COLUMNS} FROM app.metric_definitions WHERE id = ANY(:ids)
        """), {"ids": metric_ids}).mappings().all():
            metric_rows[metric_row["id"]] = metric_row
    return row, tuple(bindings), metric_rows


def list_source_rows(connection: Connection, *, limit: int,
                     offset: int) -> tuple[tuple[Mapping, ...], int]:
    rows = connection.execute(text(f"""
        SELECT {_SOURCE_COLUMNS}
        FROM app.sources s
        LEFT JOIN app.ingestion_checkpoints cp ON cp.source_id = s.id
        ORDER BY s.id
        LIMIT :limit OFFSET :offset
    """), {"limit": limit, "offset": offset}).mappings().all()
    total = connection.execute(text("SELECT count(*) FROM app.sources")).scalar_one()
    return tuple(dict(row) for row in rows), total


def get_source_row(connection: Connection, source_id: str) -> Mapping:
    row = connection.execute(text(f"""
        SELECT {_SOURCE_COLUMNS}
        FROM app.sources s
        LEFT JOIN app.ingestion_checkpoints cp ON cp.source_id = s.id
        WHERE s.id = :id
    """), {"id": source_id}).mappings().first()
    if row is None:
        raise DeliveryNotFound("data source was not found")
    return dict(row)


def source_responses(connection: Connection,
                     source_ids: tuple[str, ...]) -> tuple[DataSourceResponse, ...]:
    """Sanitized projections for the given source ids (sorted, deduplicated)."""
    unique = sorted({source_id for source_id in source_ids if source_id})
    if not unique:
        return ()
    rows = connection.execute(text(f"""
        SELECT {_SOURCE_COLUMNS}
        FROM app.sources s
        LEFT JOIN app.ingestion_checkpoints cp ON cp.source_id = s.id
        WHERE s.id = ANY(:ids)
    """), {"ids": unique}).mappings().all()
    by_id = {row["id"]: row for row in rows}
    return tuple(source_response(by_id[source_id]) for source_id in unique
                 if source_id in by_id)


# --------------------------------------------------------------------------- #
# Series and chart-view resolution
# --------------------------------------------------------------------------- #


def build_series_points(version: Mapping, content: Mapping, metric_id: UUID,
                        start: dt.date, end: dt.date,
                        filters: Mapping[str, str]) -> list[dict]:
    """Resolve one metric's points over the selection from one approved version.

    Daily datasets produce one point per selection day: an explicit missing
    point with a reason when no observation exists (inside the window) or when
    the day is outside the dataset's coverage, and an explicit unavailable
    point when several dimension variants match and no approved filter
    disambiguates them — a value is never averaged, summed or picked silently.
    Weekly/monthly/snapshot datasets surface the observations that exist in
    the selection (their grids are boundary-anchored, so synthesizing extra
    expectations would fabricate coverage).
    """
    start_dt = dt.datetime.combine(start, dt.time.min, tzinfo=UTC)
    end_dt = dt.datetime.combine(end, dt.time.min, tzinfo=UTC)
    matched = []
    for row in content["observations"].get(metric_id, ()):
        if not (start_dt <= row["period_start"] < end_dt):
            continue
        if all(row["dimensions"].get(key) == value for key, value in filters.items()):
            matched.append(row)
    by_period: dict[dt.datetime, list[dict]] = {}
    for row in matched:
        by_period.setdefault(row["period_start"], []).append(row)

    frequency = version["frequency"]
    window_start = version["start_date"]
    window_end = version["end_date"]
    if isinstance(window_start, str):
        window_start = dt.date.fromisoformat(window_start)
    if isinstance(window_end, str):
        window_end = dt.date.fromisoformat(window_end)

    points: list[dict] = []
    if frequency == "daily":
        day = start
        while day < end:
            period = dt.datetime.combine(day, dt.time.min, tzinfo=UTC)
            group = by_period.pop(period, [])
            if not group:
                reason = NO_OBSERVATION_REASON if window_start <= day < window_end \
                    else OUTSIDE_COVERAGE_REASON
                points.append(_missing_point(period, period + dt.timedelta(days=1),
                                             reason))
            elif len(group) == 1:
                points.append(_point_from_row(group[0]))
            else:
                points.append(_unavailable_point(period, period + dt.timedelta(days=1),
                                                 AMBIGUOUS_VARIANT_REASON))
            day += dt.timedelta(days=1)
        return points

    for period in sorted(by_period):
        group = by_period[period]
        if len(group) == 1:
            points.append(_point_from_row(group[0]))
        else:
            final = max(row["period_end"] for row in group)
            points.append(_unavailable_point(period, final, AMBIGUOUS_VARIANT_REASON))
    return points


def _series_sources(connection: Connection, metric_source_id: str | None,
                    dataset_source_ids: tuple[str, ...]) -> tuple[DataSourceResponse, ...]:
    ids = list(dataset_source_ids)
    if metric_source_id:
        ids.append(metric_source_id)
    return source_responses(connection, tuple(ids))


def _context_hash(chart_row: Mapping, dataset_version_id: UUID,
                  selection: ResolvedSelection,
                  metric_definition_ids: tuple[UUID, ...]) -> str:
    payload = {
        "chart_definition_version_id": str(chart_row["id"]),
        "dataset_version_id": str(dataset_version_id),
        "selection": {"start": selection.start.isoformat(),
                      "end": selection.end.isoformat(),
                      "frequency": selection.frequency,
                      "filters": dict(selection.filters.model_dump())},
        "metric_definition_versions": sorted(str(item) for item in metric_definition_ids),
    }
    return sha256_hex(dump_canonical(payload))


def build_chart_view(connection: Connection, *, chart_id: str, version: int | None,
                     start: dt.date, end: dt.date, dataset_version: UUID | None,
                     filters: dict[str, str]) -> ChartViewResponse:
    """Resolve the complete renderer-agnostic ChartView for one selection."""
    chart_row, bindings, metric_rows = load_chart_view_inputs(connection, chart_id, version)
    resolved_filters = validate_filters_against_schema(filters, chart_row["filter_schema"])

    required_ids = tuple({metric_id for metric_id, role in bindings
                          if role.startswith("required")})
    if dataset_version is None:
        dataset_version_id = resolve_latest_version(connection, required_ids)
    else:
        dataset_version_id = dataset_version
    version_row, content = load_approved_dataset(connection, dataset_version_id)
    if dataset_version is not None:
        missing = [str(metric_id) for metric_id in required_ids
                   if metric_id not in content["observations"]]
        if missing:
            raise DeliveryReferenceInvalid(
                "the resolved dataset version does not contain every required metric "
                "definition; incompatible metric versions are never mixed silently")

    selection = ResolvedSelection(start=start, end=end, frequency="day",
                                  filters=dict(resolved_filters))
    dataset = dataset_response(version_row, content)
    series: list[SeriesResponse] = []
    all_points: list[dict] = []
    for metric_id, role in bindings:
        metric_row = metric_rows.get(metric_id)
        if metric_row is None:
            raise DeliveryReferenceInvalid(
                "a bound metric definition does not resolve to a registered version")
        points = build_series_points(version_row, content, metric_id, start, end,
                                     resolved_filters)
        all_points.extend(points)
        series.append(SeriesResponse(
            metric=metric_response(metric_row), dataset=dataset, selection=selection,
            points=tuple(Observation.model_validate(point) for point in points),
            sources=_series_sources(connection, metric_row["source_id"],
                                    content["input_source_ids"])))
    return ChartViewResponse(
        definition=chart_response(chart_row), selection=selection, dataset=dataset,
        series=tuple(series), resolved_at=dt.datetime.now(UTC),
        context_hash=_context_hash(chart_row, dataset_version_id, selection,
                                   tuple(UUID(item) for item in
                                         chart_row["metric_definition_ids"])),
        quality=aggregate_quality(all_points))


def build_metric_series(connection: Connection, *, metric: MetricResponse,
                        dataset_version_id: UUID, start: dt.date, end: dt.date,
                        filters: dict[str, str]) -> SeriesResponse:
    """Resolve one metric's Series against one approved dataset version."""
    version_row, content = load_approved_dataset(connection, dataset_version_id)
    definition_id = metric.id
    if definition_id not in content["observations"]:
        member = connection.execute(text("""
            SELECT 1 FROM app.dataset_metrics
            WHERE dataset_version_id = :id AND metric_definition_id = :metric
        """), {"id": dataset_version_id, "metric": definition_id}).first()
        if member is None:
            raise DeliveryReferenceInvalid(
                "the resolved dataset version does not contain this metric definition")
    points = build_series_points(version_row, content, definition_id, start, end, filters)
    selection = ResolvedSelection(start=start, end=end, frequency="day",
                                  filters=dict(filters))
    return SeriesResponse(
        metric=metric, dataset=dataset_response(version_row, content),
        selection=selection,
        points=tuple(Observation.model_validate(point) for point in points),
        sources=_series_sources(connection, metric.source_id,
                                content["input_source_ids"]))


# --------------------------------------------------------------------------- #
# Sanitized manifest
# --------------------------------------------------------------------------- #


def build_dataset_manifest(connection: Connection, version_id: UUID) -> dict:
    """The sanitized public manifest of one approved dataset version.

    Re-derived from persisted rows through the public NI-028 query API, so the
    served payload is the recorded canonical content without any operator
    local path: inputs appear with their content-addressed storage keys and
    digests, never with binding paths or provider endpoints. An artifact whose
    license is ``prohibited`` is not served (404), identical to absent.
    """
    version, content = load_approved_dataset(connection, version_id)
    artifact = connection.execute(text("""
        SELECT license_status FROM app.artifacts WHERE id = :id
    """), {"id": version["manifest_artifact_id"]}).first()
    if artifact is None or artifact[0] == "prohibited":
        raise DeliveryNotFound("dataset manifest was not found")
    inputs = [{"kind": "artifact", "role": item["role"], "source_id": item["source_id"],
               "query_hash": item["query_hash"], "sha256": item["sha256"],
               "byte_size": item["byte_size"], "media_type": item["media_type"],
               "license_status": item["license_status"],
               "storage_key": item["storage_key"]}
              for item in list_inputs(connection, version_id)]
    observations: list[dict] = []
    offset = 0
    total = 0
    while True:
        page = list_observations(connection, version_id, limit=1000, offset=offset)
        total = page["total"]
        for row in page["items"]:
            value = row["value"]
            if value is not None:
                value = decimal_string(Decimal(value))
            observations.append({
                "metric_definition_id": str(row["metric_definition_id"]),
                "period_start": row["period_start"], "period_end": row["period_end"],
                "dimensions": row["dimensions"], "dimensions_hash": row["dimensions_hash"],
                "value": value, "quality_status": row["quality_status"],
                "bound_kind": row["bound_kind"],
                "source_record_ref": row["source_record_ref"], "quality": row["quality"]})
        offset += page["limit"]
        if offset >= total or total > MAX_MANIFEST_ROWS:
            break
    if total > MAX_MANIFEST_ROWS:
        raise DeliveryPayloadTooLarge(
            "the dataset manifest exceeds the bounded public payload size")

    def canonical_instant(value):
        if value is None:
            return None
        if isinstance(value, dt.datetime):
            return canonical_timestamp(value.astimezone(UTC))
        return str(value)

    return {
        "schema_version": 1,
        "dataset_key": version["dataset_key"],
        "version": version["version"],
        "status": version["status"],
        "frequency": version["frequency"],
        "window": {"start": str(version["start_date"]),
                   "end_exclusive": str(version["end_date"])},
        "pipeline_version": version["pipeline_version"],
        "code_commit": version["code_commit"],
        "config_hash": version["config_hash"],
        "dependency_lock_hash": version["dependency_lock_hash"],
        "source_as_of": canonical_instant(version["source_as_of"]),
        "retrieved_at": canonical_instant(version["retrieved_at"]),
        "content_sha256": version["content_sha256"],
        "quality": version["quality"],
        "member_metrics": sorted(str(item) for item in content["observations"]),
        "inputs": inputs,
        "observations": observations,
    }
