"""Export job HTTP routes (NI-058): create, poll, download.

Implements the export rows of API_SPECIFICATION under the ``/api`` prefix,
document-nested so every route resolves ownership through ONE compositional
chain (document -> job): a job id is only ever interpreted inside its
document's owned namespace, which makes absent, not-owned and
cross-document ids the same generic 404 — Bob cannot create, poll, download
or even distinguish Alice's jobs.

- POST ``/documents/{document_id}/exports`` — create (idempotently) the
  export job of the CURRENT acknowledged revision; the frozen plan is built
  in the same transaction (NI-056 rule), a superseded revision is the typed
  409 ``REVISION_NOT_ACKNOWLEDGED`` and an unresolvable pin/reference is
  the documented 422.
- GET ``/documents/{document_id}/exports/{job_id}`` — the typed lifecycle
  state, computed at read time so a past-TTL artifact reports ``expired``.
- GET ``/documents/{document_id}/exports/{job_id}/download`` — the ZIP
  (``succeeded`` + unexpired only; queued/running 409, failed 409 with the
  typed code, expired 410 — never a stale file). Private content: every
  response is ``no-store`` and the bytes live owner-scoped in the job row,
  so there is no public or signed URL to leak.

Every route authenticates through ``get_principal`` (NI-018) and derives
the owner from the verified session — never from a request field.
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
from near_api.documents import idempotency
from near_api.documents.idempotency import IdempotencyConflict, IdempotencyKeyInvalid
from near_api.exports import service
from near_api.exports.ir import ExportIrError
from near_api.exports.service import (
    ExportCorrupt,
    ExportExpired,
    ExportFailed,
    ExportNotReady,
    ExportPlanTooLarge,
)
from near_api.schemas.common import ErrorDetail, ErrorResponse
from near_api.schemas.export_job import DocumentExportRequest, ExportJobResponse

router = APIRouter(prefix="/api", tags=["exports"])

PrincipalDependency = Annotated[Principal, Depends(get_principal)]
RuntimeEngineDependency = Annotated[Engine, Depends(get_runtime_engine)]

_EXPORT_ERROR_RESPONSES = {
    status: {"model": ErrorResponse, "description": description}
    for status, description in (
        (401, "Missing or invalid session"),
        (403, "Verified account is disabled"),
        (404, "Referenced target does not exist for this owner"),
        (409, "Export is not downloadable in its current lifecycle state, or the "
              "Idempotency-Key was reused with a different request"),
        (410, "The export artifact has expired"),
        (422, "Request failed validation or references an unavailable target"),
    )
}


def _job_response(job: service.ExportJobRow) -> ExportJobResponse:
    return ExportJobResponse(
        id=job.id, document_id=job.document_id,
        document_version_id=job.document_version_id, format="markdown_zip",
        status=job.reported_status(), error_code=job.error_code,
        download_path=job.download_path(), expires_at=job.expires_at)


def _not_found(request: Request) -> JSONResponse:
    # Absent and not-owned resources share one generic response (NI-019);
    # export jobs never leak their existence to another user.
    return error_response(request, 404, "NOT_FOUND", "Resource was not found")


@router.post("/documents/{document_id}/exports", response_model=ExportJobResponse,
             operation_id="createDocumentExport", status_code=202,
             summary="Create (idempotently) the Markdown ZIP export job of the "
                     "acknowledged revision",
             responses=_EXPORT_ERROR_RESPONSES)
def create_document_export(
    request: Request, principal: PrincipalDependency, engine: RuntimeEngineDependency,
    response: Response, document_id: UUID, payload: DocumentExportRequest,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> ExportJobResponse | JSONResponse:
    """Queue one Markdown ZIP export of the owned document's current revision.

    The frozen export plan is built in the same transaction that inserts the
    job (NI-056): the requested revision must be the document's acknowledged
    current version — a valid but superseded revision is the typed 409
    ``REVISION_NOT_ACKNOWLEDGED`` (save/rename again and export the new
    current revision), and an unresolvable pin or reference is the typed 422.
    With an ``Idempotency-Key: UUID`` a repeated identical owner/route/body
    request replays the ORIGINAL job instead of creating a second one; the
    same key with a different body is a 409 idempotency collision.
    """
    if payload.format == "pdf":
        # P1 (NI-059): the single reliable MVP export is the Markdown bundle;
        # PDF is refused typed instead of simulated.
        return error_response(request, 422, "FEATURE_UNAVAILABLE",
                              "PDF export is not available yet")
    try:
        outcome = service.create_export_job(
            engine, principal, document_id, payload.document_version_id,
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
    except ExportIrError as error:
        if service.export_ir_error_kind(error) == "revision":
            return error_response(
                request, 409, "REVISION_NOT_ACKNOWLEDGED", str(error),
                details=tuple(ErrorDetail(path=path, reason=reason)
                              for path, reason in error.details))
        return error_response(
            request, 422, "REFERENCE_INVALID",
            "The revision cannot be exported: its pinned evidence is missing "
            "or inconsistent",
            details=tuple(ErrorDetail(path=path, reason=reason)
                          for path, reason in error.details))
    except ExportPlanTooLarge as error:
        return error_response(request, 422, "PAYLOAD_TOO_LARGE", str(error))
    except ResourceNotFound:
        return _not_found(request)
    response.headers["Cache-Control"] = "no-store"
    return _job_response(outcome.job)


@router.get("/documents/{document_id}/exports/{job_id}",
            response_model=ExportJobResponse, operation_id="getDocumentExport",
            summary="Poll one owned export job (typed lifecycle states)",
            responses=_EXPORT_ERROR_RESPONSES)
def get_document_export(request: Request, principal: PrincipalDependency,
                        engine: RuntimeEngineDependency, response: Response,
                        document_id: UUID, job_id: UUID,
                        ) -> ExportJobResponse | JSONResponse:
    """Return the export job's typed state, computed at read time.

    ``expired`` is reported the moment the artifact TTL passes — before and
    independently of the worker's documented sweep — so the state is always
    honest.
    """
    try:
        job = service.get_export_job(engine, principal, document_id, job_id)
    except (service.ExportJobNotFound, ResourceNotFound):
        return _not_found(request)
    response.headers["Cache-Control"] = "no-store"
    return _job_response(job)


@router.get("/documents/{document_id}/exports/{job_id}/download",
            operation_id="downloadDocumentExport",
            summary="Download the finished export ZIP (owner-only, unexpired)",
            responses={**_EXPORT_ERROR_RESPONSES,
                       200: {"content": {"application/zip": {
                           "schema": {"type": "string", "format": "binary"}}}}})
def download_document_export(
    request: Request, principal: PrincipalDependency, engine: RuntimeEngineDependency,
    document_id: UUID, job_id: UUID,
) -> Response:
    """Stream the stored ZIP of one succeeded, unexpired export job.

    The bytes are re-verified against the job's recorded SHA-256 before they
    are returned; anything else (queued/running, failed, expired, corrupt)
    is a typed refusal — never a stale or altered file.
    """
    try:
        download = service.get_export_download(engine, principal, document_id, job_id)
    except ExportNotReady as error:
        return error_response(
            request, 409, "EXPORT_NOT_READY",
            f"The export is still {error.status}; poll again before downloading")
    except ExportFailed as error:
        return error_response(
            request, 409, "EXPORT_FAILED",
            "The export failed on the worker; create a new export to retry",
            details=(ErrorDetail(path="job", reason=error.error_code or "export_failed"),))
    except ExportExpired:
        return error_response(request, 410, "EXPORT_EXPIRED",
                              "The export artifact has expired")
    except ExportCorrupt:
        return error_response(request, 409, "EXPORT_CORRUPT",
                              "The stored export bundle does not match its "
                              "recorded hash")
    except (service.ExportJobNotFound, ResourceNotFound):
        return _not_found(request)
    return Response(
        content=download.bundle, media_type="application/zip", headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="near-export-{job_id}.zip"',
        })
