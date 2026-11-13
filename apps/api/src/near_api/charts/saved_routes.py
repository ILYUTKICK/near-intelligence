"""Private saved-chart HTTP API. Identity from verified JWT only (NI-035)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import Engine

from near_api.auth.principal import Principal, get_principal, get_runtime_engine
from near_api.charts import saved
from near_api.contracts import error_response
from near_api.db.security import principal_transaction
from near_api.documents.idempotency import (
    IdempotencyConflict, execute_idempotent, request_fingerprint,
)
from near_api.pagination import PublicPage, encode_page_cursor
from near_api.schemas.saved_charts import (
    SavedChartCreateRequest, SavedChartDetailResponse, SavedChartListResponse,
    SavedChartResponse, SavedChartUpdateRequest,
)
from near_api.schemas.common import ErrorResponse

router = APIRouter(prefix="/api/saved-charts", tags=["saved-charts"], responses={
    code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 503)
})
Owner = Annotated[Principal, Depends(get_principal)]
Runtime = Annotated[Engine, Depends(get_runtime_engine)]


@router.get("", response_model=SavedChartListResponse, operation_id="listSavedCharts")
def list_saved(owner: Owner, engine: Runtime, page: PublicPage,
               q: Annotated[str | None, Query(max_length=200)] = None,
               category: Annotated[str | None, Query(max_length=40)] = None):
    offset, limit = page
    with principal_transaction(engine, owner) as connection:
        items, total = saved.list_saved(connection, owner.id, search=q, category=category,
                                       offset=offset, limit=limit)
    return SavedChartListResponse(items=items, next_cursor=(
        encode_page_cursor(offset + limit) if offset + limit < total else None))


@router.post("", response_model=SavedChartResponse, status_code=201, operation_id="createSavedChart")
def create_saved(body: SavedChartCreateRequest, owner: Owner, engine: Runtime, request: Request,
                 idempotency_key: Annotated[UUID | None, Header()] = None):
    if idempotency_key is None:
        with principal_transaction(engine, owner) as connection:
            return saved.create(connection, owner.id, body)
    route = "POST /api/saved-charts"
    try:
        outcome = execute_idempotent(
            engine, owner, route_key=route, idempotency_key=idempotency_key,
            request_hash=request_fingerprint(route, owner.id, body.model_dump(mode="json")),
            operation=lambda connection: (201, saved.create(connection, owner.id, body)
                                           .model_dump(mode="json")))
    except IdempotencyConflict:
        return error_response(request, 409, "IDEMPOTENCY_CONFLICT", "Key used for a different request")
    return JSONResponse(outcome.body, status_code=outcome.status)


@router.get("/{instance_id}", response_model=SavedChartDetailResponse, operation_id="getSavedChart")
def get_saved(
    instance_id: UUID, owner: Owner, engine: Runtime,
    preview: Annotated[bool, Query(description="Resolve the chart without recording an observation.")] = False,
):
    with principal_transaction(engine, owner) as connection:
        return saved.detail(connection, owner.id, instance_id, preview=preview)


@router.patch("/{instance_id}", response_model=SavedChartResponse, operation_id="updateSavedChart")
def update_saved(instance_id: UUID, body: SavedChartUpdateRequest, owner: Owner, engine: Runtime):
    with principal_transaction(engine, owner) as connection:
        return saved.edit(connection, owner.id, instance_id, body)


@router.delete("/{instance_id}", status_code=204, operation_id="deleteSavedChart")
def delete_saved(instance_id: UUID, owner: Owner, engine: Runtime):
    with principal_transaction(engine, owner) as connection:
        saved.remove(connection, owner.id, instance_id)
    return Response(status_code=204)
