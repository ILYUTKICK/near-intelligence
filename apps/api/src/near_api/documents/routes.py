"""Document HTTP routes (NI-036 revision service + NI-037 CRUD and versions).

Implements the "Research documents and versions" rows of API_SPECIFICATION:
list/create/get/save (NI-036) plus rename (PATCH), delete (DELETE), version
listing/detail (GET) and Idempotency-Key replay on the create/save POSTs
(NI-037). Every route authenticates through ``get_principal`` (NI-018), opens
the transaction-local verified identity (``principal_transaction``, NI-019)
and emits ``Cache-Control: no-store`` — private content is never cacheable.

Compare-and-set: create/get return ``ETag: "<revision>"``; every document
mutation (save, rename, delete) REQUIRES ``If-Match: "<revision>"`` (428
without it), rejects a stale revision with 409 REVISION_CONFLICT (including
the current revision for the owned document only) and never overwrites.
Not-owned and absent ids are the same generic 404 on every route.

Idempotency (NI-037): ``POST /documents`` and ``POST /documents/{id}/versions``
honor ``Idempotency-Key: UUID`` — the response snapshot is committed in the
same transaction as the write, so a repeated identical owner/route/body
request replays the ORIGINAL result (24h) instead of creating a second
document or revision; the same key with a different body is a 409
IDEMPOTENCY_CONFLICT. Failures are never stored, so they stay retryable.
"""

from __future__ import annotations

import base64
import csv
from collections.abc import Callable
from io import StringIO
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Connection, Engine

from near_api.auth.principal import Principal, get_principal, get_runtime_engine
from near_api.contracts import error_response
from near_api.datasets.canonical import canonical_timestamp, dump_canonical
from near_api.db.security import principal_transaction
from near_api.documents import idempotency, service
from near_api.documents.context_resolver import ReconstructionError, reconstruct_revision_chart
from near_api.documents.schema import (
    SCHEMA_VERSION,
    DocumentSchemaError,
    DocumentTooLarge,
    ReferenceInvalid,
)
from near_api.repositories.documents import DocumentRow, get_version
from near_api.schemas.common import ContractModel, ErrorDetail, ErrorResponse
from near_api.schemas.delivery import ChartViewResponse
from near_api.schemas.documents import (
    DocumentCreateRequest,
    DocumentListResponse,
    DocumentRenameRequest,
    DocumentResponse,
    DocumentSaveRequest,
    DocumentSaveResponse,
    VersionDetailResponse,
    VersionListResponse,
    VersionSummaryResponse,
)
from near_api.schemas.home import DocumentProgress, DocumentSummary

router = APIRouter(prefix="/api", tags=["documents"])

PrincipalDependency = Annotated[Principal, Depends(get_principal)]
RuntimeEngineDependency = Annotated[Engine, Depends(get_runtime_engine)]

_PRIVATE_ERROR_RESPONSES = {
    status: {"model": ErrorResponse, "description": description}
    for status, description in (
        (401, "Missing or invalid session"),
        (403, "Verified account is disabled"),
        (404, "Referenced target does not exist for this owner"),
        (409, "Revision conflict (document moved) or Idempotency-Key reused "
              "with a different request"),
        (413, "Document exceeds a hard size limit"),
        (422, "Request failed validation or references an unavailable target"),
        (428, "If-Match precondition is required"),
    )
}

_HISTORICAL_CHART_PATH = "/documents/{document_id}/versions/{version_id}/chart-blocks/{block_id}"
_HISTORICAL_CHART_ERRORS = {
    status: _PRIVATE_ERROR_RESPONSES[status] for status in (401, 403, 404, 422)
} | {409: {"model": ErrorResponse, "description": "Frozen chart evidence could not be reconstructed"}}


def _etag(revision: int) -> str:
    return f'"{revision}"'


def _document_summary(row: DocumentRow) -> DocumentSummary:
    return DocumentSummary(
        id=row.id, title=row.title, revision=row.revision,
        schema_version=row.schema_version, current_version_id=row.current_version_id,
        created_at=row.created_at, updated_at=row.updated_at,
        # Work-completion counters stay the documented zero until the home/list
        # wiring consumes the NI-036 projections (NI-024/NI-037 scope).
        progress=DocumentProgress(headings=0, charts=0, insights=0),
    )


