"""Resolve and verify document chart pins against immutable registry versions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Mapping, Sequence
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import Connection, func, select

from near_api.datasets import delivery
from near_api.datasets.canonical import dump_canonical, sha256_hex
from near_api.datasets.delivery import (
    DeliveryInvalidFilter,
    _context_hash,
    validate_filters_against_schema,
)
from near_api.db.models import (
    ChartDefinition,
    ChartMetric,
    DatasetVersion,
    MetricObservation,
    ModelRun,
)
from near_api.db.security import ResourceNotFound
from near_api.documents.schema import (
    MAX_CONTEXTS,
    CanonicalDocument,
    DocumentSchemaError,
    ModelResultNode,
    ReferenceInvalid,
    parse_document,
)
from near_api.insights.schemas import ModelContext, ResolvedContext
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


@dataclass(frozen=True)
class PublishedRunRow:
    """The immutable published-run facts document pins may reference (NI-055)."""

    run_id: UUID
    spec_id: str
    spec_version: int

    @property
    def specification_version(self) -> str:
        """The frozen ModelContext spelling of the run's specification identity."""
        return f"{self.spec_id}@{self.spec_version}"


def load_published_run(connection: Connection, run_id: UUID, *,
                       error_path: str) -> PublishedRunRow:
    """Load one published immutable model run; reject anything else.

    An absent, malformed or non-published identity is the same typed dangling
    reference (422 REFERENCE_INVALID): a ``modelResult`` block can only pin a
    row written by the operator publication gate, and no latest/substitute
    run is ever resolved in its place.
    """
    row = connection.execute(
        select(ModelRun.run_id, ModelRun.spec_id, ModelRun.spec_version)
        .where(ModelRun.run_id == run_id, ModelRun.status == "published")
    ).first()
    if row is None:
        raise ReferenceInvalid(
            "Referenced model run does not exist or is not a published "
            "immutable artifact",
            [(error_path, "dangling_model_run_reference")])
    return PublishedRunRow(run_id=row.run_id, spec_id=row.spec_id,
                           spec_version=int(row.spec_version))


def model_context_hash(model_run_id: UUID, dataset_version_id: UUID,
                       specification_version: str) -> str:
    """The canonical ModelContext hash (same dump/sha256 algorithm as ChartView)."""
    return sha256_hex(dump_canonical({
        "model_run_id": str(model_run_id),
        "dataset_version_id": str(dataset_version_id),
        "specification_version": specification_version,
    }))


def build_model_context(run: PublishedRunRow, dataset_version_id: UUID) -> ModelContext:
    """Freeze the NI-055 model context: run identity + dataset pin + hash."""
    return ModelContext(
        model_run_id=run.run_id,
        dataset_version_id=dataset_version_id,
        specification_version=run.specification_version,
        context_hash=model_context_hash(run.run_id, dataset_version_id,
                                        run.specification_version),
    )


def verify_model_result_pins(connection: Connection, node: ModelResultNode, *,
                             error_path: str) -> ModelContext:
    """Verify one modelResult block's pins and return its frozen context.

    The run must be a published immutable row and the dataset pin an approved
    public version (never substituted with latest). The context records the
    exact ids the author pinned; coefficients never travel through here —
    they stay on the immutable run row.
    """
    run = load_published_run(connection, node.model_run_id,
                             error_path=f"{error_path}.model_run_id")
    require_approved_dataset(connection, node.dataset_version_id,
                             f"{error_path}.dataset_version_id")
    return build_model_context(run, node.dataset_version_id)


def same_model_pins(observed: ModelContext, expected: ModelContext) -> bool:
    return (
        observed.model_run_id == expected.model_run_id
        and observed.dataset_version_id == expected.dataset_version_id
        and observed.specification_version == expected.specification_version
        and observed.context_hash == expected.context_hash
    )


def same_chart_pins(observed: ResolvedContext, expected: ResolvedContext) -> bool:
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


