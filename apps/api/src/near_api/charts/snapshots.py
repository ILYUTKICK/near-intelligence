"""NI-044 owner-scoped immutable research snapshots, using canonical delivery.

A snapshot freezes exactly one inspected public input set: an immutable chart
definition version, one APPROVED dataset version (never ``latest``) and the
canonical selection validated against the pinned definition. The stored
``calculation_context`` pins the resolved context hash (the same canonical
algorithm as the NI-032 ChartView hash), the bound metric definition versions
and the renderer version; ``content_sha256`` is a deterministic SHA-256 over
the frozen input tuple, so re-freezing identical inputs regenerates an
identical hash and any input drift is detectable.

Invariants:

- **Immutable.** Snapshots have no update operation at any layer; the
  database grants no UPDATE to any role (migration 0013). Reading never
  mutates the row. A comparison against live is an explicit separate read
  that resolves the SAME selection against the latest approved dataset and
  never rewrites the snapshot.
- **Frozen reads.** Detail reads resolve the pinned dataset version — the
  stored selection against the stored version — so the evidence stays fixed
  through any later publication/refresh.
- **Owner-scoped.** Identity comes from the verified principal; a foreign or
  absent snapshot is the one generic 404 (no existence leak). The
  ``saved_charts`` same-owner composite FK (migration 0013) independently
  guarantees only the owner can reference a snapshot.
- **Referenced snapshots cannot disappear.** Delete checks references first
  and returns a typed 409 ``REFERENCE_IN_USE``; the database ``ON DELETE
  RESTRICT`` FK enforces the same outcome against races.
"""

from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Connection, delete, func, insert, select

from near_api.datasets import delivery
from near_api.datasets.canonical import dump_canonical, sha256_hex
from near_api.db.models import ChartDefinition, ResearchSnapshot, SavedChart
from near_api.db.security import one_or_not_found, owner_scope, scoped_page
from near_api.schemas.delivery import ChartViewResponse, ResolvedSelection
from near_api.schemas.saved_charts import SavedChartSelectionInput
from near_api.schemas.snapshots import (
    SnapshotCalculationContext, SnapshotCompareResponse, SnapshotCreateRequest,
    SnapshotDetailResponse, SnapshotResponse,
)


class SnapshotReferenceInUse(RuntimeError):
    """A referenced snapshot cannot be deleted (typed 409 for the route)."""


def _owned(connection: Connection, owner_id: UUID, snapshot_id: UUID,
           *, lock: bool = False) -> Mapping[str, Any]:
    query = select(ResearchSnapshot.__table__).where(
        ResearchSnapshot.id == snapshot_id, owner_scope(ResearchSnapshot.owner_id, owner_id))
    if lock:
        query = query.with_for_update()
    return one_or_not_found(connection.execute(query).mappings().first())


def _response(row: Mapping[str, Any]) -> SnapshotResponse:
    return SnapshotResponse.model_validate({key: row[key] for key in SnapshotResponse.model_fields})


def _resolve_view(connection: Connection, definition_version_id: UUID,
                  selection: SavedChartSelectionInput | ResolvedSelection,
                  dataset_version_id: UUID | None) -> ChartViewResponse:
    """Resolve one view through the shared NI-032 delivery.

    With ``dataset_version_id`` the view is FROZEN: the pinned version is
    required and verified to contain every required metric definition —
    never ``latest``. With ``None`` the standard live semantics apply (latest
    approved dataset at read time), which is the explicit compare-to-live
    resolution only.
    """
    row = connection.execute(select(ChartDefinition.chart_id, ChartDefinition.version)
                             .where(ChartDefinition.id == definition_version_id)).mappings().first()
    if row is None:
        raise delivery.DeliveryNotFound("chart definition was not found")
    definition = delivery.load_chart_definition(connection, row["chart_id"], row["version"])
    if (selection.end - selection.start).days > definition.available_ranges.max_days:
        raise delivery.DeliveryInvalidFilter("Selection exceeds the chart's maximum range")
    filters = selection.filters
    if not isinstance(filters, dict):
        filters = filters.model_dump()
    return delivery.build_chart_view(
        connection, chart_id=row["chart_id"], version=row["version"],
        start=selection.start, end=selection.end, dataset_version=dataset_version_id,
        filters=filters)


def _content_hash(definition_version_id: UUID, dataset_version_id: UUID,
                  selection: ResolvedSelection, calculation_context: Mapping[str, Any]) -> str:
    """Deterministic SHA-256 over the frozen input tuple (delivery._context_hash style)."""
    payload = {
        "chart_definition_version_id": str(definition_version_id),
        "dataset_version_id": str(dataset_version_id),
        "selection": {"start": selection.start.isoformat(),
                      "end": selection.end.isoformat(),
                      "frequency": selection.frequency,
                      "filters": dict(selection.filters.model_dump())},
        "calculation_context": {
            "context_hash": calculation_context["context_hash"],
            "metric_definition_versions": list(calculation_context["metric_definition_versions"]),
            "renderer_version": calculation_context["renderer_version"],
        },
    }
    return sha256_hex(dump_canonical(payload))


