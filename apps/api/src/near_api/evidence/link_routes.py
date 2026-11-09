"""Owned document evidence and its public target picker (NI-049)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse

from near_api.db.security import principal_transaction
from near_api.documents.routes import (
    _PRIVATE_ERROR_RESPONSES,
    PrincipalDependency,
    RuntimeEngineDependency,
    mutate_document_annotation,
)
from near_api.evidence import links, targets
from near_api.insights.schemas import Evidence
from near_api.pagination import PublicPage
from near_api.repositories.documents import get_document
from near_api.schemas.document_evidence import (
    EvidenceCreateRequest,
    EvidenceDeleteResponse,
    EvidenceDeleteValue,
    EvidenceMutationResponse,
    EvidencePatchRequest,
    EvidenceTargetListResponse,
    PublicEvidenceTargetKind,
)

router = APIRouter(prefix="/api", tags=["evidence"])
_COLLECTION = "/documents/{document_id}/evidence"
_ITEM = _COLLECTION + "/{evidence_id}"
_READ_ERRORS = {status: _PRIVATE_ERROR_RESPONSES[status] for status in (401, 403, 404, 422)}


@router.get(_COLLECTION, response_model=tuple[Evidence, ...], operation_id="listDocumentEvidence",
            summary="List evidence in a current or historical owned document revision",
            responses=_READ_ERRORS)
def list_document_evidence(principal: PrincipalDependency, engine: RuntimeEngineDependency,
                           response: Response, document_id: UUID, hypothesis_id: UUID | None = None,
                           version_id: UUID | None = None) -> tuple[Evidence, ...]:
    result = links.list_evidence(engine, principal, document_id, version_id=version_id,
                                 hypothesis_id=hypothesis_id)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/documents/{document_id}/evidence-targets", response_model=EvidenceTargetListResponse,
            operation_id="listDocumentEvidenceTargets",
            summary="List selectable public evidence targets for an owned document",
            responses=_READ_ERRORS)
def list_document_evidence_targets(principal: PrincipalDependency, engine: RuntimeEngineDependency,
                                   response: Response, document_id: UUID,
                                   target_kind: PublicEvidenceTargetKind,
                                   page: PublicPage) -> EvidenceTargetListResponse:
    offset, limit = page
    with principal_transaction(engine, principal) as connection:
        get_document(connection, principal, document_id)
        result = targets.list_public_targets(connection, target_kind, offset=offset, limit=limit)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post(_COLLECTION, response_model=EvidenceMutationResponse, status_code=201,
             operation_id="createDocumentEvidence", summary="Add evidence to an owned document",
             responses=_PRIVATE_ERROR_RESPONSES)
def create_document_evidence(request: Request, principal: PrincipalDependency,
                             engine: RuntimeEngineDependency, document_id: UUID,
                             payload: EvidenceCreateRequest,
                             if_match: Annotated[str | None, Header()] = None,
                             idempotency_key: Annotated[str | None, Header()] = None) -> JSONResponse:
    return mutate_document_annotation(
        request, engine, principal, route=_COLLECTION.format(document_id=document_id),
        status=201, if_match=if_match, idempotency_key=idempotency_key, payload=payload,
        response_model=EvidenceMutationResponse,
        operation=lambda connection, expected: links.create_evidence(
            connection, principal, document_id, expected_revision=expected, payload=payload))


@router.patch(_ITEM, response_model=EvidenceMutationResponse, operation_id="updateDocumentEvidence",
              summary="Edit evidence in the current owned document revision",
              responses=_PRIVATE_ERROR_RESPONSES)
def update_document_evidence(request: Request, principal: PrincipalDependency,
                             engine: RuntimeEngineDependency, document_id: UUID,
                             evidence_id: UUID, payload: EvidencePatchRequest,
                             if_match: Annotated[str | None, Header()] = None,
                             idempotency_key: Annotated[str | None, Header()] = None) -> JSONResponse:
    return mutate_document_annotation(
        request, engine, principal,
        route=_ITEM.format(document_id=document_id, evidence_id=evidence_id),
        status=200, if_match=if_match, idempotency_key=idempotency_key, payload=payload,
        response_model=EvidenceMutationResponse,
        operation=lambda connection, expected: links.update_evidence(
            connection, principal, document_id, evidence_id, expected_revision=expected, payload=payload))


@router.delete(_ITEM, response_model=EvidenceDeleteResponse, operation_id="deleteDocumentEvidence",
               summary="Remove evidence from the current owned document revision",
               responses=_PRIVATE_ERROR_RESPONSES)
def delete_document_evidence(request: Request, principal: PrincipalDependency,
                             engine: RuntimeEngineDependency, document_id: UUID, evidence_id: UUID,
                             if_match: Annotated[str | None, Header()] = None,
                             idempotency_key: Annotated[str | None, Header()] = None) -> JSONResponse:
    return mutate_document_annotation(
        request, engine, principal,
        route=_ITEM.format(document_id=document_id, evidence_id=evidence_id),
        status=200, if_match=if_match, idempotency_key=idempotency_key, payload=None,
        response_model=EvidenceDeleteResponse,
        operation=lambda connection, expected: (
            links.delete_evidence(connection, principal, document_id, evidence_id,
                                  expected_revision=expected),
            EvidenceDeleteValue(deleted_id=evidence_id)))
