"""Emission of registered-definition dataset manifests (NI-029).

The computation formulas (see ``compute.FORMULA_REGISTRY``) produce
observation records whose ``metric_definition_id`` values are the
deterministic identities of the registered definitions. This module
assembles them into complete prepared-manifest documents for the NI-028
staging pipeline (``python -m near_api.datasets stage``):

- the flow dataset (``metrics.flows.daily``): daily purchases, conversion
  counts, treasury payouts and counts, saved prices, USD estimates,
  source-qualified provider volume/fees, daily fee ratios and the explicitly
  unavailable revenue metrics;
- the window dataset (``metrics.windows.snapshot``): the pinned supply
  boundary stocks, exact net supply changes, conservative gross lower
  bounds, the bound ratios (the issuance ratio as an upper bound), window
  USD estimates, window fee ratios and the gated fee-funded buybacks.

Every emitted document is parsed back through the strict NI-028 manifest
parser before it is returned, so an emission that violates the staging
contract fails here rather than at stage time. Inputs are declared as file
bindings so staging pins the exact consumed bytes; the same inputs always
produce byte-identical manifests (reproducibility).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Callable

from near_api.datasets.canonical import decimal_string
from near_api.datasets.manifest import (
    DATASET_KEY_PATTERN,
    ManifestFormatError,
    parse_manifest_document,
)
from near_api.metrics import registry as metric_registry
from near_api.metrics.compute import (
    MetricComputationError,
    formula_burns_lower_bound_near_v1,
    formula_conversion_count_v1,
    formula_effective_gross_fee_bps_v1,
    formula_estimated_purchase_usd_v1,
    formula_fee_funded_buybacks_near_v1,
    formula_issuance_lower_bound_near_v1,
    formula_near_price_usd_v1,
    formula_net_supply_change_near_v1,
    formula_observed_near_purchases_v1,
    formula_protocol_capture_rate_v1,
    formula_protocol_revenue_usd_v1,
    formula_provider_gross_fees_usd_v1,
    formula_provider_intents_volume_usd_v1,
    formula_purchases_to_issuance_upper_pct_v1,
    formula_purchases_to_net_supply_pct_v1,
    formula_treasury_balance_near_v1,
    formula_treasury_payout_count_v1,
    formula_treasury_payouts_near_v1,
    formula_treasury_payouts_near_v2,
    formula_total_supply_near_v1,
    payout_aggregate,
    purchases_by_day,
    window_period,
)
from near_api.metrics.events import MATCHER_VERSION, amount_string
from near_api.metrics.inputs import MetricInputs

FLOWS_DATASET_MEMBERS: tuple[tuple[str, int], ...] = (
    ("observed_near_purchases", 1), ("conversion_count", 1),
    ("treasury_payouts_near", 1), ("treasury_payouts_near", 2),
    ("treasury_payout_count", 1), ("near_price_usd", 1), ("estimated_purchase_usd", 1),
    ("provider_intents_volume_usd", 1), ("provider_gross_fees_usd", 1),
    ("effective_gross_fee_bps", 1),
    ("protocol_revenue_usd", 1), ("protocol_capture_rate", 1),
)
WINDOWS_DATASET_MEMBERS: tuple[tuple[str, int], ...] = (
    ("total_supply_near", 1), ("net_supply_change_near", 1),
    ("issuance_lower_bound_near", 1),
    ("burns_lower_bound_near", 1), ("purchases_to_net_supply_pct", 1),
    ("purchases_to_issuance_upper_pct", 1),
    ("effective_gross_fee_bps", 1), ("estimated_purchase_usd", 1),
    ("fee_funded_buybacks_near", 1),
    ("treasury_balance_near", 1),
)

# Dataset members are (metric_id, version) pairs resolved against exact
# registered definition versions: an emitted manifest names the definition
# versions its formulas actually emit, never "whatever is latest". NI-071
# adds the v2 per-recipient payout emission alongside the v1 aggregate, so a
# rebuilt dataset carries both sides of the reconciliation identity.
FORMULAS: dict[tuple[str, int], Callable] = {
    ("observed_near_purchases", 1): formula_observed_near_purchases_v1,
    ("conversion_count", 1): formula_conversion_count_v1,
    ("treasury_payouts_near", 1): formula_treasury_payouts_near_v1,
    ("treasury_payouts_near", 2): formula_treasury_payouts_near_v2,
    ("treasury_payout_count", 1): formula_treasury_payout_count_v1,
    ("near_price_usd", 1): formula_near_price_usd_v1,
    ("estimated_purchase_usd", 1): formula_estimated_purchase_usd_v1,
    ("provider_intents_volume_usd", 1): formula_provider_intents_volume_usd_v1,
    ("provider_gross_fees_usd", 1): formula_provider_gross_fees_usd_v1,
    ("effective_gross_fee_bps", 1): formula_effective_gross_fee_bps_v1,
    ("total_supply_near", 1): formula_total_supply_near_v1,
    ("net_supply_change_near", 1): formula_net_supply_change_near_v1,
    ("issuance_lower_bound_near", 1): formula_issuance_lower_bound_near_v1,
    ("burns_lower_bound_near", 1): formula_burns_lower_bound_near_v1,
    ("purchases_to_net_supply_pct", 1): formula_purchases_to_net_supply_pct_v1,
    ("purchases_to_issuance_upper_pct", 1): formula_purchases_to_issuance_upper_pct_v1,
    ("treasury_balance_near", 1): formula_treasury_balance_near_v1,
    ("protocol_revenue_usd", 1): formula_protocol_revenue_usd_v1,
    ("protocol_capture_rate", 1): formula_protocol_capture_rate_v1,
    ("fee_funded_buybacks_near", 1): formula_fee_funded_buybacks_near_v1,
}

DATASET_PERIOD_SHAPES = {
    "metrics.flows.daily": "daily",
    "metrics.windows.snapshot": "windows",
}


@dataclass(frozen=True)
class ManifestInputSpec:
    """One file binding declared in the emitted manifest (full lineage)."""

    name: str
    path: Path
    role: str
    source_id: str | None = None
    license_status: str = "unverified"


@dataclass(frozen=True)
class DatasetSpec:
    """Operator-authored dataset identity for one emission run."""

    pipeline_version: str
    quality: dict = field(default_factory=dict)
    code_commit: str | None = None
    config_hash: str | None = None
    dependency_lock_hash: str | None = None
    source_as_of: dt.datetime | None = None
    retrieved_at: dt.datetime | None = None

    def __post_init__(self):
        if not self.pipeline_version:
            raise MetricComputationError("pipeline_version is required")


def windows_dataset_span(inputs: MetricInputs) -> tuple[dt.date, dt.date]:
    """The half-open window covering every window-dataset observation."""
    candidates: list[dt.date] = [inputs.window_start, inputs.window_end_exclusive]
    for boundary in inputs.supply_boundaries:
        candidates.extend([boundary.date, boundary.date + dt.timedelta(days=1)])
    for supply_window in inputs.supply_windows:
        candidates.extend([supply_window.start, supply_window.end_exclusive])
    if inputs.treasury_balance is not None:
        day = inputs.treasury_balance.as_of.date()
        candidates.extend([day, day + dt.timedelta(days=1)])
    return min(candidates), max(candidates)


def _window_summary_quality(inputs: MetricInputs) -> dict:
    """Aggregate-level quality facts recorded on every emission run."""
    purchases = purchases_by_day(inputs)
    payouts = payout_aggregate(inputs)
    summary = {
        "window": {"start": inputs.window_start.isoformat(),
                   "end_exclusive": inputs.window_end_exclusive.isoformat()},
        "observed_purchases_total_near": amount_string(purchases.total),
        "observed_purchase_events": purchases.total_events,
        "matched_payout_total_near": amount_string(payouts.total),
        "matched_payout_count": payouts.total_count,
        "matcher_version": MATCHER_VERSION,
        "excluded_internal_hops_near": amount_string(payouts.internal_hop_total),
        "excluded_other_senders_near": amount_string(payouts.other_sender_total),
    }
    totals = [window for window in inputs.supply_windows if window.is_total]
    if totals:
        window = totals[0]
        summary["supply_total_reference"] = {
            "start": window.start.isoformat(),
            "end_exclusive": window.end_exclusive.isoformat(),
            "issuance_lower_bound_near": decimal_string(window.positive_supply_changes_near
                                                        + window.verified_simultaneous_burn_near
                                                        - Decimal("0.01")),
            "burn_lower_bound_near": decimal_string(window.negative_supply_changes_near
                                                    + window.verified_simultaneous_burn_near
                                                    - Decimal("0.01")),
            "note": "the full-span conservative bounds are range references in quality "
                    "metadata; only the atomic analysis windows are observations",
        }
    return summary


def build_manifest(inputs: MetricInputs, *, dataset_key: str,
                   dataset_spec: DatasetSpec,
                   manifest_inputs: tuple[ManifestInputSpec, ...]) -> dict:
    """Emit one complete prepared-manifest document (strict-parser verified)."""
    if not DATASET_KEY_PATTERN.match(dataset_key):
        raise MetricComputationError(f"invalid dataset key {dataset_key!r}")
    shape = DATASET_PERIOD_SHAPES.get(dataset_key)
    if shape is None:
        raise MetricComputationError(f"unknown dataset key {dataset_key!r}")
    if dataset_key == "metrics.flows.daily":
        members = FLOWS_DATASET_MEMBERS
        window_start, window_end = inputs.window_start, inputs.window_end_exclusive
    else:
        members = WINDOWS_DATASET_MEMBERS
        window_start, window_end = windows_dataset_span(inputs)
    observations: list[dict] = []
    for member_id, member_version in members:
        formula = FORMULAS.get((member_id, member_version))
        if formula is None:
            raise MetricComputationError(
                f"metric {member_id} v{member_version} has no registered formula; "
                "refusing to emit it")
        observations.extend(formula(inputs, shape=shape))
    quality = dict(dataset_spec.quality)
    quality.setdefault("emitter", "near_api.metrics (NI-029)")
    quality.setdefault("definitions", {"registry_version": 1,
                                       "member_count": len(members)})
    if dataset_key == "metrics.windows.snapshot":
        quality.setdefault("window_aggregates", _window_summary_quality(inputs))
    document = {
        "schema_version": 1,
        "dataset_key": dataset_key,
        "frequency": "daily" if dataset_key == "metrics.flows.daily" else "snapshot",
        "window": {"start": window_start.isoformat(), "end_exclusive": window_end.isoformat()},
        "pipeline_version": dataset_spec.pipeline_version,
        "code_commit": dataset_spec.code_commit,
        "config_hash": dataset_spec.config_hash,
        "dependency_lock_hash": dataset_spec.dependency_lock_hash,
        "source_as_of": (dataset_spec.source_as_of.isoformat()
                         if dataset_spec.source_as_of else None),
        "retrieved_at": (dataset_spec.retrieved_at.isoformat()
                         if dataset_spec.retrieved_at else None),
        "quality": quality,
        "member_metrics": [str(metric_registry.definition_by_metric_id_version(
                                   member_id, member_version).id)
                           for member_id, member_version in members],
        "inputs": [{"kind": "file", "path": str(item.path), "role": item.role,
                    "source_id": item.source_id, "query_hash": None,
                    "license_status": item.license_status}
                   for item in manifest_inputs],
        "observations": observations,
    }
    # Parse back through the strict NI-028 manifest parser: an emission that
    # violates the staging contract fails here, never at stage time.
    try:
        parse_manifest_document(document, context=f"emitted {dataset_key}")
    except ManifestFormatError as error:
        raise MetricComputationError(f"emitted manifest for {dataset_key} is invalid: "
                                     f"{error}") from None
    return document


def build_all_manifests(inputs: MetricInputs, *, dataset_spec: DatasetSpec,
                        manifest_inputs: tuple[ManifestInputSpec, ...]) -> dict[str, dict]:
    """Emit both dataset manifests for one computation run."""
    return {
        "metrics.flows.daily": build_manifest(
            inputs, dataset_key="metrics.flows.daily", dataset_spec=dataset_spec,
            manifest_inputs=manifest_inputs),
        "metrics.windows.snapshot": build_manifest(
            inputs, dataset_key="metrics.windows.snapshot", dataset_spec=dataset_spec,
            manifest_inputs=manifest_inputs),
    }
