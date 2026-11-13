"""NI-071 approved analytical filter dimensions (immutable, versioned mappings).

This module is the single home of the supported analytical filter
dimensions (the task card's ``charts/filter_registry.py``):
``charts/registry.py`` re-points its approved-mapping constants here and
builds every chart ``filter_schema`` from these declarations, so a filter
dimension can never drift between chart versions.

What NI-071 adds on top of the NI-031 single-value enums:

- **Multi-value selection.** A dimension may declare ``multi_value``; a
  selection then carries a list of approved values and the resolved chart
  view fans out into one series per selected value combination (server-side
  fan-out — the design decision recorded in docs/CHART_SYSTEM.md and the
  NI-071 card). The canonical order of a multi-value selection is the
  dimension's declared option order below, never the request order.
- **Reconciliation.** A dimension whose declared option universe is
  exhaustive for the bound metric may declare the aggregate metric the
  per-value series must sum to. ``datasets/delivery.build_chart_view``
  enforces the identity server-side whenever the selection covers the full
  universe: sum(selected per-value series) == aggregate series per period,
  at exact Decimal precision. A mismatch is an explicit unavailable point
  with a reason — never a silent average, sum or pick.
- **Honesty boundary.** The recipient dimension below is the ONLY
  comparison dimension added: the three named intents treasuries are the
  verified source dimension of the payout metrics (``matched_pairs``
  carries the receiver). No integrator/customer/collector classification
  is invented (docs/METRIC_CATALOG.md "counted populations" rule). The
  provider ``source`` dimension stays strictly single-value and is never
  reconcilable: cross-source sums are forbidden
  (``cross_source_sum: forbidden``).

A dimension declaration is immutable: a changed mapping appends a new chart
definition version and never rewrites a registered one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from near_api.metrics.registry import TreasuryAccounts

# Approved source/recipient/price-basis mappings, moved verbatim from
# charts/registry.py (NI-031 approved mappings; the values are unchanged).
FILTER_PROVIDER_SOURCES = ("SRC-LLAMA", "SRC-DASHBOARD")
FILTER_TREASURY_RECIPIENTS = TreasuryAccounts
FILTER_PRICE_BASES = ("start_of_day", "end_of_day")

MAX_FILTER_PROPERTIES = 4
MAX_FILTER_OPTIONS = 32

# NI-071 multi-value bounds: one selection may list at most
# MAX_FILTER_VALUES_PER_KEY approved values per dimension key, and one chart
# view resolves at most MAX_FILTER_SERIES series (bindings x value
# combinations). A request beyond the bound is a typed 422, never a
# truncated resolution.
MAX_FILTER_VALUES_PER_KEY = MAX_FILTER_OPTIONS
MAX_FILTER_SERIES = 32

# datasets/delivery marks periods that fail reconciliation with these reasons.
RECONCILIATION_MISMATCH_REASON = (
    "the selected dimension values do not reconcile with the declared "
    "aggregate definition for this period; the values are withheld instead "
    "of shown inconsistently")
RECONCILIATION_INCOMPLETE_REASON = (
    "the full comparison cannot be reconciled for this period because an "
    "exact recipient or aggregate value is unavailable")


@dataclass(frozen=True)
class FilterDimension:
    """One immutable approved filter dimension."""

    key: str
    options: tuple[str, ...]
    # Multi-value dimensions admit list selections; the resolved view fans
    # out into one series per selected value combination.
    multi_value: bool = False
    # Server-enforced sum reconciliation against an aggregate metric
    # definition of the SAME dataset version. Exactly
    # {"aggregate_metric_id", "aggregate_metric_version", "universe_note"}.
    reconciliation: dict | None = None
    description: str = ""

    def schema_property(self, *, include_comparison: bool = False) -> dict:
        """The closed JSON-Schema property bound for this dimension.

        ``include_comparison=False`` reproduces the exact NI-031 property
        shape ``{"type", "enum"}`` so every registered v1 filter schema
        stays byte-identical. ``include_comparison=True`` adds the
        NI-071 ``multi_value``/``reconciliation`` markers of this
        declaration.
        """
        bound: dict = {"type": "string", "enum": list(self.options)}
        if include_comparison:
            if self.multi_value:
                bound["multi_value"] = True
            if self.reconciliation is not None:
                bound["reconciliation"] = dict(self.reconciliation)
        return bound

    def filter_schema(self, *, include_comparison: bool = False) -> dict:
        return {"type": "object",
                "properties": {self.key: self.schema_property(
                    include_comparison=include_comparison)},
                "additionalProperties": False}


FILTER_DIMENSIONS: dict[str, FilterDimension] = {
    "source": FilterDimension(
        key="source", options=FILTER_PROVIDER_SOURCES,
        description="Provider qualification of the reported Intents series; "
                    "definitions and revisions differ between providers and "
                    "are never summed across sources."),
    "recipient": FilterDimension(
        key="recipient", options=FILTER_TREASURY_RECIPIENTS,
        multi_value=True,
        reconciliation={
            "aggregate_metric_id": "treasury_payouts_near",
            "aggregate_metric_version": 1,
            "universe_note": "the three named intents treasuries are the "
                             "complete declared universe of the payout "
                             "definitions; internal hops and non-treasury "
                             "senders are excluded by the matcher quality "
                             "rules, so the per-recipient values must sum to "
                             "the aggregate definition's value for the same "
                             "period",
        },
        description="Receiving named intents treasury of the matched payout; "
                    "a multi-selection resolves one compared series per "
                    "recipient and the full-universe selection must "
                    "reconcile with the aggregate payout definition."),
    "price_basis": FilterDimension(
        key="price_basis", options=FILTER_PRICE_BASES,
        description="Saved provider price point of the selected UTC basis "
                    "(start-of-day or end-of-day); a stock, never summed."),
}


def dimension_property(chart_key: str, *, include_comparison: bool = False) -> dict:
    """The closed schema property for ``chart_key`` (a dimension key)."""
    return FILTER_DIMENSIONS[chart_key].schema_property(
        include_comparison=include_comparison)
