"""Revision-checked chart block insertion with frozen inspection context (NI-041).

Implements the API_SPECIFICATION "Research documents and versions" row
``POST /documents/{id}/chart-blocks``: one confirmed "Add to research"
selection appends exactly ONE valid ``liveChart`` block to an owned document
through the canonical revision flow (NI-036) and captures the inspected
evidence context immutably. The endpoint never bypasses document validation —
the inserted node is validated by :func:`near_api.documents.schema.parse_document`
like any editor save, and the new revision carries the same projections.

Contract (API_SPECIFICATION row + protocol):

- **CAS.** ``If-Match: "<revision>"`` is required (428 without it); a stale
  revision is 409 ``REVISION_CONFLICT`` carrying ``current_revision`` for the
  owned document; one successful call creates exactly one new revision.
- **Owner.** The destination document must belong to the verified principal
  (NI-019 transaction-local identity); a foreign or absent document is the
  same generic 404 and no reference in the request can leak existence.
- **Pins are server verified.** The request carries the INSPECTED
  ``chart_definition_version_id`` and ``dataset_version_id``: the server
  verifies the definition against the NI-031 chart registry (an unknown or
  ``unavailable`` definition is rejected — unavailable charts are never
  advertised as live), pins EXACTLY the inspected dataset version (an
  unapproved one is rejected, never substituted with latest) and requires the
  pinned dataset to actually contain the chart's required metric definitions.
  Range/filter rules reuse the public chart-view validation (NI-032), so an
  inserted block and the explorer view it came from agree by construction.
- **Frozen context.** The new revision's ``resolved_contexts`` gains one
  ``ResolvedContext`` (NI-046 contract) for the inserted block, keyed by the
  server-allocated ``block_id``: the pinned definition/dataset/selection ids,
  the bound metric definition versions, the renderer version and a
  ``context_hash`` computed with the same canonical algorithm as the NI-032
  ChartView hash. Once written the context is NEVER re-resolved: a later
  source change (new dataset version, superseded definition) leaves the
  already-inserted block and its context untouched — fresher data is a new,
  explicit decision, not a silent mutation (EDITOR_SPECIFICATION "Live versus
  fixed evidence"). Whole-document saves carry unchanged chart contexts
  forward verbatim and reject changed/new chart blocks without a resolved
  context (full server-side re-resolution arrives with NI-043).
- **Idempotency.** ``Idempotency-Key: UUID`` reuses the NI-037 write-once
  replay store (migration 0009): a repeated identical owner/route/body
  request replays the ORIGINAL 201 result instead of appending a second
  block, so a timeout-after-commit retry is safe; the same key with a
  different body is 409 ``IDEMPOTENCY_CONFLICT``.
- **Snapshot mode.** ``mode:"snapshot"`` requires the same-owner research
  snapshot registry (NI-044, P1) and is rejected as an unverifiable
  reference until that task lands — never tolerated as dangling data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Annotated, Mapping
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import Connection, Engine, func, select

from near_api.auth.principal import Principal, get_principal, get_runtime_engine
from near_api.contracts import error_response
from near_api.datasets.delivery import (
    DeliveryInvalidFilter,
    _context_hash,
    validate_filters_against_schema,
)
from near_api.db.models import ChartDefinition, ChartMetric, MetricObservation
from near_api.db.security import principal_transaction
from near_api.documents import idempotency, service
# The document HTTP vocabulary (error map, ETag, summary, If-Match/replay
# handling) is shared with the NI-036/NI-037 routes module on purpose: one
# error surface, no second implementation.
from near_api.documents.routes import (
    _PRIVATE_ERROR_RESPONSES,
    _document_summary,
    _etag,
    _parse_if_match,
    _replay_response,
    _schema_error,
)
from near_api.documents.schema import (
    SCHEMA_VERSION,
    DocumentSchemaError,
    LiveChartNode,
    ReferenceInvalid,
    canonical_context_json,
    parse_document,
)
from near_api.schemas.chart_blocks import (
    ChartBlockInsertRequest,
    ChartBlockMutationResponse,
    ChartBlockValue,
)
from near_api.schemas.common import ErrorDetail
from near_api.schemas.chart_selection import ChartSelection
from near_api.schemas.delivery import ResolvedSelection

router = APIRouter(prefix="/api", tags=["documents"])

PrincipalDependency = Annotated[Principal, Depends(get_principal)]
RuntimeEngineDependency = Annotated[Engine, Depends(get_runtime_engine)]

ROUTE_ADD_CHART_BLOCK = "POST /api/documents/{document_id}/chart-blocks"


# --------------------------------------------------------------------------- #
# Registry-backed inspection inputs (one rule set for insert + save paths)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ChartDefinitionRow:
    """The registry facts the insertion and save gates verify against."""

    id: UUID
    chart_id: str
    version: int
    data_status: str
    unavailable_reason: str | None
    renderer_version: str
    max_days: int
    filter_schema: dict
    metric_definition_versions: tuple[UUID, ...]
    required_metric_versions: tuple[UUID, ...]


def load_chart_definition(connection: Connection, chart_definition_version_id: UUID,
                          *, error_path: str) -> ChartDefinitionRow:
    """Load one registered chart definition version; reject unknown/unavailable.

    An unknown definition id is a dangling reference (422 REFERENCE_INVALID,
    no registry existence leak beyond the typed reason), and an
    ``unavailable`` definition is rejected because it is never advertised as
    live (CHART_SYSTEM): a liveChart block must resolve to real data.
    """
    row = connection.execute(
        select(ChartDefinition.id, ChartDefinition.chart_id, ChartDefinition.version,
               ChartDefinition.data_status, ChartDefinition.unavailable_reason,
               ChartDefinition.renderer_version, ChartDefinition.allowed_ranges,
               ChartDefinition.filter_schema, ChartDefinition.metric_definition_ids)
        .where(ChartDefinition.id == chart_definition_version_id)
    ).mappings().first()
    if row is None:
        raise ReferenceInvalid(
            "Referenced chart definition version does not exist in the registered "
            "chart catalog",
            [(error_path, "dangling_chart_definition")])
    if row["data_status"] != "available":
        reason = row["unavailable_reason"]
        raise ReferenceInvalid(
            "The referenced chart definition is registered unavailable and is never "
            "advertised as live" + (f": {reason}" if reason else ""),
            [(error_path, "chart_unavailable")])
    ranges = row["allowed_ranges"]
    bindings = connection.execute(
        select(ChartMetric.metric_definition_id, ChartMetric.series_role)
        .where(ChartMetric.chart_definition_version_id == row["id"])
    ).all()
    return ChartDefinitionRow(
        id=row["id"], chart_id=row["chart_id"], version=row["version"],
        data_status=row["data_status"], unavailable_reason=row["unavailable_reason"],
        renderer_version=row["renderer_version"],
        max_days=int(ranges["max_days"]), filter_schema=dict(row["filter_schema"]),
        metric_definition_versions=tuple(
            UUID(item) for item in row["metric_definition_ids"]),
        required_metric_versions=tuple({metric_id for metric_id, role in bindings
                                        if role.startswith("required")}),
    )


def validate_selection_against_definition(definition: ChartDefinitionRow,
                                          start: date, end: date,
                                          filters: Mapping[str, str]) -> None:
    """Range/filter rules of one chart version (the NI-032 view rules, reused).

    The window may not exceed the definition's allowed maximum (the shared
    ``Selection`` contract already bounds it at 366 days), and the filters are validated against the
    definition's closed filter schema, so an inserted block can never carry a
    selection the explorer view itself would reject.
    """
    if (end - start).days > definition.max_days:
        raise DeliveryInvalidFilter(
            "the selection range exceeds this chart version's allowed maximum")
    validate_filters_against_schema(dict(filters), definition.filter_schema)


def require_metric_coverage(connection: Connection, definition: ChartDefinitionRow,
                            dataset_version_id: UUID, *, error_path: str) -> None:
    """The pinned dataset must contain every required metric of the chart.

    NI-032 refuses an explicit dataset version whose observations lack a
    required metric (incompatible metric versions are never mixed silently);
    the insertion pin is verified against the same rule so an embedded chart
    cannot reference a dataset that could never render it.
    """
    required = definition.required_metric_versions
    if not required:
        return
    covered = connection.execute(
        select(func.count(func.distinct(MetricObservation.metric_definition_id)))
        .where(MetricObservation.dataset_version_id == dataset_version_id,
               MetricObservation.metric_definition_id.in_(required))
    ).scalar_one()
    if covered != len(set(required)):
        raise ReferenceInvalid(
            "The pinned dataset version does not contain every required metric "
            "definition of the chart; incompatible metric versions are never mixed "
            "silently",
            [(error_path, "dataset_missing_required_metrics")])


def validate_document_chart(connection: Connection, chart: LiveChartNode) -> None:
    """Database-backed reference rules for one canonical liveChart node.

    This is the lifted NI-036 save gate: a whole-document save that carries a
    liveChart block verifies it exactly like the insertion endpoint does
    (registered available definition, allowed selection, approved pinned
    dataset with the required metrics). Snapshot mode stays gated on the
    P1 research snapshot registry (NI-044). Runs inside the save transaction.
    """
    if chart.mode == "snapshot":
        raise ReferenceInvalid(
            "Snapshot chart blocks require the research snapshot registry, which is "
            "not available yet (P1 NI-044)",
            [("content", "reference_unavailable")])
    definition = load_chart_definition(connection, chart.chart_definition_version_id,
                                       error_path="content")
    validate_selection_against_definition(
        definition, date.fromisoformat(chart.selection["start"]),
        date.fromisoformat(chart.selection["end"]),
        dict(chart.selection["filters"]))
    service.require_approved_dataset(connection, chart.observed_dataset_version_id,
                                     "liveChart.observed_dataset_version_id")
    require_metric_coverage(connection, definition,
                            chart.observed_dataset_version_id, error_path="content")


def chart_inspection_state(chart: LiveChartNode) -> tuple:
    """The inspection identity of a liveChart node.

    Everything whose change would alter the inspected evidence — and
    therefore require a NEW frozen context instead of the carried one. The
    ``block_id`` leads so the identity is keyed per block; the remaining
    fields are exactly the canonical liveChart attributes.
    """
    return (chart.block_id, chart.chart_definition_version_id, chart.mode,
            chart.selection, chart.observed_dataset_version_id, chart.snapshot_id)


# --------------------------------------------------------------------------- #
# Frozen inspection context (ResolvedContext; NI-046 contract shape)
# --------------------------------------------------------------------------- #


def _canonical_selection(selection: ChartSelection) -> dict:
    """The canonical selection JSON of a validated request Selection."""
    return {
        "start": selection.start.isoformat(),
        "end": selection.end.isoformat(),
        "frequency": selection.frequency,
        "filters": dict(selection.filters),
    }


def build_resolved_context(definition: ChartDefinitionRow, dataset_version_id: UUID,
                           selection: ChartSelection, *, resolved_at: datetime) -> dict:
    """Resolve the frozen inspection context of one inserted chart block.

    ``context_hash`` uses the NI-032 ChartView algorithm verbatim (canonical
    bytes over definition version + dataset version + canonical selection +
    sorted bound metric definition versions), so the stored context and the
    view the user inspected hash identically. The result is validated through
    :func:`near_api.documents.schema.canonical_context_json` — the canonical
    grammar stays the one authority for the stored shape.
    """
    selection_json = _canonical_selection(selection)
    metric_versions = sorted(str(item) for item in definition.metric_definition_versions)
    return canonical_context_json({
        "chart_definition_version_id": str(definition.id),
        "dataset_version_id": str(dataset_version_id),
        "selection": selection_json,
        "context_hash": _context_hash({"id": definition.id}, dataset_version_id,
                                      ResolvedSelection.model_validate(selection_json),
                                      definition.metric_definition_versions),
        "renderer_version": definition.renderer_version,
        "metric_definition_versions": metric_versions,
        "resolved_at": resolved_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }, path="resolved_context")


# --------------------------------------------------------------------------- #
# Insertion service (one confirmation = one valid block = one revision)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ChartBlockInsertion:
    """The new revision plus the server-allocated block identity."""

    detail: service.DocumentDetail
    block_id: UUID


def append_chart_block(engine: Engine, principal: Principal, document_id: UUID, *,
                       expected_revision: int,
                       payload: ChartBlockInsertRequest) -> ChartBlockInsertion:
    """Append one inspected chart block to an owned document (own transaction)."""
    with principal_transaction(engine, principal) as connection:
        return append_chart_block_in_transaction(
            connection, principal, document_id, expected_revision=expected_revision,
            payload=payload)


def append_chart_block_in_transaction(connection: Connection, principal: Principal,
                                      document_id: UUID, *, expected_revision: int,
                                      payload: ChartBlockInsertRequest,
                                      ) -> ChartBlockInsertion:
    """Transaction-scoped :func:`append_chart_block` (used by the idempotent route).

    One transaction: row lock -> CAS -> registry/dataset pin verification ->
    server-built canonical node insertion -> full canonical validation ->
    context resolution -> version + projections + pointer (the shared
    :func:`near_api.documents.service` revision tail). Any failure rolls back
    everything, so a rejected insertion leaves zero rows.
    """
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) \
            or expected_revision < 1:
        raise DocumentSchemaError("If-Match must be the quoted current revision",
                                  [("If-Match", "invalid_revision")])
    document = service._locked_document(connection, principal, document_id)
    if document.revision != expected_revision:
        raise service.RevisionConflict(document.revision)
    if document.current_version_id is None:
        raise ValueError(f"Document {document_id} has no current revision")
    previous = service._version_row(connection, document.current_version_id)
    previous_document = parse_document(previous.content)

    if payload.after_block_id is not None \
            and payload.after_block_id not in previous_document.block_ids:
        raise ReferenceInvalid(
            "after_block_id does not reference a top-level block of this document",
            [("after_block_id", "dangling_after_block_reference")])
    # Snapshot mode is an unverifiable reference until P1 NI-044 lands (the same
    # gate the whole-document save path enforces for canonical nodes).
    if payload.mode == "snapshot":
        raise ReferenceInvalid(
            "Snapshot chart blocks require the research snapshot registry, which is "
            "not available yet (P1 NI-044)",
            [("mode", "reference_unavailable")])

    definition = load_chart_definition(connection, payload.chart_definition_version_id,
                                       error_path="chart_definition_version_id")
    validate_selection_against_definition(
        definition, payload.selection.start, payload.selection.end,
        dict(payload.selection.filters))
    service.require_approved_dataset(connection, payload.dataset_version_id,
                                     "dataset_version_id")
    require_metric_coverage(connection, definition, payload.dataset_version_id,
                            error_path="dataset_version_id")

    block_id = uuid4()
    node = {
        "type": "liveChart",
        "attrs": {
            "block_id": str(block_id),
            "chart_definition_version_id": str(definition.id),
            "mode": payload.mode,
            "selection": _canonical_selection(payload.selection),
            "observed_dataset_version_id": str(payload.dataset_version_id),
        },
    }
    content = list(previous.content["content"])
    position = len(content)
    if payload.after_block_id is not None:
        position = next(index for index, block in enumerate(content)
                        if block["attrs"]["block_id"] == str(payload.after_block_id)) + 1
    content.insert(position, node)
    canonical = parse_document({
        "schema_version": SCHEMA_VERSION, "type": "doc", "content": content,
    })
    context = build_resolved_context(definition, payload.dataset_version_id,
                                     payload.selection, resolved_at=datetime.now(UTC))
    resolved_contexts = dict(previous.resolved_contexts or {})
    resolved_contexts[str(block_id)] = context
    detail = service._commit_new_revision(connection, principal, document,
                                          canonical=canonical,
                                          resolved_contexts=resolved_contexts)
    return ChartBlockInsertion(detail=detail, block_id=block_id)


# --------------------------------------------------------------------------- #
# HTTP route
# --------------------------------------------------------------------------- #


@router.post("/documents/{document_id}/chart-blocks",
             response_model=ChartBlockMutationResponse, operation_id="addChartBlock",
             status_code=201,
             summary="Append one inspected chart block to an owned document "
                     "(compare-and-set via If-Match)",
             responses=_PRIVATE_ERROR_RESPONSES)
def add_chart_block(request: Request, principal: PrincipalDependency,
                    engine: RuntimeEngineDependency, response: Response,
                    document_id: UUID, payload: ChartBlockInsertRequest,
                    if_match: Annotated[str | None, Header()] = None,
                    idempotency_key: Annotated[str | None, Header()] = None,
                    ) -> ChartBlockMutationResponse | JSONResponse:
    """Append one valid liveChart block with its frozen inspection context.

    With an ``Idempotency-Key`` the response snapshot is stored in the write
    transaction (NI-037 store), so a repeated identical owner/route/body
    request replays the original 201 (same revision, no second block)
    instead of a spurious 409 against the advanced document.
    """
    expected = _parse_if_match(if_match)
    if expected is None:
        return error_response(request, 428, "PRECONDITION_REQUIRED",
                              "If-Match with the current document revision is required")
    try:
        key = idempotency.parse_idempotency_key(idempotency_key)
    except DocumentSchemaError as error:
        return _schema_error(request, error)

    def execute(connection):
        insertion = append_chart_block_in_transaction(
            connection, principal, document_id, expected_revision=expected,
            payload=payload)
        body = ChartBlockMutationResponse(
            document=_document_summary(insertion.detail.document),
            value=ChartBlockValue(block_id=insertion.block_id),
        ).model_dump(mode="json")
        return 201, body

    if key is not None:
        try:
            outcome = idempotency.execute_idempotent(
                engine, principal, route_key=ROUTE_ADD_CHART_BLOCK,
                idempotency_key=key,
                request_hash=idempotency.request_fingerprint(
                    ROUTE_ADD_CHART_BLOCK, principal.id,
                    payload.model_dump(mode="json")),
                operation=execute)
        except idempotency.IdempotencyConflict:
            return error_response(
                request, 409, "IDEMPOTENCY_CONFLICT",
                "This Idempotency-Key was already used with a different request; "
                "a new key is required for a new payload")
        except service.RevisionConflict as conflict:
            # Owned-document 409: the current revision is included for the owner.
            return error_response(
                request, 409, "REVISION_CONFLICT", str(conflict),
                details=(ErrorDetail(path="If-Match",
                                     reason=f"current_revision:{conflict.current_revision}"),))
        except DocumentSchemaError as error:
            # Nothing was stored: a rejected insertion stays retryable with the key.
            return _schema_error(request, error)
        if outcome.replay:
            return _replay_response(outcome, etag_revision_path=("document", "revision"))
        response.headers["Cache-Control"] = "no-store"
        response.headers["ETag"] = _etag(int(outcome.body["document"]["revision"]))
        return ChartBlockMutationResponse.model_validate(outcome.body)
    try:
        insertion = append_chart_block(engine, principal, document_id,
                                       expected_revision=expected, payload=payload)
    except service.RevisionConflict as conflict:
        return error_response(
            request, 409, "REVISION_CONFLICT", str(conflict),
            details=(ErrorDetail(path="If-Match",
                                 reason=f"current_revision:{conflict.current_revision}"),))
    except DocumentSchemaError as error:
        return _schema_error(request, error)
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = _etag(insertion.detail.document.revision)
    return ChartBlockMutationResponse(
        document=_document_summary(insertion.detail.document),
        value=ChartBlockValue(block_id=insertion.block_id))
