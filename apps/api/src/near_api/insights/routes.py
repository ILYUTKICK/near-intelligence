"""Owner-scoped chart insight reads and revision mutations (NI-047)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse

from near_api.documents.routes import (
    _PRIVATE_ERROR_RESPONSES,
    PrincipalDependency,
    RuntimeEngineDependency,
    mutate_document_annotation,
)
from near_api.insights import service
from near_api.insights.schemas import Insight
from near_api.schemas.common import ErrorResponse
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
    return mutate_document_annotation(
        request, engine, principal, route=_COLLECTION.format(document_id=document_id),
        status=201, if_match=if_match, idempotency_key=idempotency_key, payload=payload,
        response_model=InsightMutationResponse,
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
    return mutate_document_annotation(
        request, engine, principal, route=_ITEM.format(document_id=document_id, insight_id=insight_id),
        status=200, if_match=if_match, idempotency_key=idempotency_key, payload=payload,
        response_model=InsightMutationResponse,
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
    return mutate_document_annotation(
        request, engine, principal, route=_ITEM.format(document_id=document_id, insight_id=insight_id),
        status=200, if_match=if_match, idempotency_key=idempotency_key, payload=payload,
        response_model=InsightDeleteResponse,
        operation=lambda connection, expected: (
            service.delete_insight(
                connection, principal, document_id, insight_id, expected_revision=expected,
                remove_evidence_links=payload.remove_evidence_links),
            InsightDeleteValue(deleted_id=insight_id)))