def _document_response(detail: service.DocumentDetail) -> DocumentResponse:
    return DocumentResponse(**_document_summary(detail.document).model_dump(),
                            content=detail.content,
                            resolved_contexts=detail.resolved_contexts)


def _document_save_response(detail: service.DocumentDetail) -> DocumentSaveResponse:
    version = detail.version
    return DocumentSaveResponse(
        version=VersionDetailResponse(
            id=version.id, document_id=version.document_id, revision=version.revision,
            schema_version=version.schema_version, content_sha256=version.content_sha256,
            created_at=version.created_at, content=detail.content,
            resolved_contexts=detail.resolved_contexts),
        document=_document_summary(detail.document))


def _schema_error(request: Request, error: DocumentSchemaError):
    """Map canonical validation failures to their typed error envelope."""
    if isinstance(error, DocumentTooLarge):
        status, code = 413, "PAYLOAD_TOO_LARGE"
    elif isinstance(error, ReferenceInvalid):
        status, code = 422, "REFERENCE_INVALID"
    else:
        status, code = 422, "VALIDATION_ERROR"
    details = tuple(ErrorDetail(path=path, reason=reason)
                    for path, reason in error.details)
    return error_response(request, status, code, str(error), details=details)


def _decode_cursor(cursor: str | None) -> int:
    """Decode the opaque page cursor (a bounded non-negative offset)."""
    if cursor is None:
        return 0
    try:
        value = int(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii"))
    except (ValueError, UnicodeError, base64.binascii.Error):
        raise HTTPException(422, "Request failed validation") from None
    if value < 0 or value > 10**9:
        raise HTTPException(422, "Request failed validation")
    return value


def _encode_cursor(offset: int) -> str:
    """Encode the next page offset as an opaque bounded cursor."""
    return base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii")


def _parse_if_match(if_match: str | None) -> int | None:
    """Parse If-Match: exactly the quoted current revision; None when unusable.

    HTTP If-Match is a quoted entity tag; bare numbers and weak validators
    (W/"n") are precondition failures, not revision numbers.
    """
    if if_match is None:
        return None
    value = if_match.strip()
    if len(value) < 2 or not value.startswith('"') or not value.endswith('"'):
        return None
    inner = value[1:-1]
    if not inner or not inner.isascii() or not inner.isdigit():
        return None
    return int(inner)


def _replay_response(outcome: idempotency.IdempotentOutcome, *,
                     etag_revision_path: tuple) -> JSONResponse:
    """Re-emit the stored original result of an idempotent write.

    The snapshot is returned byte-for-byte with no-store and the ETag derived
    from the recorded body (the client must never guess the new revision). A
    missing/unreadable revision field simply omits the ETag — the stored body
    itself is always authoritative.
    """
    revision: int | None = outcome.body
    for key in etag_revision_path:
        if not isinstance(revision, dict) or key not in revision:
            revision = None
            break
        revision = revision[key]
    headers = {"Cache-Control": "no-store"}
    if isinstance(revision, int) and not isinstance(revision, bool):
        headers["ETag"] = _etag(revision)
    return JSONResponse(status_code=outcome.status, content=outcome.body,
                        headers=headers)


def mutate_document_annotation(
    request: Request, engine: Engine, principal: Principal, *,
    route: str, status: int, if_match: str | None, idempotency_key: str | None,
    payload: ContractModel | None, response_model: type[DocumentSaveResponse],
    operation: Callable[[Connection, int], tuple[service.DocumentDetail, ContractModel]],
) -> JSONResponse:
    """Apply a revision mutation and record the same response used on replay."""
    expected = _parse_if_match(if_match)
    if expected is None:
        return error_response(request, 428, "PRECONDITION_REQUIRED",
                              "If-Match with the current document revision is required")

    def execute(connection: Connection) -> tuple[int, dict]:
        detail, value = operation(connection, expected)
        saved = _document_save_response(detail)
        result = response_model.model_validate({
            "document": saved.document, "version": saved.version, "value": value,
        })
        return status, result.model_dump(mode="json")

    try:
        key = idempotency.parse_idempotency_key(idempotency_key)
        if key is None:
            with principal_transaction(engine, principal) as connection:
                response_status, body = execute(connection)
            outcome = idempotency.IdempotentOutcome(False, response_status, body)
        else:
            route_key = f"{request.method} /api{route}"
            request_body = payload.model_dump(mode="json", exclude_unset=True) if payload is not None else {}
            outcome = idempotency.execute_idempotent(
                engine, principal, route_key=route_key, idempotency_key=key,
                request_hash=idempotency.request_fingerprint(route_key, principal.id, request_body),
                operation=execute)
    except idempotency.IdempotencyConflict as error:
        return error_response(request, 409, "IDEMPOTENCY_CONFLICT", str(error))
    except service.RevisionConflict as conflict:
        return error_response(
            request, 409, "REVISION_CONFLICT", str(conflict),
            details=(ErrorDetail(path="If-Match",
                                 reason=f"current_revision:{conflict.current_revision}"),))
    except service.ReferenceInUse as error:
        return error_response(
            request, 409, "REFERENCE_IN_USE", str(error),
            details=tuple(ErrorDetail(path=path, reason=reason) for path, reason in error.details))
    except DocumentSchemaError as error:
        return _schema_error(request, error)
    return _replay_response(outcome, etag_revision_path=("document", "revision"))


@router.get("/documents", response_model=DocumentListResponse, operation_id="listDocuments",
            summary="Owner-scoped document list", responses=_PRIVATE_ERROR_RESPONSES)
def list_documents(principal: PrincipalDependency, engine: RuntimeEngineDependency,
                   response: Response, q: Annotated[str | None, Query(max_length=200)] = None,
                   cursor: Annotated[str | None, Query(max_length=64)] = None,
                   limit: Annotated[int | None, Query(ge=1, le=100)] = None,
                   ) -> DocumentListResponse:
    """List the verified principal's documents, newest first, owner-scoped."""
    offset = _decode_cursor(cursor)
    page = service.list_document_details(engine, principal, search=q,
                                         limit=limit, offset=offset)
    response.headers["Cache-Control"] = "no-store"
    next_cursor = _encode_cursor(page.offset + page.limit) \
        if page.offset + page.limit < page.total else None
    return DocumentListResponse(
        items=tuple(_document_summary(item) for item in page.items),
        next_cursor=next_cursor)


@router.post("/documents", response_model=DocumentResponse, operation_id="createDocument",
             status_code=201, summary="Create an owned document with its first revision",
             responses=_PRIVATE_ERROR_RESPONSES)
def create_document(request: Request, principal: PrincipalDependency,
                    engine: RuntimeEngineDependency, response: Response,
                    payload: DocumentCreateRequest,
                    idempotency_key: Annotated[str | None, Header()] = None):
    """Create an owned document whose first revision is the empty document.

    With an ``Idempotency-Key`` header the created result is stored in the
    write transaction and a repeated identical owner/route/body request
    replays the original 201 response (24h) instead of creating a second
    document; the same key with a different body is a 409 idempotency
    collision.
    """
    if payload.template_id is not None:
        # P1 templates are feature-gated: 422 FEATURE_UNAVAILABLE, never a
        # simulated template (API_SPECIFICATION).
        return error_response(request, 422, "FEATURE_UNAVAILABLE",
                              "Document templates are not available yet")
    try:
        key = idempotency.parse_idempotency_key(idempotency_key)
    except DocumentSchemaError as error:
        return _schema_error(request, error)
    if key is not None:
        try:
            outcome = idempotency.execute_idempotent(
                engine, principal, route_key=idempotency.ROUTE_CREATE_DOCUMENT,
                idempotency_key=key,
                request_hash=idempotency.request_fingerprint(
                    idempotency.ROUTE_CREATE_DOCUMENT, principal.id,
                    payload.model_dump(mode="json")),
                operation=lambda connection: (
                    201, _document_response(service.create_document_in_transaction(
                        connection, principal, title=payload.title)
                    ).model_dump(mode="json")))
        except idempotency.IdempotencyConflict:
            return error_response(
                request, 409, "IDEMPOTENCY_CONFLICT",
                "This Idempotency-Key was already used with a different request; "
                "a new key is required for a new payload")
        except DocumentSchemaError as error:
            # Nothing was stored: a failed create stays retryable with the key.
            return _schema_error(request, error)
        if outcome.replay:
            return _replay_response(outcome, etag_revision_path=("revision",))
        response.headers["Cache-Control"] = "no-store"
        response.headers["ETag"] = _etag(int(outcome.body["revision"]))
        return DocumentResponse.model_validate(outcome.body)
    try:
        detail = service.create_document(engine, principal, title=payload.title)
    except DocumentSchemaError as error:
        return _schema_error(request, error)
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = _etag(detail.document.revision)
    return _document_response(detail)


@router.get("/documents/{document_id}", response_model=DocumentResponse,
            operation_id="getDocument", summary="Fetch an owned document with content",
            responses=_PRIVATE_ERROR_RESPONSES)
def get_document(principal: PrincipalDependency, engine: RuntimeEngineDependency,
                 response: Response, document_id: UUID) -> DocumentResponse:
    """Return the owned document with its current canonical content and ETag."""
    detail = service.get_document_detail(engine, principal, document_id)
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = _etag(detail.document.revision)
    return _document_response(detail)


@router.patch("/documents/{document_id}", response_model=DocumentSummary,
              operation_id="renameDocument",
              summary="Rename an owned document (a title change creates a new revision)",
              responses=_PRIVATE_ERROR_RESPONSES)
def rename_document(request: Request, principal: PrincipalDependency,
                    engine: RuntimeEngineDependency, response: Response,
                    document_id: UUID, payload: DocumentRenameRequest,
                    if_match: Annotated[str | None, Header()] = None) -> DocumentSummary:
    """Rename the owned document; the title change is a full new revision."""
    expected = _parse_if_match(if_match)
    if expected is None:
        return error_response(request, 428, "PRECONDITION_REQUIRED",
                              "If-Match with the current document revision is required")
    try:
        detail = service.rename_document(engine, principal, document_id,
                                         expected_revision=expected,
                                         title=payload.title)
    except service.RevisionConflict as conflict:
        # Owned-document 409: the current revision is included for the owner.
        return error_response(
            request, 409, "REVISION_CONFLICT", str(conflict),
            details=(ErrorDetail(path="If-Match",
                                 reason=f"current_revision:{conflict.current_revision}"),))
    except DocumentSchemaError as error:
        return _schema_error(request, error)
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = _etag(detail.document.revision)
    return _document_summary(detail.document)


@router.delete("/documents/{document_id}", status_code=204, operation_id="deleteDocument",
               summary="Delete an owned document with its private revisions and projections",
               responses=_PRIVATE_ERROR_RESPONSES)
def delete_document(request: Request, principal: PrincipalDependency,
                    engine: RuntimeEngineDependency, document_id: UUID,
                    if_match: Annotated[str | None, Header()] = None) -> Response:
    """Delete the owned document; private children cascade, scientific data stays."""
    expected = _parse_if_match(if_match)
    if expected is None:
        return error_response(request, 428, "PRECONDITION_REQUIRED",
                              "If-Match with the current document revision is required")
    try:
        service.delete_document(engine, principal, document_id,
                                expected_revision=expected)
    except service.RevisionConflict as conflict:
        return error_response(
            request, 409, "REVISION_CONFLICT", str(conflict),
            details=(ErrorDetail(path="If-Match",
                                 reason=f"current_revision:{conflict.current_revision}"),))
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.get("/documents/{document_id}/versions", response_model=VersionListResponse,
            operation_id="listDocumentVersions",
            summary="List an owned document's immutable revisions (newest first)",
            responses=_PRIVATE_ERROR_RESPONSES)
def list_document_versions(principal: PrincipalDependency, engine: RuntimeEngineDependency,
                           response: Response, document_id: UUID,
                           cursor: Annotated[str | None, Query(max_length=64)] = None,
                           limit: Annotated[int | None, Query(ge=1, le=100)] = None,
                           ) -> VersionListResponse:
    """Page the owned document's revisions over the stable revision DESC order."""
    offset = _decode_cursor(cursor)
    page = service.list_document_versions(engine, principal, document_id,
                                          limit=limit, offset=offset)
    response.headers["Cache-Control"] = "no-store"
    next_cursor = _encode_cursor(page.offset + page.limit) \
        if page.offset + page.limit < page.total else None
    return VersionListResponse(
        items=tuple(VersionSummaryResponse(
            id=row["id"], document_id=row["document_id"], revision=row["revision"],
            schema_version=row["schema_version"],
            content_sha256=row["content_sha256"], created_at=row["created_at"])
            for row in page.items),
        next_cursor=next_cursor)


@router.get("/documents/{document_id}/versions/{version_id}",
            response_model=VersionDetailResponse, operation_id="getDocumentVersion",
            summary="Fetch one immutable revision of an owned document",
            responses=_PRIVATE_ERROR_RESPONSES)
def get_document_version(principal: PrincipalDependency, engine: RuntimeEngineDependency,
                         response: Response, document_id: UUID, version_id: UUID,
                         ) -> VersionDetailResponse:
    """Return the revision only through its owned parent document."""
    row = service.get_document_version(engine, principal, document_id, version_id)
    response.headers["Cache-Control"] = "no-store"
    return VersionDetailResponse(
        id=row.id, document_id=row.document_id, revision=row.revision,
        schema_version=row.schema_version, content_sha256=row.content_sha256,
        created_at=row.created_at, content=row.content,
        resolved_contexts=row.resolved_contexts or {})


def _read_historical_chart(request: Request, engine: Engine, principal: Principal,
                           document_id: UUID, version_id: UUID, block_id: UUID,
                           ) -> ChartViewResponse | JSONResponse:
    try:
        with principal_transaction(engine, principal) as connection:
            version = get_version(connection, principal, document_id, version_id)
            if request.query_params:
                raise HTTPException(422, "Historical chart reads take no query parameters")
            return reconstruct_revision_chart(connection, version, block_id)
    except ReconstructionError as error:
        return error_response(
            request, 409, "RECONSTRUCTION_ERROR", str(error),
            details=(ErrorDetail(path="chart_block", reason=error.reason),))


@router.get(_HISTORICAL_CHART_PATH + "/view",
            response_model=ChartViewResponse, operation_id="getDocumentVersionChartView",
            summary="Reconstruct one chart from an owned immutable revision",
            responses=_HISTORICAL_CHART_ERRORS)
def get_document_version_chart_view(
    request: Request, principal: PrincipalDependency, engine: RuntimeEngineDependency,
    response: Response, document_id: UUID, version_id: UUID, block_id: UUID,
) -> ChartViewResponse | JSONResponse:
    view = _read_historical_chart(request, engine, principal, document_id, version_id, block_id)
    response.headers["Cache-Control"] = "no-store"
    return view


def _chart_csv(view: ChartViewResponse) -> str:
    """Serialize the exact resolved points in canonical series/period order."""
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow((
        "chart_definition_version_id", "dataset_version_id", "dataset_content_sha256",
        "renderer_version", "context_hash", "selection_start", "selection_end",
        "frequency", "filters", "metric_id", "metric_definition_version_id", "unit",
        "period_start", "period_end", "value", "quality_status", "bound_kind", "reasons",
        "coverage_observed", "coverage_expected",
    ))
    context = (
        view.definition.id, view.dataset.id, view.dataset.content_sha256,
        view.definition.renderer_version, view.context_hash, view.selection.start,
        view.selection.end, view.selection.frequency,
        dump_canonical(view.selection.filters.model_dump()).decode("utf-8"),
    )
    for series in view.series:
        metric = (series.metric.metric_id, series.metric.id, series.metric.unit)
        for point in series.points:
            writer.writerow((
                *context, *metric, canonical_timestamp(point.start), canonical_timestamp(point.end),
                point.value, point.quality.status, point.quality.bound_kind,
                dump_canonical(point.quality.reasons).decode("utf-8"),
                point.quality.coverage.observed, point.quality.coverage.expected,
            ))
    return output.getvalue()


@router.get(_HISTORICAL_CHART_PATH + "/csv", response_class=Response,
            operation_id="getDocumentVersionChartCsv",
            summary="Download exact chart data from an owned immutable revision",
            responses={**_HISTORICAL_CHART_ERRORS,
                       200: {"content": {"text/csv": {"schema": {"type": "string"}}}}})
def get_document_version_chart_csv(
    request: Request, principal: PrincipalDependency, engine: RuntimeEngineDependency,
    document_id: UUID, version_id: UUID, block_id: UUID,
) -> Response:
    view = _read_historical_chart(request, engine, principal, document_id, version_id, block_id)
    if isinstance(view, JSONResponse):
        return view
    return Response(_chart_csv(view), media_type="text/csv", headers={
        "Cache-Control": "no-store",
        "Content-Disposition": f'attachment; filename="chart-{version_id}-{block_id}.csv"',
    })


@router.post("/documents/{document_id}/versions", response_model=DocumentSaveResponse,
             operation_id="saveDocumentVersion", status_code=201,
             summary="Save a new immutable revision (compare-and-set via If-Match)",
             responses=_PRIVATE_ERROR_RESPONSES)
def save_document_version(request: Request, principal: PrincipalDependency,
                          engine: RuntimeEngineDependency, response: Response,
                          document_id: UUID, payload: DocumentSaveRequest,
                          if_match: Annotated[str | None, Header()] = None,
                          idempotency_key: Annotated[str | None, Header()] = None,
                          ) -> DocumentSaveResponse | JSONResponse:
    """Append one immutable revision; CAS against If-Match, zero rows on failure.

    With an ``Idempotency-Key`` the new revision's response snapshot is stored
    in the save transaction, so a retry of the identical owner/route/body
    request after a lost response replays the original 201 (same version, no
    second revision) instead of a spurious 409 against the advanced document.
    """
    expected = _parse_if_match(if_match)
    if expected is None:
        return error_response(request, 428, "PRECONDITION_REQUIRED",
                              "If-Match with the current document revision is required")
    if payload.schema_version != SCHEMA_VERSION:
        return error_response(
            request, 422, "VALIDATION_ERROR",
            f"Unsupported document schema version; this service saves version "
            f"{SCHEMA_VERSION} only",
            details=(ErrorDetail(path="schema_version",
                                 reason="unsupported_schema_version"),))
    declared = payload.content.get("schema_version") \
        if isinstance(payload.content, dict) else None
    if declared is not None and declared != payload.schema_version:
        return error_response(
            request, 422, "VALIDATION_ERROR",
            "schema_version does not match the content's own schema_version",
            details=(ErrorDetail(path="content.schema_version",
                                 reason="schema_version_mismatch"),))
    try:
        key = idempotency.parse_idempotency_key(idempotency_key)
    except DocumentSchemaError as error:
        return _schema_error(request, error)

    def execute(connection):
        detail = service.save_revision_in_transaction(
            connection, principal, document_id, expected_revision=expected,
            document_payload=payload.content,
            observed_contexts=list(payload.observed_contexts))
        return 201, _document_save_response(detail).model_dump(mode="json")

    if key is not None:
        route_key = idempotency.ROUTE_SAVE_DOCUMENT_VERSION.format(document_id=document_id)
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
            # Nothing was stored: a rejected save stays retryable with the key.
            return _schema_error(request, error)
        if outcome.replay:
            return _replay_response(outcome, etag_revision_path=("document", "revision"))
        response.headers["Cache-Control"] = "no-store"
        response.headers["ETag"] = _etag(int(outcome.body["document"]["revision"]))
        return DocumentSaveResponse.model_validate(outcome.body)
    try:
        detail = service.save_revision(engine, principal, document_id,
                                       expected_revision=expected,
                                       document_payload=payload.content,
                                       observed_contexts=list(payload.observed_contexts))
    except service.RevisionConflict as conflict:
        # Owned-document 409: the current revision is included for the owner.
        return error_response(
            request, 409, "REVISION_CONFLICT", str(conflict),
            details=(ErrorDetail(path="If-Match",
                                 reason=f"current_revision:{conflict.current_revision}"),))
    except DocumentSchemaError as error:
        return _schema_error(request, error)
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = _etag(detail.document.revision)
    return _document_save_response(detail)
