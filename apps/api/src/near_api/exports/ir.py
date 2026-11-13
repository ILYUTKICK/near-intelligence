"""Build the frozen export representation of one acknowledged revision (NI-056).

The export IR (:mod:`near_api.schemas.export`) is a complete, deterministic
plan of ONE immutable document revision: title/author/revision metadata plus
a typed mapping of every P0 block, the fully resolved frozen chart evidence,
the data-table specs (column keys, types, cells as exact decimal strings)
and the aggregated source/model/citation references.

Frozen semantics, enforced here:

- **No latest-data lookups.** Chart evidence resolves exclusively through the
  NI-043 historical resolver (:func:`near_api.documents.context_resolver.
  reconstruct_revision_chart`) against the revision's saved contexts — the
  same path the read-only history reader uses, which verifies the revision
  and context hashes, the chart/metric/renderer versions and the pinned
  prepared-data digest. Dataset references (dataTable pins, context pins) are
  validated as approved immutable versions by id; the latest-pointer
  resolution of the delivery layer is never consulted on this path.
- **Fail closed.** A missing or inconsistent pinned artifact, an
  unresolvable model run/citation reference or a block type the export
  contract does not support raises :class:`ExportIrError` with bounded
  ``path``/``reason`` details. Current data is never substituted and nothing
  is silently skipped.
- **Title/content correspondence.** The plan is built only while the
  requested version is the document's acknowledged current revision: every
  title change creates a new revision (NI-037), so reading the document
  title and the revision content in one transaction with that check makes
  the exported title and content describe the same revision by
  construction. (Historical revisions carry no title snapshot, so a plan
  with attribution cannot honestly be produced for them; a revision that
  stopped being acknowledged keeps exporting only through the plan already
  built for it — never silently refreshed.)
- **Determinism.** No wall-clock field is added: every timestamp in the plan
  (revision creation, annotation authorship, inspection ``resolved_at``) is
  already pinned by the revision row or the registries. Building twice
  yields identical :func:`export_ir_canonical_bytes`.

Ownership follows the NI-019 repository pattern: the revision is reachable
only through the verified principal's document (absent and not-owned ids are
the same 404-equivalent :class:`~near_api.db.security.ResourceNotFound`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import NamedTuple
from uuid import UUID

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import Connection, Engine, select

from near_api.auth.principal import Principal
from near_api.db.models import DatasetVersion, ModelRun, UserProfile
from near_api.db.security import principal_transaction
from near_api.documents.context_resolver import (
    PublishedRunRow,
    ReconstructionError,
    build_model_context,
    reconstruct_revision_chart,
    require_approved_dataset,
    same_chart_pins,
    same_model_pins,
    verify_chart_context,
)
from near_api.documents.schema import (
    SCHEMA_VERSION,
    Block,
    CanonicalDocument,
    DataTableNode,
    DocumentSchemaError,
    EvidenceNode,
    HypothesisNode,
    InsightNode,
    LiveChartNode,
    ModelResultNode,
    RiskNode,
    parse_document,
)
from near_api.evidence.targets import validate_public_targets
from near_api.insights.schemas import (
    ModelContext,
    ResolvedContext,
    RichTextBody,
    RichTextListItem,
    RichTextList,
    RichTextRun,
)
from near_api.models import service as model_service
from near_api.repositories.documents import (
    DocumentRow,
    DocumentVersionRow,
    get_document,
    get_version,
)
from near_api.schemas.chart_selection import ChartSelection
from near_api.schemas.delivery import ChartViewResponse
from near_api.schemas.export import (
    EXPORT_IR_VERSION,
    ExportAuthor,
    ExportBlock,
    ExportChartBlock,
    ExportCitationReference,
    ExportDataTableBlock,
    ExportDataTableColumn,
    ExportDataTableDatasetReference,
    ExportDividerBlock,
    ExportDocumentMeta,
    ExportEvidenceBlock,
    ExportHeadingBlock,
    ExportHypothesisBlock,
    ExportInsightBlock,
    ExportIr,
    ExportListBlock,
    ExportModelResultBlock,
    ExportModelResultSummary,
    ExportModelRunReference,
    ExportParagraphBlock,
    ExportRiskBlock,
    ExportSourceReference,
)

_MAX_ERROR_DETAILS = 20
"""Error detail lists stay bounded, like every document service error."""


class _RunIdentity(NamedTuple):
    """The immutable published-run identity the plan's references record."""

    run_id: UUID
    spec_id: str
    spec_version: int


