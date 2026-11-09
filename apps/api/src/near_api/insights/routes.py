"""Owner-scoped chart insight reads and revision mutations (NI-047)."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import Connection, Engine

from near_api.auth.principal import Principal
from near_api.contracts import error_response
from near_api.db.security import principal_transaction
from near_api.documents import idempotency
from near_api.documents.routes import (
    _PRIVATE_ERROR_RESPONSES,
    PrincipalDependency,
    RuntimeEngineDependency,
    _document_save_response,
    _parse_if_match,
    _replay_response,
    _schema_error,
)
from near_api.documents.schema import DocumentSchemaError
from near_api.documents.service import DocumentDetail, RevisionConflict
from near_api.insights import service
from near_api.insights.schemas import Insight
from near_api.schemas.common import ErrorDetail, ErrorResponse
from near_api.schemas.document_insights import (
    InsightCreateRequest,
    InsightDeleteRequest,
    InsightDeleteResponse,
    InsightDeleteValue,
    InsightMutationResponse,
    InsightPatchRequest,
)

router = APIRouter(prefix="/api", tags=["insights"])
_COLLECTION = "/documents/{document_id}/insights"
_ITEM = _COLLECTION + "/{insight_id}"
_DELETE_ERRORS = {
    **_PRIVATE_ERROR_RESPONSES,
    409: {"model": ErrorResponse, "description": "Revision, idempotency or linked-evidence conflict"},
}


def _mutate(
    request: Request, engine: Engine, principal: Principal, *,
    route: str, status: int, if_match: str | None, idempotency_key: str | None,
    payload: InsightCreateRequest | InsightPatchRequest | InsightDeleteRequest,
    operation: Callable[[Connection, int], tuple[DocumentDetail, Insight | InsightDeleteValue]],
) -> JSONResponse:
    expected = _parse_if_match(if_match)
    if expected is None:
        return error_response(request, 428, "PRECONDITION_REQUIRED",
                              "If-Match with the current document revision is required")

    def execute(connection: Connection) -> tuple[int, dict]:
        detail, value = operation(connection, expected)
        saved = _document_save_response(detail)
        if isinstance(value, Insight):
            result = InsightMutationResponse(version=saved.version, document=saved.document,
                                             value=value)
        else:
            result = InsightDeleteResponse(version=saved.version, document=saved.document,
                                           value=value)
        return status, result.model_dump(mode="json")

    try:
        key = idempotency.parse_idempotency_key(idempotency_key)
        if key is None:
            with principal_transaction(engine, principal) as connection:
                response_status, body = execute(connection)
            outcome = idempotency.IdempotentOutcome(False, response_status, body)
        else:
            route_key = f"{request.method} /api{route}"
            outcome = idempotency.execute_idempotent(
                engine, principal, route_key=route_key, idempotency_key=key,
                request_hash=idempotency.request_fingerprint(
                    route_key, principal.id, payload.model_dump(mode="json", exclude_unset=True)),
                operation=execute)
    except idempotency.IdempotencyConflict as error:
        return error_response(request, 409, "IDEMPOTENCY_CONFLICT", str(error))
    except RevisionConflict as conflict:
        return error_response(
            request, 409, "REVISION_CONFLICT", str(conflict),
            details=(ErrorDetail(path="If-Match",
                                 reason=f"current_revision:{conflict.current_revision}"),))
    except service.EvidenceLinksExist as error:
        return error_response(
            request, 409, "REFERENCE_IN_USE", str(error),
            details=(ErrorDetail(path="remove_evidence_links",
                                 reason=f"linked_evidence:{error.count}"),))
    except DocumentSchemaError as error:
        return _schema_error(request, error)
    return _replay_response(outcome, etag_revision_path=("document", "revision"))


@router.get(_COLLECTION, response_model=tuple[Insight, ...],
            operation_id="listDocumentInsights",
            summary="List insights in a current or historical owned document revision",
            responses={status: _PRIVATE_ERROR_RESPONSES[status] for status in (401, 403, 404, 422)})
def list_document_insights(principal: PrincipalDependency, engine: RuntimeEngineDependency,
                           response: Response, document_id: UUID,
                           version_id: UUID | None = None) -> tuple[Insight, ...]:
    insights = service.list_insights(engine, principal, document_id, version_id)
    response.headers["Cache-Control"] = "no-store"
    return insights


@router.post(_COLLECTION, response_model=InsightMutationResponse, status_code=201,
             operation_id="createDocumentInsight",
             summary="Add an inspected chart insight to an owned document",
             responses=_PRIVATE_ERROR_RESPONSES)
def create_document_insight(request: Request, principal: PrincipalDependency,
                            engine: RuntimeEngineDependency, document_id: UUID,
                            payload: InsightCreateRequest,
                            if_match: Annotated[str | None, Header()] = None,
                            idempotency_key: Annotated[str | None, Header()] = None) -> JSONResponse:
    return _mutate(
        request, engine, principal, route=_COLLECTION.format(document_id=document_id),
        status=201, if_match=if_match, idempotency_key=idempotency_key, payload=payload,
        operation=lambda connection, expected: service.create_insight(
            connection, principal, document_id, expected_revision=expected, payload=payload))


@router.patch(_ITEM, response_model=InsightMutationResponse,
              operation_id="updateDocumentInsight",
              summary="Edit an insight in the current owned document revision",
              responses=_PRIVATE_ERROR_RESPONSES)
def update_document_insight(request: Request, principal: PrincipalDependency,
                            engine: RuntimeEngineDependency, document_id: UUID, insight_id: UUID,
                            payload: InsightPatchRequest,
                            if_match: Annotated[str | None, Header()] = None,
                            idempotency_key: Annotated[str | None, Header()] = None) -> JSONResponse:
    return _mutate(
        request, engine, principal, route=_ITEM.format(document_id=document_id, insight_id=insight_id),
        status=200, if_match=if_match, idempotency_key=idempotency_key, payload=payload,
        operation=lambda connection, expected: service.update_insight(
            connection, principal, document_id, insight_id, expected_revision=expected,
            payload=payload))


@router.delete(_ITEM, response_model=InsightDeleteResponse,
               operation_id="deleteDocumentInsight",
               summary="Remove an insight with explicitly confirmed evidence cleanup",
               responses=_DELETE_ERRORS)
def delete_document_insight(request: Request, principal: PrincipalDependency,
                            engine: RuntimeEngineDependency, document_id: UUID, insight_id: UUID,
                            payload: InsightDeleteRequest,
                            if_match: Annotated[str | None, Header()] = None,
                            idempotency_key: Annotated[str | None, Header()] = None) -> JSONResponse:
    return _mutate(
        request, engine, principal, route=_ITEM.format(document_id=document_id, insight_id=insight_id),
        status=200, if_match=if_match, idempotency_key=idempotency_key, payload=payload,
        operation=lambda connection, expected: (
            service.delete_insight(
                connection, principal, document_id, insight_id, expected_revision=expected,
                remove_evidence_links=payload.remove_evidence_links),
            InsightDeleteValue(deleted_id=insight_id)))
