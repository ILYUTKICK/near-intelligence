"""Grounded-commentary HTTP route (NI-065): opt-in, read-only, bounded.

Implements the commentary row of API_SPECIFICATION under the ``/api`` prefix:

- ``POST /documents/{document_id}/grounded-commentary`` — advisory
  commentary over an EXPLICITLY selected context (block ids of the
  acknowledged revision). The endpoint is read-only: it never changes a pin,
  coefficient, context or document.

Availability is explicit (ADR-022): without enabled server configuration the
response carries the typed ``unavailable``/``adapter_disabled`` state — never
a fabricated successful commentary. Even when enabled, no unapproved context
leaves the machine: the prompt is built only from the selected blocks
(frozen contexts + bounded authored prose), and a number in the response that
the provided context does not contain is refused as ungrounded. The API key
stays server-side and never appears in a response, log or error body.

Every route authenticates through ``get_principal`` (NI-018) and derives the
owner from the verified session — a foreign or absent document is the same
generic 404 (NI-019 semantics) — and emits ``Cache-Control: no-store``.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.engine import Engine

from near_api.ai import adapter
from near_api.ai.settings import get_ai_commentary
from near_api.auth.principal import Principal, get_principal, get_runtime_engine
from near_api.db.security import principal_transaction
from near_api.documents.routes import _PRIVATE_ERROR_RESPONSES
from near_api.documents.schema import DocumentSchemaError, parse_document
from near_api.repositories.documents import get_document, get_version
from near_api.schemas.integrity import (
    COMMENTARY_NOTICE,
    GroundedCommentaryRequest,
    GroundedCommentaryResponse,
)
from near_api.settings import SettingsError

router = APIRouter(prefix="/api", tags=["ai"])

PrincipalDependency = Annotated[Principal, Depends(get_principal)]
RuntimeEngineDependency = Annotated[Engine, Depends(get_runtime_engine)]

_COMMENTARY_ERROR_RESPONSES = {
    status: _PRIVATE_ERROR_RESPONSES[status] for status in (401, 403, 404, 422)
}

# Test seam: the transport used for the provider call (None = the default
# httpx transport). Production passes None; adapter tests inject a
# httpx.MockTransport so no real provider request is ever possible in tests.
def _provider_transport():
    return None


def _response(document_id: UUID, version_id: UUID | None, revision: int | None,
              state: str, reason: str | None = None, message: str | None = None,
              items=()) -> GroundedCommentaryResponse:
    return GroundedCommentaryResponse(
        document_id=document_id, version_id=version_id, revision=revision,
        state=state, reason=reason, message=message, advisory=True,
        notice=COMMENTARY_NOTICE, items=items)


@router.post("/documents/{document_id}/grounded-commentary",
             response_model=GroundedCommentaryResponse,
             operation_id="createGroundedCommentary",
             summary="Request bounded advisory commentary over explicitly "
                     "selected blocks of the acknowledged revision "
                     "(requires enabled server configuration)",
             responses=_COMMENTARY_ERROR_RESPONSES)
def create_grounded_commentary(request: Request, principal: PrincipalDependency,
                               engine: RuntimeEngineDependency, response: Response,
                               document_id: UUID,
                               payload: GroundedCommentaryRequest,
                               ) -> GroundedCommentaryResponse:
    """Advisory commentary over the explicitly selected context — or the typed absence.

    Ownership is checked before anything else (one generic 404). With the
    adapter disabled the typed unavailable state is returned without reading
    any provider secret; when enabled, exactly one bounded provider call is
    made over the selected context and every returned item is marked advisory.
    """
    # Private content (document/revision references) on EVERY response path.
    response.headers["Cache-Control"] = "no-store"
    with principal_transaction(engine, principal) as connection:
        document = get_document(connection, principal, document_id)
        # Owner isolation precedes optional configuration on every path,
        # including an enabled but incomplete adapter configuration.
        try:
            config = get_ai_commentary()
        except SettingsError as error:
            return _response(document_id, None, None, "failed",
                             reason="adapter_misconfigured", message=str(error))
        if document.current_version_id is None:
            return _response(document_id, None, None, "failed",
                             reason="no_acknowledged_revision",
                             message="The document has no acknowledged revision to "
                                     "ground commentary on")
        version = get_version(connection, principal, document_id, document.current_version_id)
        if not config.enabled:
            return _response(document_id, version.id, version.revision, "unavailable",
                             reason="adapter_disabled",
                             message="Grounded commentary is not enabled on this server")
        try:
            canonical = parse_document(version.content)
        except DocumentSchemaError as error:
            return _response(document_id, version.id, version.revision, "failed",
                             reason="unresolved_block_context",
                             message=f"The acknowledged revision cannot be parsed "
                                     f"for grounding ({error.details[0][1]})")
        try:
            selected = adapter.select_context(canonical, version.resolved_contexts,
                                              payload.block_ids)
            prompt = adapter.build_prompt(selected, payload.question,
                                          revision=version.revision)
        except adapter.CommentaryError as error:
            return _response(document_id, version.id, version.revision, "failed",
                             reason=error.reason, message=error.message)
    try:
        text = adapter.call_provider(config, prompt, transport=_provider_transport())
        # Grounding source: the selected sections plus the author's question
        # (never the server preamble) — a number outside them is refused.
        grounding_source = "\n".join(block.section for block in selected) \
            + f"\nQuestion: {payload.question}"
        adapter.verify_grounded(text, grounding_source)
        items = adapter.commentary_items(selected, text)
    except adapter.CommentaryError as error:
        return _response(document_id, version.id, version.revision, "failed",
                         reason=error.reason, message=error.message)
    return _response(document_id, version.id, version.revision, "ok",
                     items=items)
