"""Owner-scoped hypothesis reads and revision mutations (NI-048)."""

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
from near_api.evidence import hypotheses
from near_api.insights.schemas import Hypothesis
from near_api.schemas.common import ErrorResponse
from near_api.schemas.document_hypotheses import (
    HypothesisCreateRequest,
    HypothesisDeleteRequest,
    HypothesisDeleteResponse,
    HypothesisDeleteValue,
    HypothesisMutationResponse,
    HypothesisPatchRequest,
)

router = APIRouter(prefix="/api", tags=["hypotheses"])
_COLLECTION = "/documents/{document_id}/hypotheses"
_ITEM = _COLLECTION + "/{hypothesis_id}"
_DELETE_ERRORS = {
    **_PRIVATE_ERROR_RESPONSES,
    409: {"model": ErrorResponse, "description": "Revision, idempotency or linked-reference conflict"},
}


@router.get(_COLLECTION, response_model=tuple[Hypothesis, ...],
            operation_id="listDocumentHypotheses",
            summary="List hypotheses in a current or historical owned document revision",
            responses={status: _PRIVATE_ERROR_RESPONSES[status] for status in (401, 403, 404, 422)})
def list_document_hypotheses(principal: PrincipalDependency, engine: RuntimeEngineDependency,
                             response: Response, document_id: UUID,
                             version_id: UUID | None = None) -> tuple[Hypothesis, ...]:
    result = hypotheses.list_hypotheses(engine, principal, document_id, version_id)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(_COLLECTION, response_model=HypothesisMutationResponse, status_code=201,
             operation_id="createDocumentHypothesis",
             summary="Add a hypothesis to an owned document",
             responses=_PRIVATE_ERROR_RESPONSES)
def create_document_hypothesis(request: Request, principal: PrincipalDependency,
                               engine: RuntimeEngineDependency, document_id: UUID,
                               payload: HypothesisCreateRequest,
                               if_match: Annotated[str | None, Header()] = None,
                               idempotency_key: Annotated[str | None, Header()] = None) -> JSONResponse:
    return mutate_document_annotation(
        request, engine, principal, route=_COLLECTION.format(document_id=document_id),
        status=201, if_match=if_match, idempotency_key=idempotency_key, payload=payload,
        response_model=HypothesisMutationResponse,
        operation=lambda connection, expected: hypotheses.create_hypothesis(
            connection, principal, document_id, expected_revision=expected, payload=payload))


@router.patch(_ITEM, response_model=HypothesisMutationResponse,
              operation_id="updateDocumentHypothesis",
              summary="Edit a hypothesis in the current owned document revision",
              responses=_PRIVATE_ERROR_RESPONSES)
def update_document_hypothesis(request: Request, principal: PrincipalDependency,
                               engine: RuntimeEngineDependency, document_id: UUID,
                               hypothesis_id: UUID, payload: HypothesisPatchRequest,
                               if_match: Annotated[str | None, Header()] = None,
                               idempotency_key: Annotated[str | None, Header()] = None) -> JSONResponse:
    return mutate_document_annotation(
        request, engine, principal,
        route=_ITEM.format(document_id=document_id, hypothesis_id=hypothesis_id),
        status=200, if_match=if_match, idempotency_key=idempotency_key, payload=payload,
        response_model=HypothesisMutationResponse,
        operation=lambda connection, expected: hypotheses.update_hypothesis(
            connection, principal, document_id, hypothesis_id, expected_revision=expected,
            payload=payload))


@router.delete(_ITEM, response_model=HypothesisDeleteResponse,
               operation_id="deleteDocumentHypothesis",
               summary="Remove a hypothesis with explicitly confirmed reference cleanup",
               responses=_DELETE_ERRORS)
def delete_document_hypothesis(request: Request, principal: PrincipalDependency,
                               engine: RuntimeEngineDependency, document_id: UUID,
                               hypothesis_id: UUID, payload: HypothesisDeleteRequest,
                               if_match: Annotated[str | None, Header()] = None,
                               idempotency_key: Annotated[str | None, Header()] = None) -> JSONResponse:
    return mutate_document_annotation(
        request, engine, principal,
        route=_ITEM.format(document_id=document_id, hypothesis_id=hypothesis_id),
        status=200, if_match=if_match, idempotency_key=idempotency_key, payload=payload,
        response_model=HypothesisDeleteResponse,
        operation=lambda connection, expected: (
            hypotheses.delete_hypothesis(
                connection, principal, document_id, hypothesis_id, expected_revision=expected,
                remove_evidence_links=payload.remove_evidence_links),
            HypothesisDeleteValue(deleted_id=hypothesis_id)))
