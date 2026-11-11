"""NI-044 private research-snapshot contracts; identity is never a request field.

A snapshot freezes one inspected public input set (immutable chart definition
version + approved dataset version + canonical selection) with the resolved
calculation context and a deterministic content hash. The freeze body is
exactly the inspected evidence triple from API_SPECIFICATION.md — no owner
field, no label: identification comes from the pinned definition the owner
can resolve, and mutations of a snapshot do not exist.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import AwareDatetime, Field

from near_api.schemas.common import ContractModel
from near_api.schemas.delivery import ChartViewResponse
from near_api.schemas.saved_charts import SavedChartSelectionInput


class SnapshotCalculationContext(ContractModel):
    """Frozen calculation inputs recorded at freeze time (immutable)."""

    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    metric_definition_versions: tuple[str, ...] = Field(min_length=1)
    renderer_version: str = Field(min_length=1, max_length=80)


class SnapshotCreateRequest(ContractModel):
    """POST /api/snapshots body (API_SPECIFICATION row, no owner field)."""

    chart_definition_version_id: UUID
    dataset_version_id: UUID
    selection: SavedChartSelectionInput


class SnapshotResponse(ContractModel):
    """One owned immutable research snapshot (DATABASE_SCHEMA row)."""

    id: UUID
    chart_definition_version_id: UUID
    dataset_version_id: UUID
    selection: SavedChartSelectionInput
    calculation_context: SnapshotCalculationContext
    artifact_id: UUID | None
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: AwareDatetime


class SnapshotListResponse(ContractModel):
    """Owner-scoped snapshot list (bounded opaque offset cursor)."""

    items: tuple[SnapshotResponse, ...]
    next_cursor: str | None


class SnapshotDetailResponse(ContractModel):
    """GET /api/snapshots/{id}: the snapshot plus its FROZEN ChartView.

    ``view`` resolves the pinned dataset version and stored selection through
    the shared NI-032 delivery service — never the latest dataset — so the
    frozen evidence stays byte-identical through any later refresh.
    """

    snapshot: SnapshotResponse
    view: ChartViewResponse


class SnapshotCompareResponse(ContractModel):
    """GET /api/snapshots/{id}/compare-live: frozen view plus the live view.

    ``live_view`` resolves the SAME selection against the latest approved
    dataset for the explicit comparison only; the snapshot row itself is
    never rewritten by a comparison.
    """

    snapshot: SnapshotResponse
    frozen_view: ChartViewResponse
    live_view: ChartViewResponse
    dataset_changed: bool
