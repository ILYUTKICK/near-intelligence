"""Public model routes implemented by NI-054.

Implements the API_SPECIFICATION ``/model-definitions`` and ``/model-runs``
rows (implemented deltas recorded in API_SPECIFICATION.md). All routes are
public read-only GETs through the unprivileged ``near_app`` role with no
authorization and no user-identifying input; they serve ONLY published
``app.model_runs`` rows written by the operator publication gate — an
unpublished, failed or gate-rejected run does not exist in the backing table
and is indistinguishable from an absent one (one generic 404, no existence
leak).

Structural no-execution guarantee: this package imports no research code and
holds no estimator — every response is a projection of an immutable published
row, so endpoint access can never trigger a fit or a provider call.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine

from near_api.auth.principal import get_runtime_engine
from near_api.db.session import user_transaction
from near_api.models import service
from near_api.pagination import PublicPage, encode_page_cursor
from near_api.schemas.models import (
    SPEC_ID_PATTERN,
    ModelDefinitionListResponse,
    ModelDefinitionResponse,
    ModelReadinessResponse,
    ModelRunDetailResponse,
    ModelRunListResponse,
)

router = APIRouter(prefix="/api", tags=["models"])

RuntimeEngineDependency = Annotated[Engine, Depends(get_runtime_engine)]

_CATALOG_CACHE = "public, max-age=60"
_IMMUTABLE_CACHE = "public, max-age=31536000, immutable"


def _not_found() -> HTTPException:
    # Absent, unpublished and not-published-yet share one generic response.
    return HTTPException(404, "Resource was not found")


@router.get("/model-runs", response_model=ModelRunListResponse,
            operation_id="listModelRuns", summary="Catalog of published model runs",
            responses={422: {"description": "Request failed validation"}})
def list_model_runs(engine: RuntimeEngineDependency, response: Response,
                    page: PublicPage,
                    model_id: Annotated[str | None, Query(max_length=80,
                                                          pattern=SPEC_ID_PATTERN)] = None
                    ) -> ModelRunListResponse:
    """List published runs newest-first (unpublished runs are never listed)."""
    offset, limit = page
    with user_transaction(engine, None) as connection:
        rows, total = service.list_published_runs(connection, limit=limit,
                                                  offset=offset, model_id=model_id)
        items = tuple(service.run_summary(row) for row in rows)
    response.headers["Cache-Control"] = _CATALOG_CACHE
    next_cursor = encode_page_cursor(offset + limit) if offset + limit < total else None
    return ModelRunListResponse(items=items, next_cursor=next_cursor)


@router.get("/model-runs/{run_id}", response_model=ModelRunDetailResponse,
            operation_id="getModelRun", summary="One published run with its results",
            responses={404: {"description": "Published run not found"}})
def get_model_run(engine: RuntimeEngineDependency, response: Response,
                  run_id: UUID) -> ModelRunDetailResponse:
    """Return one published run; non-published identities are the same 404."""
    with user_transaction(engine, None) as connection:
        row = service.get_published_run_row(connection, run_id)
        if row is None:
            raise _not_found()
        detail = service.run_detail(row)
    response.headers["Cache-Control"] = _IMMUTABLE_CACHE
    response.headers["ETag"] = f'"{run_id}"'
    return detail


@router.get("/model-runs/{run_id}/manifest", operation_id="getModelRunManifest",
            summary="Downloadable manifest bundle of one published run",
            responses={
                200: {"description": "Canonical manifest bundle JSON",
                      "content": {"application/json": {"schema": {"type": "object",
                                                                  "additionalProperties": True}}}},
                404: {"description": "Published run not found"},
            })
def get_model_run_manifest(engine: RuntimeEngineDependency, run_id: UUID) -> JSONResponse:
    """Serve the verified bundle verbatim; ``research verify --bundle`` accepts it."""
    with user_transaction(engine, None) as connection:
        row = service.get_published_run_row(connection, run_id)
        if row is None:
            raise _not_found()
        bundle = service.manifest_bundle(row)
    return JSONResponse(
        content=bundle,
        headers={"Cache-Control": _IMMUTABLE_CACHE,
                 "ETag": f'"{run_id}"',
                 "Content-Disposition":
                     f'attachment; filename="model-run-{run_id}-manifest.json"'})


@router.get("/model-definitions", response_model=ModelDefinitionListResponse,
            operation_id="listModelDefinitions",
            summary="Public model definitions (published specifications only)",
            responses={422: {"description": "Request failed validation"}})
def list_model_definitions(engine: RuntimeEngineDependency, response: Response,
                           page: PublicPage) -> ModelDefinitionListResponse:
    """List definitions derived from published runs (never from local reports)."""
    offset, limit = page
    with user_transaction(engine, None) as connection:
        items, total = service.list_model_definitions(connection, limit=limit,
                                                      offset=offset)
    response.headers["Cache-Control"] = _CATALOG_CACHE
    next_cursor = encode_page_cursor(offset + limit) if offset + limit < total else None
    return ModelDefinitionListResponse(items=tuple(items), next_cursor=next_cursor)


@router.get("/model-definitions/{model_id}", response_model=ModelDefinitionResponse,
            operation_id="getModelDefinition", summary="One public model definition",
            responses={404: {"description": "Published model definition not found"}})
def get_model_definition(engine: RuntimeEngineDependency, response: Response,
                         model_id: Annotated[str, Path(pattern=SPEC_ID_PATTERN)],
                         version: Annotated[int | None, Query(ge=1)] = None) \
        -> ModelDefinitionResponse:
    """One specification's definition from its latest published run."""
    with user_transaction(engine, None) as connection:
        definition = service.get_model_definition(connection, model_id, version=version)
        if definition is None:
            raise _not_found()
    response.headers["Cache-Control"] = _CATALOG_CACHE
    return definition


@router.get("/model-definitions/{model_id}/readiness",
            response_model=ModelReadinessResponse,
            operation_id="getModelReadiness",
            summary="NI-051 gate verdict for one specification (public)",
            responses={404: {"description": "No published readiness verdict"}})
def get_model_readiness(engine: RuntimeEngineDependency, response: Response,
                        model_id: Annotated[str, Path(pattern=SPEC_ID_PATTERN)]) \
        -> ModelReadinessResponse:
    """The recorded gate verdict; a never-published verdict is the same 404."""
    with user_transaction(engine, None) as connection:
        readiness = service.get_model_readiness(connection, model_id)
        if readiness is None:
            raise _not_found()
    response.headers["Cache-Control"] = _CATALOG_CACHE
    return readiness