class _PublishedModel(NamedTuple):
    summary: ExportModelResultSummary
    manifest_bundle: dict[str, object]


class ExportIrError(ValueError):
    """The acknowledged revision cannot become a complete frozen export plan.

    Carries bounded ``(path, reason)`` details like the document service
    errors; the message names the offending revision/block. A caller must
    never fall back to current data or a partial plan when this raises.
    """

    def __init__(self, message: str, details: tuple[tuple[str, str], ...] = ()):
        super().__init__(message)
        self.details = tuple(details)[:_MAX_ERROR_DETAILS]


def export_ir_canonical_bytes(plan: ExportIr) -> bytes:
    """Deterministic serialization of a plan (hash/compare/storage format).

    UTF-8 JSON with sorted keys and compact separators; decimal strings stay
    unchanged; no NaN/Infinity can appear (the contracts forbid non-finite
    cells and the dataset delivery emits decimal strings).
    """
    return json.dumps(plan.model_dump(mode="json"), ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


# --------------------------------------------------------------------------- #
# Cell and rich-text normalization
# --------------------------------------------------------------------------- #


def export_cell(value: object) -> str | bool | None:
    """Export one authored table cell without binary-float rounding.

    Numbers become exact decimal strings: integers directly, finite floats
    through their shortest round-trip spelling re-rendered in plain decimal
    notation (``1e30`` exports as ``1000000000000000000000000000000``). Text
    exports verbatim; booleans and explicit absence are unchanged.
    """
    if value is None or isinstance(value, bool) or isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(Decimal(repr(value)), "f")
    raise ExportIrError(
        "The stored revision contains a dataTable cell the frozen export "
        "contract cannot represent",
        [("dataTable_cell", "unsupported_cell_type")])


def _runs(nodes: list[dict]) -> tuple[RichTextRun, ...]:
    try:
        return tuple(RichTextRun.model_validate(node) for node in nodes)
    except ValidationError as error:
        raise ExportIrError(
            "The stored revision contains rich text the frozen export "
            "contract cannot represent",
            [("runs", "invalid_rich_text")]) from error


def _list_items(block_type: str, content: list[dict]) -> tuple[RichTextListItem, ...]:
    try:
        validated = RichTextList.model_validate({"type": block_type, "content": content})
    except ValidationError as error:
        raise ExportIrError(
            "The stored revision contains a list block the frozen export "
            "contract cannot represent",
            [("list_items", "invalid_rich_list")]) from error
    return validated.content


_RICH_TEXT_BODY = TypeAdapter(RichTextBody)
"""RichTextBody is an Annotated tuple alias, not a model — one shared
adapter validates canonical body fragments into it."""


def _body(fragment: list[dict]) -> RichTextBody:
    try:
        return _RICH_TEXT_BODY.validate_python(fragment)
    except ValidationError as error:
        raise ExportIrError(
            "The stored revision contains an annotation body the frozen "
            "export contract cannot represent",
            [("body", "invalid_rich_body")]) from error


# --------------------------------------------------------------------------- #
# Block mapping (every P0 type of the canonical taxonomy)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Mapping:
    """Everything one block mapper may resolve against (one transaction)."""

    connection: Connection
    version: DocumentVersionRow
    canonical: CanonicalDocument
    charts: dict[UUID, LiveChartNode]
    tables: dict[UUID, DataTableNode]
    insights: dict[UUID, InsightNode]
    hypotheses: dict[UUID, HypothesisNode]
    evidence: dict[UUID, EvidenceNode]
    risks: dict[UUID, RiskNode]
    model_blocks: dict[UUID, ModelResultNode]
    published_models: dict[UUID, _PublishedModel]


def _map_paragraph(mapping: _Mapping, block: Block, node: dict) -> ExportBlock:
    return ExportParagraphBlock(block_type="paragraph", block_id=block.block_id,
                                runs=_runs(node.get("content", [])))


def _map_heading(mapping: _Mapping, block: Block, node: dict) -> ExportBlock:
    return ExportHeadingBlock(block_type="heading", block_id=block.block_id,
                              level=block.attrs["level"],
                              runs=_runs(node.get("content", [])))


def _map_list(mapping: _Mapping, block: Block, node: dict) -> ExportBlock:
    return ExportListBlock(block_type=block.block_type,  # type: ignore[arg-type]
                           block_id=block.block_id,
                           items=_list_items(block.block_type, node.get("content", [])))


def _map_live_chart(mapping: _Mapping, block: Block, node: dict) -> ExportBlock:
    del node  # the typed chart node carries the same canonical attrs
    chart = mapping.charts[block.block_id]
    try:
        view: ChartViewResponse = reconstruct_revision_chart(
            mapping.connection, mapping.version, block.block_id)
    except ReconstructionError as error:
        # NI-043 reconstruction failure: the pinned evidence is missing or
        # inconsistent. Never substitute current data — fail with detail.
        raise ExportIrError(
            f"Chart block {block.block_id} could not be reconstructed from "
            "its frozen evidence",
            [(f"blocks.{block.block_id}", error.reason)]) from error
    return ExportChartBlock(block_type="liveChart", block_id=block.block_id,
                            chart_definition_version_id=chart.chart_definition_version_id,
                            mode=chart.mode,
                            selection=ChartSelection.model_validate(chart.selection),
                            observed_dataset_version_id=chart.observed_dataset_version_id,
                            snapshot_id=chart.snapshot_id, view=view)


def _map_data_table(mapping: _Mapping, block: Block, node: dict) -> ExportBlock:
    del node
    table = mapping.tables[block.block_id]
    columns = tuple(ExportDataTableColumn.model_validate(column)
                    for column in table.columns)
    rows = None
    if table.rows is not None:
        rows = tuple(tuple(export_cell(cell) for cell in row) for row in table.rows)
    dataset = None
    if table.dataset_version_id is not None:
        dataset = _table_dataset_reference(mapping.connection, table.dataset_version_id)
    return ExportDataTableBlock(block_type="dataTable", block_id=block.block_id,
                                columns=columns, rows=rows, dataset=dataset)


def _table_dataset_reference(connection: Connection,
                             dataset_version_id: UUID) -> ExportDataTableDatasetReference:
    """Validate a pinned table dataset and record its immutable identity.

    A staged/validated/rejected/absent version is a failed export, never a
    substitution with a latest pointer (shared NI-036 reference rule).
    """
    try:
        require_approved_dataset(connection, dataset_version_id,
                                 "dataTable.dataset_version_id")
    except DocumentSchemaError as error:
        raise ExportIrError(
            "The stored dataTable references a dataset version that is not "
            "an approved public dataset",
            error.details) from error
    row = connection.execute(
        select(DatasetVersion.dataset_key, DatasetVersion.version,
               DatasetVersion.content_sha256)
        .where(DatasetVersion.id == dataset_version_id)).one()
    return ExportDataTableDatasetReference(
        dataset_version_id=dataset_version_id, dataset_key=row.dataset_key,
        version=row.version, content_sha256=row.content_sha256)


def _map_insight(mapping: _Mapping, block: Block, node: dict) -> ExportBlock:
    del node
    insight = mapping.insights[block.block_id]
    return ExportInsightBlock(
        block_type="insight", block_id=block.block_id, insight_id=insight.insight_id,
        insight_type=insight.insight_type, classification=insight.classification,
        body=_body(insight.body_json),
        context=_verify_insight_context(mapping, block.block_id, insight.context),
        authored_at=insight.authored_at, modified_at=insight.modified_at,
        hypothesis_id=insight.hypothesis_id)


def _verify_insight_context(mapping: _Mapping, block_id: UUID,
                            context: dict) -> ResolvedContext | ModelContext:
    """Verify one stored insight context against its immutable registries.

    Chart contexts re-verify through the shared pin chain (definition
    version, selection rules, approved dataset, required-metric coverage,
    canonical context hash) with ``resolved_at`` pinned to the stored
    inspection time, so a changed or missing pin fails closed instead of
    exporting a stale claim. Model contexts must reference a published run
    (validated with the other public references before the blocks map).
    """
    try:
        parsed = ResolvedContext.model_validate(context)
    except ValidationError:
        try:
            return ModelContext.model_validate(context)
        except ValidationError as error:
            raise ExportIrError(
                f"Insight block {block_id} carries a context the frozen "
                "export contract cannot represent",
                [("context", "invalid_context")]) from error
    try:
        verified = verify_chart_context(mapping.connection, parsed,
                                        resolved_at=parsed.resolved_at)
    except DocumentSchemaError as error:
        raise ExportIrError(
            f"Insight block {block_id} pins chart evidence that is missing "
            "or inconsistent",
            error.details) from error
    if not same_chart_pins(parsed, verified):
        raise ExportIrError(
            f"Insight block {block_id} pins chart evidence that is missing "
            "or inconsistent",
            [(f"blocks.{block_id}", "insight_context_mismatch")])
    return parsed


def _map_hypothesis(mapping: _Mapping, block: Block, node: dict) -> ExportBlock:
    del node
    hypothesis = mapping.hypotheses[block.block_id]
    return ExportHypothesisBlock(
        block_type="hypothesis", block_id=block.block_id,
        hypothesis_id=hypothesis.hypothesis_id, statement=hypothesis.statement,
        assessment=hypothesis.assessment, authored_at=hypothesis.authored_at,
        modified_at=hypothesis.modified_at)


def _map_evidence(mapping: _Mapping, block: Block, node: dict) -> ExportBlock:
    del node
    item = mapping.evidence[block.block_id]
    target_block_id: UUID | None = None
    if item.target_kind == "chart_block":
        target_block_id = item.target_id
    elif item.target_kind == "insight":
        same_document = {node_item.insight_id: node_item.block_id
                         for node_item in mapping.canonical.insights}
        target_block_id = same_document.get(item.target_id)
        if target_block_id is None:  # canonical validation guarantees a hit
            raise ExportIrError(
                f"Evidence block {block.block_id} targets an insight that "
                "does not exist in the same revision",
                [(f"blocks.{block.block_id}", "dangling_insight_reference")])
    return ExportEvidenceBlock(
        block_type="evidence", block_id=block.block_id, evidence_id=item.evidence_id,
        hypothesis_id=item.hypothesis_id, classification=item.classification,
        target_kind=item.target_kind, target_id=item.target_id,
        target_block_id=target_block_id, explanation=item.explanation)


def _map_risk(mapping: _Mapping, block: Block, node: dict) -> ExportBlock:
    risk = mapping.risks[block.block_id]
    return ExportRiskBlock(block_type="risk", block_id=block.block_id,
                           title=node["attrs"]["title"],
                           body=_body(node["attrs"]["body"]),
                           related_hypothesis_id=risk.related_hypothesis_id)


def _map_divider(mapping: _Mapping, block: Block, node: dict) -> ExportBlock:
    del mapping, node
    return ExportDividerBlock(block_type="divider", block_id=block.block_id)


def _project_model_result(run_id: UUID, row: dict) -> _PublishedModel:
    """Freeze the published summary and the exact reviewed manifest content."""
    from near_api.research.publication import (
        MANIFEST_KEYS,
        canonical_artifact_hash,
        derive_run_id,
    )

    try:
        detail = model_service.run_detail(row)
        bundle = model_service.manifest_bundle(row)
        manifests = bundle["manifests"]
        approval = bundle["approval"]
        hashes = {key: canonical_artifact_hash(manifests[key]) for key in MANIFEST_KEYS}
        if (detail.run_id != run_id or bundle["run_id"] != str(run_id)
                or detail.model_id != bundle["spec_id"]
                or detail.model_version != row["spec_version"]
                or derive_run_id(hashes) != run_id):
            raise ValueError("Published run identity disagrees with the manifest")
        artifact_hashes = {**hashes, "publication_approval": canonical_artifact_hash(approval)}
        if set(manifests) != set(MANIFEST_KEYS) or artifact_hashes != bundle["artifact_sha256"]:
            raise ValueError("Published artifact hashes disagree with the manifest")
        if any(approval["approved_artifacts"][key] != value for key, value in hashes.items()):
            raise ValueError("The recorded approval disagrees with the manifest")
        summary = ExportModelResultSummary(
            run_id=detail.run_id, model_id=detail.model_id,
            model_version=detail.model_version, gate_verdict=detail.gate_verdict,
            sample_start=detail.sample.start, sample_end_exclusive=detail.sample.end_exclusive,
            nobs=detail.sample.nobs,
            coefficient_rtol=detail.tolerances.coefficient_rtol,
            coefficient_atol=detail.tolerances.coefficient_atol,
            manifest_url=detail.manifest_url,
            coefficients=detail.coefficients, diagnostics=detail.diagnostics,
            limitations=detail.limitations)
    except (KeyError, TypeError, ValueError, model_service.ModelNotFoundError) as error:
        raise ExportIrError(
            f"The published model run {run_id} does not carry a servable "
            "recorded result and verified manifest set",
            [("model_run", "model_result_projection_failed")]) from error
    return _PublishedModel(summary, bundle)


def _verify_model_context(version: DocumentVersionRow, model: ModelResultNode,
                          summary: ExportModelResultSummary) -> None:
    path = f"blocks.{model.block_id}"
    contexts = version.resolved_contexts
    if contexts is not None and not isinstance(contexts, dict):
        raise ExportIrError("The stored model contexts are malformed",
                            [(path, "invalid_model_context")])
    stored = (contexts or {}).get(str(model.block_id))
    if stored is None:
        raise ExportIrError("The model result is missing its frozen revision context",
                            [(path, "missing_model_context")])
    try:
        context = ModelContext.model_validate(stored)
    except ValidationError as error:
        raise ExportIrError("The stored model context is malformed",
                            [(path, "invalid_model_context")]) from error
    expected = build_model_context(
        PublishedRunRow(summary.run_id, summary.model_id, summary.model_version),
        model.dataset_version_id)
    if not same_model_pins(context, expected):
        raise ExportIrError("The frozen model context disagrees with the revision pins",
                            [(path, "model_context_mismatch")])


def _map_model_result(mapping: _Mapping, block: Block, node: dict) -> ExportBlock:
    """Map a modelResult block against its immutable published run (NI-055).

    The run is re-verified published-only at build time (an unpublished,
    absent or malformed identity fails closed — never a substitution with a
    newer run) and the dataset pin is re-verified as an approved public
    version. The exported values are projected from the run row, never read
    from the document, so the plan cannot carry a number the author typed.
    """
    del node
    model = mapping.model_blocks[block.block_id]
    try:
        require_approved_dataset(mapping.connection, model.dataset_version_id,
                                 "modelResult.dataset_version_id")
    except DocumentSchemaError as error:
        raise ExportIrError(
            "The stored modelResult references a dataset version that is not "
            "an approved public dataset",
            error.details) from error
    projection = mapping.published_models.get(model.model_run_id)
    if projection is None:
        row = model_service.get_published_run_row(mapping.connection, model.model_run_id)
        if row is None or row.get("status") != "published":
            raise ExportIrError(
                f"Model result block {block.block_id} pins a model run that is "
                "not a published immutable artifact",
                [(f"blocks.{block.block_id}", "dangling_model_run_reference")])
        projection = _project_model_result(model.model_run_id, row)
        mapping.published_models[model.model_run_id] = projection
    summary = projection.summary
    _verify_model_context(mapping.version, model, summary)
    return ExportModelResultBlock(
        block_type="modelResult", block_id=block.block_id,
        model_run_id=model.model_run_id,
        dataset_version_id=model.dataset_version_id,
        spec_id=summary.model_id, spec_version=summary.model_version,
        interpretation=_body(model.interpretation_json),
        summary=summary)


_BLOCK_MAPPERS = {
    "paragraph": _map_paragraph,
    "heading": _map_heading,
    "bullet_list": _map_list,
    "ordered_list": _map_list,
    "liveChart": _map_live_chart,
    "dataTable": _map_data_table,
    "insight": _map_insight,
    "hypothesis": _map_hypothesis,
    "evidence": _map_evidence,
    "risk": _map_risk,
    "modelResult": _map_model_result,
    "divider": _map_divider,
}
"""Exhaustive dispatch over the canonical P0 taxonomy. A block type missing
here means the canonical schema and the export contract drifted apart — the
mapper fails closed instead of exporting a partial document."""


def _map_block(mapping: _Mapping, block: Block, node: dict) -> ExportBlock:
    mapper = _BLOCK_MAPPERS.get(block.block_type)
    if mapper is None:
        raise ExportIrError(
            "The stored revision contains a block type the frozen export "
            "contract does not support",
            [(f"blocks.{block.block_id}", "unsupported_block_type")])
    return mapper(mapping, block, node)


# --------------------------------------------------------------------------- #
# Public references (published model runs, public citations, source lineage)
# --------------------------------------------------------------------------- #


def _verify_public_references(connection: Connection, canonical: CanonicalDocument,
                              contexts: tuple[ResolvedContext | ModelContext, ...],
                              ) -> dict[UUID, _RunIdentity]:
    """Validate every public reference the plan will carry; return run rows.

    Evidence ``model_run``/``citation`` targets go through NI-049's shared
    validator (the same rule the save transaction enforced); insight
    ``ModelContext`` runs and NI-055 ``modelResult`` pins resolve through the
    same published-only catalog.
    """
    try:
        validate_public_targets(connection, canonical)
    except DocumentSchemaError as error:
        raise ExportIrError(
            "The stored revision references a public evidence target that is "
            "missing or not public",
            error.details) from error
    run_ids = {item.target_id for item in canonical.evidence
               if item.target_kind == "model_run"}
    run_ids |= {context.model_run_id for context in contexts
                if isinstance(context, ModelContext)}
    run_ids |= {model.model_run_id for model in canonical.model_results}
    runs: dict[UUID, _RunIdentity] = {}
    if run_ids:
        rows = connection.execute(
            select(ModelRun.run_id, ModelRun.spec_id, ModelRun.spec_version)
            .where(ModelRun.run_id.in_(run_ids),
                   ModelRun.status == "published")).all()
        runs = {row.run_id: _RunIdentity(row.run_id, row.spec_id, row.spec_version)
                for row in rows}
        if len(runs) != len(run_ids):
            raise ExportIrError(
                "The stored revision references a model run that is not a "
                "published immutable artifact",
                [("model_run", "dangling_model_run_reference")])
    return runs


def _source_references(blocks: tuple[ExportBlock, ...]) -> tuple[ExportSourceReference, ...]:
    """Deduplicated, id-sorted data-source references of the resolved charts."""
    by_id: dict[str, str] = {}
    for block in blocks:
        if isinstance(block, ExportChartBlock):
            for series in block.view.series:
                for source in series.sources:
                    by_id.setdefault(source.id, source.name)
    return tuple(ExportSourceReference(source_id=source_id, name=by_id[source_id])
                 for source_id in sorted(by_id))


def _model_run_references(blocks: tuple[ExportBlock, ...], runs: dict[UUID, _RunIdentity],
                          published_models: dict[UUID, _PublishedModel],
                          ) -> tuple[ExportModelRunReference, ...]:
    referenced: set[UUID] = set()
    for block in blocks:
        if isinstance(block, ExportInsightBlock) and isinstance(block.context, ModelContext):
            referenced.add(block.context.model_run_id)
        elif isinstance(block, ExportEvidenceBlock) and block.target_kind == "model_run":
            referenced.add(block.target_id)
        elif isinstance(block, ExportModelResultBlock):
            referenced.add(block.model_run_id)
    return tuple(ExportModelRunReference(
        run_id=run.run_id, spec_id=run.spec_id, spec_version=run.spec_version,
        manifest_bundle=published_models[run.run_id].manifest_bundle
        if run.run_id in published_models else None)
        for run in sorted((runs[item] for item in referenced), key=lambda row: row.run_id))


def _citation_references(blocks: tuple[ExportBlock, ...]) -> tuple[ExportCitationReference, ...]:
    referenced = {block.target_id for block in blocks
                  if isinstance(block, ExportEvidenceBlock)
                  and block.target_kind == "citation"}
    return tuple(ExportCitationReference(artifact_id=item)
                 for item in sorted(referenced, key=str))


# --------------------------------------------------------------------------- #
# The builder
# --------------------------------------------------------------------------- #


def build_export_ir(engine: Engine, principal: Principal, document_id: UUID,
                    version_id: UUID) -> ExportIr:
    """Build the frozen export plan of the owned acknowledged revision.

    The document row and the revision are read in ONE principal transaction;
    the revision must be the document's acknowledged current version (see the
    module docstring for the title/content correspondence rule). Absent or
    not-owned ids raise the shared 404-equivalent; an unexportable revision
    raises :class:`ExportIrError` with details.
    """
    with principal_transaction(engine, principal) as connection:
        return build_export_ir_in_transaction(connection, principal, document_id,
                                              version_id)


def build_export_ir_in_transaction(connection: Connection, principal: Principal,
                                   document_id: UUID, version_id: UUID) -> ExportIr:
    """Build the frozen plan on the CALLER's open principal transaction.

    The export-job creation (NI-058) runs inside one transaction that also
    inserts the job row, so the plan, the ownership checks and the job are
    atomic: a job never exists without its complete frozen plan. The
    acknowledged-revision rule and the fail-closed semantics are the
    :func:`build_export_ir` ones.
    """
    document = get_document(connection, principal, document_id)
    version = get_version(connection, principal, document_id, version_id)
    return _build_ir(connection, document, version)


def _build_ir(connection: Connection, document: DocumentRow,
              version: DocumentVersionRow) -> ExportIr:
    if version.id != document.current_version_id:
        raise ExportIrError(
            f"Revision {version.id} is not the acknowledged revision of "
            f"document {document.id}; a frozen export plan with attribution "
            "is built from the acknowledged revision only",
            [("version_id", "revision_not_acknowledged")])
    try:
        canonical = parse_document(version.content)
    except DocumentSchemaError as error:
        raise ExportIrError(
            "The stored revision content is not a valid canonical document",
            error.details) from error
    if canonical.content_sha256 != version.content_sha256:
        raise ExportIrError(
            "The stored revision content does not match its recorded hash",
            [("content_sha256", "revision_content_hash_mismatch")])
    if version.schema_version != SCHEMA_VERSION:
        raise ExportIrError(
            "The stored revision schema version is not supported by the "
            "frozen export contract",
            [("schema_version", "unsupported_schema_version")])

    mapping = _Mapping(
        connection=connection, version=version, canonical=canonical,
        charts={chart.block_id: chart for chart in canonical.live_charts},
        tables={table.block_id: table for table in canonical.data_tables},
        insights={item.block_id: item for item in canonical.insights},
        hypotheses={item.block_id: item for item in canonical.hypotheses},
        evidence={item.block_id: item for item in canonical.evidence},
        risks={item.block_id: item for item in canonical.risks},
        model_blocks={model.block_id: model for model in canonical.model_results},
        published_models={})

    blocks: list[ExportBlock] = []
    for block, node in zip(canonical.blocks, canonical.canonical["content"]):
        blocks.append(_map_block(mapping, block, node))

    contexts = tuple(block.context for block in blocks
                     if isinstance(block, ExportInsightBlock))
    runs = _verify_public_references(connection, canonical, contexts)
    frozen_blocks = tuple(blocks)
    return ExportIr(
        ir_version=EXPORT_IR_VERSION,
        document=_document_meta(connection, document, version),
        blocks=frozen_blocks,
        sources=_source_references(frozen_blocks),
        model_runs=_model_run_references(frozen_blocks, runs, mapping.published_models),
        citations=_citation_references(frozen_blocks))


def _document_meta(connection: Connection, document: DocumentRow,
                   version: DocumentVersionRow) -> ExportDocumentMeta:
    """Revision metadata: title, author, revision date, immutable identity."""
    return ExportDocumentMeta(
        document_id=document.id, version_id=version.id, revision=version.revision,
        schema_version=version.schema_version, content_sha256=version.content_sha256,
        title=document.title, author=_export_author(connection, document.owner_id),
        created_at=version.created_at)


def _export_author(connection: Connection, owner_id: UUID) -> ExportAuthor:
    """The verified owner plus the profile display name (None when absent)."""
    display_name = connection.execute(
        select(UserProfile.display_name).where(UserProfile.user_id == owner_id)
    ).scalar_one_or_none()
    if display_name is not None and not display_name.strip():
        display_name = None
    return ExportAuthor(owner_id=owner_id, display_name=display_name)
