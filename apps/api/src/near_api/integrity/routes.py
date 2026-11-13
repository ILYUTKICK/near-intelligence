"""Integrity report HTTP route (NI-065): one owner-scoped, read-only GET.

Implements the integrity row of API_SPECIFICATION under the ``/api`` prefix.
The report is a deterministic analysis of ONE immutable revision row:

- ``GET /documents/{document_id}/integrity`` — the acknowledged current
  revision by default (an owned document without one gets the explicit empty
  report, never fabricated content); an optional ``version_id`` query checks
  a historical revision, labeled ``is_acknowledged:false`` — read-only
  advisory, never refused.

Every route authenticates through ``get_principal`` (NI-018) and derives the
owner from the verified session — a foreign or absent document is the same
generic 404 (NI-019 semantics) — and emits ``Cache-Control: no-store``
(private analysis, never cacheable). The checks write nothing: a rerun is a
new GET, and no finding can trigger a mutation server-side.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.engine import Engine

from near_api.auth.principal import Principal, get_principal, get_runtime_engine
from near_api.db.security import principal_transaction
from near_api.documents.routes import _PRIVATE_ERROR_RESPONSES
from near_api.integrity.checks import build_integrity_report
from near_api.repositories.documents import get_document, get_version
from near_api.schemas.integrity import IntegrityReport

router = APIRouter(prefix="/api", tags=["integrity"])

PrincipalDependency = Annotated[Principal, Depends(get_principal)]
RuntimeEngineDependency = Annotated[Engine, Depends(get_runtime_engine)]

_INTEGRITY_ERROR_RESPONSES = {
    status: _PRIVATE_ERROR_RESPONSES[status] for status in (401, 403, 404, 422)
}


@router.get("/documents/{document_id}/integrity", response_model=IntegrityReport,
            operation_id="getDocumentIntegrity",
            summary="Run the deterministic advisory integrity checks on an owned "
                    "document's acknowledged (or requested historical) revision",
            responses=_INTEGRITY_ERROR_RESPONSES)
def get_document_integrity(request: Request, principal: PrincipalDependency,
                           engine: RuntimeEngineDependency, response: Response,
                           document_id: UUID,
                           version_id: Annotated[UUID | None, Query()] = None,
                           ) -> IntegrityReport:
    """Report advisory integrity findings for one immutable revision.

    Read-only and deterministic per revision content: findings carry exact
    block/entity/context/dataset/definition references and advisory severities
    (never a truth score), and no finding can change a pin, coefficient or
    document — refresh and citation remain explicit author actions.
    """
    response.headers["Cache-Control"] = "no-store"
    with principal_transaction(engine, principal) as connection:
        document = get_document(connection, principal, document_id)
        if version_id is None:
            current = document.current_version_id
            if current is None:
                # Explicit empty result for an owned document with no
                # acknowledged revision (evidence/links.py precedent):
                # missing is reported, never substituted with fake content.
                return IntegrityReport(
                    document_id=document.id, version_id=None,
                    revision=document.revision, is_acknowledged=False,
                    findings=(), counts=())
            version = get_version(connection, principal, document_id, current)
            report = build_integrity_report(connection, document, version,
                                            is_acknowledged=True)
        else:
            version = get_version(connection, principal, document_id, version_id)
            report = build_integrity_report(
                connection, document, version,
                is_acknowledged=version.id == document.current_version_id)
    response.headers["Cache-Control"] = "no-store"
    return report
