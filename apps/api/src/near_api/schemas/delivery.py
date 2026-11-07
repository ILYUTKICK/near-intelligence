"""NI-032 public delivery contracts: metrics, charts, series, chart views,
datasets and data sources.

These models pin the response side of the API_SPECIFICATION "Charts and data
— public except saved instances" rows. Field sets follow the specification's
reusable schemas (Metric, ChartDefinition, Dataset, DataSource, Series,
ChartView) with the implemented additions recorded in API_SPECIFICATION.md:

- ``ChartDefinitionResponse`` carries ``data_status``/``unavailable_reason``
  (the honest NI-031 advertisement — unavailable charts are never advertised
  as live), ``source_lineage`` (provenance for the source drawer) and
  ``available_ranges`` as the bounded ``{presets_days,max_days}`` object the
  registry stores (a plain preset-string list would lose the max-day bound).
- ``ResolvedSelection`` reuses the shared ``Selection`` window rules while
  carrying the chart-version-validated filter values that the request supplied
  through the urlencoded ``filters`` query parameter. The bootstrap
  ``SelectionFilters`` model stays strict-empty; only server-validated values
  against a resolved chart version's closed ``filter_schema`` are ever
  serialized here, so a resolved selection can never contain an unapproved
  filter.
- Decimal values are strings, raw amounts stay integers-in-strings and every
  observation carries explicit quality and UTC timestamps (shared
  ``Observation``/``DataQuality`` from near_api.schemas.common).
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator
from typing import Annotated

from near_api.schemas.common import ContractModel, DataQuality, Observation, Selection

SHA256_HEX = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]

AvailabilityCode = Literal["A", "P", "B", "G"]


class ResolvedSelectionFilters(ContractModel):
    """Chart-version-validated filters carried inside a resolved selection.

    Request filters arrive as the urlencoded ``filters`` query parameter and
    are validated server-side against the resolved chart definition version's
    closed ``filter_schema`` (the NI-031 versioned allowlist: string enums
    from approved source/recipient/price-basis mappings only). Unknown keys
    and unlisted values are rejected before any resolution happens, so this
    permissive container never serializes an unapproved filter value.
    """

    model_config = ContractModel.model_config | {"extra": "allow"}


class ResolvedSelection(Selection):
    """The resolved selection echoed back on series/chart-view responses.

    Same window rules as the shared bootstrap ``Selection`` (ISO dates,
    frequency ``day``, non-empty half-open window of at most 366 days), but
    ``filters`` carries the chart-version-validated values instead of the
    strict-empty bootstrap object.
    """

    filters: ResolvedSelectionFilters


class MetricResponse(ContractModel):
    """One immutable metric definition version (API_SPECIFICATION ``Metric``).

    ``formula`` is the registered computation identifier (``formula_key``) —
    a stable provenance label, never executable user input.
    """

    id: UUID
    metric_id: str = Field(min_length=1, max_length=80)
    version: int = Field(strict=True, ge=1)
    title: str = Field(min_length=1, max_length=200)
    definition: str = Field(min_length=1)
    formula: str = Field(min_length=1, max_length=80)
    unit: str = Field(min_length=1, max_length=40)
    frequency: Literal["daily", "weekly", "monthly", "snapshot"]
    source_id: str | None = Field(default=None, min_length=1, max_length=40)
    economic_scope: str = Field(min_length=1)
    availability: AvailabilityCode
    limitations: tuple[str, ...] = Field(max_length=50)


class MetricListResponse(ContractModel):
    items: tuple[MetricResponse, ...]
    next_cursor: str | None


class AvailableRanges(ContractModel):
    """Bounded query ranges of a chart definition (registry ``allowed_ranges``)."""

    presets_days: tuple[int, ...] = Field(min_length=1, max_length=8)
    max_days: int = Field(strict=True, ge=1, le=366)

    @model_validator(mode="after")
    def presets_within_bound(self):
        if any(day > self.max_days for day in self.presets_days):
            raise ValueError("a preset cannot exceed the chart's maximum range")
        return self


class ChartDefinitionResponse(ContractModel):
    """One immutable chart definition version (API_SPECIFICATION ``ChartDefinition``).

    ``data_status`` is the honest advertisement: only ``available`` charts may
    be rendered as live; ``unavailable`` charts always carry their recorded
    reason and are never advertised as live.
    """

    id: UUID
    chart_id: str = Field(min_length=1, max_length=80)
    version: int = Field(strict=True, ge=1)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    category: Literal["activity", "fees", "treasury", "supply", "model"]
    metric_definition_ids: tuple[UUID, ...] = Field(max_length=16)
    visualization_type: Literal["line", "area", "bar", "scatter", "panels"]
    units: dict[str, str]
    filter_schema: dict[str, object]
    available_ranges: AvailableRanges
    renderer_version: str = Field(min_length=1, max_length=80)
    update_frequency: Literal["daily", "weekly", "monthly", "snapshot"]
    data_status: Literal["available", "unavailable"]
    unavailable_reason: str | None = None
    source_lineage: dict[str, object]

    @model_validator(mode="after")
    def honest_availability(self):
        if (self.data_status == "available") != (self.unavailable_reason is None):
            raise ValueError("only an unavailable chart carries an unavailable_reason")
        return self


class ChartListResponse(ContractModel):
    items: tuple[ChartDefinitionResponse, ...]
    next_cursor: str | None


class DatasetResponse(ContractModel):
    """One approved immutable dataset version (API_SPECIFICATION ``Dataset``).

    Public delivery serves ``approved`` versions only: staged, validated and
    rejected versions are indistinguishable from absent ones (404) and can
    never appear under ``latest``.
    """

    id: UUID
    dataset_key: str = Field(min_length=1, max_length=120)
    version: int = Field(strict=True, ge=1)
    status: Literal["approved"]
    start: date
    end: date
    source_as_of: datetime | None
    retrieved_at: datetime | None
    pipeline_version: str = Field(min_length=1, max_length=80)
    content_sha256: SHA256_HEX
    quality: DataQuality
    manifest_url: str | None
    supersedes_id: UUID | None


class DataSourceResponse(ContractModel):
    """Sanitized source projection (API_SPECIFICATION ``DataSource``).

    The provider endpoint (``base_url``) and every credential-bearing value
    are never serialized: ``docs_url`` is nulled unless it is a credential-free
    http(s) URL. ``expected_update_frequency`` stays null until the operator
    catalog records it (missing is not fabricated); ``last_success_at`` comes
    from the ingestion checkpoint zone when the source has been refreshed.
    """

    id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    docs_url: str | None
    verified_at: datetime | None
    license_status: Literal["unknown", "unverified", "verified", "prohibited"]
    access_status: Literal["disabled", "documented", "approved"]
    lineage: tuple[str, ...] = Field(max_length=20)
    expected_update_frequency: str | None
    last_success_at: datetime | None


class DataSourceListResponse(ContractModel):
    items: tuple[DataSourceResponse, ...]
    next_cursor: str | None


class SeriesResponse(ContractModel):
    """One metric's resolved series (API_SPECIFICATION ``Series``).

    ``points`` carry explicit nulls with gap reasons; a point's null value is
    never converted to zero and every point keeps its UTC half-open interval,
    quality status, bound kind and reasons.
    """

    metric: MetricResponse
    dataset: DatasetResponse
    selection: ResolvedSelection
    points: tuple[Observation, ...]
    sources: tuple[DataSourceResponse, ...]


class ChartViewResponse(ContractModel):
    """Resolved renderer-agnostic chart view (API_SPECIFICATION ``ChartView``).

    ``context_hash`` covers the chart definition version, the pinned dataset
    version, the canonical selection (including validated filters) and the
    bound metric definition versions, so identical selections hash identically
    and any changed input changes the hash.
    """

    definition: ChartDefinitionResponse
    selection: ResolvedSelection
    dataset: DatasetResponse
    series: tuple[SeriesResponse, ...]
    resolved_at: datetime
    context_hash: SHA256_HEX
    quality: DataQuality
