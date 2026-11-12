"""NI-035 private saved-chart contracts; identity is never a request field.

The canonical selection is shared with chart delivery. Explicit context edits
are validated again by the same definition/dataset/filter resolver.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from near_api.schemas.common import ContractModel
from near_api.schemas.chart_selection import ChartSelection
from near_api.schemas.delivery import ChartViewResponse

SAVED_CHART_MODES = ("live", "snapshot")
"""``live`` is a working-view resolution policy (latest approved dataset at
read time, labeled); ``snapshot`` pins an owner-matched research snapshot
(NI-044): the context renders exactly the frozen snapshot's pinned dataset
version and selection, never latest."""


class SavedChartSelectionInput(ChartSelection):
    """Create-time canonical selection (half-open window rules inherited)."""

    pass


class SavedChartCreateRequest(ContractModel):
    """POST /saved-charts body (API_SPECIFICATION row, no owner field)."""

    chart_definition_version_id: UUID
    label: str | None = Field(default=None, min_length=1, max_length=200)
    selection: SavedChartSelectionInput
    mode: Literal["live", "snapshot"]
    dataset_version_id: UUID
    snapshot_id: UUID | None = None


class SavedChartUpdateRequest(ContractModel):
    """Explicit contextual edits; absence retains a field, label null clears it."""

    label: str | None = Field(default=None, min_length=1, max_length=200)
    selection: SavedChartSelectionInput | None = None
    mode: Literal["live", "snapshot"] | None = None
    dataset_version_id: UUID | None = None
    snapshot_id: UUID | None = None


class SavedChartResponse(ContractModel):
    """One owned saved chart instance (API_SPECIFICATION ``SavedChart``)."""

    id: UUID
    label: str | None
    mode: Literal["live", "snapshot"]
    chart_definition_version_id: UUID
    selection: SavedChartSelectionInput
    snapshot_id: UUID | None
    last_resolved_dataset_version_id: UUID | None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class SavedChartListResponse(ContractModel):
    """Owner-scoped saved-chart list (bounded opaque offset cursor)."""

    items: tuple[SavedChartResponse, ...]
    next_cursor: str | None


class SavedChartDetailResponse(ContractModel):
    """GET /saved-charts/{id}: the owned instance plus its resolved view.

    ``view`` is the standard public ``ChartView`` resolved through the shared
    NI-032 delivery service — for ``live`` mode against the latest approved
    dataset at read time, so live updates are labeled by the view's own
    dataset identity and ``last_resolved_dataset_version_id``.
    """

    saved_chart: SavedChartResponse
    view: ChartViewResponse
    dataset_changed: bool
