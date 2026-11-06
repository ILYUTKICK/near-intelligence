"""NI-051 model dataset readiness gate (offline research code).

The gate decides which empirical question is ADMISSIBLE before any fitting
happens (fitting is NI-052). It never fits, never invents a coefficient and
never substitutes a metric: the preferred dependent variable — an
independently reconciled daily ``protocol_revenue_usd`` — does not exist in
the saved archive (OQ-01), so the gate either admits one explicitly named
proxy specification with recorded limits, or reports that no model is
admissible with reproducible reason codes.

Hard rules encoded here (docs/ECONOMETRIC_METHODOLOGY.md, docs/MVP_SCOPE.md):

- No gross-fee/payout proxy passes as protocol revenue. A specification
  whose family is not ``true_revenue`` but whose declared target is
  protocol revenue is always REJECTED
  (``PROXY_CANNOT_PASS_AS_PROTOCOL_REVENUE``).
- The registered gated metric ``protocol_revenue_usd`` (availability G) has
  zero observations by design; a true-revenue specification over the
  current archive is NOT_READY with the OQ-01 reason, never fitted around.
- Lower-bound issuance/burn series are window aggregates with a partially
  audited mint-header set; they are never exact daily outcomes and any
  specification built on them is REJECTED.
- Missing is never zero: gaps are reported per calendar day with reasons,
  differences are formed only between calendar-adjacent complete days, and
  genuine zeros exclude a strict-log specification instead of being
  epsiloned away.
- Project sample gates: at least 60 complete daily observations, at least
  10 observations per estimated parameter (including intercept), at most 3
  substantive slopes. A window shorter than the minimum (for example the
  3-day provenance attribution cohort or the 7-day reconciliation week) is
  rejected for daily long-run inference.

The gate reads the research archive strictly through the NI-029 loaders
(``near_api.metrics.loaders`` — import only, no duplication and no
modification), builds one calendar-aligned prepared table (30-day atomic
supply windows plus the 90-day period keep their saved shapes), profiles
every model series (missing/zero/negative days, adjacency, bound status,
source disagreement, fee-rate regime) and evaluates every registered
specification config. The same inputs always produce a byte-identical
report: every number is an exact Decimal rendered through
``decimal_string``, there are no wall-clock timestamps, and the input
files are pinned by SHA-256.

Boundaries: the archive is opened READ-ONLY; reports are written only to
the operator-provided output directory (never inside ``research/``); no
network call and no database access happens anywhere. Persistence of fit
runs in the database belongs to NI-052/NI-054, not to this gate.

CLI::

    uv run --project apps/api python research/models/readiness.py \
        --archive-root /path/to/research \
        --configs-dir research/models/configs \
        --out-dir research/models/reports

Exit codes: 0 success; 4 contract/policy failure; 2 usage.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from near_api.datasets.canonical import decimal_string
from near_api.metrics import registry as metric_registry
from near_api.metrics.compute import (
    PROVIDER_SOURCES,
    SUPPLY_FLOAT_TOLERANCE_NEAR,
    TREASURY_ACCOUNTS,
    MetricComputationError,
    effective_fee_bps,
    near_amount,
)
from near_api.metrics.events import (
    COMPUTE_CONTEXT,
    aggregate_purchases,
    match_payouts,
)
from near_api.metrics.loaders import (
    load_daily_flows,
    load_longitudinal_flows,
    load_supply_summary,
    load_treasury_summary,
)

EXIT_OK = 0
EXIT_CONTRACT = 4
EXIT_USAGE = 2

GATE_VERSION = 1
REPORT_TYPE = "model_dataset_readiness"

# Strict-log specifications require strictly positive values on both sides;
# anything else is a predeclared level/scaled decision for NI-052, never an
# epsilon added here.
BASELINE_DIFFERENCE_LOG = "difference_log"
BASELINE_LEVEL = "level"
BASELINES = (BASELINE_DIFFERENCE_LOG, BASELINE_LEVEL)

# Family constants: the admissibility class of a specification.
FAMILY_TRUE_REVENUE = "true_revenue"
FAMILY_PROXY = "proxy"
FAMILY_COHORT = "cohort"
FAMILY_SUPPLY_BOUND = "supply_bound"
FAMILIES = (FAMILY_TRUE_REVENUE, FAMILY_PROXY, FAMILY_COHORT, FAMILY_SUPPLY_BOUND)

# Registry metric whose declared target is protocol revenue.
PROTOCOL_REVENUE_METRIC = "protocol_revenue_usd"

# Verdicts.
VERDICT_READY = "READY"
VERDICT_READY_WITH_LIMITS = "READY_WITH_LIMITS"
VERDICT_NOT_READY = "NOT_READY"
VERDICT_REJECTED = "REJECTED"

SEVERITY_REJECTING = "rejecting"
SEVERITY_LIMIT = "limit"
SEVERITY_INFORMATIONAL = "informational"

# Series dimension registry: which series exist, what their dimension slot
# is and which values it may take. This is the typed bridge between spec
# configs and the prepared table; unknown metric/dimension combinations are
# contract errors at spec-load time.
DIMENSION_SOURCE = "source"
DIMENSION_PRICE_BASIS = "price_basis"
SERIES_REGISTRY = {
    "protocol_revenue_usd": None,
    "provider_intents_volume_usd": DIMENSION_SOURCE,
    "provider_gross_fees_usd": DIMENSION_SOURCE,
    "effective_gross_fee_bps": DIMENSION_SOURCE,
    "near_price_usd": DIMENSION_PRICE_BASIS,
    "estimated_purchase_usd": DIMENSION_PRICE_BASIS,
    "observed_near_purchases": None,
    "conversion_count": None,
    "treasury_payouts_near": None,
    "treasury_payout_count": None,
    # Window/snapshot metrics: the prepared table has no daily value for them
    # by construction; the profile shows them missing on every calendar day
    # and any daily-frequency dependent variable over them is rejected.
    "total_supply_near": None,
    "net_supply_change_near": None,
    "issuance_lower_bound_near": None,
    "burns_lower_bound_near": None,
}
PRICE_BASES = ("start", "end")

REASON_CATALOG = {
    "PROTOCOL_REVENUE_NOT_ESTABLISHED_OQ01": (
        SEVERITY_REJECTING,
        "No verified daily economically attributable protocol revenue ledger exists "
        "(OQ-01); the preferred dependent series cannot be observed in the archive and "
        "is not approximated by fees, payouts or any other series."),
    "GATED_METRIC_NO_OBSERVATIONS": (
        SEVERITY_REJECTING,
        "The metric is registry-gated (availability G): every observation is null with "
        "a reason; missing is never zero and the gate never fabricates a value."),
    "PROXY_CANNOT_PASS_AS_PROTOCOL_REVENUE": (
        SEVERITY_REJECTING,
        "A specification that is not the registered true-revenue specification may "
        "never declare protocol revenue as its target or be published under that "
        "label; the mislabeling attempt is rejected by construction."),
    "LOWER_BOUND_SERIES_NOT_EXACT_OUTCOME": (
        SEVERITY_REJECTING,
        "The series is a conservative lower bound, not an exact daily outcome; bounds "
        "never serve as regression outcomes and are never inserted into exact "
        "accounting identities."),
    "WINDOW_AGGREGATE_NOT_DAILY": (
        SEVERITY_REJECTING,
        "The metric is observed only as boundary-window or snapshot aggregates; it has "
        "no daily observations and cannot feed a daily-frequency specification."),
    "MINT_HEADER_AUDIT_INCOMPLETE": (
        SEVERITY_REJECTING,
        "The mint-header audit behind the supply bounds is partial; the unverified "
        "simultaneous offset is unknown and never assumed zero."),
    "ZERO_VALUES_EXCLUDE_LOG_SPEC": (
        SEVERITY_REJECTING,
        "Genuine zero observations exist in a required series; the strict log "
        "specification requires strictly positive values and zeros are never removed "
        "by an arbitrary epsilon. A level/scaled alternative must be predeclared "
        "first, not chosen after seeing the sample."),
    "NEGATIVE_VALUES_EXCLUDE_LOG_SPEC": (
        SEVERITY_REJECTING,
        "Negative values exist in a required series; a strict log specification "
        "requires strictly positive values."),
    "INSUFFICIENT_COMPLETE_OBSERVATIONS": (
        SEVERITY_REJECTING,
        "Complete daily observations are below the project gate minimum."),
    "INSUFFICIENT_OBSERVATIONS_PER_PARAMETER": (
        SEVERITY_REJECTING,
        "Complete daily observations are below the required count per estimated "
        "parameter (including intercept)."),
    "TOO_MANY_SUBSTANTIVE_SLOPES": (
        SEVERITY_REJECTING,
        "The specification declares more substantive slopes than the project maximum "
        "for a first specification."),
    "SHORT_ATTRIBUTION_WINDOW": (
        SEVERITY_REJECTING,
        "The declared sample window is shorter than the minimum inferential sample; "
        "it is rejected for daily long-run inference. Short attribution cohorts stay "
        "descriptive evidence."),
    "SPEC_WINDOW_MISMATCH": (
        SEVERITY_REJECTING,
        "The specification declares a sample window different from the gate window; "
        "the gate evaluates one fixed calendar-aligned window."),
    "NONADJACENT_DAYS_FOR_DIFFERENCING": (
        SEVERITY_INFORMATIONAL,
        "Calendar gaps exist; differences are formed only between calendar-adjacent "
        "complete days and incomplete adjacent pairs are dropped, never differenced "
        "across as if contiguous."),
    "VERIFIED_ZERO_DAYS_PRESENT": (
        SEVERITY_INFORMATIONAL,
        "Extract-covered days without qualifying records are proven zeros (coverage "
        "rows present), not missing data; they count as observations."),
    "SOURCE_DISAGREEMENT_UNRESOLVED": (
        SEVERITY_INFORMATIONAL,
        "The parallel provider sources disagree; they are never summed, cross-source "
        "agreement is not independent confirmation (shared Dune lineage), and the "
        "reconciliation stays unresolved (OQ-11)."),
    "MECHANICAL_FEE_VOLUME_RELATIONSHIP": (
        SEVERITY_LIMIT,
        "Provider gross fees are constructed from reported volume through an effective "
        "fee rate; a fee-on-volume association largely restates that construction and "
        "must be displayed before any coefficient interpretation. It is not demand "
        "elasticity, not sustainable revenue and not token value."),
    "PROXY_NOT_PROTOCOL_REVENUE": (
        SEVERITY_LIMIT,
        "The fitted object is the explicitly named proxy only; it must never be "
        "labeled protocol revenue, and H1/H4 stay unresolved."),
    "OQ02_JUDGING_ACCEPTANCE_RISK": (
        SEVERITY_LIMIT,
        "External acceptance of a transparent reproducible proxy association while "
        "H1/H4 remain unresolved is an open judging risk (OQ-02)."),
    "SINGLE_PROVIDER_LINEAGE_NOT_INDEPENDENT": (
        SEVERITY_LIMIT,
        "All model variables come from one provider lineage; their association is not "
        "independent confirmation of anything."),
    "COHORT_NOT_MARKET_DEMAND": (
        SEVERITY_LIMIT,
        "The observed purchases cohort covers treasury-linked collector accounts "
        "only; it is not whole-market demand and cannot estimate protocol revenue."),
    "PAYOUTS_ARE_CASH_FLOWS_NOT_REVENUE": (
        SEVERITY_LIMIT,
        "Treasury payouts are successful cash transfers out of the intents contract, "
        "not accrual revenue, not profit and not permanently removed supply."),
    "SOURCE_REVISIONS_POSSIBLE": (
        SEVERITY_LIMIT,
        "Provider-reported series are revisable; the saved snapshot is not declared "
        "final and a revision is a new dataset version, never an overwrite."),
    "SHORT_SAMPLE_NO_LONG_RUN_CLAIM": (
        SEVERITY_LIMIT,
        "The window cannot establish a long-term stable mechanism; inference stays "
        "short-run and descriptive regardless of fit quality."),
    "NO_CAUSAL_IDENTIFICATION": (
        SEVERITY_LIMIT,
        "Observational association only: endogeneity, unobserved incentives, common "
        "market trends and provider construction remain limitations even with robust "
        "standard errors."),
}

LIMITS_BY_FAMILY = {
    FAMILY_PROXY: ("MECHANICAL_FEE_VOLUME_RELATIONSHIP", "PROXY_NOT_PROTOCOL_REVENUE",
                   "OQ02_JUDGING_ACCEPTANCE_RISK"),
    FAMILY_COHORT: ("COHORT_NOT_MARKET_DEMAND", "PROXY_NOT_PROTOCOL_REVENUE",
                    "OQ02_JUDGING_ACCEPTANCE_RISK"),
}

LIMITS_BY_METRIC = {
    "treasury_payouts_near": ("PAYOUTS_ARE_CASH_FLOWS_NOT_REVENUE",),
}

# Open questions recorded with the gate decision (docs/OPEN_QUESTIONS.md).
OQ_REGISTER = (
    {"id": "OQ-01",
     "question": "Daily economically attributable revenue/allocation ledger availability",
     "effect": "protocol_revenue_usd stays registry-gated with zero observations; "
               "only an explicitly named proxy specification can be admitted, and it "
               "is never labeled protocol revenue"},
    {"id": "OQ-02",
     "question": "Will judges accept a transparent reproducible proxy association",
     "effect": "the selected proxy verdict is READY_WITH_LIMITS, never READY; the "
               "judging risk is recorded with the decision and H1/H4 stay unresolved"},
    {"id": "OQ-08",
     "question": "Exact historical mapping of affiliate recipients, collectors and "
                 "business revenue channels",
     "effect": "pooled funds are not attributable to specific payouts; the narrow "
               "provenance inventory equivalent (27 Oct-2 Nov) stays a bounded "
               "research artifact and never a daily revenue series"},
    {"id": "OQ-10",
     "question": "Complete gross issuance/burn series availability",
     "effect": "issuance/burn stay conservative lower bounds over partially audited "
               "windows; they are rejected as exact daily outcomes"},
    {"id": "OQ-11",
     "question": "Provider revenue definition versus intended economic entitlement",
     "effect": "provider series stay source-qualified and parallel; disagreement and "
               "shared lineage are recorded, cross-source sums stay forbidden"},
)

KNOWN_CAVEATS = (
    {"cohort": "near-weekly",
     "note": "Five API-provided intent hashes (cases S01/S03/S07/S16/S17, 20 Oct-3 Nov "
             "scope) were not found in the indexed intents.near logs; the source "
             "discrepancy is documented and unresolved. Saved aggregates are used as "
             "saved; no silent substitution."},
    {"cohort": "near-supply",
     "note": "291 of 297 positive-change mint headers are unaudited; issuance/burn "
             "stay conservative lower bounds over 30-day windows and the 90-day "
             "period, never daily outcomes."},
    {"cohort": "near-provenance",
     "note": "The strict 27 Oct-2 Nov inventory equivalent is a bounded accounting "
             "model over a mixed pool (OQ-08); it is a research artifact with a "
             "multi-day scope and is rejected for daily long-run inference."},
    {"cohort": "near-dollar",
     "note": "SRC-LLAMA and SRC-DASHBOARD share Dune lineage; the parallel series are "
             "kept source-qualified, never summed, and their disagreement is reported."},
)


class ReadinessGateError(ValueError):
    """Inputs, policy or spec configuration make an honest gate impossible."""


# --------------------------------------------------------------------------- #
# Policy and specification loading (typed, strict)
# --------------------------------------------------------------------------- #


def _canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _config_hash(document: dict) -> str:
    return hashlib.sha256(_canonical_json(document).encode("utf-8")).hexdigest()


def _load_json(path: Path, *, context: str) -> dict:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ReadinessGateError(f"cannot read {context} {path}: {error}") from None
    except json.JSONDecodeError as error:
        raise ReadinessGateError(f"{context} {path} is not valid JSON: {error}") from None
    if not isinstance(document, dict):
        raise ReadinessGateError(f"{context} {path} must be a JSON object")
    return document


def _reject_unknown_fields(document: dict, allowed: set, *, context: str) -> None:
    unknown = sorted(set(document) - allowed)
    if unknown:
        raise ReadinessGateError(f"{context}: unknown fields {unknown}")


@dataclass(frozen=True)
class GatePolicy:
    """Fixed project gate numbers and the archive input map."""

    policy_id: str
    policy_version: int
    window_start: dt.date
    window_end_exclusive: dt.date
    min_complete_daily_observations: int
    min_observations_per_parameter: int
    max_substantive_slopes: int
    intercept_required: bool
    long_run_min_days: int
    fee_bps_regime_tolerance_pct: Decimal
    spec_evaluation_order: tuple
    inputs: dict  # name -> {"cohort": str, "path": str}
    config_hash: str

    @property
    def window_days(self) -> int:
        return (self.window_end_exclusive - self.window_start).days

    def as_report(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "window": {"start": self.window_start.isoformat(),
                       "end_exclusive": self.window_end_exclusive.isoformat(),
                       "days": self.window_days},
            "min_complete_daily_observations": self.min_complete_daily_observations,
            "min_observations_per_parameter": self.min_observations_per_parameter,
            "max_substantive_slopes": self.max_substantive_slopes,
            "intercept_required": self.intercept_required,
            "long_run_min_days": self.long_run_min_days,
            "fee_bps_regime_tolerance_pct": decimal_string(self.fee_bps_regime_tolerance_pct),
            "spec_evaluation_order": list(self.spec_evaluation_order),
            "config_hash": self.config_hash,
        }


def load_policy(path: Path) -> GatePolicy:
    document = _load_json(path, context="gate policy")
    _reject_unknown_fields(document, {
        "policy_id", "policy_version", "window", "min_complete_daily_observations",
        "min_observations_per_parameter", "max_substantive_slopes", "intercept_required",
        "long_run_min_days", "fee_bps_regime_tolerance_pct", "spec_evaluation_order",
        "inputs",
    }, context=f"gate policy {path.name}")
    config_hash = _config_hash(document)
    for key in ("policy_id", "policy_version", "window", "min_complete_daily_observations",
                "min_observations_per_parameter", "max_substantive_slopes",
                "intercept_required", "long_run_min_days", "fee_bps_regime_tolerance_pct",
                "spec_evaluation_order", "inputs"):
        if key not in document:
            raise ReadinessGateError(f"gate policy {path.name}: missing required key {key!r}")
    window = document["window"]
    if not isinstance(window, dict) or set(window) != {"start", "end_exclusive"}:
        raise ReadinessGateError(f"gate policy {path.name}: window must be "
                                 "{start, end_exclusive}")
    try:
        start = dt.date.fromisoformat(window["start"])
        end = dt.date.fromisoformat(window["end_exclusive"])
    except (TypeError, ValueError):
        raise ReadinessGateError(f"gate policy {path.name}: window dates must be ISO") from None
    if end <= start:
        raise ReadinessGateError(f"gate policy {path.name}: window must be non-empty")
    tolerance = document["fee_bps_regime_tolerance_pct"]
    if not isinstance(tolerance, str):
        raise ReadinessGateError(f"gate policy {path.name}: fee_bps_regime_tolerance_pct "
                                 "must be a decimal string")
    try:
        tolerance_decimal = Decimal(tolerance)
    except Exception:
        raise ReadinessGateError(f"gate policy {path.name}: fee_bps_regime_tolerance_pct "
                                 f"{tolerance!r} is not a decimal string") from None
    inputs = document["inputs"]
    if not isinstance(inputs, dict) or not inputs:
        raise ReadinessGateError(f"gate policy {path.name}: inputs must be a non-empty object")
    for name, binding in inputs.items():
        if not isinstance(binding, dict) or set(binding) != {"cohort", "path"}:
            raise ReadinessGateError(f"gate policy {path.name}: input {name!r} must be "
                                     "{cohort, path}")
    order = document["spec_evaluation_order"]
    if not isinstance(order, list) or not all(isinstance(item, str) for item in order):
        raise ReadinessGateError(f"gate policy {path.name}: spec_evaluation_order must "
                                 "be a list of spec ids")
    for key in ("min_complete_daily_observations", "min_observations_per_parameter",
                "max_substantive_slopes", "long_run_min_days"):
        if not isinstance(document[key], int) or isinstance(document[key], bool) \
                or document[key] <= 0:
            raise ReadinessGateError(f"gate policy {path.name}: {key} must be a positive "
                                     "integer")
    if not isinstance(document["intercept_required"], bool):
        raise ReadinessGateError(f"gate policy {path.name}: intercept_required must be "
                                 "boolean")
    return GatePolicy(
        policy_id=str(document["policy_id"]),
        policy_version=int(document["policy_version"]),
        window_start=start,
        window_end_exclusive=end,
        min_complete_daily_observations=document["min_complete_daily_observations"],
        min_observations_per_parameter=document["min_observations_per_parameter"],
        max_substantive_slopes=document["max_substantive_slopes"],
        intercept_required=document["intercept_required"],
        long_run_min_days=document["long_run_min_days"],
        fee_bps_regime_tolerance_pct=tolerance_decimal,
        spec_evaluation_order=tuple(order),
        inputs={str(name): {"cohort": str(binding["cohort"]), "path": str(binding["path"])}
                for name, binding in inputs.items()},
        config_hash=config_hash,
    )


@dataclass(frozen=True)
class VariableSpec:
    """One model variable bound to a registered metric and dimension."""

    metric_id: str
    dimension: str | None
    role: str

    @property
    def series_key(self) -> str:
        return f"{self.metric_id}|{self.dimension or ''}"


@dataclass(frozen=True)
class ModelSpec:
    """A typed, preregistered model specification (never fitted here)."""

    spec_id: str
    spec_version: int
    family: str
    declared_target: str
    frequency: str
    dependent: VariableSpec
    explanatory: tuple[VariableSpec, ...]
    baseline: str
    substantive_slopes: int
    intercept: bool
    prohibited_labels: tuple[str, ...]
    limitation_notes: tuple[str, ...]
    sample_start: dt.date
    sample_end_exclusive: dt.date
    config_hash: str

    @property
    def required_variables(self) -> tuple[VariableSpec, ...]:
        return (self.dependent,) + self.explanatory

    @property
    def parameters_count(self) -> int:
        return self.substantive_slopes + (1 if self.intercept else 0)

    def as_report(self) -> dict:
        return {
            "spec_id": self.spec_id,
            "spec_version": self.spec_version,
            "family": self.family,
            "declared_target": self.declared_target,
            "frequency": self.frequency,
            "dependent_variable": {"metric_id": self.dependent.metric_id,
                                   "dimension": self.dependent.dimension},
            "explanatory_variables": [{"metric_id": variable.metric_id,
                                       "dimension": variable.dimension,
                                       "role": variable.role}
                                      for variable in self.explanatory],
            "baseline": self.baseline,
            "substantive_slopes": self.substantive_slopes,
            "intercept": self.intercept,
            "config_hash": self.config_hash,
        }


def load_spec(path: Path, policy: GatePolicy) -> ModelSpec:
    """Load and validate one specification config against the metric registry."""
    document = _load_json(path, context="model spec")
    _reject_unknown_fields(document, {
        "spec_id", "spec_version", "family", "declared_target", "frequency",
        "dependent_variable", "explanatory_variables", "transformations", "parameters",
        "sample_window", "prohibited_labels", "limitation_notes",
    }, context=f"model spec {path.name}")
    config_hash = _config_hash(document)
    context = f"model spec {path.name}"
    for key in ("spec_id", "spec_version", "family", "declared_target", "frequency",
                "dependent_variable", "explanatory_variables", "transformations",
                "parameters", "sample_window"):
        if key not in document:
            raise ReadinessGateError(f"{context}: missing required key {key!r}")
    if document["family"] not in FAMILIES:
        raise ReadinessGateError(f"{context}: unknown family {document['family']!r}")
    if document["frequency"] != "daily":
        raise ReadinessGateError(f"{context}: the gate evaluates daily specifications only")
    transformations = document["transformations"]
    parameters = document["parameters"]
    if not isinstance(transformations, dict) or not isinstance(parameters, dict):
        raise ReadinessGateError(f"{context}: transformations/parameters must be objects")
    _reject_unknown_fields(transformations, {
        "baseline", "strictly_positive_required", "difference_adjacency",
        "float64_conversion",
    }, context=f"{context}.transformations")
    _reject_unknown_fields(parameters, {"substantive_slopes", "intercept", "controls"},
                           context=f"{context}.parameters")
    baseline = transformations.get("baseline")
    if baseline not in BASELINES:
        raise ReadinessGateError(f"{context}: baseline must be one of {BASELINES}")
    slopes = parameters.get("substantive_slopes")
    intercept = parameters.get("intercept")
    if not isinstance(slopes, int) or isinstance(slopes, bool) or slopes < 1:
        raise ReadinessGateError(f"{context}: substantive_slopes must be a positive integer")
    if not isinstance(intercept, bool):
        raise ReadinessGateError(f"{context}: intercept must be boolean")
    if policy.intercept_required and not intercept:
        raise ReadinessGateError(f"{context}: the project gate requires an intercept")
    if slopes > policy.max_substantive_slopes:
        raise ReadinessGateError(f"{context}: {slopes} substantive slopes exceed the "
                                 f"project maximum of {policy.max_substantive_slopes}; "
                                 "reduce the specification instead of loosening the gate")
    if baseline == BASELINE_DIFFERENCE_LOG and not transformations.get(
            "strictly_positive_required"):
        raise ReadinessGateError(f"{context}: the log-difference baseline must declare "
                                 "strictly_positive_required")
    if transformations.get("difference_adjacency") not in (None, "calendar_adjacent_only"):
        raise ReadinessGateError(f"{context}: differences may only use "
                                 "calendar_adjacent_only adjacency")

    def variable(payload, *, kind: str) -> VariableSpec:
        if not isinstance(payload, dict) or set(payload) - {"metric_id", "source", "role"}:
            raise ReadinessGateError(f"{context}: {kind} must be an object with "
                                     "metric_id/source/role keys only")
        metric_id = payload.get("metric_id")
        if not isinstance(metric_id, str) or metric_id not in SERIES_REGISTRY:
            raise ReadinessGateError(f"{context}: {kind} metric {metric_id!r} is not a "
                                     "series the gate can prepare")
        definition = metric_registry.definition_by_metric_id(metric_id)
        dimension = payload.get("source")
        dimension_slot = SERIES_REGISTRY[metric_id]
        if dimension_slot is None:
            if dimension is not None:
                raise ReadinessGateError(f"{context}: {kind} metric {metric_id} takes no "
                                         "source dimension")
        elif dimension_slot == DIMENSION_SOURCE:
            if dimension not in PROVIDER_SOURCES:
                raise ReadinessGateError(f"{context}: {kind} metric {metric_id} requires a "
                                         f"source dimension from {PROVIDER_SOURCES}")
        else:  # price basis
            if dimension not in PRICE_BASES:
                raise ReadinessGateError(f"{context}: {kind} metric {metric_id} requires a "
                                         f"price basis from {PRICE_BASES}")
        if definition.definition["availability"] == "G" and kind != "dependent_variable":
            raise ReadinessGateError(f"{context}: gated metric {metric_id} has no "
                                     "observations and cannot serve as an explanatory "
                                     "variable")
        return VariableSpec(metric_id=metric_id, dimension=dimension,
                            role=str(payload.get("role", kind)))

    dependent = variable(document["dependent_variable"], kind="dependent_variable")
    explanatory_payload = document["explanatory_variables"]
    if not isinstance(explanatory_payload, list):
        raise ReadinessGateError(f"{context}: explanatory_variables must be a list")
    explanatory = tuple(variable(item, kind=f"explanatory_variables[{index}]")
                        for index, item in enumerate(explanatory_payload))
    sample = document["sample_window"]
    if not isinstance(sample, dict) or set(sample) != {"start", "end_exclusive"}:
        raise ReadinessGateError(f"{context}: sample_window must be {{start, end_exclusive}}")
    try:
        sample_start = dt.date.fromisoformat(sample["start"])
        sample_end = dt.date.fromisoformat(sample["end_exclusive"])
    except (TypeError, ValueError):
        raise ReadinessGateError(f"{context}: sample_window dates must be ISO") from None
    prohibited = document.get("prohibited_labels", [])
    if not isinstance(prohibited, list) or not all(isinstance(item, str) for item in prohibited):
        raise ReadinessGateError(f"{context}: prohibited_labels must be a list of strings")
    notes = document.get("limitation_notes", [])
    if not isinstance(notes, list) or not all(isinstance(item, str) for item in notes):
        raise ReadinessGateError(f"{context}: limitation_notes must be a list of strings")
    return ModelSpec(
        spec_id=str(document["spec_id"]),
        spec_version=int(document["spec_version"]),
        family=str(document["family"]),
        declared_target=str(document["declared_target"]),
        frequency=str(document["frequency"]),
        dependent=dependent,
        explanatory=explanatory,
        baseline=baseline,
        substantive_slopes=slopes,
        intercept=intercept,
        prohibited_labels=tuple(prohibited),
        limitation_notes=tuple(notes),
        sample_start=sample_start,
        sample_end_exclusive=sample_end,
        config_hash=config_hash,
    )


# --------------------------------------------------------------------------- #
# Archive loading and the calendar-aligned prepared table
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class LoadedArchive:
    """The saved aggregates loaded read-only through the NI-029 loaders."""

    window_start: dt.date
    window_end_exclusive: dt.date
    flows: object                    # FlowRecords
    daily_flows: tuple               # tuple[DailyFlowRow, ...]
    supply_boundaries: tuple
    supply_windows: tuple
    mint_headers_verified: int
    mint_headers_target: int
    treasury: object | None
    files: tuple  # {"cohort", "path", "bytes", "sha256"}


def load_archive(archive_root: Path, policy: GatePolicy) -> LoadedArchive:
    """Load the declared archive inputs strictly; the archive is never written."""
    bindings = policy.inputs
    for required in ("flows", "daily_flows", "supply"):
        if required not in bindings:
            raise ReadinessGateError(f"gate policy inputs lack the required {required!r} binding")
    files: list[dict] = []

    def read(name: str) -> Path:
        binding = bindings[name]
        path = (archive_root / binding["path"]).resolve()
        if archive_root.resolve() not in path.parents:
            raise ReadinessGateError(f"input {name!r} escapes the archive root: {path}")
        try:
            data = path.read_bytes()
        except OSError as error:
            raise ReadinessGateError(f"cannot read input {name!r} at {path}: {error}") from None
        files.append({"name": name, "cohort": binding["cohort"],
                      "path": binding["path"], "bytes": len(data),
                      "sha256": hashlib.sha256(data).hexdigest()})
        return path

    flows = load_longitudinal_flows(read("flows"))
    daily_flows = load_daily_flows(read("daily_flows"))
    boundaries, windows = load_supply_summary(read("supply"))
    treasury = None
    if "treasury" in bindings:
        treasury = load_treasury_summary(read("treasury"))
    # The saved summary audits the atomic windows; the total window repeats the
    # same audited headers, so only atomic windows are summed (no double count).
    verified = sum(window.mint_headers_verified for window in windows if not window.is_total)
    target = max((window.mint_headers_target for window in windows), default=0)
    return LoadedArchive(window_start=policy.window_start,
                         window_end_exclusive=policy.window_end_exclusive,
                         flows=flows, daily_flows=daily_flows,
                         supply_boundaries=boundaries, supply_windows=windows,
                         mint_headers_verified=verified, mint_headers_target=target,
                         treasury=treasury, files=tuple(files))


@dataclass(frozen=True)
class PreparedDay:
    """One calendar day with every model column (None means missing, never zero)."""

    date: dt.date
    row_present: bool          # a saved daily row exists for the date
    extract_covered: bool      # the longitudinal extract proves coverage
    price_start: Decimal | None
    price_end: Decimal | None
    provider_volume: dict      # source -> Decimal | None
    provider_fees: dict        # source -> Decimal | None
    purchases_near: Decimal | None   # verified zero on covered eventless days
    buy_events: int | None
    payout_near: Decimal | None      # verified zero on covered eventless days
    payout_count: int | None
    estimated_purchase_usd: dict     # price basis -> Decimal | None
    protocol_revenue_usd: None       # always None with the OQ-01 reason


def build_prepared_table(archive: LoadedArchive) -> dict:
    """Build the calendar-aligned prepared table; no date is ever joined away."""
    window_start, window_end = archive.window_start, archive.window_end_exclusive
    calendar = []
    day = window_start
    while day < window_end:
        calendar.append(day)
        day += dt.timedelta(days=1)

    daily_rows = {row.date: row for row in archive.daily_flows}
    covered = {row.block_date for row in archive.flows.coverage}
    parse_error_days = sorted(row.block_date for row in archive.flows.quality
                              if row.json_parse_errors)
    purchases = aggregate_purchases(archive.flows.conversions, window_start=window_start,
                                    window_end_exclusive=window_end)
    payouts = match_payouts(archive.flows.withdrawals, archive.flows.native_transfers,
                            treasury_accounts=TREASURY_ACCOUNTS, window_start=window_start,
                            window_end_exclusive=window_end)

    days: list[PreparedDay] = []
    for date in calendar:
        row = daily_rows.get(date)
        is_covered = date in covered
        purchase_raw = purchases.by_day.get(date)
        payout_raw = payouts.by_day.get(date)
        if purchase_raw is None and is_covered:
            purchase_raw, purchase_events = Decimal(0), 0
        else:
            purchase_events = purchases.events_by_day.get(date)
        if payout_raw is None and is_covered:
            payout_raw, payout_count = Decimal(0), 0
        else:
            payout_count = payouts.count_by_day.get(date)
        purchases_near = near_amount(purchase_raw) if purchase_raw is not None else None
        payout_near = near_amount(payout_raw) if payout_raw is not None else None
        price_start = row.price_start_utc if row is not None else None
        price_end = row.price_end_utc if row is not None else None
        volume: dict = {}
        fees: dict = {}
        for source in PROVIDER_SOURCES:
            if source == "SRC-LLAMA" and row is not None:
                volume[source], fees[source] = row.volume_usd, row.gross_fees_usd
            elif source == "SRC-DASHBOARD" and row is not None:
                volume[source] = row.dashboard_volume_usd
                fees[source] = row.dashboard_gross_fees_usd
            else:
                volume[source], fees[source] = None, None
        estimated = {}
        for basis, price in (("start", price_start), ("end", price_end)):
            if purchases_near is not None and price is not None:
                estimated[basis] = COMPUTE_CONTEXT.multiply(purchases_near, price)
            else:
                estimated[basis] = None
        days.append(PreparedDay(
            date=date, row_present=row is not None, extract_covered=is_covered,
            price_start=price_start, price_end=price_end, provider_volume=volume,
            provider_fees=fees, purchases_near=purchases_near, buy_events=purchase_events,
            payout_near=payout_near, payout_count=payout_count,
            estimated_purchase_usd=estimated, protocol_revenue_usd=None))

    return {
        "calendar": tuple(calendar),
        "days": tuple(days),
        "daily_rows_present": len(daily_rows),
        "extract_uncovered_days": tuple(date for date in calendar if date not in covered),
        "extract_parse_error_days": tuple(parse_error_days),
        "payout_aggregate": payouts,
        "purchase_aggregate": purchases,
    }


# --------------------------------------------------------------------------- #
# Series extraction and profiling
# --------------------------------------------------------------------------- #


def series_value(day: PreparedDay, variable: VariableSpec) -> Decimal | None:
    """Read one series value from the prepared table (None = missing)."""
    metric_id, dimension = variable.metric_id, variable.dimension
    if metric_id == "protocol_revenue_usd":
        return None
    if metric_id == "provider_intents_volume_usd":
        return day.provider_volume.get(dimension)
    if metric_id == "provider_gross_fees_usd":
        return day.provider_fees.get(dimension)
    if metric_id == "effective_gross_fee_bps":
        volume, fees = day.provider_volume.get(dimension), day.provider_fees.get(dimension)
        if volume is None or fees is None:
            return None
        return effective_fee_bps(volume, fees)
    if metric_id == "near_price_usd":
        return day.price_start if dimension == "start" else day.price_end
    if metric_id == "estimated_purchase_usd":
        return day.estimated_purchase_usd.get(dimension)
    if metric_id == "observed_near_purchases":
        return day.purchases_near
    if metric_id == "conversion_count":
        return None if day.buy_events is None else Decimal(day.buy_events)
    if metric_id == "treasury_payouts_near":
        return day.payout_near
    if metric_id == "treasury_payout_count":
        return None if day.payout_count is None else Decimal(day.payout_count)
    if metric_id in ("total_supply_near", "net_supply_change_near",
                     "issuance_lower_bound_near", "burns_lower_bound_near"):
        # Window/snapshot aggregates have no daily observation by construction.
        return None
    raise ReadinessGateError(f"unmapped series {metric_id!r}")


def series_definition(variable: VariableSpec) -> dict:
    """Registry identity of a series (versioned definitions, never ad-hoc)."""
    definition = metric_registry.definition_by_metric_id(variable.metric_id)
    return {"metric_id": definition.metric_id, "version": definition.version,
            "availability": definition.definition["availability"],
            "frequency": definition.frequency, "source_id": definition.source_id,
            "dimension": variable.dimension, "series_key": variable.series_key}


def profile_series(variable: VariableSpec, table: dict) -> dict:
    """Deterministic data profile of one series over the gate calendar."""
    calendar, days = table["calendar"], table["days"]
    definition = series_definition(variable)
    values = {day.date: series_value(day, variable) for day in days}
    present = [date for date in calendar if values[date] is not None]
    missing = [date for date in calendar if values[date] is None]
    zeros = [date for date in present if values[date] == 0]
    negatives = [date for date in present if values[date] < 0]
    adjacent_pairs = sum(1 for previous, current in zip(present, present[1:])
                         if (current - previous).days == 1)
    gaps = []
    for previous, current in zip(present, present[1:]):
        distance = (current - previous).days
        if distance > 1:
            gaps.append({"after": previous.isoformat(), "before": current.isoformat(),
                         "missing_calendar_days": distance - 1})
    finite_as_float64 = all(_finite_as_float64(values[date]) for date in present)
    minimum = min((values[date] for date in present), default=None)
    maximum = max((values[date] for date in present), default=None)
    return {
        **definition,
        "present_days": len(present),
        "missing_days": [date.isoformat() for date in missing],
        "zero_days": [date.isoformat() for date in zeros],
        "negative_days": [date.isoformat() for date in negatives],
        "calendar_gaps": gaps,
        "adjacent_present_pairs": adjacent_pairs,
        "first_present": present[0].isoformat() if present else None,
        "last_present": present[-1].isoformat() if present else None,
        "min": decimal_string(minimum) if minimum is not None else None,
        "max": decimal_string(maximum) if maximum is not None else None,
        "float64_finite": finite_as_float64,
    }


def supply_windows_profile(archive: LoadedArchive) -> dict:
    """The saved supply windows keep their shape: atomic 30-day windows + total."""
    boundaries = {boundary.date: boundary for boundary in archive.supply_boundaries}

    def window_row(window) -> dict:
        opening, closing = boundaries.get(window.opening_date), boundaries.get(window.closing_date)
        row = {
            "start": window.start.isoformat(),
            "end_exclusive": window.end_exclusive.isoformat(),
            "days": (window.end_exclusive - window.start).days,
            "opening_boundary": {"date": window.opening_date.isoformat(),
                                 "block_height": opening.block_height if opening else None,
                                 "supply_near": decimal_string(opening.supply_near)
                                 if opening else None},
            "closing_boundary": {"date": window.closing_date.isoformat(),
                                 "block_height": closing.block_height if closing else None,
                                 "supply_near": decimal_string(closing.supply_near)
                                 if closing else None},
            "net_supply_change_near": decimal_string(COMPUTE_CONTEXT.subtract(
                closing.supply_near, opening.supply_near)) if opening and closing else None,
            "issuance_lower_bound_near": decimal_string(COMPUTE_CONTEXT.subtract(
                COMPUTE_CONTEXT.add(window.positive_supply_changes_near,
                                    window.verified_simultaneous_burn_near),
                SUPPLY_FLOAT_TOLERANCE_NEAR)),
            "burns_lower_bound_near": decimal_string(COMPUTE_CONTEXT.subtract(
                COMPUTE_CONTEXT.add(window.negative_supply_changes_near,
                                    window.verified_simultaneous_burn_near),
                SUPPLY_FLOAT_TOLERANCE_NEAR)),
            "gross_issuance_and_burn_complete": window.gross_issuance_and_burn_complete,
            "mint_headers_verified": window.mint_headers_verified,
            "mint_headers_target": window.mint_headers_target,
            "bound_kind": "lower",
        }
        return row

    atomic = sorted((window for window in archive.supply_windows if not window.is_total),
                    key=lambda window: window.start)
    total = next((window for window in archive.supply_windows if window.is_total), None)
    return {
        "atomic_windows": [window_row(window) for window in atomic],
        "total_window": window_row(total) if total else None,
        "bound_policy": "conservative lower bounds minus the documented 0.01 NEAR "
                        "FLOAT64 tolerance; the unaudited simultaneous offset is "
                        "unknown and never assumed zero; bounds are never exact daily "
                        "outcomes and never enter exact accounting identities",
        "mint_headers_verified_total": archive.mint_headers_verified,
        "mint_headers_target_total": archive.mint_headers_target,
    }


def source_comparison_profile(table: dict) -> dict:
    """Parallel qualified provider sources: disagreement recorded, never summed."""
    days = table["days"]
    result = {}
    for source_a, source_b in (("SRC-LLAMA", "SRC-DASHBOARD"),):
        for metric_name, column in (("provider_intents_volume_usd", "provider_volume"),
                                    ("provider_gross_fees_usd", "provider_fees")):
            overlapping = 0
            differing = 0
            max_relative = Decimal(0)
            for day in days:
                value_a, value_b = getattr(day, column).get(source_a), getattr(day, column).get(source_b)
                if value_a is None or value_b is None:
                    continue
                overlapping += 1
                if value_a != value_b:
                    differing += 1
                    if value_a != 0:
                        relative = COMPUTE_CONTEXT.divide(abs(value_a - value_b), abs(value_a))
                        max_relative = max(max_relative, relative)
            result[f"{metric_name}|{source_a}-vs-{source_b}"] = {
                "overlapping_days": overlapping,
                "differing_days": differing,
                "max_relative_difference": decimal_string(max_relative),
            }
    result["policy"] = "sources are parallel qualified observations; never summed; " \
                       "agreement would not be independent confirmation (shared Dune " \
                       "lineage); the reconciliation stays open (OQ-11)"
    return result


def fee_rate_profile(table: dict, policy: GatePolicy) -> dict:
    """Descriptive daily fee-rate regime profile (no fitting)."""
    days = table["days"]
    result = {}
    for source in PROVIDER_SOURCES:
        daily_bps = {}
        for day in days:
            volume = day.provider_volume.get(source)
            fees = day.provider_fees.get(source)
            daily_bps[day.date] = (effective_fee_bps(volume, fees)
                                   if volume is not None and fees is not None else None)
        present = {date: value for date, value in daily_bps.items() if value is not None}
        window_volume = sum(
            (day.provider_volume.get(source) for day in days
             if day.provider_volume.get(source) is not None), Decimal(0))
        window_fees = sum(
            (day.provider_fees.get(source) for day in days
             if day.provider_fees.get(source) is not None), Decimal(0))
        window_bps = effective_fee_bps(window_volume, window_fees)
        tolerance = policy.fee_bps_regime_tolerance_pct / Decimal(100)
        flagged = []
        if window_bps is not None and window_bps != 0:
            for date in sorted(present):
                deviation = COMPUTE_CONTEXT.divide(abs(present[date] - window_bps),
                                                   abs(window_bps))
                if deviation > tolerance:
                    flagged.append(date.isoformat())
        result[source] = {
            "days_with_rate": len(present),
            "min_daily_bps": decimal_string(min(present.values())) if present else None,
            "max_daily_bps": decimal_string(max(present.values())) if present else None,
            "window_ratio_of_sums_bps": (decimal_string(window_bps)
                                         if window_bps is not None else None),
            "days_outside_tolerance_of_window_rate": flagged,
            "tolerance_pct": decimal_string(policy.fee_bps_regime_tolerance_pct),
            "note": "descriptive profile only; the effective fee rate shows how fees "
                    "are constructed from volume, which is exactly the mechanical "
                    "relationship any fee-on-volume model restates",
        }
    return result


# --------------------------------------------------------------------------- #
# Specification evaluation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SpecEvaluation:
    spec: ModelSpec
    verdict: str
    reason_codes: tuple  # {"code", "severity", "detail"}
    sample: dict

    def as_report(self) -> dict:
        return {"spec": self.spec.as_report(), "verdict": self.verdict,
                "reason_codes": list(self.reason_codes), "sample": self.sample}


def _code(code: str, detail: str = "") -> dict:
    if code not in REASON_CATALOG:
        raise ReadinessGateError(f"reason code {code!r} is not in the catalog")
    severity = REASON_CATALOG[code][0]
    entry = {"code": code, "severity": severity,
             "detail": detail or REASON_CATALOG[code][1]}
    return entry


def _finite_as_float64(value: Decimal) -> bool:
    """The preparation policy requires explicit finite float64 conversion."""
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _series_missing_reason(day: PreparedDay, variable: VariableSpec) -> str | None:
    if not day.row_present:
        return "calendar_day_absent_from_daily_rows"
    if variable.metric_id == "protocol_revenue_usd":
        return "gated_metric_no_observations_oq01"
    definition = metric_registry.definition_by_metric_id(variable.metric_id)
    if definition.frequency != "daily":
        return "window_aggregate_no_daily_observations"
    if series_value(day, variable) is not None:
        return None
    if variable.metric_id == "estimated_purchase_usd":
        return "missing_price_or_purchases"
    if variable.metric_id == "effective_gross_fee_bps":
        return "missing_or_nonpositive_denominator"
    if not day.extract_covered:
        return "extract_coverage_unproven"
    return "missing_value"


def evaluate_spec(spec: ModelSpec, table: dict, policy: GatePolicy,
                  archive: LoadedArchive) -> SpecEvaluation:
    """Evaluate one specification against the prepared table (no fitting)."""
    codes: list[dict] = []
    calendar = table["calendar"]
    window_days = policy.window_days

    # --- specification-level structural checks ------------------------------
    if spec.sample_start != policy.window_start or spec.sample_end_exclusive != policy.window_end_exclusive:
        codes.append(_code("SPEC_WINDOW_MISMATCH",
                           f"spec declares {spec.sample_start}..{spec.sample_end_exclusive}, "
                           f"the gate window is {policy.window_start}..{policy.window_end_exclusive}"))
    if spec.substantive_slopes > policy.max_substantive_slopes:
        codes.append(_code("TOO_MANY_SUBSTANTIVE_SLOPES",
                           f"{spec.substantive_slopes} substantive slopes exceed the "
                           f"project maximum of {policy.max_substantive_slopes}"))
    if spec.declared_target == "protocol_revenue" and spec.family != FAMILY_TRUE_REVENUE:
        codes.append(_code("PROXY_CANNOT_PASS_AS_PROTOCOL_REVENUE",
                           f"family {spec.family!r} with declared_target "
                           f"{spec.declared_target!r} is rejected by construction"))
    dependent_definition = metric_registry.definition_by_metric_id(spec.dependent.metric_id)
    dependent_availability = dependent_definition.definition["availability"]
    if dependent_definition.frequency != "daily":
        codes.append(_code("WINDOW_AGGREGATE_NOT_DAILY",
                           f"metric {spec.dependent.metric_id} is "
                           f"{dependent_definition.frequency}-frequency; it has no daily "
                           "observations"))
    if spec.family == FAMILY_SUPPLY_BOUND:
        codes.append(_code("LOWER_BOUND_SERIES_NOT_EXACT_OUTCOME",
                           f"dependent {spec.dependent.metric_id} is a conservative bound, "
                           "never an exact daily regression outcome"))
        if archive.mint_headers_verified < archive.mint_headers_target:
            codes.append(_code("MINT_HEADER_AUDIT_INCOMPLETE",
                               f"{archive.mint_headers_verified} of "
                               f"{archive.mint_headers_target} mint headers audited; the "
                               "unverified simultaneous offset is unknown"))
    if dependent_availability == "G":
        codes.append(_code("GATED_METRIC_NO_OBSERVATIONS",
                           f"registry metric {spec.dependent.metric_id} v"
                           f"{dependent_definition.version} is gated; every observation "
                           "is null with a reason"))
        if spec.dependent.metric_id == PROTOCOL_REVENUE_METRIC:
            codes.append(_code("PROTOCOL_REVENUE_NOT_ESTABLISHED_OQ01",
                               "no verified daily economically attributable revenue "
                               "ledger exists (OQ-01); treasury payouts and gross fees "
                               "are not substitutes"))

    # --- sample assembly over the fixed calendar ----------------------------
    values = {variable: {day.date: series_value(day, variable) for day in table["days"]}
              for variable in spec.required_variables}
    reasons = {variable: {} for variable in spec.required_variables}
    for variable in spec.required_variables:
        for date in calendar:
            reason = _series_missing_reason(table["days"][(date - policy.window_start).days],
                                            variable)
            if reason:
                reasons[variable][date] = reason
    complete_days = [date for date in calendar
                     if all(date not in reasons[variable]
                            for variable in spec.required_variables)]
    excluded_days = []
    for date in calendar:
        for variable in spec.required_variables:
            reason = reasons[variable].get(date)
            if reason:
                excluded_days.append({"date": date.isoformat(),
                                      "series": variable.series_key,
                                      "reason": reason})
    zero_days = sorted(
        {date.isoformat() for variable in spec.required_variables
         for date in complete_days if values[variable][date] == 0})
    negative_days = sorted(
        {date.isoformat() for variable in spec.required_variables
         for date in complete_days if values[variable][date] < 0})
    finite_as_float64 = all(
        _finite_as_float64(values[variable][date])
        for variable in spec.required_variables for date in complete_days)

    # differences only between calendar-adjacent complete days
    complete_set = set(complete_days)
    adjacent_pairs = sum(1 for date in complete_days
                         if (date - dt.timedelta(days=1)) in complete_set)
    if spec.baseline == BASELINE_DIFFERENCE_LOG:
        if zero_days:
            codes.append(_code("ZERO_VALUES_EXCLUDE_LOG_SPEC",
                               f"{len(zero_days)} zero value day(s) in required series; "
                               "zeros are genuine observations and are never epsiloned"))
        if negative_days:
            codes.append(_code("NEGATIVE_VALUES_EXCLUDE_LOG_SPEC",
                               f"{len(negative_days)} negative value day(s) in required "
                               "series"))
        usable = adjacent_pairs
        # Full-calendar adjacent pairs minus the usable ones: incomplete
        # adjacent-day pairs are dropped, never differenced across gaps.
        dropped_pairs = max(0, (window_days - 1) - adjacent_pairs)
        if dropped_pairs > 0:
            codes.append(_code("NONADJACENT_DAYS_FOR_DIFFERENCING",
                               f"{dropped_pairs} incomplete adjacent-day pair(s) dropped; "
                               "differences are never taken across gaps"))
    else:
        usable = len(complete_days)
        dropped_pairs = 0

    if window_days < policy.min_complete_daily_observations or spec.family == FAMILY_COHORT:
        if usable < policy.min_complete_daily_observations:
            codes.append(_code("SHORT_ATTRIBUTION_WINDOW",
                               f"the window holds {window_days} calendar day(s) and the "
                               f"sample reaches {usable} usable observation(s), below "
                               f"the {policy.min_complete_daily_observations}-day project "
                               "gate; rejected for daily long-run inference"))
    if usable < policy.min_complete_daily_observations:
        codes.append(_code("INSUFFICIENT_COMPLETE_OBSERVATIONS",
                           f"{usable} usable observation(s) < "
                           f"{policy.min_complete_daily_observations}"))
    parameters = spec.parameters_count
    min_required = parameters * policy.min_observations_per_parameter
    if usable < min_required:
        codes.append(_code("INSUFFICIENT_OBSERVATIONS_PER_PARAMETER",
                           f"{usable} usable observation(s) < {min_required} "
                           f"({parameters} parameter(s) x "
                           f"{policy.min_observations_per_parameter})"))

    # --- verdict -------------------------------------------------------------
    # A gated dependent variable is honest unavailability (NOT_READY), not a
    # specification rejection; every other rejecting code yields REJECTED.
    if dependent_availability == "G":
        verdict = VERDICT_NOT_READY
    elif any(entry["severity"] == SEVERITY_REJECTING for entry in codes):
        verdict = VERDICT_REJECTED
    elif spec.family in (FAMILY_TRUE_REVENUE,):
        verdict = VERDICT_READY
    else:
        verdict = VERDICT_READY_WITH_LIMITS

    # --- limits (never rejecting; always attached verbatim) ------------------
    if verdict in (VERDICT_READY, VERDICT_READY_WITH_LIMITS):
        for code in LIMITS_BY_FAMILY.get(spec.family, ()):
            codes.append(_code(code))
        for variable in spec.required_variables:
            for code in LIMITS_BY_METRIC.get(variable.metric_id, ()):
                codes.append(_code(code))
        if any(metric_registry.definition_by_metric_id(v.metric_id).definition["availability"] == "P"
               for v in spec.required_variables):
            codes.append(_code("SOURCE_REVISIONS_POSSIBLE"))
        used_sources = {v.dimension for v in spec.required_variables
                        if SERIES_REGISTRY[v.metric_id] == DIMENSION_SOURCE}
        if len(used_sources) == 1:
            codes.append(_code("SINGLE_PROVIDER_LINEAGE_NOT_INDEPENDENT"))
        if window_days < policy.long_run_min_days:
            codes.append(_code("SHORT_SAMPLE_NO_LONG_RUN_CLAIM",
                               f"{window_days} calendar day(s) cannot establish a "
                               "long-term stable mechanism"))
        codes.append(_code("NO_CAUSAL_IDENTIFICATION"))

    sample_report = {
        "calendar_days": window_days,
        "complete_days": len(complete_days),
        "usable_observations": usable,
        "nonadjacent_dropped_pairs": dropped_pairs,
        "required_parameters": parameters,
        "min_required_observations": min_required,
        "zero_days_on_complete_days": zero_days,
        "negative_days_on_complete_days": negative_days,
        "excluded_days_count": len(excluded_days),
        "excluded_days": excluded_days,
        "float64_finite": finite_as_float64,
        "verified_zero_days": sorted(
            {day.date.isoformat() for day in table["days"]
             if day.extract_covered and day.purchases_near == 0})
        if any(v.metric_id == "observed_near_purchases" for v in spec.required_variables)
        else [],
    }
    if sample_report["verified_zero_days"]:
        codes.append(_code("VERIFIED_ZERO_DAYS_PRESENT",
                           f"{len(sample_report['verified_zero_days'])} covered day(s) "
                           "with no qualifying records are proven zeros, not gaps"))
    return SpecEvaluation(spec=spec, verdict=verdict, reason_codes=tuple(codes),
                          sample=sample_report)


# --------------------------------------------------------------------------- #
# Gate run, invariants and report assembly
# --------------------------------------------------------------------------- #


def _check_invariants(evaluations: tuple[SpecEvaluation, ...], report: dict) -> None:
    """Fail closed if any project invariant is violated by the evaluation itself."""
    # 1. No gross-fee/payout proxy passes as protocol revenue.
    for evaluation in evaluations:
        targets_revenue = (evaluation.spec.declared_target == "protocol_revenue"
                           or evaluation.spec.dependent.metric_id == PROTOCOL_REVENUE_METRIC)
        if targets_revenue and evaluation.spec.family != FAMILY_TRUE_REVENUE:
            if evaluation.verdict not in (VERDICT_NOT_READY, VERDICT_REJECTED):
                raise ReadinessGateError(
                    f"invariant violated: {evaluation.spec.spec_id} passed as protocol "
                    f"revenue with verdict {evaluation.verdict}")
        if (targets_revenue and evaluation.spec.family == FAMILY_TRUE_REVENUE
                and evaluation.verdict == VERDICT_READY):
            raise ReadinessGateError(
                "invariant violated: a true-revenue specification evaluated READY; "
                "protocol revenue is not established (OQ-01) and the gate must not "
                "manufacture it")
    report["invariants"]["no_proxy_passes_as_protocol_revenue"] = True
    # 2. Gaps/exclusions are explicit: every profile lists missing/zero days and
    # every evaluation carries the exclusion table (structural, asserted).
    for profile in report["prepared_table"]["series"]:
        for key in ("missing_days", "zero_days", "calendar_gaps"):
            if key not in profile:
                raise ReadinessGateError(f"invariant violated: series profile lacks {key}")
    for evaluation in evaluations:
        if "excluded_days" not in evaluation.sample:
            raise ReadinessGateError("invariant violated: evaluation lacks exclusions")
    report["invariants"]["gaps_and_exclusions_explicit"] = True
    # 3. Short attribution datasets are rejected for daily long-run inference.
    minimum = report["gate_policy"]["min_complete_daily_observations"]
    for evaluation in evaluations:
        if evaluation.sample["usable_observations"] < minimum \
                and evaluation.verdict in (VERDICT_READY, VERDICT_READY_WITH_LIMITS):
            raise ReadinessGateError(
                f"invariant violated: {evaluation.spec.spec_id} passed with "
                f"{evaluation.sample['usable_observations']} usable observations")
    report["invariants"]["short_attribution_rejected"] = True
    # 4. Every emitted code is cataloged (reproducible vocabulary).
    for evaluation in evaluations:
        for entry in evaluation.reason_codes:
            if entry["code"] not in REASON_CATALOG:
                raise ReadinessGateError(f"uncataloged reason code {entry['code']!r}")
    report["invariants"]["reason_codes_cataloged"] = True


def run_readiness_gate(archive_root: Path, configs_dir: Path,
                       policy_path: Path) -> dict:
    """Run the gate end to end and return the deterministic report document."""
    policy = load_policy(policy_path)
    archive = load_archive(archive_root, policy)
    table = build_prepared_table(archive)

    spec_paths = []
    if not configs_dir.is_dir():
        raise ReadinessGateError(f"configs directory not found: {configs_dir}")
    for path in sorted(configs_dir.glob("*.json")):
        if path.name.startswith(".") or path.resolve() == policy_path.resolve():
            continue
        spec_paths.append(path)
    if not spec_paths:
        raise ReadinessGateError(f"no specification configs found in {configs_dir}")
    specs = [load_spec(path, policy) for path in spec_paths]
    by_id = {}
    for spec in specs:
        if spec.spec_id in by_id:
            raise ReadinessGateError(f"duplicate spec_id {spec.spec_id!r}")
        by_id[spec.spec_id] = spec
    for spec_id in policy.spec_evaluation_order:
        if spec_id not in by_id:
            raise ReadinessGateError(f"policy evaluation order references unknown "
                                     f"spec {spec_id!r}")
    for spec in specs:
        if spec.spec_id not in policy.spec_evaluation_order:
            raise ReadinessGateError(f"spec {spec.spec_id!r} is not in the policy "
                                     "evaluation order; add it explicitly or remove it")

    evaluations = []
    for spec_id in policy.spec_evaluation_order:
        evaluations.append(evaluate_spec(by_id[spec_id], table, policy, archive))

    selected = None
    for evaluation in evaluations:
        if evaluation.verdict in (VERDICT_READY, VERDICT_READY_WITH_LIMITS):
            selected = evaluation
            break
    protocol_ready = any(e.spec.family == FAMILY_TRUE_REVENUE and e.verdict == VERDICT_READY
                         for e in evaluations)
    if selected is None:
        overall = "NOT_READY_NO_MODEL"
    elif selected.spec.family == FAMILY_TRUE_REVENUE:
        overall = "TRUE_REVENUE_READY"
    else:
        overall = "PROXY_ONLY_READY_WITH_LIMITS"
    if selected is not None:
        selected_index = next(i for i, e in enumerate(evaluations) if e is selected)
        evaluations[selected_index] = SpecEvaluation(
            spec=selected.spec, verdict=selected.verdict,
            reason_codes=selected.reason_codes,
            sample={**selected.sample, "selected": True})
    rationale = (
        "protocol_revenue_usd is registry-gated with zero observations (OQ-01), so the "
        "preferred true-revenue specification is NOT_READY; the explicitly named proxy "
        f"specification {selected.spec.spec_id} is admitted with limits"
        if selected is not None and selected.spec.family != FAMILY_TRUE_REVENUE else
        ("no specification passed the gate" if selected is None else
         f"{selected.spec.spec_id} passed the gate"))

    metric_definitions = {}
    for variable_set in ([e.spec.required_variables for e in evaluations]):
        for variable in variable_set:
            if variable.metric_id not in metric_definitions:
                metric_definitions[variable.metric_id] = series_definition(variable)

    report = {
        "report_type": REPORT_TYPE,
        "gate_version": GATE_VERSION,
        "policy": policy.as_report(),
        "window": {"start": policy.window_start.isoformat(),
                   "end_exclusive": policy.window_end_exclusive.isoformat(),
                   "days": policy.window_days},
        "inputs": {
            "archive_root_name": archive_root.name,
            "files": [{"name": item["name"], "cohort": item["cohort"],
                       "path": item["path"], "bytes": item["bytes"],
                       "sha256": item["sha256"]} for item in archive.files],
            "metric_definitions": metric_definitions,
        },
        "prepared_table": {
            "calendar_days": policy.window_days,
            "daily_rows_present": table["daily_rows_present"],
            "extract_coverage_days": policy.window_days - len(table["extract_uncovered_days"]),
            "extract_uncovered_days": [date.isoformat()
                                       for date in table["extract_uncovered_days"]],
            "extract_parse_error_days": [date.isoformat()
                                         for date in table["extract_parse_error_days"]],
            "series": [profile_series(VariableSpec(metric_id=metric_id, dimension=dimension,
                                                   role="profile"), table)
                       for metric_id, dimension in (
                           ("protocol_revenue_usd", None),
                           ("provider_intents_volume_usd", "SRC-LLAMA"),
                           ("provider_intents_volume_usd", "SRC-DASHBOARD"),
                           ("provider_gross_fees_usd", "SRC-LLAMA"),
                           ("provider_gross_fees_usd", "SRC-DASHBOARD"),
                           ("effective_gross_fee_bps", "SRC-LLAMA"),
                           ("effective_gross_fee_bps", "SRC-DASHBOARD"),
                           ("near_price_usd", "start"),
                           ("near_price_usd", "end"),
                           ("observed_near_purchases", None),
                           ("conversion_count", None),
                           ("treasury_payouts_near", None),
                           ("treasury_payout_count", None),
                           ("estimated_purchase_usd", "start"),
                           ("estimated_purchase_usd", "end"))],
            "supply_windows": supply_windows_profile(archive),
            "source_comparison": source_comparison_profile(table),
            "fee_rate_profile": fee_rate_profile(table, policy),
            "known_caveats": [dict(caveat) for caveat in KNOWN_CAVEATS],
        },
        "gate_policy": policy.as_report(),
        "spec_evaluations": [evaluation.as_report() for evaluation in evaluations],
        "selection": {
            "selected_spec": selected.spec.spec_id if selected else None,
            "overall_verdict": overall,
            "protocol_revenue_ready": protocol_ready,
            "rationale": rationale,
        },
        "oq_register": [dict(item) for item in OQ_REGISTER],
        "invariants": {},
    }
    _check_invariants(tuple(evaluations), report)
    return report


# --------------------------------------------------------------------------- #
# Rendering (deterministic JSON + human-readable markdown)
# --------------------------------------------------------------------------- #


def render_report_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def render_report_markdown(report: dict) -> str:
    """Human-readable summary rendered from the same deterministic document."""
    lines = []
    selection = report["selection"]
    lines.append(f"# Model dataset readiness report (gate v{report['gate_version']})")
    lines.append("")
    lines.append(f"Window: {report['window']['start']} .. (exclusive) "
                 f"{report['window']['end_exclusive']} ({report['window']['days']} days).")
    lines.append("")
    lines.append(f"Overall verdict: **{selection['overall_verdict']}**; "
                 f"selected spec: `{selection['selected_spec'] or 'none'}`.")
    lines.append("")
    lines.append(selection["rationale"])
    lines.append("")
    lines.append("## Specification evaluations")
    lines.append("")
    for evaluation in report["spec_evaluations"]:
        spec = evaluation["spec"]
        lines.append(f"### {spec['spec_id']} (family {spec['family']}, "
                     f"target {spec['declared_target']}) - {evaluation['verdict']}")
        sample = evaluation["sample"]
        lines.append("")
        lines.append(f"Complete days {sample['complete_days']}, usable observations "
                     f"{sample['usable_observations']}, required parameters "
                     f"{sample['required_parameters']} "
                     f"(minimum {sample['min_required_observations']}), excluded days "
                     f"{sample['excluded_days_count']}.")
        lines.append("")
        if evaluation["reason_codes"]:
            for entry in evaluation["reason_codes"]:
                lines.append(f"- `{entry['code']}` ({entry['severity']}): "
                             f"{entry['detail']}")
        else:
            lines.append("- no reason codes")
        lines.append("")
    lines.append("## Prepared table profiles")
    lines.append("")
    lines.append("| series | present | missing | zero | gaps | availability |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for profile in report["prepared_table"]["series"]:
        lines.append(f"| `{profile['series_key']}` | {profile['present_days']} | "
                     f"{len(profile['missing_days'])} | {len(profile['zero_days'])} | "
                     f"{len(profile['calendar_gaps'])} | {profile['availability']} |")
    lines.append("")
    supply = report["prepared_table"]["supply_windows"]
    lines.append(f"Supply windows: {len(supply['atomic_windows'])} atomic windows plus the "
                 f"total period; mint headers audited "
                 f"{supply['mint_headers_verified_total']}/{supply['mint_headers_target_total']}; "
                 "all issuance/burn values are conservative lower bounds.")
    lines.append("")
    lines.append("## Invariants")
    lines.append("")
    for name, value in sorted(report["invariants"].items()):
        lines.append(f"- {name}: {'held' if value else 'VIOLATED'}")
    lines.append("")
    lines.append("## Open questions carried with the decision")
    lines.append("")
    for item in report["oq_register"]:
        lines.append(f"- **{item['id']}** {item['question']}: {item['effect']}")
    lines.append("")
    lines.append("## Reproduction")
    lines.append("")
    inputs = report["inputs"]["files"]
    lines.append("Inputs (SHA-256 pinned):")
    lines.append("")
    for item in inputs:
        lines.append(f"- `{item['cohort']}/{item['path']}` ({item['bytes']} bytes, "
                     f"`{item['sha256']}`)")
    lines.append("")
    lines.append("Command: `uv run --project apps/api python research/models/readiness.py "
                 "--archive-root <research root> --configs-dir research/models/configs "
                 "--out-dir <output directory>`; the same inputs always render a "
                 "byte-identical report.")
    lines.append("")
    lines.append("Limitation: this gate decides admissibility before fitting. It fits "
                 "nothing; the estimator is NI-052 and must reuse the admitted "
                 "specification unchanged.")
    lines.append("")
    return "\n".join(lines)


def write_report(report: dict, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "readiness_report.json"
    markdown_path = out_dir / "readiness_report.md"
    json_path.write_text(render_report_json(report), encoding="utf-8")
    markdown_path.write_text(render_report_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archive-root", type=Path, required=True,
                        help="read-only research archive root")
    parser.add_argument("--configs-dir", type=Path, default=None,
                        help="specification configs directory "
                             "(default: <script dir>/configs)")
    parser.add_argument("--policy", type=Path, default=None,
                        help="gate policy JSON (default: <configs-dir>/"
                             "readiness_gate_policy_v1.json)")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="write readiness_report.json/.md here (default: stdout)")
    arguments = parser.parse_args(argv)
    script_dir = Path(__file__).resolve().parent
    configs_dir = (arguments.configs_dir or script_dir / "configs").resolve()
    policy_path = (arguments.policy or configs_dir / "readiness_gate_policy_v1.json").resolve()
    try:
        report = run_readiness_gate(archive_root=arguments.archive_root,
                                    configs_dir=configs_dir, policy_path=policy_path)
    except (ReadinessGateError, MetricComputationError) as error:
        print(f"readiness gate contract failure: {error}", file=sys.stderr)
        return EXIT_CONTRACT
    if arguments.out_dir is not None:
        json_path, markdown_path = write_report(report, arguments.out_dir)
        selection = report["selection"]
        print(f"overall verdict: {selection['overall_verdict']}; "
              f"selected spec: {selection['selected_spec'] or 'none'}")
        print(f"report: {json_path}")
        print(f"report: {markdown_path}")
    else:
        sys.stdout.write(render_report_json(report))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
