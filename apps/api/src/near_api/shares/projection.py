"""Narrow the verified export IR into the public share projection (NI-060).

The share projection (ADR-021) is a PURE narrowing transform of the NI-056
frozen export IR: the IR builder has already re-verified every pin through
the NI-043 historical resolver, validated the public references and failed
closed on unsupported blocks — this module removes everything private and
never resolves, substitutes or invents anything. Building it twice for the
same IR yields byte-identical canonical serialization (no wall-clock field
is added; the revision ``created_at`` and pinned inspection times are the
only timestamps).

Excluded here (structurally absent from :mod:`near_api.schemas.share`):
owner id and author identity, document/version/insight/hypothesis/evidence/
target private UUIDs, annotation authorship and modified timestamps, evidence
explanations, snapshot ids.
"""

from __future__ import annotations

import json

from near_api.exports.ir import ExportIrError
from near_api.schemas.export import (
    ExportBlock,
    ExportChartBlock,
    ExportDataTableBlock,
    ExportDividerBlock,
    ExportEvidenceBlock,
    ExportHeadingBlock,
    ExportHypothesisBlock,
    ExportInsightBlock,
    ExportIr,
    ExportListBlock,
    ExportModelResultBlock,
    ExportParagraphBlock,
    ExportRiskBlock,
)
from near_api.schemas.models import RunSampleResponse, TolerancesResponse
from near_api.schemas.share import (
    SHARE_PROJECTION_VERSION,
    ShareBlock,
    ShareCitationReference,
    ShareChartBlock,
    ShareDataTableBlock,
    ShareDataTableColumn,
    ShareDataTableDatasetReference,
    ShareDividerBlock,
    ShareDocumentMeta,
    ShareEvidenceBlock,
    ShareHeadingBlock,
    ShareHypothesisBlock,
    ShareInsightBlock,
    ShareListBlock,
    ShareModelResultBlock,
    ShareModelRunReference,
    ShareParagraphBlock,
    ShareProjection,
    ShareRiskBlock,
    ShareScopeSummary,
    ShareSourceReference,
)

_LIMITATIONS = (
    "Frozen read-only publication of one research revision: charts and tables "
    "show only the data pinned at inspection time, never refresh, and carry "
    "their own sources, dataset versions and quality statuses."
)
"""The deterministic limitations line published with every share."""


