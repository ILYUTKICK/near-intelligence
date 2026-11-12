"""Deterministic advisory integrity checks over one immutable revision (NI-065).

The checks re-read a SAVED revision row and report the conditions that can
genuinely arise after save-time validation blocked everything it covers
(ADR-021). Save-time rules already refuse broken same-document links,
unapproved dataset pins, unverifiable insight contexts and unknown public
targets, so those conditions are NOT re-reported — a check that cannot fire
would be dead weight. What remains advisory reality after a save:

- a NEWER approved dataset version exists for a pinned chart (stale context);
- a pinned chart definition or dataset version left the available/approved
  registry state after the save (availability drift);
- a public model run or citation artifact an evidence link or insight context
  pins is no longer published/public (target drift);
- a stored chart context went missing or invalid for a saved block
  (corruption signal — reported, never swallowed);
- pinned data (chart/table) carries no evidence link and no insight context
  citing it (uncited pinned data — never a save blocker, advisory only).

Read-only and deterministic: no state is written, no wall-clock enters the
report, and a rerun is simply a new GET over the same immutable row. A check
never mutates a pin, coefficient or document — the editor's refresh stays the
author's explicit action on the chart block.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import Connection, select

from near_api.datasets import delivery
from near_api.db.models import DatasetVersion
from near_api.documents.context_resolver import ChartDefinitionRow, load_chart_definition
from near_api.documents.schema import (
    CanonicalDocument,
    DocumentSchemaError,
    parse_document,
)
from near_api.insights.schemas import ModelContext, ResolvedContext
from near_api.repositories.documents import DocumentRow, DocumentVersionRow
from near_api.schemas.integrity import (
    IntegrityCheckCount,
    IntegrityFinding,
    IntegrityReport,
)


def _finding(check_id: str, severity: str, message: str, *, jump: str = "block",
             **references) -> IntegrityFinding:
    return IntegrityFinding(check_id=check_id, severity=severity,
                            message=message, jump=jump,
                            **references)


def _insight_pins(canonical: CanonicalDocument) -> tuple[set[tuple[UUID, UUID]], set[UUID]]:
    """(definition, dataset) pairs and bare dataset ids cited by insight contexts.

    An insight IS a source-bearing annotation: its frozen context cites the
    exact chart definition/dataset or model run it interprets, so the uncited
    checks treat it as a citation (ADR-021 precise definition).
    """
    pairs: set[tuple[UUID, UUID]] = set()
    datasets: set[UUID] = set()
    for insight in canonical.insights:
        context = insight.context
        if "chart_definition_version_id" in context:
            definition_id = UUID(context["chart_definition_version_id"])
            dataset_id = UUID(context["dataset_version_id"])
            pairs.add((definition_id, dataset_id))
            datasets.add(dataset_id)
        elif "model_run_id" in context:
            datasets.add(UUID(context["dataset_version_id"]))
    return pairs, datasets


def _chart_cited(canonical: CanonicalDocument, chart_block_id: UUID,
                 chart_definition_id: UUID, chart_dataset_id: UUID,
                 insight_pairs: set[tuple[UUID, UUID]]) -> bool:
    for evidence in canonical.evidence:
        if evidence.target_kind == "chart_block" and evidence.target_id == chart_block_id:
            return True
    return (chart_definition_id, chart_dataset_id) in insight_pairs


def _table_cited(canonical: CanonicalDocument, dataset_id: UUID,
                 insight_datasets: set[UUID]) -> bool:
    return dataset_id in insight_datasets


def build_integrity_report(connection: Connection, document: DocumentRow,
                           version: DocumentVersionRow, *,
                           is_acknowledged: bool) -> IntegrityReport:
    """Run every deterministic check over one immutable revision row."""
    findings: list[IntegrityFinding] = []
    try:
        canonical = parse_document(version.content)
    except DocumentSchemaError:
        findings.append(_finding(
            "invalid_revision_content", "warning",
            "The stored revision content no longer parses as a canonical editor "
            "document. This is a corruption signal: inspect the revision before "
            "editing; nothing was changed by this check.",
            jump="none"))
        return _report(document, version, is_acknowledged, findings)

    contexts = version.resolved_contexts
    if contexts is not None and not isinstance(contexts, dict):
        contexts = None
        findings.append(_finding(
            "invalid_chart_context", "warning",
            "The revision's stored chart-context map is not an object. This is a "
            "corruption signal: frozen contexts cannot be verified until the "
            "document is re-saved.", jump="none"))

    insight_pairs, insight_datasets = _insight_pins(canonical)
    pinned_datasets = {UUID(chart.observed_dataset_version_id) for chart in canonical.live_charts}
    pinned_datasets.update(UUID(table.dataset_version_id) for table in canonical.data_tables
                           if table.dataset_version_id is not None)
    for insight in canonical.insights:
        pinned_datasets.add(UUID(insight.context["dataset_version_id"]))

    # Public target drift: re-run the save-time registry membership check
    # READ-ONLY and report divergence instead of raising (save-time raises).
    public_runs, public_citations = _public_targets(connection, canonical)
    for evidence in canonical.evidence:
        if evidence.target_kind == "model_run" and evidence.target_id not in public_runs:
            findings.append(_finding(
                "evidence_target_unavailable", "advisory",
                f"Evidence target (model run {evidence.target_id}) is no longer a "
                "published model run; the link cannot be verified against the "
                "registry. Re-link the evidence explicitly.",
                block_id=evidence.block_id, entity_id=evidence.evidence_id,
                target_kind="model_run"))
        elif evidence.target_kind == "citation" and evidence.target_id not in public_citations:
            findings.append(_finding(
                "evidence_target_unavailable", "advisory",
                f"Evidence target (citation {evidence.target_id}) is no longer a "
                "public immutable citation artifact; the link cannot be verified "
                "against the registry. Re-link the evidence explicitly.",
                block_id=evidence.block_id, entity_id=evidence.evidence_id,
                target_kind="citation"))

    # Insight context drift: a pinned model run that left the published set.
    for insight in canonical.insights:
        context = insight.context
        if "model_run_id" in context and UUID(context["model_run_id"]) not in public_runs:
            findings.append(_finding(
                "insight_context_unavailable", "advisory",
                f"The model run pinned in this insight's context "
                f"({context['model_run_id']}) is no longer published; the frozen "
                "context stays verbatim and the insight stays advisory-only.",
                block_id=insight.block_id, entity_id=insight.insight_id,
                context_hash=str(context["context_hash"])))

    # Dataset availability drift (charts, pinned tables, insight contexts):
    # one batched status read for every pinned dataset version.
    unapproved = _unapproved_datasets(connection, pinned_datasets)

    latest_by_requirements: dict[frozenset, UUID | None] = {}
    definitions: dict[UUID, ChartDefinitionRow] = {}

    for chart in canonical.live_charts:
        stored = contexts.get(str(chart.block_id)) if contexts is not None else None
        context = None
        if stored is None:
            findings.append(_finding(
                "missing_chart_context", "warning",
                "The saved chart has no frozen context entry in this revision's "
                "resolved contexts. This is a corruption signal: the chart cannot "
                "be reconstructed until it is explicitly re-inspected and saved.",
                block_id=chart.block_id,
                chart_definition_version_id=chart.chart_definition_version_id,
                dataset_version_id=chart.observed_dataset_version_id))
        else:
            try:
                context = ResolvedContext.model_validate(stored)
            except ValidationError:
                findings.append(_finding(
                    "invalid_chart_context", "warning",
                    "The frozen context of this chart does not match the stored "
                    "ResolvedContext schema and cannot be verified. This is a "
                    "corruption signal: inspect before editing.",
                    block_id=chart.block_id,
                    chart_definition_version_id=chart.chart_definition_version_id,
                    dataset_version_id=chart.observed_dataset_version_id))

        if UUID(chart.observed_dataset_version_id) in unapproved:
            findings.append(_finding(
                "dataset_pin_unavailable", "advisory",
                f"The pinned dataset {chart.observed_dataset_version_id} is no "
                "longer an approved public dataset; the saved pin stays verbatim "
                "and is never substituted.",
                block_id=chart.block_id,
                chart_definition_version_id=chart.chart_definition_version_id,
                dataset_version_id=chart.observed_dataset_version_id))

        try:
            definition = definitions.get(chart.chart_definition_version_id)
            if definition is None:
                definition = load_chart_definition(
                    connection, chart.chart_definition_version_id, error_path="content")
                definitions[chart.chart_definition_version_id] = definition
        except DocumentSchemaError:
            findings.append(_finding(
                "chart_definition_unavailable", "advisory",
                f"The pinned chart definition {chart.chart_definition_version_id} "
                "is not an available registered definition anymore; the saved pin "
                "stays verbatim.",
                block_id=chart.block_id,
                chart_definition_version_id=chart.chart_definition_version_id,
                dataset_version_id=chart.observed_dataset_version_id))
            definition = None

        if context is not None and definition is not None:
            requirements = frozenset(definition.required_metric_versions)  # type: ignore[union-attr]
            if requirements not in latest_by_requirements:
                latest_by_requirements[requirements] = _latest_version(connection, requirements)
            latest = latest_by_requirements[requirements]
            if latest is not None and latest != context.dataset_version_id:
                findings.append(_finding(
                    "stale_chart_context", "advisory",
                    "A newer approved dataset exists for this chart's required "
                    "metrics. The saved observation stays pinned; refreshing is "
                    "an explicit action on the chart block, never an automatic "
                    "rewrite.",
                    block_id=chart.block_id,
                    context_hash=str(context.context_hash),
                    dataset_version_id=context.dataset_version_id,
                    chart_definition_version_id=context.chart_definition_version_id,
                    latest_dataset_version_id=latest))

        if not _chart_cited(canonical, chart.block_id, chart.chart_definition_version_id,
                            chart.observed_dataset_version_id, insight_pairs):
            findings.append(_finding(
                "uncited_pinned_chart", "advisory",
                "This pinned chart has no linked evidence and no insight carrying "
                "its context in this revision. Cite it with an evidence link or an "
                "insight if it supports a claim; the pin itself is unaffected.",
                block_id=chart.block_id,
                chart_definition_version_id=chart.chart_definition_version_id,
                dataset_version_id=chart.observed_dataset_version_id))

    for table in canonical.data_tables:
        if table.dataset_version_id is None:
            continue
        if table.dataset_version_id in unapproved:
            findings.append(_finding(
                "dataset_pin_unavailable", "advisory",
                f"The pinned dataset {table.dataset_version_id} is no longer an "
                "approved public dataset; the saved pin stays verbatim and is "
                "never substituted.",
                block_id=table.block_id, dataset_version_id=table.dataset_version_id))
        if not _table_cited(canonical, table.dataset_version_id, insight_datasets):
            findings.append(_finding(
                "uncited_pinned_dataset_table", "advisory",
                "This pinned dataset table has no insight carrying the same "
                "dataset in this revision (evidence links cannot target tables). "
                "Add an insight over the dataset if it supports a claim.",
                block_id=table.block_id, dataset_version_id=table.dataset_version_id))

    return _report(document, version, is_acknowledged, findings)


def _report(document: DocumentRow, version: DocumentVersionRow,
            is_acknowledged: bool, findings: list[IntegrityFinding]) -> IntegrityReport:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.check_id] = counts.get(finding.check_id, 0) + 1
    return IntegrityReport(
        document_id=document.id, version_id=version.id, revision=version.revision,
        is_acknowledged=is_acknowledged,
        findings=tuple(findings),
        counts=tuple(IntegrityCheckCount(check_id=check_id, count=count)
                     for check_id, count in sorted(counts.items())))


def _public_targets(connection: Connection,
                    canonical: CanonicalDocument) -> tuple[set[UUID], set[UUID]]:
    """Read-only membership sets of published runs and public citation artifacts."""
    from near_api.db.models import Artifact, ModelRun
    run_ids = {item.target_id for item in canonical.evidence
               if item.target_kind == "model_run"}
    run_ids.update(UUID(insight.context["model_run_id"]) for insight in canonical.insights
                   if "model_run_id" in insight.context)
    citation_ids = {item.target_id for item in canonical.evidence
                    if item.target_kind == "citation"}
    runs = set(connection.scalars(
        select(ModelRun.run_id).where(
            ModelRun.status == "published", ModelRun.run_id.in_(run_ids)))) if run_ids else set()
    citations = set(connection.scalars(
        select(Artifact.id).where(
            Artifact.scope == "public", Artifact.id.in_(citation_ids)))) if citation_ids else set()
    return runs, citations


def _unapproved_datasets(connection: Connection, pinned: set[UUID]) -> set[UUID]:
    if not pinned:
        return set()
    rows = connection.execute(
        select(DatasetVersion.id, DatasetVersion.status).where(DatasetVersion.id.in_(pinned)))
    return {row.id for row in rows if row.status != "approved"}


def _latest_version(connection: Connection, requirements: frozenset) -> UUID | None:
    """Newest approved dataset version for the required metrics, or None.

    ``None`` means the newest version cannot be determined (no approved
    dataset covers the requirement, or the data plane is not ready) — an
    honest check skip, never a fabricated stale finding (missing is not zero).
    """
    try:
        return delivery.resolve_latest_version(connection, tuple(requirements), use_cache=False)
    except delivery.DeliveryError:
        return None
