"""Public chart catalog and chart-view routes implemented by NI-032.

Implements the API_SPECIFICATION ``/charts`` rows: the catalog of latest
definitions (with the honest ``data_status`` advertisement — unavailable
charts are never advertised as live), one definition by slug/version and the
resolved renderer-agnostic ChartView. The view validates the selection window
against the definition's bounded ranges, validates ``filters`` against the
resolved version's closed filter schema (unknown keys and unlisted values are
rejected, never ignored) and pins exactly one approved dataset version per
request through the shared delivery service.
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
from near_api.schemas.delivery import (
    ChartDefinitionResponse,
    ChartListResponse,
    ChartViewResponse,
)

router = APIRouter(prefix="/api", tags=["charts"])

RuntimeEngineDependency = Annotated[Engine, Depends(get_runtime_engine)]

_CATALOG_CACHE = "public, max-age=60"
_IMMUTABLE_CACHE = "public, max-age=31536000, immutable"

_CATEGORIES = ("activity", "fees", "treasury", "supply", "model")


def _resolve_dataset_version(raw: str) -> UUID | None:
    if raw == "latest":
        return None
    try:
        return UUID(raw)
    except (ValueError, AttributeError):
        raise DeliveryInvalidFilter(
            "dataset_version must be 'latest' or an immutable dataset version id") from None


@router.get("/charts", response_model=ChartListResponse, operation_id="listCharts",
            summary="Public chart definition catalog",
            responses={422: {"description": "Request failed validation"}})
def list_charts(engine: RuntimeEngineDependency, response: Response, page: PublicPage,
                q: Annotated[str | None, Query(max_length=200)] = None,
                category: Annotated[str | None, Query(max_length=40)] = None,
                ) -> ChartListResponse:
    """List the latest registered version of every chart definition."""
    if category is not None and category not in _CATEGORIES:
        raise DeliveryInvalidFilter("category must be one of activity, fees, treasury, "
                                    "supply, model")
    offset, limit = page
    with user_transaction(engine, None) as connection:
        items, total = delivery.list_chart_definitions(
            connection, search=q, category=category, limit=limit, offset=offset)
    response.headers["Cache-Control"] = _CATALOG_CACHE
    next_cursor = encode_page_cursor(offset + limit) if offset + limit < total else None
    return ChartListResponse(items=items, next_cursor=next_cursor)


@router.get("/charts/{chart_id}/view", response_model=ChartViewResponse,
            operation_id="getChartView",
            summary="Resolved chart view pinned to one approved dataset version",
            responses={404: {"description": "Chart or dataset not found"},
                       422: {"description": "Range, filter or reference invalid"},
                       503: {"description": "No approved dataset exists for latest"}})
def get_chart_view(engine: RuntimeEngineDependency, response: Response, chart_id: str,
                   definition_version: Annotated[int, Query(ge=1)],
                   start: date, end: date,
                   dataset_version: Annotated[str, Query()] = "latest",
                   frequency: Annotated[str, Query()] = "day",
                   filters: Annotated[str | None, Query(max_length=2048)] = None,
                   ) -> ChartViewResponse:
    """Resolve the chart view: definition, series, quality and context hash."""
    if frequency != "day":
        raise DeliveryInvalidFilter("frequency must be day")
    Selection(start=start, end=end, frequency="day", filters={})
    parsed_filters = delivery.parse_filters_document(filters)
    requested_version = _resolve_dataset_version(dataset_version)
    with user_transaction(engine, None) as connection:
        definition = delivery.load_chart_definition(connection, chart_id,
                                                    definition_version)
        max_days = definition.available_ranges.max_days
        if (end - start).days > max_days:
            raise DeliveryInvalidFilter(
                "the selection range exceeds this chart version's allowed maximum")
        view = delivery.build_chart_view(
            connection, chart_id=chart_id, version=definition_version, start=start,
            end=end, dataset_version=requested_version, filters=parsed_filters)
    response.headers["Cache-Control"] = _CATALOG_CACHE if dataset_version == "latest" \
        else _IMMUTABLE_CACHE
    return view


@router.get("/charts/{chart_id}", response_model=ChartDefinitionResponse,
            operation_id="getChart", summary="One chart definition version",
            responses={404: {"description": "Chart definition not found"}})
def get_chart(engine: RuntimeEngineDependency, response: Response, chart_id: str,
              version: Annotated[int | None, Query(ge=1)] = None,
              ) -> ChartDefinitionResponse:
    """Return one registered chart definition (latest version by default)."""
    with user_transaction(engine, None) as connection:
        definition = delivery.load_chart_definition(connection, chart_id, version)
    response.headers["Cache-Control"] = _CATALOG_CACHE
    return definition