def _project_block(block: ExportBlock) -> ShareBlock:
    if isinstance(block, ExportParagraphBlock):
        return ShareParagraphBlock(block_type="paragraph", block_id=block.block_id,
                                   runs=block.runs)
    if isinstance(block, ExportHeadingBlock):
        return ShareHeadingBlock(block_type="heading", block_id=block.block_id,
                                 level=block.level, runs=block.runs)
    if isinstance(block, ExportListBlock):
        return ShareListBlock(block_type=block.block_type, block_id=block.block_id,
                              items=block.items)
    if isinstance(block, ExportChartBlock):
        return ShareChartBlock(block_type="liveChart", block_id=block.block_id,
                               chart_definition_version_id=block.chart_definition_version_id,
                               mode=block.mode, selection=block.selection,
                               observed_dataset_version_id=block.observed_dataset_version_id,
                               view=block.view)
    if isinstance(block, ExportDataTableBlock):
        # Sibling contract models are not auto-coerced: the two nested
        # dataTable models are revalidated into their share counterparts.
        return ShareDataTableBlock(
            block_type="dataTable", block_id=block.block_id,
            columns=tuple(ShareDataTableColumn.model_validate(column.model_dump())
                          for column in block.columns),
            rows=block.rows,
            dataset=ShareDataTableDatasetReference.model_validate(block.dataset.model_dump())
            if block.dataset is not None else None)
    if isinstance(block, ExportInsightBlock):
        return ShareInsightBlock(block_type="insight", block_id=block.block_id,
                                 insight_type=block.insight_type,
                                 classification=block.classification, body=block.body,
                                 context=block.context)
    if isinstance(block, ExportHypothesisBlock):
        return ShareHypothesisBlock(block_type="hypothesis", block_id=block.block_id,
                                    statement=block.statement,
                                    assessment=block.assessment)
    if isinstance(block, ExportEvidenceBlock):
        # The published reference is the target's PUBLIC identity: the
        # in-revision target block id for insight/chart targets (the export
        # IR already resolved insight ids to block ids), the published run id
        # or the public artifact id otherwise.
        in_revision = block.target_kind in ("insight", "chart_block")
        target_ref = block.target_block_id if in_revision else block.target_id
        return ShareEvidenceBlock(block_type="evidence", block_id=block.block_id,
                                  classification=block.classification,
                                  target_kind=block.target_kind,
                                  target_ref=target_ref)
    if isinstance(block, ExportRiskBlock):
        return ShareRiskBlock(block_type="risk", block_id=block.block_id,
                              title=block.title, body=block.body)
    if isinstance(block, ExportModelResultBlock):
        summary = block.summary
        return ShareModelResultBlock(
            block_type="modelResult", block_id=block.block_id,
            model_run_id=block.model_run_id, dataset_version_id=block.dataset_version_id,
            spec_id=block.spec_id, spec_version=block.spec_version,
            interpretation=block.interpretation, gate_verdict=summary.gate_verdict,
            sample=RunSampleResponse(start=summary.sample_start,
                                     end_exclusive=summary.sample_end_exclusive, nobs=summary.nobs),
            tolerances=TolerancesResponse(coefficient_rtol=summary.coefficient_rtol,
                                         coefficient_atol=summary.coefficient_atol),
            limitations=summary.limitations, coefficients=summary.coefficients,
        )
    if isinstance(block, ExportDividerBlock):
        return ShareDividerBlock(block_type="divider", block_id=block.block_id)
    raise ExportIrError("The revision contains an unsupported share block",
                        ((f"blocks.{block.block_id}", "unsupported_share_block"),))


def build_share_projection(plan: ExportIr) -> ShareProjection:
    """Narrow one verified export IR into the public projection."""
    meta = plan.document
    blocks = tuple(_project_block(block) for block in plan.blocks)
    return ShareProjection(
        share_projection_version=SHARE_PROJECTION_VERSION,
        document=ShareDocumentMeta(
            title=meta.title, revision=meta.revision,
            schema_version=meta.schema_version,
            content_sha256=meta.content_sha256, created_at=meta.created_at,
            limitations=_LIMITATIONS),
        blocks=blocks,
        sources=tuple(ShareSourceReference(source_id=source.source_id, name=source.name)
                      for source in plan.sources),
        model_runs=tuple(ShareModelRunReference(run_id=run.run_id, spec_id=run.spec_id,
                                                spec_version=run.spec_version)
                         for run in plan.model_runs),
        citations=tuple(ShareCitationReference(artifact_id=citation.artifact_id)
                        for citation in plan.citations),
    )


def share_projection_canonical_bytes(projection: ShareProjection) -> bytes:
    """Deterministic serialization of a projection (hash/compare/storage).

    The exact same canonical form as the export IR (UTF-8 JSON, sorted keys,
    compact separators, no NaN/Infinity): stored bytes ARE this spelling, so
    the recorded SHA-256 is the projection identity.
    """
    return json.dumps(projection.model_dump(mode="json"), ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def share_scope_summary(projection: ShareProjection) -> ShareScopeSummary:
    """The bounded visible-scope restatement shown with the consent flow."""
    return ShareScopeSummary(
        kind="frozen_revision_allowlist",
        chart_blocks=sum(1 for block in projection.blocks
                         if block.block_type == "liveChart"),
        data_table_blocks=sum(1 for block in projection.blocks
                              if block.block_type == "dataTable"),
        insight_blocks=sum(1 for block in projection.blocks
                           if block.block_type == "insight"),
        source_references=len(projection.sources),
    )
