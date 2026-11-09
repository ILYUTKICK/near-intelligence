"""Typed frozen document export representation (NI-056).

The export IR is the deterministic intermediate representation of ONE
acknowledged immutable document revision: the complete plan the export
pipeline (NI-057 static chart assets, NI-058 Markdown ZIP delivery) renders
from. It is a service-level contract, not an HTTP response: no route exposes
it in MVP, so these models are deliberately NOT registered in the OpenAPI
components (registering them would change the generated client, which is
NI-058's contract-change duty when a route consumes the IR).

Every value carried here is already pinned by the revision row itself or by
the immutable registries it references — the builder
(:mod:`near_api.exports.ir`) resolves chart evidence through the NI-043
historical resolver against the revision's saved contexts, so a chart's
series, units and quality equal the frozen view the author inspected. The IR
adds no wall-clock field of its own: building it twice for the same revision
yields byte-identical canonical serialization.

Reuse, never duplication: rich-text runs/lists and annotation bodies reuse
the NI-046 typed projections of the canonical editor grammar, chart evidence
reuses the NI-032 ``ChartViewResponse`` contract, selections reuse the shared
``ChartSelection``, and timestamps reuse ``ServerTimestamp``. Financial cell
values are exact decimal strings (never JavaScript-style binary floats);
raw token amounts keep integer/decimal-string spelling.
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

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

EXPORT_IR_VERSION = 1
"""The only frozen-representation version this builder emits. A future
representation change appends a new version and a pure transform; existing
export artifacts never silently refresh (REPRODUCIBILITY)."""

_DATA_TABLE_COLUMN_TYPES = ("string", "number", "date")

DataTableColumnType = Literal[_DATA_TABLE_COLUMN_TYPES]
ChartMode = Literal["live"]
"""P0 export admits live-pinned charts only: a ``snapshot`` block cannot be
reconstructed at all (the research snapshot registry is P1 NI-044), so the
builder fails closed before any snapshot spelling could reach the plan."""


class ExportAuthor(ContractModel):
    """Attribution of the exported revision (DATABASE_SCHEMA documents.owner).

    The owner is the verified principal's id; the display name comes from the
    owner's profile row and is ``None`` when no profile exists — missing is
    never fabricated into a placeholder author.
    """

    owner_id: UUID
    display_name: str | None = Field(default=None, min_length=1, max_length=80)


class ExportDocumentMeta(ContractModel):
    """Revision identification of the frozen export plan.

    ``title`` is the document row's title read in the SAME transaction as the
    revision content while the revision is the document's acknowledged
    current version (every title change creates a new revision), so the title
    and the content always describe the same revision. ``created_at`` is the
    immutable revision creation time — the export's revision date.
    """

    document_id: UUID
    version_id: UUID
    revision: int = Field(strict=True, ge=1)
    schema_version: int = Field(strict=True, ge=1)
    content_sha256: Sha256Hex
    title: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    author: ExportAuthor
    created_at: ServerTimestamp


class ExportSourceReference(ContractModel):
    """One data source referenced by the plan's resolved chart evidence.

    Carried as the sanitized delivery projection fields (id and name); the
    credential-bearing provider details of the source catalog stay excluded.
    """

    source_id: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=200)]


class ExportModelRunReference(ContractModel):
    """One published model run referenced by the plan (NI-054 catalog).

    Only published runs resolve; an unpublished run id can never appear here
    because the builder refuses it, and a published run is immutable.
    """

    run_id: UUID
    spec_id: Annotated[str, StringConstraints(min_length=3, max_length=80)]
    spec_version: int = Field(strict=True, ge=1)


class ExportCitationReference(ContractModel):
    """One public citation artifact referenced by an evidence block.

    The artifact registry records no public title (NI-049), so the plan
    carries the immutable public artifact id and the renderer labels it
    honestly from the id.
    """

    artifact_id: UUID


class ExportParagraphBlock(ContractModel):
    block_type: Literal["paragraph"]
    block_id: UUID
    runs: tuple[RichTextRun, ...]


class ExportHeadingBlock(ContractModel):
    block_type: Literal["heading"]
    block_id: UUID
    level: int = Field(strict=True, ge=1, le=3)
    runs: tuple[RichTextRun, ...]


class ExportListBlock(ContractModel):
    """A top-level bullet/ordered list block (canonical rich list grammar)."""

    block_type: Literal["bullet_list", "ordered_list"]
    block_id: UUID
    items: tuple[RichTextListItem, ...] = Field(min_length=1)


class ExportChartBlock(ContractModel):
    """A liveChart block with its fully resolved frozen evidence.

    ``view`` is the NI-043 historical reconstruction of the pinned context
    (the same ``ChartViewResponse`` the read-only history reader renders),
    with ``resolved_at`` equal to the context's saved inspection time — never
    a build-time clock reading. Series points carry explicit null values with
    quality reasons; absent data is never zero-filled.
    """

    block_type: Literal["liveChart"]
    block_id: UUID
    chart_definition_version_id: UUID
    mode: ChartMode
    selection: ChartSelection
    observed_dataset_version_id: UUID
    snapshot_id: UUID | None
    view: ChartViewResponse


class ExportDataTableColumn(ContractModel):
    """One authored dataTable column spec (key, label, type, optional unit)."""

    key: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    label: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    type: DataTableColumnType
    unit: str | None = Field(default=None, min_length=1, max_length=40)


class ExportDataTableDatasetReference(ContractModel):
    """The approved dataset version an authored table projects from.

    The pin is the reference (big data uses reference and pagination per
    EDITOR_SPECIFICATION); the renderer resolves the projection through this
    immutable version, never through a latest pointer.
    """

    dataset_version_id: UUID
    dataset_key: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    version: int = Field(strict=True, ge=1)
    content_sha256: Sha256Hex


DataTableCell = str | bool | None
"""An exported authored cell. Numbers are exported as exact decimal strings
(integers and finite floats alike — the shortest exact decimal spelling of
the stored value, no binary-float rounding), text verbatim, booleans and
explicit absence unchanged. Formulas are not executable content."""


class ExportDataTableBlock(ContractModel):
    """A dataTable block: authored rows XOR an approved dataset reference.

    ``rows`` carries the authored cells as exported (numbers normalized to
    exact decimal strings, at most 1k cells — the canonical bound). Exactly
    one of ``rows``/``dataset`` is set, mirroring the canonical block rule.
    """

    block_type: Literal["dataTable"]
    block_id: UUID
    columns: tuple[ExportDataTableColumn, ...] = Field(min_length=1, max_length=100)
    rows: tuple[tuple[DataTableCell, ...], ...] | None = None
    dataset: ExportDataTableDatasetReference | None = None

    @model_validator(mode="after")
    def exclusive_payload(self):
        """Authored rows and a dataset reference are mutually exclusive —
        the same canonical block rule, enforced on the exported plan."""
        if (self.rows is not None) == (self.dataset is not None):
            raise ValueError(
                "a dataTable export carries authored rows or a dataset "
                "reference, never both and never neither")
        return self


class ExportInsightBlock(ContractModel):
    """A structured observation/hypothesis/risk/conclusion card.

    ``context`` is the frozen inspection record stored on the node
    (:class:`~near_api.insights.schemas.ResolvedContext` or
    :class:`~near_api.insights.schemas.ModelContext`); the builder verified it
    against the immutable registries before exporting it verbatim.
    """

    block_type: Literal["insight"]
    block_id: UUID
    insight_id: UUID
    insight_type: InsightType
    classification: EvidenceClassification
    body: RichTextBody
    context: InsightContext
    authored_at: ServerTimestamp
    modified_at: ServerTimestamp
    hypothesis_id: UUID | None


class ExportHypothesisBlock(ContractModel):
    block_type: Literal["hypothesis"]
    block_id: UUID
    hypothesis_id: UUID
    statement: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    assessment: HypothesisAssessment
    authored_at: ServerTimestamp
    modified_at: ServerTimestamp


class ExportEvidenceBlock(ContractModel):
    """An evidence relationship block.

    ``target_block_id`` is set only when the target lives in this same
    revision (``insight``/``chart_block``); public ``model_run``/``citation``
    targets stay id references resolved through the immutable public catalogs.
    """

    block_type: Literal["evidence"]
    block_id: UUID
    evidence_id: UUID
    hypothesis_id: UUID
    classification: EvidenceClassification
    target_kind: EvidenceTargetKind
    target_id: UUID
    target_block_id: UUID | None
    explanation: Annotated[str, StringConstraints(min_length=1, max_length=2000)]


class ExportRiskBlock(ContractModel):
    """An explicit counterargument card (no algorithmic probability score)."""

    block_type: Literal["risk"]
    block_id: UUID
    title: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    body: RichTextBody
    related_hypothesis_id: UUID | None


class ExportDividerBlock(ContractModel):
    block_type: Literal["divider"]
    block_id: UUID


ExportBlock = Annotated[
    ExportParagraphBlock | ExportHeadingBlock | ExportListBlock | ExportChartBlock
    | ExportDataTableBlock | ExportInsightBlock | ExportHypothesisBlock
    | ExportEvidenceBlock | ExportRiskBlock | ExportDividerBlock,
    Field(discriminator="block_type"),
]
"""Every P0 block type of the canonical taxonomy (paragraph, heading,
bullet_list, ordered_list, liveChart, dataTable, insight, hypothesis,
evidence, risk, divider). The builder's dispatch covers exactly this union —
a block type outside it fails closed with a typed error instead of being
silently skipped."""


class ExportIr(ContractModel):
    """The complete frozen export plan of one acknowledged revision.

    ``document`` identifies the revision (title/author/date/revision
    metadata); ``blocks`` maps every block of the revision in document order;
    ``sources``/``model_runs``/``citations`` aggregate the immutable external
    references the plan's blocks resolve to (deduplicated, deterministic
    order) so a renderer can build its source appendix without re-resolving.
    """

    ir_version: Literal[EXPORT_IR_VERSION]
    document: ExportDocumentMeta
    blocks: tuple[ExportBlock, ...] = Field(max_length=200)
    sources: tuple[ExportSourceReference, ...]
    model_runs: tuple[ExportModelRunReference, ...]
    citations: tuple[ExportCitationReference, ...]
