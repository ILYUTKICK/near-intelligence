"""Public metric catalog and series routes implemented by NI-032.

Implements the API_SPECIFICATION ``/metrics`` rows: the catalog (latest
registered version per metric), one definition by slug/version and the
resolved series. Every route is a public read: authorization is not required
and no user identity is accepted anywhere — the dataset resolution flows
exclusively through approved ``app.active_datasets`` pointers.

Responses carry decimal values as strings, per-point quality and UTC
timestamps; the latest pointer is served with a bounded 60 s public cache and
immutable explicit versions with an immutable cache policy.
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.engine import Engine

from near_api.auth.principal import get_runtime_engine
from near_api.datasets import delivery
from near_api.datasets.delivery import DeliveryInvalidFilter
from near_api.db.session import user_transaction
from near_api.pagination import PublicPage, encode_page_cursor
from near_api.schemas.common import Selection
from near_api.schemas.delivery import MetricListResponse, MetricResponse, SeriesResponse

router = APIRouter(prefix="/api", tags=["metrics"])

RuntimeEngineDependency = Annotated[Engine, Depends(get_runtime_engine)]

_CATALOG_CACHE = "public, max-age=60"
_IMMUTABLE_CACHE = "public, max-age=31536000, immutable"

_AVAILABILITY_CODES = ("A", "P", "B", "G")


def _selection_window(start: date, end: date) -> None:
    """Validate the half-open UTC selection window through the shared contract."""
    Selection(start=start, end=end, frequency="day", filters={})


def _resolve_dataset_version(raw: str) -> UUID | None:
    """Parse ``dataset_version=latest|UUID``; anything else is unsupported."""
    if raw == "latest":
        return None
    try:
        return UUID(raw)
    except (ValueError, AttributeError):
        raise DeliveryInvalidFilter(
            "dataset_version must be 'latest' or an immutable dataset version id") from None


@router.get("/metrics", response_model=MetricListResponse, operation_id="listMetrics",
            summary="Public metric definition catalog",
            responses={422: {"description": "Request failed validation"}})
def list_metrics(engine: RuntimeEngineDependency, response: Response, page: PublicPage,
                 availability: Annotated[str | None, Query()] = None,
                 category: Annotated[str | None, Query(max_length=40)] = None,
                 ) -> MetricListResponse:
    """List the latest registered version of every metric definition."""
    if category is not None:
        # Metrics carry no category axis; unknown filter axes are rejected,
        # never ignored (the category axis belongs to the chart catalog).
        raise DeliveryInvalidFilter("metrics have no category axis; category is a "
                                    "chart-catalog filter")
    if availability is not None and availability not in _AVAILABILITY_CODES:
        raise DeliveryInvalidFilter("availability must be one of A, P, B, G")
    offset, limit = page
    with user_transaction(engine, None) as connection:
        items, total = delivery.list_metric_definitions(
            connection, availability=availability, limit=limit, offset=offset)
    response.headers["Cache-Control"] = _CATALOG_CACHE
    next_cursor = encode_page_cursor(offset + limit) if offset + limit < total else None
    return MetricListResponse(items=items, next_cursor=next_cursor)


@router.get("/metrics/{metric_id}/series", response_model=SeriesResponse,
            operation_id="getMetricSeries",
            summary="Resolved metric series from one approved dataset version",
            responses={404: {"description": "Metric or dataset not found"},
                       422: {"description": "Range, filter or reference invalid"},
                       503: {"description": "No approved dataset exists for latest"}})
def get_metric_series(engine: RuntimeEngineDependency, response: Response,
                      metric_id: str,
                      definition_version: Annotated[int, Query(ge=1)],
                      start: date, end: date,
                      dataset_version: Annotated[str, Query()] = "latest",
                      frequency: Annotated[str, Query()] = "day",
                      filters: Annotated[str | None, Query(max_length=2048)] = None,
                      ) -> SeriesResponse:
    """Resolve the metric's series over the selection from one approved dataset."""
    if frequency != "day":
        raise DeliveryInvalidFilter("frequency must be day")
    _selection_window(start, end)
    resolved_filters = delivery.parse_filters_document(filters)
    if resolved_filters:
        # No metric-level filter domain is registered yet; dimensions are
        # qualified by the dataset, so an under-specified request must never
        # pick a variant silently.
        raise DeliveryInvalidFilter("no approved filter domain is registered for "
                                    "metric series")
    version_id = _resolve_dataset_version(dataset_version)
    with user_transaction(engine, None) as connection:
        metric = delivery.get_metric_definition(connection, metric_id, definition_version)
        if version_id is None:
            version_id = delivery.resolve_latest_version(connection, (metric.id,))
        series = delivery.build_metric_series(
            connection, metric=metric, dataset_version_id=version_id,
            start=start, end=end, filters=resolved_filters)
    response.headers["Cache-Control"] = _CATALOG_CACHE if dataset_version == "latest" \
        else _IMMUTABLE_CACHE
    return series


@router.get("/metrics/{metric_id}", response_model=MetricResponse, operation_id="getMetric",
            summary="One metric definition version",
            responses={404: {"description": "Metric definition not found"}})
def get_metric(engine: RuntimeEngineDependency, response: Response, metric_id: str,
               version: Annotated[int | None, Query(ge=1)] = None) -> MetricResponse:
    """Return one registered metric definition (latest version by default)."""
    with user_transaction(engine, None) as connection:
        metric = delivery.get_metric_definition(connection, metric_id, version)
    response.headers["Cache-Control"] = _CATALOG_CACHE
    return metric
