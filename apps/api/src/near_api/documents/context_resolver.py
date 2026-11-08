"""Resolve and verify document chart pins against immutable registry versions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Mapping, Sequence
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import Connection, func, select

from near_api.datasets import delivery
from near_api.datasets.delivery import (
    DeliveryInvalidFilter,
    _context_hash,
    validate_filters_against_schema,
)
from near_api.db.models import ChartDefinition, ChartMetric, DatasetVersion, MetricObservation
from near_api.db.security import ResourceNotFound
from near_api.documents.schema import (
    MAX_CONTEXTS,
    CanonicalDocument,
    DocumentSchemaError,
    ReferenceInvalid,
    parse_document,
)
from near_api.insights.schemas import ResolvedContext
from near_api.repositories.documents import DocumentVersionRow
from near_api.schemas.chart_selection import ChartSelection
from near_api.schemas.delivery import ChartViewResponse, ResolvedSelection


@dataclass(frozen=True)
class ChartDefinitionRow:
    """The immutable chart registry facts used by document evidence."""

    id: UUID
    chart_id: str
    version: int
    data_status: str
    unavailable_reason: str | None
    renderer_version: str
    max_days: int
    filter_schema: dict
    metric_definition_versions: tuple[UUID, ...]
    required_metric_versions: tuple[UUID, ...]


def load_chart_definition(connection: Connection, chart_definition_version_id: UUID,
                          *, error_path: str) -> ChartDefinitionRow:
    """Load one registered chart definition version; reject unknown/unavailable.

    An unknown definition id is a dangling reference (422 REFERENCE_INVALID,
    no registry existence leak beyond the typed reason), and an
    ``unavailable`` definition is rejected because it is never advertised as
    live (CHART_SYSTEM): a liveChart block must resolve to real data.
    """
    row = connection.execute(
        select(ChartDefinition.id, ChartDefinition.chart_id, ChartDefinition.version,
               ChartDefinition.data_status, ChartDefinition.unavailable_reason,
               ChartDefinition.renderer_version, ChartDefinition.allowed_ranges,
               ChartDefinition.filter_schema, ChartDefinition.metric_definition_ids)
        .where(ChartDefinition.id == chart_definition_version_id)
    ).mappings().first()
    if row is None:
        raise ReferenceInvalid(
            "Referenced chart definition version does not exist in the registered "
            "chart catalog",
            [(error_path, "dangling_chart_definition")])
    if row["data_status"] != "available":
        reason = row["unavailable_reason"]
        raise ReferenceInvalid(
            "The referenced chart definition is registered unavailable and is never "
            "advertised as live" + (f": {reason}" if reason else ""),
            [(error_path, "chart_unavailable")])
    try:
        max_days = int(row["allowed_ranges"]["max_days"])
        filters = dict(row["filter_schema"])
        metric_versions = tuple(UUID(item) for item in row["metric_definition_ids"])
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ReferenceInvalid(
            "The chart definition's registered version is malformed",
            [(error_path, "invalid_chart_definition")]) from None
    bindings = connection.execute(
        select(ChartMetric.metric_definition_id, ChartMetric.series_role)
        .where(ChartMetric.chart_definition_version_id == row["id"])
    ).all()
    if not bindings or sorted(metric_versions) != sorted(metric_id for metric_id, _ in bindings):
        raise ReferenceInvalid(
            "The chart definition's metric bindings do not match its registered versions",
            [(error_path, "chart_metric_bindings_mismatch")])
    return ChartDefinitionRow(
        id=row["id"], chart_id=row["chart_id"], version=row["version"],
        data_status=row["data_status"], unavailable_reason=row["unavailable_reason"],
        renderer_version=row["renderer_version"],
        max_days=max_days, filter_schema=filters,
        metric_definition_versions=metric_versions,
        required_metric_versions=tuple({metric_id for metric_id, role in bindings
                                        if role.startswith("required")}),
    )


def validate_selection_against_definition(definition: ChartDefinitionRow,
                                          start: date, end: date,
                                          filters: Mapping[str, str]) -> None:
    """Range/filter rules of one chart version (the NI-032 view rules, reused).

    The definition can narrow the shared 366-day window and controls the
    allowable values for every filter.
    """
    if (end - start).days > definition.max_days:
        raise DeliveryInvalidFilter(
            "the selection range exceeds this chart version's allowed maximum")
    validate_filters_against_schema(dict(filters), definition.filter_schema)


def require_metric_coverage(connection: Connection, definition: ChartDefinitionRow,
                            dataset_version_id: UUID, *, error_path: str) -> None:
    """The pinned dataset must contain every required metric of the chart.

    NI-032 refuses an explicit dataset version whose observations lack a
    required metric (incompatible metric versions are never mixed silently);
    the insertion pin is verified against the same rule so an embedded chart
    cannot reference a dataset that could never render it.
    """
    required = definition.required_metric_versions
    if not required:
        return
    covered = connection.execute(
        select(func.count(func.distinct(MetricObservation.metric_definition_id)))
        .where(MetricObservation.dataset_version_id == dataset_version_id,
               MetricObservation.metric_definition_id.in_(required))
    ).scalar_one()
    if covered != len(set(required)):
        raise ReferenceInvalid(
            "The pinned dataset version does not contain every required metric "
            "definition of the chart; incompatible metric versions are never mixed "
            "silently",
            [(error_path, "dataset_missing_required_metrics")])


def require_live_chart_mode(mode: str, *, error_path: str) -> None:
    if mode == "snapshot":
        raise ReferenceInvalid(
            "Snapshot chart blocks require the research snapshot registry, which is "
            "not available yet (P1 NI-044)",
            [(error_path, "reference_unavailable")])


def build_resolved_context(definition: ChartDefinitionRow, dataset_version_id: UUID,
                           selection: ChartSelection, *, resolved_at: datetime) -> ResolvedContext:
    """Build the frozen context using the same canonical hash as ChartView."""
    metric_versions = tuple(sorted(definition.metric_definition_versions))
    return ResolvedContext(
        chart_definition_version_id=definition.id,
        dataset_version_id=dataset_version_id,
        selection=selection,
        context_hash=_context_hash(
            {"id": definition.id}, dataset_version_id,
            ResolvedSelection.model_validate(selection.model_dump()), metric_versions),
        renderer_version=definition.renderer_version,
        metric_definition_versions=metric_versions,
        resolved_at=resolved_at,
    )


def require_approved_dataset(connection: Connection, dataset_version_id: UUID,
                             path: str) -> None:
    """A pinned dataset must be an approved (public) immutable version.

    Shared reference rule (NI-036 dataTable pins, NI-041 liveChart pins):
    staged/validated/rejected versions never leak existence and are never
    substituted with a latest pointer — the pinned id is the evidence.
    """
    exists = connection.execute(
        select(DatasetVersion.id).where(DatasetVersion.id == dataset_version_id,
                                        DatasetVersion.status == "approved")
    ).first()
    if exists is None:
        raise ReferenceInvalid(
            "Referenced dataset version does not exist or is not an approved "
            "public dataset",
            [(path, "dangling_dataset_reference")])


def _same_pins(observed: ResolvedContext, expected: ResolvedContext) -> bool:
    # resolved_at records a server decision. Ordering metric IDs does not
    # change the selection or canonical context hash.
    return (
        observed.chart_definition_version_id == expected.chart_definition_version_id
        and observed.dataset_version_id == expected.dataset_version_id
        and observed.selection == expected.selection
        and observed.context_hash == expected.context_hash
        and observed.renderer_version == expected.renderer_version
        and sorted(observed.metric_definition_versions) == sorted(expected.metric_definition_versions)
    )


def resolve_revision_contexts(connection: Connection, canonical: CanonicalDocument,
                              previous: DocumentVersionRow, *,
                              observed_contexts: Sequence[ResolvedContext | dict] = ()) -> dict:
    """Validate inspected evidence and pin every chart in a new revision.

    Claims match a chart by its exact pinned evidence, so multiple blocks
    with the same evidence can share a claim. A legacy save may submit no
    claims and still identifies the inspected versions through canonical attrs.
    """
    if len(observed_contexts) > MAX_CONTEXTS:
        raise DocumentSchemaError(
            "Too many observed chart contexts", [("observed_contexts", "too_many_entries")])
    previous_contexts = previous.resolved_contexts or {}
    previous_charts = {}
    if previous_contexts and canonical.live_charts:
        if not isinstance(previous_contexts, dict):
            raise ReferenceInvalid(
                "The stored chart contexts are malformed",
                [("content", "invalid_chart_context")])
        previous_charts = {
            chart.block_id: chart for chart in parse_document(previous.content).live_charts
        }
    contexts = {}
    expected_by_hash: dict[str, ResolvedContext] = {}
    definitions: dict[UUID, ChartDefinitionRow] = {}
    approved_datasets: set[UUID] = set()
    verified_coverage: set[tuple[UUID, UUID]] = set()
    resolved_at = datetime.now(UTC)
    for chart in canonical.live_charts:
        require_live_chart_mode(chart.mode, error_path="content")
        definition = definitions.get(chart.chart_definition_version_id)
        if definition is None:
            definition = load_chart_definition(connection, chart.chart_definition_version_id,
                                               error_path="content")
            definitions[definition.id] = definition
        selection = ChartSelection.model_validate(chart.selection)
        validate_selection_against_definition(definition, selection.start, selection.end,
                                              selection.filters)
        dataset_id = chart.observed_dataset_version_id
        if dataset_id not in approved_datasets:
            require_approved_dataset(connection, dataset_id, "liveChart.observed_dataset_version_id")
            approved_datasets.add(dataset_id)
        coverage_key = (definition.id, dataset_id)
        if coverage_key not in verified_coverage:
            require_metric_coverage(connection, definition, dataset_id, error_path="content")
            verified_coverage.add(coverage_key)

        expected = build_resolved_context(definition, dataset_id, selection,
                                          resolved_at=resolved_at)
        expected_by_hash[expected.context_hash] = expected
        block_id = str(chart.block_id)
        if previous_charts.get(chart.block_id) == chart and block_id in previous_contexts:
            prior = previous_contexts[block_id]
            try:
                compatible = _same_pins(ResolvedContext.model_validate(prior), expected)
            except ValidationError:
                compatible = False
            if not compatible:
                raise ReferenceInvalid(
                    "The stored chart context disagrees with its immutable pins",
                    [("content", "chart_context_mismatch")])
            contexts[block_id] = prior
        else:
            contexts[block_id] = expected.model_dump(mode="json")

    for index, claim in enumerate(observed_contexts):
        path = f"observed_contexts[{index}]"
        try:
            observed = ResolvedContext.model_validate(claim)
        except ValidationError:
            raise DocumentSchemaError("Invalid observed chart context",
                                      [(path, "invalid_context")]) from None
        expected = expected_by_hash.get(observed.context_hash)
        if expected is None or not _same_pins(observed, expected):
            raise ReferenceInvalid(
                "The observed context does not match a chart's immutable definition, "
                "dataset, selection and version pins in this revision",
                [(path, "observed_context_mismatch")])
    return contexts


class ReconstructionError(ValueError):
    """An owned revision lacks consistent evidence needed for a chart read."""

    def __init__(self, reason: str):
        super().__init__("The saved chart could not be reconstructed from its frozen evidence")
        self.reason = reason


def reconstruct_revision_chart(connection: Connection, version: DocumentVersionRow,
                               block_id: UUID) -> ChartViewResponse:
    """Reconstruct one saved chart without consulting current document or latest data."""
    try:
        document = parse_document(version.content)
    except DocumentSchemaError:
        raise ReconstructionError("invalid_revision_content") from None
    if document.canonical["schema_version"] != version.schema_version:
        raise ReconstructionError("invalid_revision_content")
    if document.content_sha256 != version.content_sha256:
        raise ReconstructionError("revision_content_hash_mismatch")
    chart = next((item for item in document.live_charts if item.block_id == block_id), None)
    if chart is None:
        raise ResourceNotFound("Chart block is absent from this revision")
    if version.resolved_contexts is not None and not isinstance(version.resolved_contexts, dict):
        raise ReconstructionError("invalid_chart_context")
    stored_context = (version.resolved_contexts or {}).get(str(block_id))
    if stored_context is None:
        raise ReconstructionError("missing_chart_context")
    try:
        context = ResolvedContext.model_validate(stored_context)
    except ValidationError:
        raise ReconstructionError("invalid_chart_context") from None
    try:
        require_live_chart_mode(chart.mode, error_path="content")
        definition = load_chart_definition(connection, chart.chart_definition_version_id,
                                           error_path="content")
        selection = ChartSelection.model_validate(chart.selection)
        validate_selection_against_definition(definition, selection.start, selection.end,
                                              selection.filters)
        expected = build_resolved_context(definition, chart.observed_dataset_version_id,
                                          selection, resolved_at=context.resolved_at)
    except (DocumentSchemaError, DeliveryInvalidFilter, ValidationError):
        raise ReconstructionError("pinned_definition_unavailable") from None
    if not _same_pins(context, expected):
        raise ReconstructionError("chart_context_mismatch")
    try:
        view = delivery.build_chart_view(
            connection, chart_id=definition.chart_id, version=definition.version,
            start=context.selection.start, end=context.selection.end,
            filters=context.selection.filters, dataset_version=context.dataset_version_id,
            verify_content=True)
    except (delivery.DeliveryError, ValidationError):
        raise ReconstructionError("pinned_artifact_unavailable") from None
    if (view.context_hash != context.context_hash
            or view.definition.renderer_version != context.renderer_version
            or sorted(series.metric.id for series in view.series)
            != sorted(context.metric_definition_versions)):
        raise ReconstructionError("chart_context_mismatch")
    return view.model_copy(update={"resolved_at": context.resolved_at})
