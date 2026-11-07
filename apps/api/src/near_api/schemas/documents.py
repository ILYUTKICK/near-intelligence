"""NI-036 document HTTP contracts for the implemented routes.

Pinned to API_SPECIFICATION.md: ``Document`` is the summary plus the canonical
content and resolved contexts; ``VersionSummary``/``VersionDetail`` describe
immutable revisions; the save request carries ``schema_version``, the editor
document and ``observed_contexts``. The summary/progress models are REUSED
from :mod:`near_api.schemas.home` (no duplicate DTOs); the inner canonical
document JSON is validated by :mod:`near_api.documents.schema` (strict
unknown-node/attribute rejection lives there, not in these envelope models).
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from near_api.schemas.common import ContractModel
from near_api.schemas.home import DocumentSummary


class DocumentCreateRequest(ContractModel):
    """POST /documents body. `template_id` is P1: providing it is a typed 422."""

    title: str = Field(min_length=1, max_length=200)
    template_id: Literal["investment-v1"] | None = None


class DocumentResponse(DocumentSummary):
    """`Document` = DocumentSummary plus current canonical content."""

    content: dict
    resolved_contexts: dict


class DocumentListResponse(ContractModel):
    """GET /documents response: bounded page with an opaque next cursor."""

    items: tuple[DocumentSummary, ...]
    next_cursor: str | None


class DocumentSaveRequest(ContractModel):
    """POST /documents/{id}/versions body (If-Match header carries the CAS)."""

    schema_version: int = Field(strict=True, ge=1)
    content: dict
    observed_contexts: tuple[dict, ...] = ()


class DocumentRenameRequest(ContractModel):
    """PATCH /documents/{id} body: the new title (a title change creates a
    full new revision — EDITOR_SPECIFICATION; an unchanged title is a no-op)."""

    title: str = Field(min_length=1, max_length=200)


class VersionSummaryResponse(ContractModel):
    id: UUID
    document_id: UUID
    revision: int = Field(strict=True, ge=1)
    schema_version: int = Field(strict=True, ge=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime


class VersionDetailResponse(VersionSummaryResponse):
    content: dict
    resolved_contexts: dict


class DocumentSaveResponse(ContractModel):
    """201 body of the save route: the new revision plus the moved summary."""

    version: VersionDetailResponse
    document: DocumentSummary


class VersionListResponse(ContractModel):
    """GET /documents/{id}/versions response: bounded page, newest first."""

    items: tuple[VersionSummaryResponse, ...]
    next_cursor: str | None
