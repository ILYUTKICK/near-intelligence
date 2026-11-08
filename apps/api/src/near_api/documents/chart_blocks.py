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
  forward verbatim; NI-042 explicit changed/new chart blocks build a context
  from their validated inspected pin. NI-043 validates supplied observation
  claims against those server-resolved pins.
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
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import Connection, Engine

from near_api.auth.principal import Principal, get_principal, get_runtime_engine
from near_api.charts.routes import _resolve_dataset_version
from near_api.contracts import error_response
from near_api.datasets import delivery
from near_api.db.security import principal_transaction
from near_api.documents import idempotency, service
from near_api.documents.context_resolver import (
    build_resolved_context,
    load_chart_definition,
    require_approved_dataset,
    require_live_chart_mode,
    require_metric_coverage,
    resolve_revision_contexts,
    validate_selection_against_definition,
)
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
    ReferenceInvalid,
    parse_document,
)
from near_api.schemas.chart_blocks import (
    ChartBlockInsertRequest,
    ChartBlockMutationResponse,
    ChartBlockValue,
    DocumentChartViewResponse,
)
from near_api.schemas.common import ErrorDetail
from near_api.schemas.chart_selection import ChartSelection

router = APIRouter(prefix="/api", tags=["documents"])

PrincipalDependency = Annotated[Principal, Depends(get_principal)]
RuntimeEngineDependency = Annotated[Engine, Depends(get_runtime_engine)]

ROUTE_ADD_CHART_BLOCK = idempotency.ROUTE_ADD_CHART_BLOCK


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
    require_live_chart_mode(payload.mode, error_path="mode")

    definition = load_chart_definition(connection, payload.chart_definition_version_id,
                                       error_path="chart_definition_version_id")
    validate_selection_against_definition(
        definition, payload.selection.start, payload.selection.end,
        dict(payload.selection.filters))
    require_approved_dataset(connection, payload.dataset_version_id, "dataset_version_id")
    require_metric_coverage(connection, definition, payload.dataset_version_id,
                            error_path="dataset_version_id")

    block_id = uuid4()
    node = {
        "type": "liveChart",
        "attrs": {
            "block_id": str(block_id),
            "chart_definition_version_id": str(definition.id),
            "mode": payload.mode,
            "selection": payload.selection.model_dump(mode="json"),
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
    resolved_contexts = resolve_revision_contexts(connection, previous_document, previous)
    resolved_contexts[str(block_id)] = context.model_dump(mode="json")
    detail = service._commit_new_revision(connection, principal, document,
                                          canonical=canonical,
                                          resolved_contexts=resolved_contexts)
    return ChartBlockInsertion(detail=detail, block_id=block_id)


# --------------------------------------------------------------------------- #
# HTTP route
# --------------------------------------------------------------------------- #


@router.get("/documents/{document_id}/chart-view",
            response_model=DocumentChartViewResponse, operation_id="getDocumentChartView",
            summary="Inspect one canonical chart context for an owned working document",
            responses={**_PRIVATE_ERROR_RESPONSES,
                       503: {"description": "Approved chart data is unavailable"}})
def get_document_chart_view(request: Request, principal: PrincipalDependency,
                            engine: RuntimeEngineDependency, response: Response,
                            document_id: UUID, chart_definition_version_id: UUID,
                            start: date, end: date,
                            dataset_version: Annotated[str, Query(max_length=36)],
                            filters: Annotated[str | None, Query(max_length=2048)] = None,
                            ) -> DocumentChartViewResponse | JSONResponse:
    """Resolve an editor inspection through the canonical public chart adapter.

    The dataset choice is REQUIRED: normal reopen/range/filter requests send
    the observed immutable UUID; only an explicit Refresh sends ``latest``.
    Resolution does not mutate the document. A successful explicit editor
    action adopts the returned selection + dataset UUID in one undoable edit,
    and the ordinary CAS revision save validates and freezes those attrs.
    New/duplicated unsaved blocks can be inspected too, without requiring a
    persisted block id. The latest approved UUID is separate metadata so a
    publication can be signaled while the inspected data stays pinned.
    """
    with principal_transaction(engine, principal) as connection:
        # Check ownership BEFORE resolving the requested scientific reference.
        # This is the same safe404 as the document read/save routes.
        service._owned_document_row(connection, principal, document_id)
        try:
            selection = ChartSelection(start=start, end=end, frequency="day",
                                       filters=delivery.parse_filters_document(filters))
            definition = load_chart_definition(connection, chart_definition_version_id,
                                               error_path="query")
            validate_selection_against_definition(definition, start, end,
                                                   selection.filters)
            requested_version = _resolve_dataset_version(dataset_version)
            try:
                latest_version = delivery.resolve_latest_version(
                    connection, definition.required_metric_versions, use_cache=False)
            except delivery.DeliveryDataNotReady:
                if requested_version is None:
                    raise
                latest_version = None
            view = delivery.build_chart_view(
                connection, chart_id=definition.chart_id, version=definition.version,
                start=start, end=end, dataset_version=requested_version or latest_version,
                filters=dict(selection.filters))
        except ValidationError:
            return error_response(request, 422, "VALIDATION_ERROR",
                                  "Request failed validation")
        except DocumentSchemaError as error:
            return _schema_error(request, error)
    response.headers["Cache-Control"] = "no-store"
    return DocumentChartViewResponse(
        **dict(view), latest_approved_dataset_version_id=latest_version)


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
        route_key = ROUTE_ADD_CHART_BLOCK.format(document_id=document_id)
        try:
            outcome = idempotency.execute_idempotent(
                engine, principal, route_key=route_key,
                idempotency_key=key,
                request_hash=idempotency.request_fingerprint(
                    route_key, principal.id,
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
