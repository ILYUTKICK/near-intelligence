"""Document HTTP routes implemented by NI-036.

Implements the first four rows of the API_SPECIFICATION "Research documents
and versions" section on the revision service: list/create/get/save. Every
route authenticates through ``get_principal`` (NI-018), opens the
transaction-local verified identity (``principal_transaction``, NI-019) and
emits ``Cache-Control: no-store`` — private content is never cacheable.

Compare-and-set: create/get return ``ETag: "<revision>"``; the save route
REQUIRES ``If-Match: "<revision>"`` (428 without it), rejects a stale revision
with 409 REVISION_CONFLICT (including the current revision for the owned
document only) and never overwrites. Not-owned and absent ids are the same
generic 404. Idempotency keys, rename/delete and version listing are NI-037
scope and are deliberately absent here.
"""

from __future__ import annotations

import base64
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy.engine import Engine

from near_api.auth.principal import Principal, get_principal, get_runtime_engine
from near_api.contracts import error_response
from near_api.documents import service
from near_api.documents.schema import (
    SCHEMA_VERSION,
    DocumentSchemaError,
    DocumentTooLarge,
    ReferenceInvalid,
)
from near_api.repositories.documents import DocumentRow
from near_api.schemas.common import ErrorDetail, ErrorResponse
from near_api.schemas.documents import (
    DocumentCreateRequest,
    DocumentListResponse,
    DocumentResponse,
    DocumentSaveRequest,
    DocumentSaveResponse,
    VersionDetailResponse,
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
        (409, "Revision conflict: the document moved since the request was built"),
        (413, "Document exceeds a hard size limit"),
        (422, "Request failed validation or references an unavailable target"),
        (428, "If-Match precondition is required"),
    )
}


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
                    payload: DocumentCreateRequest):
    """Create an owned document whose first revision is the empty document."""
    if payload.template_id is not None:
        # P1 templates are feature-gated: 422 FEATURE_UNAVAILABLE, never a
        # simulated template (API_SPECIFICATION).
        return error_response(request, 422, "FEATURE_UNAVAILABLE",
                              "Document templates are not available yet")
    detail = service.create_document(engine, principal, title=payload.title)
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


@router.post("/documents/{document_id}/versions", response_model=DocumentSaveResponse,
             operation_id="saveDocumentVersion", status_code=201,
             summary="Save a new immutable revision (compare-and-set via If-Match)",
             responses=_PRIVATE_ERROR_RESPONSES)
def save_document_version(request: Request, principal: PrincipalDependency,
                          engine: RuntimeEngineDependency, response: Response,
                          document_id: UUID, payload: DocumentSaveRequest,
                          if_match: Annotated[str | None, Header()] = None,
                          ) -> DocumentSaveResponse:
    """Append one immutable revision; CAS against If-Match, zero rows on failure."""
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
    return DocumentSaveResponse(
        version=VersionDetailResponse(
            id=detail.version.id, document_id=detail.version.document_id,
            revision=detail.version.revision,
            schema_version=detail.version.schema_version,
            content_sha256=detail.version.content_sha256,
            created_at=detail.version.created_at, content=detail.content,
            resolved_contexts=detail.resolved_contexts),
        document=_document_summary(detail.document))
