"""Typed read-only share projection and share HTTP contracts (NI-060, ADR-021).

The share projection is the PUBLIC allowlist payload of ONE frozen document
revision: a deliberate narrowing of the NI-056 export IR built by
:mod:`near_api.shares.projection`. It is a DISTINCT model, never the export
IR itself — everything private is structurally absent:

- excluded: owner id, author identity, document/version/insight/hypothesis/
  evidence/target private UUIDs, annotation authorship and modified
  timestamps, evidence explanations, snapshot ids;
- kept: title, revision, revision creation time, content SHA-256, schema
  version, block ids (needed to address chart blocks), public-safe chart pins
  (chart definition version, dataset version, selection, the frozen
  ``ChartViewResponse``), dataTable columns/rows/dataset references, rich
  text, insight/hypothesis content, risk cards, sanitized source id+name,
  published model run references, citation artifact ids and a deterministic
  limitations line.

Unlike :mod:`near_api.schemas.export` (service-level, not registered), these
models ARE the public HTTP response of ``GET /api/shares/{token}``, so they
are registered in the OpenAPI components and the generated client.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, StringConstraints

from near_api.insights.schemas import (
    EvidenceClassification,
    EvidenceTargetKind,
    HypothesisAssessment,
    InsightContext,
    InsightType,
    RichTextBody,
    RichTextListItem,
    RichTextRun,
    ServerTimestamp,
    Sha256Hex,
)
from near_api.schemas.chart_selection import ChartSelection
from near_api.schemas.common import ContractModel
from near_api.schemas.delivery import ChartViewResponse

SHARE_PROJECTION_VERSION = 1
"""The only publication-projection version this builder emits. A future
change appends a new version and a pure transform; stored share bytes never
silently refresh (REPRODUCIBILITY)."""

ChartMode = Literal["live"]
"""P0 publication admits live-pinned charts only (the same rule as the
frozen export IR; a snapshot block cannot be reconstructed at all)."""


class ShareDocumentMeta(ContractModel):
    """Revision attribution of the published projection.

    ``title`` is the document row's title read in the same transaction as the
    revision content while that revision was the acknowledged current version.
    No author identity is carried: the share publishes content, not its
    owner's identity.
    """

    title: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    revision: int = Field(strict=True, ge=1)
    schema_version: int = Field(strict=True, ge=1)
    content_sha256: Sha256Hex
    created_at: ServerTimestamp
    limitations: Annotated[str, StringConstraints(min_length=1, max_length=500)]


class ShareParagraphBlock(ContractModel):
    block_type: Literal["paragraph"]
    block_id: UUID
    runs: tuple[RichTextRun, ...]


class ShareHeadingBlock(ContractModel):
    block_type: Literal["heading"]
    block_id: UUID
    level: int = Field(strict=True, ge=1, le=3)
    runs: tuple[RichTextRun, ...]


class ShareListBlock(ContractModel):
    block_type: Literal["bullet_list", "ordered_list"]
    block_id: UUID
    items: tuple[RichTextListItem, ...] = Field(min_length=1)


class ShareChartBlock(ContractModel):
    """A liveChart block with its fully resolved frozen evidence.

    ``view`` is the embedded NI-043 reconstruction (the pinned
    ``ChartViewResponse``); the public chart routes serve it and its derived
    CSV verbatim from the stored projection bytes. Unlike the export IR, no
    snapshot id is carried.
    """

    block_type: Literal["liveChart"]
    block_id: UUID
    chart_definition_version_id: UUID
    mode: ChartMode
    selection: ChartSelection
    observed_dataset_version_id: UUID
    view: ChartViewResponse


class ShareDataTableColumn(ContractModel):
    key: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    label: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    type: Literal["string", "number", "date"]
    unit: str | None = Field(default=None, min_length=1, max_length=40)


class ShareDataTableDatasetReference(ContractModel):
    """The approved dataset version an authored table projects from."""

    dataset_version_id: UUID
    dataset_key: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    version: int = Field(strict=True, ge=1)
    content_sha256: Sha256Hex


ShareDataTableCell = str | bool | None
"""A published authored cell (exact decimal strings; see the export IR)."""


class ShareDataTableBlock(ContractModel):
    block_type: Literal["dataTable"]
    block_id: UUID
    columns: tuple[ShareDataTableColumn, ...] = Field(min_length=1, max_length=100)
    rows: tuple[tuple[ShareDataTableCell, ...], ...] | None = None
    dataset: ShareDataTableDatasetReference | None = None


class ShareInsightBlock(ContractModel):
    """A structured observation card without its private editorial metadata.

    The insight's internal id, authorship timestamps and hypothesis link are
    excluded; ``context`` keeps only public-safe pins (chart definition /
    dataset version / selection / resolved-at, or the published run
    reference).
    """

    block_type: Literal["insight"]
    block_id: UUID
    insight_type: InsightType
    classification: EvidenceClassification
    body: RichTextBody
    context: InsightContext


class ShareHypothesisBlock(ContractModel):
    block_type: Literal["hypothesis"]
    block_id: UUID
    statement: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    assessment: HypothesisAssessment


class ShareEvidenceBlock(ContractModel):
    """An evidence relationship without its private explanation.

    ``target_ref`` is the resolvable public reference of the target: the
    in-revision target BLOCK id for ``insight``/``chart_block`` targets, the
    published run id for ``model_run`` and the public artifact id for
    ``citation``. The private evidence/hypothesis ids are excluded.
    """

    block_type: Literal["evidence"]
    block_id: UUID
    classification: EvidenceClassification
    target_kind: EvidenceTargetKind
    target_ref: UUID | None


class ShareRiskBlock(ContractModel):
    block_type: Literal["risk"]
    block_id: UUID
    title: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    body: RichTextBody


class ShareDividerBlock(ContractModel):
    block_type: Literal["divider"]
    block_id: UUID


ShareBlock = Annotated[
    ShareParagraphBlock | ShareHeadingBlock | ShareListBlock | ShareChartBlock
    | ShareDataTableBlock | ShareInsightBlock | ShareHypothesisBlock
    | ShareEvidenceBlock | ShareRiskBlock | ShareDividerBlock,
    Field(discriminator="block_type"),
]


class ShareSourceReference(ContractModel):
    """One data source referenced by the published charts (id + name only)."""

    source_id: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class ShareModelRunReference(ContractModel):
    """One published model run referenced by the projection (NI-054)."""

    run_id: UUID
    spec_id: Annotated[str, StringConstraints(min_length=3, max_length=80)]
    spec_version: int = Field(strict=True, ge=1)


class ShareCitationReference(ContractModel):
    """One public citation artifact referenced by an evidence block."""

    artifact_id: UUID


class ShareProjection(ContractModel):
    """The complete public payload of one share (stored bytes = this)."""

    share_projection_version: Literal[SHARE_PROJECTION_VERSION]
    document: ShareDocumentMeta
    blocks: tuple[ShareBlock, ...] = Field(max_length=200)
    sources: tuple[ShareSourceReference, ...]
    model_runs: tuple[ShareModelRunReference, ...]
    citations: tuple[ShareCitationReference, ...]


class ShareScopeSummary(ContractModel):
    """The bounded visible-scope restatement the owner consents to.

    The counts are validated against the rebuilt projection at create time,
    so a stale preview (content edited after it was shown) is refused instead
    of silently publishing something else.
    """

    kind: Literal["frozen_revision_allowlist"]
    chart_blocks: int = Field(strict=True, ge=0)
    data_table_blocks: int = Field(strict=True, ge=0)
    insight_blocks: int = Field(strict=True, ge=0)
    source_references: int = Field(strict=True, ge=0)


class SharePreviewResponse(ContractModel):
    """The exact projection that would be published, with its identity."""

    document_id: UUID
    revision: int = Field(strict=True, ge=1)
    projection: ShareProjection
    projection_sha256: Sha256Hex
    scope: ShareScopeSummary


class DocumentShareCreateRequest(ContractModel):
    """The explicit consent to publish one frozen revision.

    ``acknowledged_revision`` and ``visible_scope`` name the revision and the
    visible scope; ``preview_sha256`` binds the consent to the exact preview
    bytes (server-verified).
    """

    acknowledged_revision: int = Field(strict=True, ge=1)
    visible_scope: ShareScopeSummary
    preview_sha256: Sha256Hex
    expires_at: AwareDatetime | None = None


class ShareCreatedResponse(ContractModel):
    """The owner's share record after create (or idempotent replay).

    ``share_token`` is returned exactly ONCE — the first (non-replay) create.
    A replay identifies the same share but cannot re-emit the unrecoverable
    token; the owner revokes and creates a new share to obtain a new link.
    """

    id: UUID
    document_id: UUID
    document_version_id: UUID
    revision: int = Field(strict=True, ge=1)
    status: Literal["active"]
    created_at: ServerTimestamp
    expires_at: ServerTimestamp | None
    share_token: str | None = Field(default=None, min_length=32, max_length=200)
    share_path: str | None = Field(default=None, min_length=32, max_length=300)


class ShareSummaryResponse(ContractModel):
    """One owner-visible share record (never the token or its hash)."""

    id: UUID
    document_id: UUID
    document_version_id: UUID
    revision: int = Field(strict=True, ge=1)
    status: Literal["active", "expired", "revoked"]
    created_at: ServerTimestamp
    expires_at: ServerTimestamp | None
    revoked_at: ServerTimestamp | None


class DocumentShareListResponse(ContractModel):
    """The owned document's shares, newest first (bounded, no pagination)."""

    items: tuple[ShareSummaryResponse, ...] = Field(max_length=100)