def verify_chart_context(connection: Connection, observed: ResolvedContext,
                         *, resolved_at: datetime) -> ResolvedContext:
    """Verify a submitted inspection against the exact immutable chart inputs."""
    definition = load_chart_definition(connection, observed.chart_definition_version_id,
                                       error_path="context.chart_definition_version_id")
    selection = observed.selection
    validate_selection_against_definition(definition, selection.start, selection.end,
                                          selection.filters)
    require_approved_dataset(connection, observed.dataset_version_id,
                             "context.dataset_version_id")
    require_metric_coverage(connection, definition, observed.dataset_version_id,
                            error_path="context.dataset_version_id")
    expected = build_resolved_context(definition, observed.dataset_version_id,
                                      selection, resolved_at=resolved_at)
    if not same_chart_pins(observed, expected):
        raise ReferenceInvalid(
            "The inspected context disagrees with its immutable chart pins",
            [("context", "chart_context_mismatch")])
    return expected


def resolve_revision_contexts(connection: Connection, canonical: CanonicalDocument,
                              previous: DocumentVersionRow, *,
                              observed_contexts: Sequence[ResolvedContext | dict] = ()) -> dict:
    """Validate inspected evidence and pin every chart/model block in a revision.

    Claims match a chart by its exact pinned evidence, so multiple blocks
    with the same evidence can share a claim. A legacy save may submit no
    claims and still identifies the inspected versions through canonical attrs.

    NI-055: every ``modelResult`` block is verified against the published-run
    catalog and the approved-dataset pin, and its frozen ``ModelContext`` is
    keyed by block_id in the same map. An unchanged block (same run id,
    dataset pin and interpretation-independent identity) carries its prior
    context VERBATIM after re-verification — a newer dataset publication or a
    newer published run never re-points or refits an already-inserted result.
    """
    if len(observed_contexts) > MAX_CONTEXTS:
        raise DocumentSchemaError(
            "Too many observed chart contexts", [("observed_contexts", "too_many_entries")])
    previous_contexts = previous.resolved_contexts or {}
    previous_charts = {}
    previous_models = {}
    if previous_contexts and (canonical.live_charts or canonical.model_results):
        if not isinstance(previous_contexts, dict):
            raise ReferenceInvalid(
                "The stored chart contexts are malformed",
                [("content", "invalid_chart_context")])
        prior_document = parse_document(previous.content)
        previous_charts = {chart.block_id: chart for chart in prior_document.live_charts}
        previous_models = {model.block_id: model for model in prior_document.model_results}
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
                compatible = same_chart_pins(ResolvedContext.model_validate(prior), expected)
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
        if expected is None or not same_chart_pins(observed, expected):
            raise ReferenceInvalid(
                "The observed context does not match a chart's immutable definition, "
                "dataset, selection and version pins in this revision",
                [(path, "observed_context_mismatch")])

    published_runs: dict[UUID, PublishedRunRow] = {}
    approved_model_datasets: set[UUID] = set()
    for model in canonical.model_results:
        block_id = str(model.block_id)
        prior = previous_models.get(model.block_id)
        if (prior is not None and prior.model_run_id == model.model_run_id
                and prior.dataset_version_id == model.dataset_version_id
                and block_id in previous_contexts):
            # Unchanged pin: the stored context stays verbatim after the same
            # published-run/approved-dataset re-verification every save runs.
            run = published_runs.get(model.model_run_id)
            if run is None:
                run = load_published_run(
                    connection, model.model_run_id,
                    error_path=f"modelResult.{block_id}.model_run_id")
                published_runs[model.model_run_id] = run
            if model.dataset_version_id not in approved_model_datasets:
                require_approved_dataset(
                    connection, model.dataset_version_id,
                    f"modelResult.{block_id}.dataset_version_id")
                approved_model_datasets.add(model.dataset_version_id)
            expected_model = build_model_context(run, model.dataset_version_id)
            try:
                stored = ModelContext.model_validate(previous_contexts[block_id])
            except ValidationError:
                raise ReferenceInvalid(
                    "The stored model context is malformed",
                    [("content", "invalid_model_context")]) from None
            if not same_model_pins(stored, expected_model):
                raise ReferenceInvalid(
                    "The stored model context disagrees with its immutable run "
                    "and dataset pins",
                    [("content", "model_context_mismatch")])
            contexts[block_id] = previous_contexts[block_id]
        else:
            # New or re-pointed block: verify the exact pins and freeze the
            # context. Existing results keep their prior context untouched —
            # a changed data pointer is a NEW frozen context, never a refit
            # of the old result.
            expected_model = verify_model_result_pins(
                connection, model, error_path=f"modelResult.{block_id}")
            contexts[block_id] = expected_model.model_dump(mode="json")
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
    if not same_chart_pins(context, expected):
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
