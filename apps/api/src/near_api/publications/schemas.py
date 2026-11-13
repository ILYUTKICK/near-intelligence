"""NI-045 publication HTTP contracts for the implemented routes.

Pinned to API_SPECIFICATION.md: ``GET /publications/{slug}`` serves the
published public projection verbatim (``{id, slug, version, title, content,
evidence_manifest, published_at, content_sha256}``); ``POST
/publications/{slug}/duplicate`` takes the pinned ``publication_version``
and an optional private title and returns the created private ``Document``
(201). The inner canonical document JSON is validated by
:mod:`near_api.documents.schema` (strict unknown-node rejection lives
there); these envelope models carry the identity/projection fields only.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from near_api.schemas.common import ContractModel

SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{0,79}$"
"""Public slug grammar (mirrors the migration CHECK and the idempotency
route-key bound: 24-char prefix + 80-char slug stays under 120 chars)."""

MAX_MANIFEST_ENTRIES = 200
"""Bound on one publication's public evidence manifest entries."""


class PublicationEvidenceRef(ContractModel):
    """One public evidence reference inside a publication's manifest."""

    kind: Literal["model_run", "citation"]
    id: UUID
    label: str | None = Field(default=None, max_length=300)


class PublicationResponse(ContractModel):
    """GET /publications/{slug} response: one published release projection."""

    id: UUID
    slug: str = Field(pattern=SLUG_PATTERN)
    version: int = Field(strict=True, ge=1)
    title: str = Field(min_length=1, max_length=200)
    content: dict
    evidence_manifest: tuple[PublicationEvidenceRef, ...] \
        = Field(default=(), max_length=MAX_MANIFEST_ENTRIES)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    published_at: datetime


class PublicationDuplicateRequest(ContractModel):
    """POST /publications/{slug}/duplicate body.

    ``publication_version`` pins the cloned release (never "latest" by
    accident — the client states the version it read); ``title`` defaults to
    the publication's title when omitted.
    """

    publication_version: int = Field(strict=True, ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)


__all__ = [
    "MAX_MANIFEST_ENTRIES",
    "SLUG_PATTERN",
    "PublicationDuplicateRequest",
    "PublicationEvidenceRef",
    "PublicationResponse",
]
