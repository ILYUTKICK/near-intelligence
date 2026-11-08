"""NI-035 owner-scoped saved analytical contexts, using canonical delivery.

Definitions remain global/immutable; instance mutations never copy or delete
registry rows. Only metadata/context edits affect recency. Successful live
reads record the resolved dataset without reordering the private list.
"""

from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Connection, delete, insert, or_, select, update

from near_api.charts.registry import CATEGORIES
from near_api.datasets import delivery
from near_api.db.models import ChartDefinition, SavedChart
from near_api.db.security import one_or_not_found, owner_scope, scoped_page
from near_api.schemas.saved_charts import (
    SavedChartCreateRequest, SavedChartDetailResponse, SavedChartResponse,
    SavedChartUpdateRequest, SavedChartSelectionInput,
)

from near_api.schemas.delivery import ChartViewResponse, ResolvedSelection


def _owned(connection: Connection, owner_id: UUID, instance_id: UUID, *, lock: bool = False) -> Mapping[str, Any]:
    query = select(SavedChart.__table__).where(
        SavedChart.id == instance_id, owner_scope(SavedChart.owner_id, owner_id))
    if lock:
        query = query.with_for_update()
    return one_or_not_found(connection.execute(query).mappings().first())


def _response(row: Mapping[str, Any]) -> SavedChartResponse:
    return SavedChartResponse.model_validate({key: row[key] for key in SavedChartResponse.model_fields})


def _mode(mode: str | None, snapshot_id: UUID | None) -> None:
    # No private snapshot table/ownership contract exists in P0. Deny it at
    # both service and DB boundaries; NI-044 may lift this with real FKs.
    if mode != "live" or snapshot_id is not None:
        raise delivery.DeliveryReferenceInvalid("Explicit snapshots are unavailable in P0")


def _resolve(connection: Connection, definition_id: UUID,
             selection: SavedChartSelectionInput | ResolvedSelection,
             dataset_id: UUID | None) -> ChartViewResponse:
    row = connection.execute(select(ChartDefinition.chart_id, ChartDefinition.version)
                             .where(ChartDefinition.id == definition_id)).mappings().first()
    if row is None:
        raise delivery.DeliveryNotFound()
    definition = delivery.load_chart_definition(connection, row["chart_id"], row["version"])
    if (selection.end - selection.start).days > definition.available_ranges.max_days:
        raise delivery.DeliveryInvalidFilter("Selection exceeds the chart's maximum range")
    filters = selection.filters
    if not isinstance(filters, dict):
        filters = filters.model_dump()
    return delivery.build_chart_view(
        connection, chart_id=row["chart_id"], version=row["version"],
        start=selection.start, end=selection.end, dataset_version=dataset_id, filters=filters)


def create(connection: Connection, owner_id: UUID, body: SavedChartCreateRequest) -> SavedChartResponse:
    _mode(body.mode, body.snapshot_id)
    view = _resolve(connection, body.chart_definition_version_id, body.selection, body.dataset_version_id)
    row = connection.execute(insert(SavedChart).values(
        id=uuid4(), owner_id=owner_id, chart_definition_version_id=body.chart_definition_version_id,
        label=body.label, mode=body.mode, selection=view.selection.model_dump(mode="json"),
        last_resolved_dataset_version_id=view.dataset.id,
    ).returning(*SavedChart.__table__.columns)).mappings().one()
    return _response(row)


def list_saved(connection: Connection, owner_id: UUID, *, search: str | None = None, category: str | None = None,
               offset: int = 0, limit: int = 20) -> tuple[tuple[SavedChartResponse, ...], int]:
    query = select(SavedChart.__table__).join(
        ChartDefinition, ChartDefinition.id == SavedChart.chart_definition_version_id)
    if category is not None:
        if category not in CATEGORIES:
            raise delivery.DeliveryInvalidFilter("Unknown chart category")
        query = query.where(ChartDefinition.category == category)
    if search:
        # Literal substring search: wildcard characters never broaden a query.
        query = query.where(or_(SavedChart.label.icontains(search, autoescape=True),
                                ChartDefinition.title.icontains(search, autoescape=True)))
    page = scoped_page(connection, query.order_by(SavedChart.updated_at.desc(), SavedChart.id),
                       owner_scope(SavedChart.owner_id, owner_id), offset=offset, limit=limit)
    return tuple(_response(row) for row in page.items), page.total


def detail(connection: Connection, owner_id: UUID, instance_id: UUID) -> SavedChartDetailResponse:
    row = _owned(connection, owner_id, instance_id, lock=True)
    saved = _response(row)
    view = _resolve(connection, saved.chart_definition_version_id, saved.selection, None)
    changed = saved.last_resolved_dataset_version_id != view.dataset.id
    connection.execute(update(SavedChart).where(
        SavedChart.id == instance_id, owner_scope(SavedChart.owner_id, owner_id))
        .values(last_resolved_dataset_version_id=view.dataset.id))
    return SavedChartDetailResponse(saved_chart=saved.model_copy(update={
        "last_resolved_dataset_version_id": view.dataset.id}), view=view, dataset_changed=changed)


def edit(connection: Connection, owner_id: UUID, instance_id: UUID, body: SavedChartUpdateRequest) -> SavedChartResponse:
    row = _owned(connection, owner_id, instance_id, lock=True)
    changes = body.model_dump(exclude_unset=True)
    if any(changes.get(key, "absent") is None for key in ("selection", "mode", "dataset_version_id")):
        raise delivery.DeliveryReferenceInvalid("Context fields cannot be null")
    mode = body.mode if "mode" in changes else row["mode"]
    _mode(mode, body.snapshot_id if "snapshot_id" in changes else row["snapshot_id"])
    values = {key: changes[key] for key in ("label", "mode") if key in changes}
    if any(key in changes for key in ("selection", "dataset_version_id")):
        selection = body.selection or SavedChartSelectionInput.model_validate(row["selection"])
        view = _resolve(connection, row["chart_definition_version_id"], selection,
                        body.dataset_version_id or row["last_resolved_dataset_version_id"])
        values.update(selection=view.selection.model_dump(mode="json"),
                      last_resolved_dataset_version_id=view.dataset.id)
    if not values:
        return _response(row)
    updated = connection.execute(update(SavedChart).where(
        SavedChart.id == instance_id, owner_scope(SavedChart.owner_id, owner_id))
        .values(**values).returning(*SavedChart.__table__.columns)).mappings().one()
    return _response(updated)


def remove(connection: Connection, owner_id: UUID, instance_id: UUID) -> None:
    _owned(connection, owner_id, instance_id, lock=True)
    connection.execute(delete(SavedChart).where(
        SavedChart.id == instance_id, owner_scope(SavedChart.owner_id, owner_id)))