def owned_snapshot_reference(connection: Connection, owner_id: UUID,
                             snapshot_id: UUID | None) -> Mapping[str, Any] | None:
    """The owned snapshot row behind a saved-chart reference, or None.

    Saved-chart snapshot mode (NI-035) validates through this helper: a
    missing or foreign snapshot reference never leaks existence — the caller
    raises the typed 422 REFERENCE_INVALID for either outcome.
    """
    if snapshot_id is None:
        return None
    return connection.execute(select(ResearchSnapshot.__table__).where(
        ResearchSnapshot.id == snapshot_id,
        owner_scope(ResearchSnapshot.owner_id, owner_id))).mappings().first()


def create(connection: Connection, owner_id: UUID,
           body: SnapshotCreateRequest) -> SnapshotResponse:
    """Freeze the inspected evidence triple into one immutable snapshot row."""
    view = _resolve_view(connection, body.chart_definition_version_id,
                         body.selection, body.dataset_version_id)
    calculation_context = SnapshotCalculationContext(
        context_hash=view.context_hash,
        metric_definition_versions=tuple(
            sorted(str(item) for item in view.definition.metric_definition_ids)),
        renderer_version=view.definition.renderer_version)
    content_hash = _content_hash(body.chart_definition_version_id, body.dataset_version_id,
                                 view.selection, calculation_context.model_dump())
    row = connection.execute(insert(ResearchSnapshot).values(
        id=uuid4(), owner_id=owner_id,
        chart_definition_version_id=body.chart_definition_version_id,
        dataset_version_id=view.dataset.id,
        selection=view.selection.model_dump(mode="json"),
        calculation_context=calculation_context.model_dump(mode="json"),
        content_sha256=content_hash,
    ).returning(*ResearchSnapshot.__table__.columns)).mappings().one()
    return _response(row)


def list_snapshots(connection: Connection, owner_id: UUID, *,
                   offset: int = 0, limit: int = 20) -> tuple[tuple[SnapshotResponse, ...], int]:
    """Owner-scoped, newest-first snapshot page."""
    query = select(ResearchSnapshot.__table__)
    page = scoped_page(connection, query.order_by(ResearchSnapshot.created_at.desc(),
                                                  ResearchSnapshot.id),
                       owner_scope(ResearchSnapshot.owner_id, owner_id),
                       offset=offset, limit=limit)
    return tuple(_response(row) for row in page.items), page.total


def detail(connection: Connection, owner_id: UUID, snapshot_id: UUID) -> SnapshotDetailResponse:
    """The owned snapshot plus its FROZEN renderer view (read never mutates)."""
    row = _owned(connection, owner_id, snapshot_id)
    selection = SavedChartSelectionInput.model_validate(row["selection"])
    view = _resolve_view(connection, row["chart_definition_version_id"],
                         selection, row["dataset_version_id"])
    return SnapshotDetailResponse(snapshot=_response(row), view=view)


def compare_with_live(connection: Connection, owner_id: UUID,
                      snapshot_id: UUID) -> SnapshotCompareResponse:
    """Resolve the SAME selection against latest for an explicit comparison.

    The frozen view always resolves the pinned dataset version; the live view
    always resolves the latest approved dataset at read time (the standard
    live semantics). The snapshot row itself is never rewritten by this
    comparison.
    """
    row = _owned(connection, owner_id, snapshot_id)
    selection = SavedChartSelectionInput.model_validate(row["selection"])
    frozen_view = _resolve_view(connection, row["chart_definition_version_id"],
                                selection, row["dataset_version_id"])
    live_view = _resolve_view(connection, row["chart_definition_version_id"],
                              selection, None)
    return SnapshotCompareResponse(
        snapshot=_response(row), frozen_view=frozen_view, live_view=live_view,
        dataset_changed=row["dataset_version_id"] != live_view.dataset.id)


def remove(connection: Connection, owner_id: UUID, snapshot_id: UUID) -> None:
    """Delete an unreferenced owned snapshot; referenced snapshots are 409.

    No row lock: snapshots are immutable, and the ``saved_charts`` RESTRICT
    FK makes a concurrent reference impossible, so a racing insert either
    committed first (the count below sees it) or fails against the frozen
    row that no longer exists.
    """
    _owned(connection, owner_id, snapshot_id)
    referenced = connection.execute(
        select(func.count()).select_from(SavedChart.__table__)
        .where(SavedChart.snapshot_id == snapshot_id)).scalar_one()
    if referenced:
        raise SnapshotReferenceInUse(
            "The snapshot is referenced by a saved chart and cannot be deleted")
    connection.execute(delete(ResearchSnapshot).where(
        ResearchSnapshot.id == snapshot_id, owner_scope(ResearchSnapshot.owner_id, owner_id)))
