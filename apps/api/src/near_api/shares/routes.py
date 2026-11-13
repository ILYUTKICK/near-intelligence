"""Share HTTP routes (NI-060): owner consent plane + token capability plane.

Implements the "Document shares (read-only publication)" rows of
API_SPECIFICATION under the ``/api`` prefix (ADR-021):

Owner plane (``get_principal`` + ``principal_transaction``):
- GET ``/documents/{document_id}/shares/preview`` — the EXACT projection that
  would be published, with its canonical SHA-256 and visible-scope counts;
- POST ``/documents/{document_id}/shares`` — publish the CURRENT acknowledged
  revision after explicit consent (revision + scope named in the payload,
  bound to the preview hash; Idempotency-Key replay identifies the same share
  but never re-emits the token);
- GET ``/documents/{document_id}/shares`` — the owner's share records (never
  the token or its hash);
- DELETE ``/documents/{document_id}/shares/{share_id}`` — revoke: the one-way
  transition that clears the stored bytes (export-sweep semantics).

Capability plane (NO identity — the token digest is the only credential):
- GET ``/shares/{token}`` — the frozen projection;
- GET ``/shares/{token}/charts/{block_id}/view`` — one frozen chart view;
- GET ``/shares/{token}/charts/{block_id}/csv`` — its exact-value CSV.

Every share response — success AND deny, owner AND capability plane — is
``Cache-Control: no-store`` with ``Referrer-Policy: no-referrer`` (private
content is never cacheable and the capability token never leaks through a
referring page). Unknown/revoked/expired/malformed tokens are ONE generic
404 with no distinguishing oracle.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine

from near_api.auth.principal import Principal, get_principal, get_runtime_engine
from near_api.contracts import error_response
from near_api.db.security import ResourceNotFound
from near_api.documents.idempotency import IdempotencyConflict, IdempotencyKeyInvalid
from near_api.documents.schema import DocumentSchemaError
from near_api.exports.ir import ExportIrError
from near_api.schemas.common import ErrorDetail, ErrorResponse
from near_api.schemas.delivery import ChartViewResponse
from near_api.schemas.share import (
    DocumentShareCreateRequest,
    DocumentShareListResponse,
    ShareCreatedResponse,
    SharePreviewResponse,
    ShareProjection,
    ShareSummaryResponse,
)
from near_api.shares import service
from near_api.shares.projection import share_scope_summary
from near_api.shares.service import (
    ShareExpired,
    ShareLimitExceeded,
    ShareNotFound,
    SharePreviewMismatch,
    ShareProjectionTooLarge,
    ShareRevisionMismatch,
    ShareScopeMismatch,
)

router = APIRouter(prefix="/api", tags=["shares"])

PrincipalDependency = Annotated[Principal, Depends(get_principal)]
RuntimeEngineDependency = Annotated[Engine, Depends(get_runtime_engine)]

_SHARE_ERROR_RESPONSES = {
    status: {"model": ErrorResponse, "description": description}
    for status, description in (
        (401, "Missing or invalid session"),
        (403, "Verified account is disabled"),
        (404, "Referenced target does not exist for this owner"),
        (409, "The consented revision or preview is not current, or the "
              "Idempotency-Key was reused with a different request"),
        (422, "Request failed validation or references an unavailable target"),
    )
}

_PUBLIC_SHARE_ERROR_RESPONSES = {
    404: {"model": ErrorResponse,
          "description": "The share or chart is unavailable (one generic deny)"},
    "default": {"model": ErrorResponse, "description": "Request failed"},
}


def _share_headers() -> dict[str, str]:
    """The mandatory headers of every share response (ADR-021)."""
    return {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}


def _not_found(request: Request) -> JSONResponse:
    """Absent and not-owned resources share one generic response (NI-019);
    shares never leak their existence to another user."""
    return error_response(request, 404, "NOT_FOUND", "Resource was not found")


def _public_deny(request: Request) -> JSONResponse:
    """One generic deny for unknown, revoked, expired, malformed and corrupt
    capabilities — never an oracle distinguishing them."""
    return error_response(request, 404, "NOT_FOUND", "Resource was not found")


def _reference_invalid(request: Request, error: ExportIrError) -> JSONResponse:
    return error_response(
        request, 422, "REFERENCE_INVALID",
        "The revision cannot be published: its pinned evidence is missing "
        "or inconsistent",
        details=tuple(ErrorDetail(path=path, reason=reason)
                      for path, reason in error.details))


def _summary(row: service.ShareRow) -> ShareSummaryResponse:
    return ShareSummaryResponse(
        id=row.id, document_id=row.document_id,
        document_version_id=row.document_version_id, revision=row.revision,
        status=row.reported_status(), created_at=row.created_at,
        expires_at=row.expires_at, revoked_at=row.revoked_at)


@router.post("/documents/{document_id}/shares", response_model=ShareCreatedResponse,
             operation_id="createDocumentShare", status_code=201,
             summary="Publish the acknowledged revision after explicit consent "
                     "(the share token is returned once)",
             responses=_SHARE_ERROR_RESPONSES)
def create_document_share(
    request: Request, principal: PrincipalDependency, engine: RuntimeEngineDependency,
    response: Response, document_id: UUID, payload: DocumentShareCreateRequest,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> ShareCreatedResponse | JSONResponse:
    """Publish one read-only share of the owned document's current revision.

    The request is the recorded consent: it names the acknowledged revision
    and the visible scope and carries the preview hash shown to the owner;
    the server rebuilds the frozen projection in the same transaction and
    refuses any divergence. The share token appears in this response exactly
    once (a replay cannot re-emit it) and is never stored — only its digest.
    """
    try:
        outcome = service.create_share(
            engine, principal, document_id, consent=payload,
            idempotency_key=idempotency_key)
    except IdempotencyKeyInvalid:
        return error_response(
            request, 422, "VALIDATION_ERROR", "Idempotency-Key must be a UUID",
            details=(ErrorDetail(path="Idempotency-Key",
                                 reason="invalid_idempotency_key"),))
    except IdempotencyConflict:
        return error_response(
            request, 409, "IDEMPOTENCY_CONFLICT",
            "This Idempotency-Key was already used with a different request; "
            "a new key is required for a new payload")
    except ShareRevisionMismatch as error:
        return error_response(request, 409, "REVISION_NOT_ACKNOWLEDGED", str(error))
    except SharePreviewMismatch as error:
        return error_response(request, 409, "PREVIEW_MISMATCH", str(error))
    except ShareScopeMismatch as error:
        return error_response(request, 422, "SCOPE_MISMATCH", str(error))
    except ShareProjectionTooLarge as error:
        return error_response(request, 422, "PAYLOAD_TOO_LARGE", str(error))
    except ShareLimitExceeded as error:
        return error_response(request, 422, "SHARE_LIMIT_EXCEEDED", str(error))
    except ShareExpired as error:
        return error_response(request, 422, "VALIDATION_ERROR", str(error))
    except ExportIrError as error:
        return _reference_invalid(request, error)
    except DocumentSchemaError as error:
        return error_response(
            request, 422, "VALIDATION_ERROR", str(error),
            details=tuple(ErrorDetail(path=path, reason=reason)
                          for path, reason in error.details))
    except ResourceNotFound:
        return _not_found(request)
    response.headers.update(_share_headers())
    return ShareCreatedResponse(
        id=outcome.share.id, document_id=outcome.share.document_id,
        document_version_id=outcome.share.document_version_id,
        revision=outcome.share.revision, status=outcome.share.reported_status(),
        created_at=outcome.share.created_at,
        expires_at=outcome.share.expires_at,
        share_token=outcome.token, share_path=outcome.share_path())


@router.get("/documents/{document_id}/shares/preview",
            response_model=SharePreviewResponse, operation_id="previewDocumentShare",
            summary="Preview exactly what publishing this revision would expose",
            responses=_SHARE_ERROR_RESPONSES)
def preview_document_share(request: Request, principal: PrincipalDependency,
                           engine: RuntimeEngineDependency, response: Response,
                           document_id: UUID) -> SharePreviewResponse | JSONResponse:
    """Build the publication projection of the owned acknowledged revision.

    The response IS the exact payload a consented create of the same revision
    would store (same builder, same canonical bytes); the owner dialog renders
    it before any consent, and the create request must carry its SHA-256.
    """
    try:
        preview = service.preview_share(engine, principal, document_id)
    except ExportIrError as error:
        return _reference_invalid(request, error)
    except DocumentSchemaError as error:
        return error_response(
            request, 422, "VALIDATION_ERROR", str(error),
            details=tuple(ErrorDetail(path=path, reason=reason)
                          for path, reason in error.details))
    except ResourceNotFound:
        return _not_found(request)
    response.headers.update(_share_headers())
    return SharePreviewResponse(
        document_id=preview.document_id, revision=preview.revision,
        projection=preview.projection,
        projection_sha256=preview.projection_sha256,
        scope=share_scope_summary(preview.projection))


@router.get("/documents/{document_id}/shares", response_model=DocumentShareListResponse,
            operation_id="listDocumentShares",
            summary="List an owned document's shares (never the token)",
            responses=_SHARE_ERROR_RESPONSES)
def list_document_shares(request: Request, principal: PrincipalDependency,
                         engine: RuntimeEngineDependency, response: Response,
                         document_id: UUID) -> DocumentShareListResponse | JSONResponse:
    """List the owned document's share records, newest first.

    The lifecycle state is computed at read time (``expired`` the moment the
    consent window passes), and no record ever carries the token or its hash.
    """
    try:
        shares = service.list_shares(engine, principal, document_id)
    except ResourceNotFound:
        return _not_found(request)
    response.headers.update(_share_headers())
    return DocumentShareListResponse(items=tuple(_summary(row) for row in shares))


@router.delete("/documents/{document_id}/shares/{share_id}", status_code=204,
               operation_id="revokeDocumentShare",
               summary="Revoke one owned share (denies on the next request)",
               responses=_SHARE_ERROR_RESPONSES)
def revoke_document_share(request: Request, principal: PrincipalDependency,
                          engine: RuntimeEngineDependency, response: Response,
                          document_id: UUID, share_id: UUID) -> Response:
    """Revoke the owned share; the stored bytes are cleared with the transition."""
    try:
        service.revoke_share(engine, principal, document_id, share_id)
    except (ShareNotFound, ResourceNotFound):
        return _not_found(request)
    return Response(status_code=204, headers=_share_headers())


# --------------------------------------------------------------------------- #
# Capability plane — no principal; the token digest is the credential
# --------------------------------------------------------------------------- #


@router.get("/shares/{token}", response_model=ShareProjection,
            operation_id="getSharedRevision",
            summary="Read one shared frozen revision by token (read-only)",
            responses=_PUBLIC_SHARE_ERROR_RESPONSES)
def get_shared_revision(request: Request, engine: RuntimeEngineDependency,
                        response: Response,
                        token: str) -> ShareProjection | JSONResponse:
    """Return the published projection behind one share link.

    Every request re-checks the live share state; revoked, expired and
    unknown links are the same generic 404.
    """
    try:
        projection = service.read_share_projection(engine, token)
    except ShareNotFound:
        return _public_deny(request)
    response.headers.update(_share_headers())
    return projection


@router.get("/shares/{token}/charts/{block_id:uuid}/view", response_model=ChartViewResponse,
            operation_id="getSharedChartView",
            summary="Read one frozen chart view of a shared revision",
            responses=_PUBLIC_SHARE_ERROR_RESPONSES)
def get_shared_chart_view(request: Request, engine: RuntimeEngineDependency,
                          response: Response, token: str, block_id: UUID,
                          ) -> ChartViewResponse | JSONResponse:
    """Return the pinned chart view stored in the shared projection."""
    try:
        view, _csv = service.read_share_chart(engine, token, block_id)
    except ShareNotFound:
        return _public_deny(request)
    response.headers.update(_share_headers())
    return view


@router.get("/shares/{token}/charts/{block_id:uuid}/csv", response_class=Response,
            operation_id="getSharedChartCsv",
            summary="Download the exact chart data of a shared revision",
            responses={**_PUBLIC_SHARE_ERROR_RESPONSES,
                       200: {"content": {"text/csv": {"schema": {"type": "string"}}}}})
def get_shared_chart_csv(request: Request, engine: RuntimeEngineDependency,
                         token: str, block_id: UUID) -> Response:
    """Return the exact-value CSV derived from the frozen chart view."""
    try:
        _view, csv_text = service.read_share_chart(engine, token, block_id)
    except ShareNotFound:
        return _public_deny(request)
    return Response(csv_text, media_type="text/csv", headers={
        **_share_headers(),
        "Content-Disposition": f'attachment; filename="chart-{block_id}.csv"',
    })
