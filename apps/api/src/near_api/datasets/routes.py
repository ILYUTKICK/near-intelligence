"""Public dataset and data-source routes implemented by NI-032.

Implements the API_SPECIFICATION ``/datasets`` and ``/data-sources`` rows:
approved dataset versions with their aggregated quality, the sanitized
prepared manifest and the sanitized source catalog. Only ``approved``
versions are visible — staged/validated/rejected versions are
indistinguishable from absent — and source projections never carry the
provider endpoint or any credential-bearing value.
"""

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Response
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine

from near_api.auth.principal import get_runtime_engine
from near_api.datasets import delivery
from near_api.db.session import user_transaction
from near_api.pagination import PublicPage, encode_page_cursor
from near_api.schemas.delivery import (
    DataSourceListResponse,
    DataSourceResponse,
    DatasetResponse,
)

router = APIRouter(prefix="/api", tags=["datasets"])

RuntimeEngineDependency = Annotated[Engine, Depends(get_runtime_engine)]

_CATALOG_CACHE = "public, max-age=60"
_IMMUTABLE_CACHE = "public, max-age=31536000, immutable"

_SOURCE_ID_PATTERN = r"^SRC-[A-Z0-9]+(-[A-Z0-9]+)*$"


@router.get("/data-sources", response_model=DataSourceListResponse,
            operation_id="listDataSources", summary="Sanitized public source catalog",
            responses={422: {"description": "Request failed validation"}})
def list_data_sources(engine: RuntimeEngineDependency, response: Response,
                      page: PublicPage) -> DataSourceListResponse:
    """List the sanitized source projections (never provider endpoints)."""
    offset, limit = page
    with user_transaction(engine, None) as connection:
        rows, total = delivery.list_source_rows(connection, limit=limit, offset=offset)
        items = tuple(delivery.source_response(row) for row in rows)
    response.headers["Cache-Control"] = _CATALOG_CACHE
    next_cursor = encode_page_cursor(offset + limit) if offset + limit < total else None
    return DataSourceListResponse(items=items, next_cursor=next_cursor)


@router.get("/data-sources/{source_id}", response_model=DataSourceResponse,
            operation_id="getDataSource", summary="One sanitized source projection",
            responses={404: {"description": "Data source not found"}})
def get_data_source(engine: RuntimeEngineDependency, response: Response,
                    source_id: Annotated[str, Path(pattern=_SOURCE_ID_PATTERN)],
                    ) -> DataSourceResponse:
    """Return one source's sanitized projection (missing sources are 404)."""
    with user_transaction(engine, None) as connection:
        row = delivery.get_source_row(connection, source_id)
    response.headers["Cache-Control"] = _CATALOG_CACHE
    return delivery.source_response(row)


@router.get("/datasets/{version_id}", response_model=DatasetResponse,
            operation_id="getDataset",
            summary="One approved immutable dataset version",
            responses={404: {"description": "Approved dataset version not found"}})
def get_dataset(engine: RuntimeEngineDependency, response: Response,
                version_id: UUID) -> DatasetResponse:
    """Return one approved dataset version; non-approved versions are 404."""
    with user_transaction(engine, None) as connection:
        version, content = delivery.load_approved_dataset(connection, version_id)
        dataset = delivery.dataset_response(version, content)
    response.headers["Cache-Control"] = _IMMUTABLE_CACHE
    # The immutable content hash is the strongest entity tag the version has.
    response.headers["ETag"] = f'"{dataset.content_sha256}"'
    return dataset


@router.get("/datasets/{version_id}/manifest", operation_id="getDatasetManifest",
            summary="Sanitized prepared manifest of one approved dataset version",
            responses={
                200: {"description": "Sanitized prepared manifest JSON",
                      "content": {"application/json": {"schema": {"type": "object",
                                                                  "additionalProperties": True}}}},
                404: {"description": "Approved version or servable manifest not found"},
                413: {"description": "Manifest exceeds the bounded public payload size"},
            })
def get_dataset_manifest(engine: RuntimeEngineDependency, version_id: UUID) -> JSONResponse:
    """Serve the sanitized manifest: storage digests, never operator paths."""
    with user_transaction(engine, None) as connection:
        manifest = delivery.build_dataset_manifest(connection, version_id)
    # json.dumps round-trip guarantees the served bytes carry only strict JSON
    # types (the manifest is already canonicalized by the delivery service).
    return JSONResponse(content=json.loads(json.dumps(manifest)),
                        headers={"Cache-Control": _IMMUTABLE_CACHE,
                                 "ETag": f'"{manifest["content_sha256"]}"'})
