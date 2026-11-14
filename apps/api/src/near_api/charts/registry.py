"""Registered chart definitions for NI-031 (immutable, versioned).

One :class:`ChartDefinition` per catalog concept of docs/CHART_SYSTEM.md
("Initial catalog"). The definition UUID is ``uuid5`` over
``"<chart_id>:v<version>"`` in a fixed chart-registry namespace, so the same
definition always carries the same identity across code, saved charts,
documents and database rows. Definitions are immutable: a changed chart
appends ``version 2`` and never rewrites version 1.

A definition is registry-driven and complete: it fully describes what the
generic renderer and the API show — visualization type, category, metric
definition bindings with required/optional series roles, per-series units,
allowed query ranges, the supported-filter JSON Schema, the expected update
frequency, source lineage and the renderer version. A page consumes the
resolved contract (see :func:`view_contract`); adding a supported definition
needs no new page implementation.

``data_status`` is the honest advertisement (CHART_SYSTEM "Initial catalog
(only publish when inputs validate)"): only ``available`` charts are
advertised as live. Charts bound to gated metrics (``availability == "G"``
in docs/METRIC_CATALOG.md) or waiting for a published model artifact are
registered ``unavailable`` with the recorded reason and are never advertised
as live. Last-updated, data quality and actual date coverage belong to the
resolved ChartView dataset (NI-032), never to this definition.

``register_charts`` persists the current registry into ``app.chart_definitions``
+ ``app.chart_metrics`` (migration 0007) as the unprivileged ``near_operator``.
It is idempotent and content-verified, mirroring
``near_api.metrics.registry.register_definitions``: an existing
``(chart_id, version)`` row whose payload diverges from the code registry is a
registry error — the row may only be superseded by a new version, never edited.
Every referenced metric UUID must resolve to a registered metric definition,
every declared unit must equal the bound metric's unit, every filter option
must come from the definition's approved mappings, and a chart bound to a
gated metric must be ``unavailable`` — a violation of any of these fails
``validate_registry`` closed.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, replace
from typing import Mapping
from uuid import UUID

from sqlalchemy import text

from near_api.charts.filter_registry import (
    FILTER_DIMENSIONS,
    FILTER_PRICE_BASES,
    FILTER_PROVIDER_SOURCES,
    FILTER_TREASURY_RECIPIENTS,
    MAX_FILTER_OPTIONS,
    MAX_FILTER_PROPERTIES,
)
from near_api.metrics.registry import (
    MetricDefinition,
    definition_by_metric_id_version,
)

# Deterministic identity namespace for the NI-031 chart registry
# (uuid5 over the name string below; do not regenerate).
CHART_REGISTRY_NAMESPACE = uuid.UUID("6a79f809-5ba7-44a8-8fba-ea5426d1ddd4")

CHART_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,79}$")

# Fixed supported categories (DATABASE_SCHEMA.md: "supported categories fixed").
CATEGORIES = ("activity", "fees", "treasury", "supply", "model")
VISUALIZATION_TYPES = ("line", "area", "bar", "scatter", "panels")
# Required/optional series roles of the chart_metrics junction: a required_*
# series must resolve for the chart to render; optional_* series add context
# when their observations exist.
SERIES_ROLES = ("required_primary", "required_secondary", "required_x_axis",
                "required_y_axis", "optional_overlay", "optional_context")
FREQUENCIES = ("daily", "weekly", "monthly", "snapshot")
DATA_STATUSES = ("available", "unavailable")

# CHART_SYSTEM query/render contract: "date range <= 366 days initially";
# default presets are 7/30/90 days relative to the latest complete observation.
MAX_RANGE_DAYS = 366
MAX_HISTORY_RANGE_DAYS = 730
DEFAULT_PRESET_DAYS = (7, 30, 90)

# Approved source/recipient/price-basis filter mappings live in the NI-071
# filter registry (charts/filter_registry.py) and are re-exported here for
# compatibility; every chart filter_schema is built from those declarations,
# so a dimension mapping can never drift between chart versions.
__all__ = ["CHARTS", "CATEGORIES", "ChartDefinition", "ChartRegistryError",
           "CHART_REGISTRY_NAMESPACE", "DATA_STATUSES", "DEFAULT_PRESET_DAYS",
           "FILTER_PRICE_BASES", "FILTER_PROVIDER_SOURCES",
           "FILTER_TREASURY_RECIPIENTS", "FREQUENCIES", "MAX_RANGE_DAYS",
           "MAX_FILTER_OPTIONS", "MAX_FILTER_PROPERTIES", "RENDERER_VERSION",
           "SERIES_ROLES", "VISUALIZATION_TYPES", "chart_by_chart_id",
           "register_charts", "validate_registry", "view_contract"]

# The generic modular ECharts SVG renderer (browser + Node SSR builder share
# it); a definition pins which renderer capability set it targets.
RENDERER_VERSION = "echarts-modular-svg@1"


class ChartRegistryError(RuntimeError):
    """The chart registry is internally inconsistent or diverges from rows."""


@dataclass(frozen=True)
class ChartSeries:
    """One metric binding: the registered metric id, its exact definition
    version and its series role.

    NI-071: metric ids are superseded by new versions over time, so a chart
    version pins the exact definition version it binds. Registered charts
    keep that binding forever (their junction rows are content-verified);
    resolving "whatever is latest" would silently rebind a stored chart.
    """

    metric_id: str
    series_role: str
    metric_version: int = 1


def resolve_binding(metrics: Mapping[str, MetricDefinition],
                    binding: ChartSeries) -> MetricDefinition:
    """The exact registered metric definition version one binding pins.

    ``metrics`` holds the latest version per metric id (the shape callers
    build from the registry tuple); a binding pinned to another version
    resolves through the versioned registry lookup.
    """
    metric = metrics.get(binding.metric_id)
    if metric is not None and metric.version == binding.metric_version:
        return metric
    return definition_by_metric_id_version(binding.metric_id, binding.metric_version)


@dataclass(frozen=True)
class ChartDefinition:
    """One immutable chart definition version."""

    chart_id: str
    version: int
    title: str
    description: str
    category: str
    visualization_type: str
    update_frequency: str
    series: tuple[ChartSeries, ...] = ()
    data_status: str = "available"
    unavailable_reason: str | None = None
    allowed_ranges: dict = field(
        default_factory=lambda: {"presets_days": list(DEFAULT_PRESET_DAYS),
                                 "max_days": MAX_RANGE_DAYS})
    filter_schema: dict = field(
        default_factory=lambda: {"type": "object", "properties": {},
                                 "additionalProperties": False})
    unit_schema: dict = field(default_factory=dict)
    source_lineage: dict = field(default_factory=dict)
    renderer_version: str = RENDERER_VERSION

    @property
    def id(self) -> UUID:
        return uuid.uuid5(CHART_REGISTRY_NAMESPACE, f"{self.chart_id}:v{self.version}")

    def row(self, metrics: Mapping[str, MetricDefinition]) -> dict:
        """Column payload for app.chart_definitions (canonical JSON values)."""
        return {
            "id": self.id,
            "chart_id": self.chart_id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "visualization_type": self.visualization_type,
            "data_status": self.data_status,
            "unavailable_reason": self.unavailable_reason,
            "update_frequency": self.update_frequency,
            "allowed_ranges": self.allowed_ranges,
            "filter_schema": self.filter_schema,
            "unit_schema": self.unit_schema,
            "metric_definition_ids": sorted(str(resolve_binding(metrics, s).id)
                                            for s in self.series),
            "source_lineage": self.source_lineage,
            "renderer_version": self.renderer_version,
        }

    def junction_rows(self, metrics: Mapping[str, MetricDefinition]) -> list[dict]:
        return [{"chart_definition_version_id": self.id,
                 "metric_definition_id": resolve_binding(metrics, s).id,
                 "series_role": s.series_role}
                for s in self.series]


def _filter_enum(name: str, options: tuple[str, ...],
                 applies_to: tuple[str, ...] | None = None) -> dict:
    """The closed NI-031 single-value filter schema for one dimension.

    Built from the NI-071 filter registry declaration so the mapping cannot
    drift. ``applies_to`` (NI-094) optionally scopes the dimension to specific
    series roles: a series whose role is not listed is never filtered by it —
    the filter exists to disambiguate that dimension's variants, not to blank
    sibling series that do not carry it.
    """
    dimension = FILTER_DIMENSIONS[name]
    if tuple(dimension.options) != tuple(options):
        raise ChartRegistryError(
            f"filter dimension {name!r} options disagree with the filter registry")
    bound: dict = {"type": "string", "enum": list(options)}
    if applies_to is not None:
        bound["applies_to"] = list(applies_to)
    return {"type": "object",
            "properties": {name: bound},
            "additionalProperties": False}


def _filter_comparison(name: str) -> dict:
    """The NI-071 multi-value/reconciliation schema for one dimension."""
    return FILTER_DIMENSIONS[name].filter_schema(include_comparison=True)


def _chart(chart_id: str, *, version: int, title: str, description: str, category: str,
           visualization_type: str, update_frequency: str,
           series: tuple[ChartSeries, ...] = (), data_status: str = "available",
           unavailable_reason: str | None = None, allowed_ranges: dict | None = None,
           filter_schema: dict | None = None, unit_schema: dict | None = None,
           source_lineage: dict | None = None) -> ChartDefinition:
    return ChartDefinition(
        chart_id=chart_id, version=version, title=title, description=description,
        category=category, visualization_type=visualization_type,
        update_frequency=update_frequency, series=series, data_status=data_status,
        unavailable_reason=unavailable_reason,
        allowed_ranges=allowed_ranges if allowed_ranges is not None else
        {"presets_days": list(DEFAULT_PRESET_DAYS), "max_days": MAX_RANGE_DAYS},
        filter_schema=filter_schema if filter_schema is not None else
        {"type": "object", "properties": {}, "additionalProperties": False},
        unit_schema=unit_schema if unit_schema is not None else {},
        source_lineage=source_lineage if source_lineage is not None else
        {"sources": [], "note": ""},
    )


def _series(*bindings: "tuple[str, str] | tuple[str, str, int]") -> tuple[ChartSeries, ...]:
    return tuple(ChartSeries(metric_id=binding[0], series_role=binding[1],
                             metric_version=binding[2] if len(binding) > 2 else 1)
                 for binding in bindings)


GatedRevenueReason = ("protocol_revenue_usd is gated (OQ-01): no verified economically "
                      "attributable revenue/allocation ledger exists; gross fees and "
                      "treasury payouts are not substitutes.")

CHARTS: tuple[ChartDefinition, ...] = (
    _chart(
        "intents-volume", version=1,
        title="Provider-reported Intents gross volume",
        description="Daily provider-reported Intents gross turnover in USD, "
                    "source-qualified. Answers whether observed activity is growing; "
                    "provider turnover is not token value.",
        category="activity", visualization_type="area", update_frequency="daily",
        series=_series(("provider_intents_volume_usd", "required_primary")),
        filter_schema=_filter_enum("source", FILTER_PROVIDER_SOURCES),
        unit_schema={"required_primary": "USD"},
        source_lineage={"sources": ["SRC-LLAMA"],
                        "note": "Provider-reported series kept exactly as reported per "
                                "qualified source; definitions and revisions differ "
                                "between providers and are never summed across sources."},
    ),
    _chart(
        "gross-fees", version=1,
        title="Provider-reported Intents gross fees",
        description="Daily provider-reported gross fees in USD, source-qualified. "
                    "Accrual definitions and provider revisions stay visible; this is "
                    "not revenue retained by NEAR.",
        category="fees", visualization_type="bar", update_frequency="daily",
        series=_series(("provider_gross_fees_usd", "required_primary")),
        filter_schema=_filter_enum("source", FILTER_PROVIDER_SOURCES),
        unit_schema={"required_primary": "USD"},
        source_lineage={"sources": ["SRC-LLAMA"],
                        "note": "Not attributable protocol revenue (OQ-01); recent "
                                "completed days can be revised by the provider and a "
                                "revision is a new dataset version."},
    ),
    _chart(
        "observed-conversions", version=1,
        title="Observed NEAR purchases and conversion events",
        description="How much NEAR the observed treasury-linked cohort acquired, in two "
                    "separate aligned panels: NEAR quantity and conversion event count. "
                    "The panels are never merged or dual-axed.",
        category="activity", visualization_type="panels", update_frequency="daily",
        series=_series(("observed_near_purchases", "required_primary"),
                       ("conversion_count", "required_secondary")),
        unit_schema={"required_primary": "NEAR", "required_secondary": "events"},
        source_lineage={"sources": ["SRC-BQ"],
                        "note": "Successful wrap.near conversions of the saved 90-day "
                                "cohort only; an event count is not a user count and "
                                "never a NEAR amount."},
    ),
    _chart(
        "treasury-payouts", version=1,
        title="Treasury payouts from intents.near",
        description="What cash transfers reached the selected named wallets: matched "
                    "successful native transfers out of intents.near, per recipient.",
        category="treasury", visualization_type="bar", update_frequency="daily",
        series=_series(("treasury_payouts_near", "required_primary", 1)),
        filter_schema=_filter_enum("recipient", FILTER_TREASURY_RECIPIENTS),
        unit_schema={"required_primary": "NEAR"},
        source_lineage={"sources": ["SRC-BQ"],
                        "note": "Cash transfers out of the intents contract to the three "
                                "named wallets; internal treasury hops, other-sender "
                                "inflows and failed transfers are excluded."},
    ),
    _chart(
        "treasury-payouts", version=2,
        title="Treasury payouts from intents.near by recipient",
        description="Matched successful native transfers out of intents.near, one "
                    "compared series per selected recipient. Selecting the full "
                    "declared universe (all three named wallets) must reconcile "
                    "with the aggregate payout definition; a mismatch is withheld "
                    "with a reason, never shown inconsistently.",
        category="treasury", visualization_type="bar", update_frequency="daily",
        series=_series(("treasury_payouts_near", "required_primary", 2)),
        filter_schema=_filter_comparison("recipient"),
        unit_schema={"required_primary": "NEAR"},
        source_lineage={"sources": ["SRC-BQ"],
                        "note": "Cash transfers out of the intents contract to the three "
                                "named wallets; internal treasury hops, other-sender "
                                "inflows and failed transfers are excluded. The "
                                "recipient dimension is the verified receiver of each "
                                "matched transfer; no integrator or customer "
                                "classification is invented."},
    ),
    _chart(
        "quantity-usd-sensitivity", version=1,
        title="Purchase quantity versus USD estimate",
        description="Does the saved price explain observed token quantity changes? "
                    "Indexed comparison only with an explicitly chosen base, next to an "
                    "accessible raw-value table; the USD series carries an estimate "
                    "badge.",
        category="activity", visualization_type="line", update_frequency="daily",
        series=_series(("observed_near_purchases", "required_primary"),
                       ("estimated_purchase_usd", "required_secondary")),
        filter_schema=_filter_enum("price_basis", FILTER_PRICE_BASES),
        unit_schema={"required_primary": "NEAR", "required_secondary": "USD"},
        source_lineage={"sources": ["SRC-BQ", "SRC-PRICE"],
                        "note": "The USD series is a daily saved-price valuation "
                                "estimate, not execution consideration; a missing price "
                                "makes the day's USD value missing, never zero."},
    ),
    _chart(
        "supply-context", version=1,
        title="Purchases in the context of net supply change",
        description="How large observed purchases are relative to net supply growth, as "
                    "matched-boundary-period bars and table. A scale comparison only; "
                    "purchases are never subtracted from total supply.",
        category="supply", visualization_type="bar", update_frequency="snapshot",
        series=_series(("net_supply_change_near", "required_primary"),
                       ("observed_near_purchases", "required_secondary")),
        unit_schema={"required_primary": "NEAR", "required_secondary": "NEAR"},
        source_lineage={"sources": ["SRC-FASTNEAR", "SRC-BQ"],
                        "note": "Exact pinned-boundary supply differences against the "
                                "observed purchases of the matched window; the chart "
                                "never implies purchases reduce total supply."},
    ),
    _chart(
        "fee-volume-association", version=1,
        title="Gross fees versus volume association",
        description="Is the fee relationship mechanical? Per-day scatter of "
                    "provider-reported volume and gross fees from the same qualified "
                    "source, with date labels; a published-model overlay is added only "
                    "when a fitted model exists.",
        category="fees", visualization_type="scatter", update_frequency="daily",
        series=_series(("provider_intents_volume_usd", "required_x_axis"),
                       ("provider_gross_fees_usd", "required_y_axis")),
        filter_schema=_filter_enum("source", FILTER_PROVIDER_SOURCES),
        unit_schema={"required_x_axis": "USD", "required_y_axis": "USD"},
        source_lineage={"sources": ["SRC-LLAMA"],
                        "note": "Descriptive association of two provider series that "
                                "share Dune lineage; agreement is not independent "
                                "confirmation and the ratio is not a contracted rate."},
    ),
    _chart(
        "model-diagnostics", version=1,
        title="Model residual diagnostics",
        description="Are residuals consistent with the published specification? "
                    "Residual/time/ACF panels rendered from a published model run's "
                    "stored diagnostics, never from invented plot values.",
        category="model", visualization_type="panels", update_frequency="snapshot",
        data_status="unavailable",
        unavailable_reason="No published, reviewed model artifact exists yet; the "
                           "panels require a published model run (NI-052/NI-054) and "
                           "are never drawn from invented values.",
        allowed_ranges={"presets_days": [90], "max_days": MAX_RANGE_DAYS},
        source_lineage={"sources": [],
                        "note": "Resolves a published model artifact by run ID; this "
                                "chart binds no metric series, so it stays unavailable "
                                "until a reviewed artifact is published."},
    ),
    _chart(
        "protocol-revenue", version=1,
        title="Economically attributable protocol revenue (gated)",
        description="Explicitly unavailable chart: attributable protocol revenue stays "
                    "gated until a reconciled fee/allocation ledger exists. Gross fees, "
                    "volume and treasury payouts are not substitutes.",
        category="fees", visualization_type="bar", update_frequency="daily",
        series=_series(("protocol_revenue_usd", "required_primary")),
        data_status="unavailable", unavailable_reason=GatedRevenueReason,
        unit_schema={"required_primary": "USD"},
        source_lineage={"sources": [],
                        "note": "Bound to the gated protocol_revenue_usd definition "
                                "(OQ-01); every observation is null with that reason "
                                "until the gate passes."},
    ),
    _chart(
        "capture-rate", version=1,
        title="Protocol capture rate (gated)",
        description="Explicitly unavailable chart: the capture rate needs an "
                    "attributable revenue numerator and a compatible gross-fee "
                    "denominator; both reconciliations are open questions.",
        category="fees", visualization_type="line", update_frequency="daily",
        series=_series(("protocol_capture_rate", "required_primary")),
        data_status="unavailable",
        unavailable_reason="protocol_capture_rate is gated (OQ-01/OQ-11): the revenue "
                           "numerator and the compatible fee denominator are "
                           "unresolved, so every observation is null with a reason.",
        unit_schema={"required_primary": "percent"},
        source_lineage={"sources": [],
                        "note": "Bound to the gated protocol_capture_rate definition; no "
                                "hard daily 0-100 clip hides the mismatch."},
    ),
    _chart(
        "fee-funded-buybacks", version=1,
        title="Fee-funded buybacks (gated)",
        description="Explicitly unavailable chart: executed conversions attributable to "
                    "earned fees cannot be identified because pooled funds are not "
                    "physically tagged.",
        category="treasury", visualization_type="bar", update_frequency="snapshot",
        series=_series(("fee_funded_buybacks_near", "required_primary")),
        data_status="unavailable",
        unavailable_reason="fee_funded_buybacks_near is gated (OQ-08): no documented "
                           "mixed-pool accounting attribution exists for the full "
                           "window, so every observation is null with a reason.",
        unit_schema={"required_primary": "NEAR"},
        source_lineage={"sources": [],
                        "note": "The narrow 27 Oct-2 Nov strict inventory equivalent is "
                                "a NI-051 research artifact, not this metric."},
    ),
)

# NI-083: append immutable long-history versions; v1 remains byte-for-byte.
CHARTS += tuple(replace(chart, version=2,
    allowed_ranges={"presets_days": [30, 90, 365, 730], "max_days": MAX_HISTORY_RANGE_DAYS})
    for chart in CHARTS if chart.chart_id in {"intents-volume", "gross-fees"})

# NI-094: the price_basis filter applies to the USD series only (the purchases
# series carries no price dimension and must not be blanked by it); v1 remains
# byte-for-byte.
CHARTS += tuple(replace(chart, version=2,
    filter_schema=_filter_enum("price_basis", FILTER_PRICE_BASES,
                               applies_to=("required_secondary",)))
    for chart in CHARTS if chart.chart_id == "quantity-usd-sensitivity")

_CHARTS_BY_CHART_ID: dict[str, ChartDefinition] = {}
for _chart_item in CHARTS:
    _previous = _CHARTS_BY_CHART_ID.get(_chart_item.chart_id)
    if _previous is not None:
        # Superseding versions of one chart id coexist in the registry; the
        # map holds the latest registered version. An exact (chart_id,
        # version) repeat or a non-ascending order is a registry authoring
        # error.
        if _previous.version >= _chart_item.version:
            raise ChartRegistryError(
                f"chart versions must ascend in the registry: "
                f"{_chart_item.chart_id} v{_chart_item.version} after "
                f"v{_previous.version}")
    _CHARTS_BY_CHART_ID[_chart_item.chart_id] = _chart_item


def chart_by_chart_id(chart_id: str) -> ChartDefinition:
    """The latest registered definition version of one chart id."""
    return _CHARTS_BY_CHART_ID[chart_id]


# --------------------------------------------------------------------------- #
# Integrity validation
# --------------------------------------------------------------------------- #

def _reject(condition: bool, message: str) -> None:
    if condition:
        raise ChartRegistryError(message)


def _validate_allowed_ranges(chart: ChartDefinition) -> None:
    ranges = chart.allowed_ranges
    _reject(set(ranges) != {"presets_days", "max_days"},
            f"{chart.chart_id}: allowed_ranges must hold exactly presets_days/max_days")
    presets = ranges["presets_days"]
    _reject(not isinstance(presets, list) or not presets
            or any(not isinstance(day, int) or isinstance(day, bool) or day < 1
                   for day in presets),
            f"{chart.chart_id}: presets_days must be positive integers")
    _reject(list(presets) != sorted(set(presets)),
            f"{chart.chart_id}: presets_days must be unique and ascending")
    max_days = ranges["max_days"]
    _reject(not isinstance(max_days, int) or isinstance(max_days, bool)
            or not 1 <= max_days <= MAX_HISTORY_RANGE_DAYS,
            f"{chart.chart_id}: max_days must be an integer within {MAX_HISTORY_RANGE_DAYS}")
    _reject(any(day > max_days for day in presets),
            f"{chart.chart_id}: a preset exceeds max_days")


def _validate_filter_schema(chart: ChartDefinition) -> None:
    schema = chart.filter_schema
    _reject(set(schema) != {"type", "properties", "additionalProperties"},
            f"{chart.chart_id}: filter_schema must hold exactly type/properties/"
            "additionalProperties")
    _reject(schema["type"] != "object" or schema["additionalProperties"] is not False,
            f"{chart.chart_id}: only closed objects with additionalProperties=false are "
            "supported; unknown filter options must be rejected")
    properties = schema["properties"]
    _reject(not isinstance(properties, dict)
            or len(properties) > MAX_FILTER_PROPERTIES,
            f"{chart.chart_id}: at most {MAX_FILTER_PROPERTIES} filter properties")
    for name, bound in properties.items():
        extra_keys = set(bound) - {"type", "enum"} if isinstance(bound, dict) else set()
        _reject(not isinstance(name, str) or not name or not isinstance(bound, dict)
                or not {"type", "enum"} <= set(bound)
                or extra_keys - {"multi_value", "reconciliation", "applies_to"}
                or ("reconciliation" in extra_keys) > ("multi_value" in extra_keys)
                or bound["type"] != "string",
                f"{chart.chart_id}: filter {name!r} must be a string enum (with the "
                "optional NI-071 multi_value/reconciliation and NI-094 applies_to "
                "markers)")
        applies_to = bound.get("applies_to")
        _reject(applies_to is not None
                and (not isinstance(applies_to, list) or not applies_to
                     or any(role not in SERIES_ROLES for role in applies_to)),
                f"{chart.chart_id}: filter {name!r} applies_to must list known "
                "series roles")
        options = bound["enum"]
        _reject(not isinstance(options, list) or not options
                or len(options) > MAX_FILTER_OPTIONS
                or any(not isinstance(option, str) or not option or len(option) > 120
                       for option in options)
                or len(set(options)) != len(options),
                f"{chart.chart_id}: filter {name!r} enum must hold at most "
                f"{MAX_FILTER_OPTIONS} unique nonempty strings")
        if "multi_value" in bound:
            _reject(bound["multi_value"] is not True,
                    f"{chart.chart_id}: filter {name!r} multi_value must be true when "
                    "present")
            _reject(name not in FILTER_DIMENSIONS
                    or not FILTER_DIMENSIONS[name].multi_value,
                    f"{chart.chart_id}: filter {name!r} is not a registered multi-value "
                    "dimension of the filter registry")
        if "reconciliation" in bound:
            reconciliation = bound["reconciliation"]
            _reject(not isinstance(reconciliation, dict)
                    or set(reconciliation) != {"aggregate_metric_id",
                                               "aggregate_metric_version",
                                               "universe_note"}
                    or not isinstance(reconciliation["aggregate_metric_id"], str)
                    or not reconciliation["aggregate_metric_id"]
                    or len(reconciliation["aggregate_metric_id"]) > 80
                    or not isinstance(reconciliation["aggregate_metric_version"], int)
                    or isinstance(reconciliation["aggregate_metric_version"], bool)
                    or reconciliation["aggregate_metric_version"] < 1
                    or not isinstance(reconciliation["universe_note"], str)
                    or not reconciliation["universe_note"].strip()
                    or len(reconciliation["universe_note"]) > 500,
                    f"{chart.chart_id}: filter {name!r} reconciliation must declare "
                    "aggregate_metric_id, aggregate_metric_version and universe_note")
            _reject("multi_value" not in bound,
                    f"{chart.chart_id}: filter {name!r} reconciliation requires a "
                    "multi-value dimension")
            try:
                aggregate = definition_by_metric_id_version(
                    reconciliation["aggregate_metric_id"],
                    reconciliation["aggregate_metric_version"])
            except KeyError:
                aggregate = None
            _reject(aggregate is None,
                    f"{chart.chart_id}: filter {name!r} reconciliation names metric "
                    f"{reconciliation['aggregate_metric_id']!r} v"
                    f"{reconciliation['aggregate_metric_version']} which is not a "
                    "registered metric definition version")
            _reject(aggregate is not None
                    and aggregate.definition.get("availability") == "G",
                    f"{chart.chart_id}: filter {name!r} reconciliation aggregate must "
                    "not be a gated metric")


def _validate_source_lineage(chart: ChartDefinition, metrics: Mapping[str, MetricDefinition]) -> None:
    lineage = chart.source_lineage
    _reject(set(lineage) != {"sources", "note"},
            f"{chart.chart_id}: source_lineage must hold exactly sources/note")
    sources = lineage["sources"]
    _reject(not isinstance(sources, list)
            or any(not isinstance(source, str) or not source.startswith("SRC-")
                   for source in sources)
            or len(set(sources)) != len(sources),
            f"{chart.chart_id}: source_lineage sources must be unique SRC-* ids")
    note = lineage["note"]
    _reject(not isinstance(note, str) or not note,
            f"{chart.chart_id}: source_lineage requires a qualification note")
    declared_sources = {resolve_binding(metrics, s).source_id for s in chart.series
                        if resolve_binding(metrics, s).source_id is not None}
    _reject(not set(sources) <= declared_sources,
            f"{chart.chart_id}: source_lineage lists sources that no bound metric "
            "definition records")
    if chart.data_status == "unavailable":
        reason = chart.unavailable_reason
        _reject(not isinstance(reason, str) or not reason.strip()
                or len(reason) > 500,
                f"{chart.chart_id}: an unavailable chart requires a bounded reason")


def _validate_chart(chart: ChartDefinition, metrics: Mapping[str, MetricDefinition],
                    seen: set[UUID]) -> None:
    if not CHART_ID_PATTERN.match(chart.chart_id):
        raise ChartRegistryError(f"invalid chart_id {chart.chart_id!r}")
    if chart.version < 1:
        raise ChartRegistryError(f"{chart.chart_id}: version must be positive")
    if chart.id in seen:
        raise ChartRegistryError(f"uuid collision for {chart.chart_id}")
    seen.add(chart.id)
    _reject(not chart.title or len(chart.title) > 200,
            f"{chart.chart_id}: title must be 1..200 characters")
    _reject(not chart.description or len(chart.description) > 1000,
            f"{chart.chart_id}: description must be 1..1000 characters")
    _reject(chart.category not in CATEGORIES,
            f"{chart.chart_id}: unsupported category {chart.category!r}")
    _reject(chart.visualization_type not in VISUALIZATION_TYPES,
            f"{chart.chart_id}: unsupported visualization_type")
    _reject(chart.update_frequency not in FREQUENCIES,
            f"{chart.chart_id}: unsupported update_frequency")
    _reject(chart.data_status not in DATA_STATUSES,
            f"{chart.chart_id}: unsupported data_status")
    _reject((chart.data_status == "available") != (chart.unavailable_reason is None),
            f"{chart.chart_id}: only an unavailable chart carries a reason")
    _reject(not chart.renderer_version or len(chart.renderer_version) > 80,
            f"{chart.chart_id}: renderer_version must be 1..80 characters")
    _validate_allowed_ranges(chart)
    _validate_filter_schema(chart)
    # NI-071: a reconcilable comparison dimension sums the fan-out series of
    # the bound metric against exactly one aggregate definition, so a chart
    # carrying such a dimension binds exactly one metric.
    if any("reconciliation" in bound
           for bound in chart.filter_schema["properties"].values()):
        _reject(len(chart.series) != 1,
                f"{chart.chart_id}: a reconcilable filter dimension requires exactly "
                "one bound metric series")

    bound_metrics: list[MetricDefinition] = []
    bound_pairs: set[tuple[str, str]] = set()
    for binding in chart.series:
        if binding.series_role not in SERIES_ROLES:
            raise ChartRegistryError(
                f"{chart.chart_id}: unsupported series role {binding.series_role!r}")
        try:
            metric = resolve_binding(metrics, binding)
        except KeyError:
            raise ChartRegistryError(
                f"{chart.chart_id}: metric {binding.metric_id!r} "
                f"v{binding.metric_version} is not a registered metric definition "
                "version; a chart may only bind resolved definitions") from None
        if (binding.metric_id, binding.series_role) in bound_pairs:
            raise ChartRegistryError(
                f"{chart.chart_id}: duplicate binding {binding.metric_id}/"
                f"{binding.series_role}")
        bound_pairs.add((binding.metric_id, binding.series_role))
        bound_metrics.append(metric)

    _reject(len({binding.metric_id for binding in chart.series}) != len(chart.series),
            f"{chart.chart_id}: a metric is bound more than once")

    # Expected update frequency must describe at least one bound series.
    if bound_metrics:
        _reject(chart.update_frequency not in
                {metric.frequency for metric in bound_metrics},
                f"{chart.chart_id}: update_frequency {chart.update_frequency!r} matches "
                "no bound metric frequency")

    # Units are bound to the metric definition's unit, never restated loosely.
    roles = {binding.series_role for binding in chart.series}
    _reject(set(chart.unit_schema) != roles,
            f"{chart.chart_id}: unit_schema must hold exactly the bound series roles")
    for binding in chart.series:
        metric = resolve_binding(metrics, binding)
        _reject(chart.unit_schema[binding.series_role] != metric.unit,
                f"{chart.chart_id}: series {binding.series_role} declares unit "
                f"{chart.unit_schema[binding.series_role]!r} but metric "
                f"{binding.metric_id} is registered with unit {metric.unit!r}")

    # Honest availability: a chart bound to a gated metric is never advertised
    # as live (CHART_SYSTEM: "only publish when inputs validate").
    gated = [metric.metric_id for metric in bound_metrics
             if metric.definition.get("availability") == "G"]
    if chart.data_status == "available":
        _reject(not bound_metrics,
                f"{chart.chart_id}: an available chart binds at least one metric")
        _reject(gated,
                f"{chart.chart_id}: available chart binds gated metrics {gated}; "
                "unavailable metrics must not be advertised as live")
    else:
        _reject(bool(gated) != bool(bound_metrics) or
                (bound_metrics and not gated),
                f"{chart.chart_id}: an unavailable chart must be unavailable because "
                "all of its bound metrics are gated (or it binds none)")
    _validate_source_lineage(chart, metrics)


def validate_registry(metrics: Mapping[str, MetricDefinition]) -> None:
    """Fail closed on an internally inconsistent chart registry."""
    seen: set[UUID] = set()
    for chart in CHARTS:
        _validate_chart(chart, metrics, seen)


def view_contract(chart: ChartDefinition,
                  metrics: Mapping[str, MetricDefinition]) -> dict:
    """Registry-driven rendering contract for the generic renderer/pages.

    Everything a page needs comes from the definition: visualization, series
    with roles/units/availability (so bounds and estimates can be labeled
    generically), filters, ranges and lineage. No chart-specific page code
    exists; a newly registered supported definition renders through this
    contract unchanged.
    """
    return {
        "chart_definition_id": str(chart.id),
        "chart_id": chart.chart_id,
        "definition_version": chart.version,
        "title": chart.title,
        "description": chart.description,
        "category": chart.category,
        "visualization_type": chart.visualization_type,
        "renderer_version": chart.renderer_version,
        "update_frequency": chart.update_frequency,
        "data_status": chart.data_status,
        "unavailable_reason": chart.unavailable_reason,
        "allowed_ranges": chart.allowed_ranges,
        "filter_schema": chart.filter_schema,
        "series": [{"series_role": binding.series_role,
                    "metric_id": binding.metric_id,
                    "metric_definition_id": str(resolve_binding(metrics, binding).id),
                    "unit": resolve_binding(metrics, binding).unit,
                    "frequency": resolve_binding(metrics, binding).frequency,
                    "availability": resolve_binding(metrics, binding)
                                    .definition["availability"]}
                   for binding in chart.series],
        "source_lineage": chart.source_lineage,
    }


# --------------------------------------------------------------------------- #
# Idempotent, content-verified registration
# --------------------------------------------------------------------------- #

def _canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


CHART_COLUMNS = ("id", "chart_id", "version", "title", "description", "category",
                 "visualization_type", "data_status", "unavailable_reason",
                 "update_frequency", "allowed_ranges", "filter_schema", "unit_schema",
                 "metric_definition_ids", "source_lineage", "renderer_version")


def _stored_chart_matches(stored, row: dict) -> None:
    expected = {key: (_canonical_json(value) if isinstance(value, (dict, list)) else value)
                for key, value in row.items()}
    actual = {key: (_canonical_json(stored[key]) if isinstance(stored[key], (dict, list))
                    else stored[key])
              for key in expected}
    if actual != expected:
        diverging = sorted(key for key in expected if actual[key] != expected[key])
        raise ChartRegistryError(
            f"Stored chart definition {row['chart_id']} v{row['version']} diverges from "
            f"the code registry in {diverging}; a registered chart is immutable - "
            "supersede it with a new version instead of editing it")
    if stored["id"] != row["id"]:
        raise ChartRegistryError(
            f"Stored chart definition {row['chart_id']} v{row['version']} has identity "
            f"{stored['id']} instead of the deterministic {row['id']}")


def register_charts(connection) -> dict:
    """Idempotently insert the chart registry as near_operator; verify content.

    The caller must already be inside an operator transaction, after
    ``near_api.metrics.register_definitions`` has run (the junction FK
    resolves chart metric bindings against ``app.metric_definitions``).
    Existing rows with identical content (including the junction bindings)
    are kept; existing rows with diverging content are a registry error.
    """
    from near_api.metrics.registry import DEFINITIONS as METRIC_DEFINITIONS

    metrics = {definition.metric_id: definition for definition in METRIC_DEFINITIONS}
    validate_registry(metrics)
    registered, existing = 0, 0
    for chart in CHARTS:
        row = chart.row(metrics)
        stored = connection.execute(text("""
            SELECT id, chart_id, version, title, description, category,
                   visualization_type, data_status, unavailable_reason,
                   update_frequency, allowed_ranges, filter_schema, unit_schema,
                   metric_definition_ids, source_lineage, renderer_version
            FROM app.chart_definitions WHERE chart_id = :chart_id AND version = :version
        """), {"chart_id": row["chart_id"], "version": row["version"]}).mappings().first()
        if stored is not None:
            existing += 1
            _stored_chart_matches(stored, row)
            stored_bindings = connection.execute(text("""
                SELECT metric_definition_id, series_role FROM app.chart_metrics
                WHERE chart_definition_version_id = :id
            """), {"id": row["id"]}).all()
            expected_bindings = sorted((str(binding["metric_definition_id"]),
                                        binding["series_role"])
                                       for binding in chart.junction_rows(metrics))
            if sorted((str(metric_id), role) for metric_id, role in stored_bindings) != \
                    expected_bindings:
                raise ChartRegistryError(
                    f"Stored chart definition {row['chart_id']} v{row['version']} has "
                    "series bindings diverging from the code registry")
            continue
        connection.execute(text("""
            INSERT INTO app.chart_definitions(id, chart_id, version, title, description,
                category, visualization_type, data_status, unavailable_reason,
                update_frequency, allowed_ranges, filter_schema, unit_schema,
                metric_definition_ids, source_lineage, renderer_version)
            VALUES (:id, :chart_id, :version, :title, :description, :category,
                    :visualization_type, :data_status, :unavailable_reason,
                    :update_frequency, CAST(:allowed_ranges AS jsonb),
                    CAST(:filter_schema AS jsonb), CAST(:unit_schema AS jsonb),
                    CAST(:metric_definition_ids AS jsonb),
                    CAST(:source_lineage AS jsonb), :renderer_version)
        """), {key: (_canonical_json(value) if isinstance(value, (dict, list)) else value)
                for key, value in row.items()})
        for binding in chart.junction_rows(metrics):
            connection.execute(text("""
                INSERT INTO app.chart_metrics(chart_definition_version_id,
                    metric_definition_id, series_role)
                VALUES (:chart_definition_version_id, :metric_definition_id, :series_role)
            """), binding)
        registered += 1
    return {"registered": registered, "existing": existing, "total": len(CHARTS)}
