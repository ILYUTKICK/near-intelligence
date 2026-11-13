"""Public publication read route and the private duplicate route (NI-045).

Implements the API_SPECIFICATION ``/publications/{slug}`` rows:

- ``GET /publications/{slug}`` — public read through the unprivileged
  ``near_app`` role with NO identity and no user-identifying input; serves
  ONLY published rows (absent/unpublished is the one generic 404, no
  existence leak). A pinned ``version`` response is immutable content, so it
  carries the immutable cache header and the content-hash ETag; the
  latest-version default re-resolves when a new release is seeded, so it
  carries the catalog cache lifetime.
- ``POST /publications/{slug}/duplicate`` — owner-scoped: the verified
  principal receives a PRIVATE document (the publication stays public,
  untouched, immutable); the copy belongs to the requesting owner alone and
  is invisible to everyone else. Honors ``Idempotency-Key: UUID`` — the
  created document's response snapshot is committed in the same transaction
  as the write, so a repeated identical owner/route/body request replays the
  ORIGINAL 201 (same document id, byte-identical) instead of a second copy;
  the same key with a different body is a 409 IDEMPOTENCY_CONFLICT. If-Match
  does not apply: the request does not address an existing private resource.

The document envelope and revision ETag are shared with the documents routes.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Header, Path, Query, Request, Response
from sqlalchemy.engine import Engine

from near_api.auth.principal import Principal, get_principal, get_runtime_engine
from near_api.contracts import error_response
from near_api.documents import idempotency
from near_api.documents.routes import _document_response, _etag, _schema_error
from near_api.documents.schema import DocumentSchemaError, canonical_bytes
from near_api.db.session import user_transaction
from near_api.publications import duplicate, store
from near_api.publications.schemas import (
    SLUG_PATTERN,
    PublicationDuplicateRequest,
    PublicationResponse,
)
from near_api.schemas.common import ErrorResponse
from near_api.schemas.documents import DocumentResponse

router = APIRouter(prefix="/api", tags=["publications"])

PrincipalDependency = Annotated[Principal, Depends(get_principal)]
RuntimeEngineDependency = Annotated[Engine, Depends(get_runtime_engine)]

_CATALOG_CACHE = "public, max-age=60"
_IMMUTABLE_CACHE = "public, max-age=31536000, immutable"

_DUPLICATE_ERROR_RESPONSES = {
    status: {"model": ErrorResponse, "description": description}
    for status, description in (
        (401, "Missing or invalid session"),
        (403, "Verified account is disabled"),
        (404, "Published release not found"),
        (409, "Idempotency-Key reused with a different request"),
        (422, "Request failed validation or a public pin is unavailable"),
    )
}


def _publication_response(row: store.PublicationRow) -> PublicationResponse:
    return PublicationResponse(
        id=row.id, slug=row.slug, version=row.version, title=row.title,
        content=row.content,
        evidence_manifest=tuple(row.evidence_manifest),
        content_sha256=row.content_sha256, published_at=row.published_at)


@router.get("/publications/{slug}", response_model=PublicationResponse,
            operation_id="getPublication",
            summary="One published public research release",
            responses={404: {"description": "Published release not found"}})
def get_publication(engine: RuntimeEngineDependency, response: Response,
                    slug: Annotated[str, Path(pattern=SLUG_PATTERN)],
                    version: Annotated[int | None, Query(ge=1)] = None,
                    ) -> PublicationResponse:
    """Return the published release; unpublished identities are the same 404."""
    with user_transaction(engine, None) as connection:
        row = store.get_published_publication(connection, slug, version=version)
    if row is None:
        # Absent, mis-slugged and not-published share one generic 404.
        raise HTTPException(404, "Resource was not found")
    if version is None:
        # "Latest approved default": a newer release changes the answer.
        response.headers["Cache-Control"] = _CATALOG_CACHE
    else:
        # A pinned (slug, version) row is immutable: cache it with its hash.
        response.headers["Cache-Control"] = _IMMUTABLE_CACHE
        response.headers["ETag"] = f'"{row.content_sha256}"'
    return _publication_response(row)


@router.post("/publications/{slug}/duplicate", response_model=DocumentResponse,
             operation_id="duplicatePublication", status_code=201,
             summary="Clone a published release into a new private document",
             responses=_DUPLICATE_ERROR_RESPONSES)
def duplicate_publication_route(request: Request, principal: PrincipalDependency,
                                engine: RuntimeEngineDependency, response: Response,
                                payload: PublicationDuplicateRequest,
                                slug: Annotated[str, Path(pattern=SLUG_PATTERN)],
                                idempotency_key: Annotated[str | None, Header()] = None,
                                ) -> DocumentResponse | Response:
    """Clone one pinned release into a new private document with attribution.

    The clone allocates fresh private IDs, rebuilds and re-verifies every
    chart context from its immutable pins (an unavailable pinned dataset or
    chart definition is an explicit typed 422, never a latest substitution),
    keeps public data/model pins verbatim and records the source release as
    retained attribution. The publication itself is immutable and unchanged.
    """
    try:
        key = idempotency.parse_idempotency_key(idempotency_key)
    except DocumentSchemaError as error:
        return _schema_error(request, error)
    if key is not None:
        # The concrete slug is part of the route identity (one release cannot
        # replay another release's result); the fingerprint body covers the
        # pinned version and the chosen title.
        route_key = f"POST /api/publications/{slug}/duplicate"
        try:
            outcome = idempotency.execute_idempotent(
                engine, principal, route_key=route_key, idempotency_key=key,
                request_hash=idempotency.request_fingerprint(
                    route_key, principal.id, payload.model_dump(mode="json")),
                operation=lambda connection: (
                    201, _document_response(duplicate.load_and_duplicate_in_transaction(
                        connection, principal, slug=slug,
                        version=payload.publication_version, title=payload.title))
                    .model_dump(mode="json")))
        except idempotency.IdempotencyConflict:
            return error_response(
                request, 409, "IDEMPOTENCY_CONFLICT",
                "This Idempotency-Key was already used with a different request; "
                "a new key is required for a new payload")
        except DocumentSchemaError as error:
            # Nothing was stored: a failed duplicate stays retryable.
            return _schema_error(request, error)
        # The stored JSONB response can return its keys in a different order.
        # Serialize fresh and replayed snapshots identically.
        return Response(
            content=canonical_bytes(outcome.body),
            status_code=outcome.status,
            media_type="application/json",
            headers={"Cache-Control": "no-store", "ETag": _etag(outcome.body["revision"])},
        )
    try:
        detail = duplicate.duplicate_publication(
            engine, principal, slug=slug, version=payload.publication_version,
            title=payload.title)
    except DocumentSchemaError as error:
        return _schema_error(request, error)
    response.headers["Cache-Control"] = "no-store"
    response.headers["ETag"] = _etag(detail.document.revision)
    return _document_response(detail)
