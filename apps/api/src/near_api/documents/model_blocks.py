"""Revision-checked model-result block insertion with frozen context (NI-055).

Implements the API_SPECIFICATION "Research documents and versions" row
``POST /documents/{id}/model-blocks``: one confirmed "Add Model" selection
appends exactly ONE valid ``modelResult`` block to an owned document through
the canonical revision flow (NI-036) and captures the pinned model context
immutably. The endpoint never bypasses document validation — the inserted
node is validated by :func:`near_api.documents.schema.parse_document` like
any editor save, and the new revision carries the same projections.

Contract (mirrors the NI-041 chart-block insertion exactly):

- **CAS.** ``If-Match: "<revision>"`` is required (428 without it); a stale
  revision is 409 ``REVISION_CONFLICT`` carrying ``current_revision`` for the
  owned document; one successful call creates exactly one new revision.
- **Owner.** The destination document must belong to the verified principal
  (NI-019 transaction-local identity); a foreign or absent document is the
  same generic 404 and no reference in the request can leak existence.
- **Pins are server verified.** The request carries the chosen published
  ``model_run_id`` and the pinned ``dataset_version_id``: the server verifies
  the run against the NI-054 published-only catalog (an unknown or
  non-published run is rejected — there is no substitute run) and pins
  EXACTLY the approved public dataset version (an unapproved one is
  rejected, never substituted with latest). The request body can carry NO
  statistical value: coefficients/diagnostics live only on the immutable
  ``app.model_runs`` row and are re-projected for display, so editing the
  interpretation can never change the recorded result and a source revision
  never refits it.
- **Frozen context.** The new revision's ``resolved_contexts`` gains one
  ``ModelContext`` (NI-046 contract) for the inserted block, keyed by the
  server-allocated ``block_id``: the pinned run id, the pinned dataset
  version, the specification identity and the canonical ``context_hash``.
  Once written the context is NEVER re-resolved: whole-document saves carry
  unchanged model contexts forward verbatim (a newer published run or a
  newer dataset publication is a NEW explicit pin, never a silent refit) and
  reopening a historical revision shows the original context.
- **Idempotency.** ``Idempotency-Key: UUID`` reuses the NI-037 write-once
  replay store (migration 0009): a repeated identical owner/route/body
  request replays the ORIGINAL 201 result instead of appending a second
  block, so a timeout-after-commit retry is safe; the same key with a
  different body is 409 ``IDEMPOTENCY_CONFLICT``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import Connection, Engine

from near_api.auth.principal import Principal, get_principal, get_runtime_engine
from near_api.contracts import error_response
from near_api.db.security import principal_transaction
from near_api.documents import idempotency, service
from near_api.documents.context_resolver import (
    resolve_revision_contexts,
    verify_model_result_pins,
)
# The document HTTP vocabulary (error map, ETag, summary, If-Match/replay
# handling) is shared with the NI-036/NI-037/NI-041 routes modules on purpose:
# one error surface, no second implementation.
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
from near_api.schemas.common import ErrorDetail
from near_api.schemas.model_blocks import (
    ModelBlockInsertRequest,
    ModelBlockMutationResponse,
    ModelBlockValue,
)

router = APIRouter(prefix="/api", tags=["documents"])

PrincipalDependency = Annotated[Principal, Depends(get_principal)]
RuntimeEngineDependency = Annotated[Engine, Depends(get_runtime_engine)]

ROUTE_ADD_MODEL_BLOCK = idempotency.ROUTE_ADD_MODEL_BLOCK


# --------------------------------------------------------------------------- #
# Insertion service (one confirmation = one valid block = one revision)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ModelBlockInsertion:
    """The new revision plus the server-allocated block identity."""

    detail: service.DocumentDetail
    block_id: UUID


def append_model_block(engine: Engine, principal: Principal, document_id: UUID, *,
                       expected_revision: int,
                       payload: ModelBlockInsertRequest) -> ModelBlockInsertion:
    """Append one pinned model-result block to an owned document (own transaction)."""
    with principal_transaction(engine, principal) as connection:
        return append_model_block_in_transaction(
            connection, principal, document_id, expected_revision=expected_revision,
            payload=payload)


def append_model_block_in_transaction(connection: Connection, principal: Principal,
                                      document_id: UUID, *, expected_revision: int,
                                      payload: ModelBlockInsertRequest,
                                      ) -> ModelBlockInsertion:
    """Transaction-scoped :func:`append_model_block` (used by the idempotent route).

    One transaction: row lock -> CAS -> published-run/dataset pin verification ->
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

    block_id = uuid4()
    node = {
        "type": "modelResult",
        "attrs": {
            "block_id": str(block_id),
            "model_run_id": str(payload.model_run_id),
            "dataset_version_id": str(payload.dataset_version_id),
            "interpretation": payload.model_dump(mode="json")["interpretation"],
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
    # Server-side pin verification happens here AND in resolve_revision_contexts
    # (the shared per-revision rule): verify once for the frozen context of THIS
    # insertion, then let the shared rule carry every prior model context of the
    # document forward verbatim.
    verify_model_result_pins(connection, canonical.model_results[-1],
                             error_path=f"modelResult.{block_id}")
    resolved_contexts = resolve_revision_contexts(connection, canonical, previous)
    detail = service._commit_new_revision(connection, principal, document,
                                          canonical=canonical,
                                          resolved_contexts=resolved_contexts)
    return ModelBlockInsertion(detail=detail, block_id=block_id)


# --------------------------------------------------------------------------- #
# HTTP route
# --------------------------------------------------------------------------- #


@router.post("/documents/{document_id}/model-blocks",
             response_model=ModelBlockMutationResponse, operation_id="addModelBlock",
             status_code=201,
             summary="Append one pinned model-result block to an owned document "
                     "(compare-and-set via If-Match)",
             responses=_PRIVATE_ERROR_RESPONSES)
def add_model_block(request: Request, principal: PrincipalDependency,
                    engine: RuntimeEngineDependency, response: Response,
                    document_id: UUID, payload: ModelBlockInsertRequest,
                    if_match: Annotated[str | None, Header()] = None,
                    idempotency_key: Annotated[str | None, Header()] = None,
                    ) -> ModelBlockMutationResponse | JSONResponse:
    """Append one valid modelResult block with its frozen model context.

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
        insertion = append_model_block_in_transaction(
            connection, principal, document_id, expected_revision=expected,
            payload=payload)
        body = ModelBlockMutationResponse(
            document=_document_summary(insertion.detail.document),
            value=ModelBlockValue(block_id=insertion.block_id),
        ).model_dump(mode="json")
        return 201, body

    if key is not None:
        route_key = ROUTE_ADD_MODEL_BLOCK.format(document_id=document_id)
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
        return ModelBlockMutationResponse.model_validate(outcome.body)
    try:
        insertion = append_model_block(engine, principal, document_id,
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
    return ModelBlockMutationResponse(
        document=_document_summary(insertion.detail.document),
        value=ModelBlockValue(block_id=insertion.block_id))
