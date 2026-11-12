"""Private research-snapshot HTTP API (NI-044). Identity from verified JWT only.

Freeze (POST) supports the same ``Idempotency-Key`` replay semantics as the
saved-chart mutation so a lost committed response can never duplicate a
frozen snapshot. Reads are owner-scoped and no-store; delete refuses a
snapshot that a saved chart references with 409 ``REFERENCE_IN_USE``.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import Engine

from near_api.auth.principal import Principal, get_principal, get_runtime_engine
from near_api.charts import snapshots
from near_api.contracts import error_response
from near_api.db.security import principal_transaction
from near_api.documents.idempotency import (
    IdempotencyConflict, execute_idempotent, request_fingerprint,
)
from near_api.pagination import PublicPage, encode_page_cursor
from near_api.schemas.common import ErrorResponse
from near_api.schemas.snapshots import (
    SnapshotCompareResponse, SnapshotCreateRequest, SnapshotDetailResponse,
    SnapshotListResponse, SnapshotResponse,
)

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"], responses={
    code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 503)
})
Owner = Annotated[Principal, Depends(get_principal)]
Runtime = Annotated[Engine, Depends(get_runtime_engine)]


@router.get("", response_model=SnapshotListResponse, operation_id="listSnapshots")
def list_snapshots(owner: Owner, engine: Runtime, page: PublicPage):
    offset, limit = page
    with principal_transaction(engine, owner) as connection:
        items, total = snapshots.list_snapshots(connection, owner.id,
                                                offset=offset, limit=limit)
    return SnapshotListResponse(items=items, next_cursor=(
        encode_page_cursor(offset + limit) if offset + limit < total else None))


@router.post("", response_model=SnapshotResponse, status_code=201, operation_id="createSnapshot")
def create_snapshot(body: SnapshotCreateRequest, owner: Owner, engine: Runtime, request: Request,
                    idempotency_key: Annotated[UUID | None, Header()] = None):
    if idempotency_key is None:
        with principal_transaction(engine, owner) as connection:
            return snapshots.create(connection, owner.id, body)
    route = "POST /api/snapshots"
    try:
        outcome = execute_idempotent(
            engine, owner, route_key=route, idempotency_key=idempotency_key,
            request_hash=request_fingerprint(route, owner.id, body.model_dump(mode="json")),
            operation=lambda connection: (201, snapshots.create(connection, owner.id, body)
                                          .model_dump(mode="json")))
    except IdempotencyConflict:
        return error_response(request, 409, "IDEMPOTENCY_CONFLICT", "Key used for a different request")
    return JSONResponse(outcome.body, status_code=outcome.status)


@router.get("/{snapshot_id}/compare-live", response_model=SnapshotCompareResponse,
            operation_id="compareSnapshotWithLive")
def compare_snapshot(snapshot_id: UUID, owner: Owner, engine: Runtime):
    with principal_transaction(engine, owner) as connection:
        return snapshots.compare_with_live(connection, owner.id, snapshot_id)


@router.get("/{snapshot_id}", response_model=SnapshotDetailResponse, operation_id="getSnapshot")
def get_snapshot(snapshot_id: UUID, owner: Owner, engine: Runtime):
    with principal_transaction(engine, owner) as connection:
        return snapshots.detail(connection, owner.id, snapshot_id)


@router.delete("/{snapshot_id}", status_code=204, operation_id="deleteSnapshot")
def delete_snapshot(snapshot_id: UUID, owner: Owner, engine: Runtime, request: Request):
    with principal_transaction(engine, owner) as connection:
        try:
            snapshots.remove(connection, owner.id, snapshot_id)
        except snapshots.SnapshotReferenceInUse as error:
            return error_response(request, 409, "REFERENCE_IN_USE", str(error))
    return Response(status_code=204)
