"""NI-052 fixed deterministic econometric estimator (offline research code).

The estimator fits ONE defensible real-data association with declared
transformations and covariance. It is bound to the NI-051 readiness gate:
the admitted specification (``gross_fee_activity_v1``) is loaded through the
gate's own loaders and re-evaluated on the same archive, and a fit is only
started when the gate verdict is ``READY`` or ``READY_WITH_LIMITS``. The
specification is reused UNCHANGED — the estimator never edits the dependent
variable, the explanatory variables, the transformations or the sample
window, and it never invents a coefficient.

Hard rules encoded here (docs/ECONOMETRIC_METHODOLOGY.md, NI-052 card):

- No p-value-driven search. The design matrix contains exactly the columns
  the preregistered specification declares (intercept if declared, one slope
  per declared explanatory variable); no variable, lag, sample or
  specification choice is ever made from p-values, fit quality or residual
  diagnostics. The lag count of the covariance estimator is a fixed
  preregistered number (``maxlags_rule = fixed``), never selected from the
  data.
- Strict positivity for log transformations: every value entering a log is
  checked against ``value > 0`` on the exact Decimal source. Genuine zeros
  are never removed by an epsilon, never interpolated and never silently
  dropped; a zero or negative value in a required series is a structured
  error, never a fit.
- Differences are formed only between calendar-adjacent complete days;
  incomplete adjacent-day pairs are dropped, never differenced across gaps
  as if contiguous. Missing stays missing: the gate's exclusion table is
  copied verbatim into the manifest.
- Explicit intercept, parameter-count, rank and condition checks run BEFORE
  estimation. A rank-deficient design (or a design that does not match the
  declared parameter count) is a structured error, never fitted through a
  pseudo-inverse or column dropping.
- OLS with HAC (Newey-West, Bartlett kernel) covariance from the locked
  statsmodels; kernel, lag, correction and t/normal settings are recorded
  from the preregistered fit config, not from defaults.
- Limitations travel with the result: the specification's
  ``limitation_notes`` (including the mechanical fee-volume construction
  warning) and every gate limit code are attached verbatim to the manifest
  and to the CLI output.

The same inputs, configs and lock always produce a byte-identical manifest
on the same platform: there are no wall-clock fields, inputs are pinned by
SHA-256, source design values are hashed as exact decimal strings and every
float is emitted through ``repr``. Cross-platform reproduction compares
fitted values under the documented tolerance (rtol 1e-8 / atol 1e-10); the
IEEE-754 hex design digest is a same-platform byte-identity aid and may
differ across libm implementations while the tolerance comparison still
governs.

Boundaries: the archive is opened READ-ONLY; the manifest is written only to
the operator-provided output directory (never inside ``research/``); no
network call, no database access, no provider request and no arbitrary user
code execution happens anywhere. The real-archive fit run is operator-side
evidence (like the NI-051 gate run): this repository ships the code, the
preregistered configs and the tests, not fitted real-data results.

CLI (research code, same pattern as readiness.py)::

    uv run --project apps/api python research/models/fit.py \
        --archive-root /path/to/research \
        --out-dir research/models/reports \
        --code-commit <git sha>

The same estimator is reachable as the apps/api research CLI::

    uv run --project apps/api python -m near_api.research fit \
        --archive-root /path/to/research --out-dir research/models/reports

Exit codes: 0 success; 4 contract/policy failure (gate not admitted, rank
deficiency, positivity violation, config/spec mismatch); 2 usage.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
import platform
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import numpy as np
import scipy
import statsmodels
from near_api.datasets.canonical import decimal_string
from near_api.metrics.compute import MetricComputationError
from statsmodels.regression.linear_model import OLS

EXIT_OK = 0
EXIT_CONTRACT = 4
EXIT_USAGE = 2

FIT_VERSION = 1
MANIFEST_TYPE = "model_fit_run"

# The repository root is two levels above this file (research/models/fit.py).
REPO_ROOT = Path(__file__).resolve().parents[2]

# Estimator vocabulary (fixed; unknown values are contract errors).
ESTIMATOR_OLS = "ols"
COVARIANCE_HAC = "HAC"
KERNEL_BARTLETT = "bartlett"
MAXLAGS_RULE_FIXED = "fixed"
FLOAT64_CONVERSION_POLICY = "explicit_finite_required"
DIFFERENCE_ADJACENCY_CALENDAR = "calendar_adjacent_only"

# Column naming (deterministic; derived from the specification only).
INTERCEPT_COLUMN = "const"

REPRODUCTION_COMMAND = (
    "uv run --project apps/api python -m near_api.research fit "
    "--archive-root <research root> --out-dir <output directory> "
    "--code-commit <git sha>")

P_VALUE_USAGE_NOTE = (
    "p-values are recorded for the declared output contract only; no "
    "variable, lag, sample or specification choice was made from them "
    "(no p-value-driven search anywhere in this estimator).")

DESIGN_FLOAT_HASH_NOTE = (
    "SHA-256 over the IEEE-754 hex serialization of the float64 design; "
    "byte-identical on the same platform. Across platforms libm rounding "
    "may differ at the last unit in the last place; cross-platform "
    "reproduction is governed by the declared tolerance comparison, not by "
    "this digest.")

DESIGN_SOURCE_HASH_NOTE = (
    "SHA-256 over the canonical JSON of the exact Decimal source values and "
    "calendar dates behind every design row; stable across platforms.")


class FitError(ValueError):
    """Inputs, configs, gate admission or design properties make an honest
    deterministic fit impossible."""


def _load_readiness_module():
    """Import-only reuse of the NI-051 gate: its loaders, policy/spec
    validation, prepared table and evaluation are the single source of
    admissibility; nothing is duplicated here."""
    module_name = "ni051_readiness_for_fit"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    path = Path(__file__).resolve().parent / "readiness.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise FitError(f"cannot load the NI-051 readiness module at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


readiness = _load_readiness_module()


# --------------------------------------------------------------------------- #
# Preregistered fit configuration (typed, strict)
# --------------------------------------------------------------------------- #


def _canonical_json(value) -> str:
    return readiness._canonical_json(value)


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CovarianceConfig:
    """Fixed HAC (Newey-West) settings; the lag rule is preregistered."""

    covariance_type: str
    kernel: str
    maxlags: int
    maxlags_rule: str
    use_correction: bool
    use_t: bool
    rationale: str

    def as_report(self) -> dict:
        return {
            "type": self.covariance_type,
            "kernel": self.kernel,
            "maxlags": self.maxlags,
            "maxlags_rule": self.maxlags_rule,
            "use_correction": self.use_correction,
            "use_t": self.use_t,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class FitConfig:
    """The preregistered estimator settings for one specification."""

    fit_config_id: str
    fit_config_version: int
    spec_id: str
    spec_config: str
    gate_policy_config: str
    estimator: str
    covariance: CovarianceConfig
    coefficient_rtol: Decimal
    coefficient_atol: Decimal
    config_hash: str

    @property
    def maxlags(self) -> int:
        return self.covariance.maxlags

    def as_report(self) -> dict:
        return {
            "fit_config_id": self.fit_config_id,
            "fit_config_version": self.fit_config_version,
            "spec_id": self.spec_id,
            "spec_config": self.spec_config,
            "gate_policy_config": self.gate_policy_config,
            "estimator": self.estimator,
            "covariance": self.covariance.as_report(),
            "reproduction": {
                "coefficient_rtol": decimal_string(self.coefficient_rtol),
                "coefficient_atol": decimal_string(self.coefficient_atol),
            },
            "config_hash": self.config_hash,
        }


def load_fit_config(path: Path) -> FitConfig:
    """Load and validate one preregistered fit config (fail closed)."""
    try:
        return _load_fit_config(path)
    except readiness.ReadinessGateError as error:
        # The strict JSON helpers belong to the gate; the estimator surfaces
        # every contract failure as FitError.
        raise FitError(str(error)) from error


def _load_fit_config(path: Path) -> FitConfig:
    document = readiness._load_json(path, context="fit config")
    readiness._reject_unknown_fields(document, {
        "fit_config_id", "fit_config_version", "spec_id", "spec_config",
        "gate_policy_config", "estimator", "covariance", "reproduction",
    }, context=f"fit config {path.name}")
    for key in ("fit_config_id", "fit_config_version", "spec_id", "spec_config",
                "gate_policy_config", "estimator", "covariance", "reproduction"):
        if key not in document:
            raise FitError(f"fit config {path.name}: missing required key {key!r}")
    context = f"fit config {path.name}"
    estimator = document["estimator"]
    if estimator != ESTIMATOR_OLS:
        raise FitError(f"{context}: estimator must be {ESTIMATOR_OLS!r}")
    covariance = document["covariance"]
    if not isinstance(covariance, dict):
        raise FitError(f"{context}: covariance must be an object")
    readiness._reject_unknown_fields(covariance, {
        "type", "kernel", "maxlags_rule", "maxlags", "use_correction",
        "use_t", "rationale",
    }, context=f"{context}.covariance")
    for key in ("type", "kernel", "maxlags_rule", "maxlags", "use_correction",
                "use_t", "rationale"):
        if key not in covariance:
            raise FitError(f"{context}.covariance: missing required key {key!r}")
    if covariance["type"] != COVARIANCE_HAC:
        raise FitError(f"{context}.covariance: type must be {COVARIANCE_HAC!r} "
                       "(Newey-West); other covariance estimators are not preregistered")
    if covariance["kernel"] != KERNEL_BARTLETT:
        raise FitError(f"{context}.covariance: kernel must be {KERNEL_BARTLETT!r}")
    if covariance["maxlags_rule"] != MAXLAGS_RULE_FIXED:
        raise FitError(f"{context}.covariance: maxlags_rule must be "
                       f"{MAXLAGS_RULE_FIXED!r}; sample- or p-value-driven lag "
                       "selection is forbidden")
    maxlags = covariance["maxlags"]
    if not isinstance(maxlags, int) or isinstance(maxlags, bool) or maxlags <= 0:
        raise FitError(f"{context}.covariance: maxlags must be a positive integer")
    if not isinstance(covariance["use_correction"], bool) \
            or not isinstance(covariance["use_t"], bool):
        raise FitError(f"{context}.covariance: use_correction/use_t must be booleans")
    rationale = covariance["rationale"]
    if not isinstance(rationale, str) or not rationale.strip():
        raise FitError(f"{context}.covariance: rationale must be a non-empty string "
                       "recording the timing justification of the fixed lag count")
    reproduction = document["reproduction"]
    if not isinstance(reproduction, dict):
        raise FitError(f"{context}: reproduction must be an object")
    readiness._reject_unknown_fields(reproduction, {"coefficient_rtol",
                                                    "coefficient_atol"},
                                     context=f"{context}.reproduction")
    tolerances = {}
    for key in ("coefficient_rtol", "coefficient_atol"):
        value = reproduction.get(key)
        if not isinstance(value, str):
            raise FitError(f"{context}.reproduction: {key} must be a decimal string")
        try:
            parsed = Decimal(value)
        except Exception:
            raise FitError(f"{context}.reproduction: {key} {value!r} is not a "
                           "decimal string") from None
        if parsed <= 0:
            raise FitError(f"{context}.reproduction: {key} must be positive")
        tolerances[key] = parsed
    version = document["fit_config_version"]
    if not isinstance(version, int) or isinstance(version, bool) or version <= 0:
        raise FitError(f"{context}: fit_config_version must be a positive integer")
    for key in ("fit_config_id", "spec_id", "spec_config", "gate_policy_config"):
        if not isinstance(document[key], str) or not document[key]:
            raise FitError(f"{context}: {key} must be a non-empty string")
    return FitConfig(
        fit_config_id=document["fit_config_id"],
        fit_config_version=version,
        spec_id=document["spec_id"],
        spec_config=document["spec_config"],
        gate_policy_config=document["gate_policy_config"],
        estimator=estimator,
        covariance=CovarianceConfig(
            covariance_type=covariance["type"], kernel=covariance["kernel"],
            maxlags=maxlags, maxlags_rule=covariance["maxlags_rule"],
            use_correction=covariance["use_correction"], use_t=covariance["use_t"],
            rationale=rationale),
        coefficient_rtol=tolerances["coefficient_rtol"],
        coefficient_atol=tolerances["coefficient_atol"],
        config_hash=_sha256_hex(_canonical_json(document)),
    )


# --------------------------------------------------------------------------- #
# Design builder (pure; transformations exactly as declared)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DesignRow:
    """One design row: the exact source values behind the transformed
    observation (kept for the platform-stable source hash)."""

    date: dt.date
    previous_date: dt.date | None
    values: dict  # series_key -> {"current": str, "previous": str | None}


@dataclass(frozen=True)
class Design:
    """The assembled design matrix plus its deterministic provenance."""

    spec: object                    # ModelSpec
    evaluation: object              # SpecEvaluation
    baseline: str
    transformations: dict           # verbatim echo of the spec transformations
    columns: tuple[str, ...]
    rows: tuple[DesignRow, ...]
    y: object                       # np.ndarray float64
    X: object                       # np.ndarray float64 (nobs, parameters)
    source_hash: str
    float64_hex_hash: str

    @property
    def nobs(self) -> int:
        return int(self.X.shape[0])

    @property
    def parameters(self) -> int:
        return int(self.X.shape[1])


def _series_key(variable) -> str:
    return variable.series_key


def _slope_column_name(baseline: str, series_key: str) -> str:
    prefix = "dlog" if baseline == readiness.BASELINE_DIFFERENCE_LOG else "level"
    return f"{prefix}({series_key})"


def expected_columns(spec) -> tuple[str, ...]:
    """The only columns the estimator is allowed to build."""
    columns = []
    if spec.intercept:
        columns.append(INTERCEPT_COLUMN)
    for variable in spec.explanatory:
        columns.append(_slope_column_name(spec.baseline, _series_key(variable)))
    return tuple(columns)


def _finite_float(value: Decimal, *, date: dt.date, series_key: str) -> float:
    """Explicit finite float64 conversion; non-finite is a contract error."""
    try:
        converted = float(value)
    except (OverflowError, ValueError):
        raise FitError(f"float64 conversion of {series_key} on {date.isoformat()} "
                       f"failed for {decimal_string(value)}; the policy requires "
                       "explicit finite conversion") from None
    if not math.isfinite(converted):
        raise FitError(f"float64 conversion of {series_key} on {date.isoformat()} "
                       f"is not finite ({decimal_string(value)})")
    return converted


def _strictly_positive(value: Decimal, *, date: dt.date, series_key: str) -> None:
    if value <= 0:
        raise FitError(
            f"strict positivity violated for {series_key} on {date.isoformat()}: "
            f"{decimal_string(value)}. Genuine zeros and negatives are observations; "
            "they are never removed by an epsilon, interpolated or silently dropped. "
            "A level/scaled alternative must be predeclared first, not chosen after "
            "seeing the sample.")


def build_design(spec, policy, table: dict, evaluation,
                 transformations: dict) -> Design:
    """Build the design matrix from the prepared table exactly as the
    specification declares; no selection, no epsilon, no silent exclusion."""
    baseline = spec.baseline

    if baseline == readiness.BASELINE_DIFFERENCE_LOG:
        if transformations.get("strictly_positive_required") is not True:
            raise FitError("the log-difference baseline must declare "
                           "strictly_positive_required (the specification is reused "
                           "unchanged; the estimator does not repair it)")
        if transformations.get("difference_adjacency") != DIFFERENCE_ADJACENCY_CALENDAR:
            raise FitError("differences may only use "
                           f"{DIFFERENCE_ADJACENCY_CALENDAR!r} adjacency")
    if transformations.get("float64_conversion") not in (None, FLOAT64_CONVERSION_POLICY):
        raise FitError(f"float64_conversion must declare "
                       f"{FLOAT64_CONVERSION_POLICY!r}")
    if len(spec.explanatory) != spec.substantive_slopes:
        raise FitError(f"the specification declares {spec.substantive_slopes} "
                       f"substantive slope(s) but binds {len(spec.explanatory)} "
                       "explanatory variable(s); the design must match the declared "
                       "parameter count exactly")
    if len(spec.explanatory) == 0:
        raise FitError("the specification binds no explanatory variable; an "
                       "intercept-only model is not a fit of a declared association")

    variables = spec.required_variables
    days = table["days"]
    day_index = {day.date: day for day in days}
    values = {variable: {date: readiness.series_value(day, variable)
                         for date, day in day_index.items()}
              for variable in variables}

    # The gate's exclusion table is authoritative; the design assembles the
    # same sample and never joins a missing day away.
    excluded_dates = {dt.date.fromisoformat(item["date"])
                      for item in evaluation.sample["excluded_days"]}
    complete_days = [date for date in table["calendar"] if date not in excluded_dates]
    complete_set = set(complete_days)

    check_positivity = (baseline == readiness.BASELINE_DIFFERENCE_LOG
                        or transformations.get("strictly_positive_required") is True)

    rows: list[DesignRow] = []
    y_values: list[float] = []
    x_values: list[list[float]] = []
    dependent_key = _series_key(spec.dependent)
    explanatory_keys = [_series_key(variable) for variable in spec.explanatory]

    if baseline == readiness.BASELINE_DIFFERENCE_LOG:
        pairs = [date for date in complete_days
                 if (date - dt.timedelta(days=1)) in complete_set]
        for date in pairs:
            previous = date - dt.timedelta(days=1)
            row_values: dict = {}
            # Strict positivity is checked on every exact source value entering
            # a log, current and previous, before any float conversion.
            for variable, key in ((spec.dependent, dependent_key),) \
                    + tuple(zip(spec.explanatory, explanatory_keys)):
                current = values[variable][date]
                earlier = values[variable][previous]
                if current is None or earlier is None:
                    raise FitError(f"missing value for {key} on "
                                   f"{date.isoformat()}/{previous.isoformat()} inside "
                                   "an adjacent complete pair; the gate sample and the "
                                   "design disagree")
                if check_positivity:
                    _strictly_positive(current, date=date, series_key=key)
                    _strictly_positive(earlier, date=previous, series_key=key)
                row_values[key] = {"current": decimal_string(current),
                                   "previous": decimal_string(earlier)}
            rows.append(DesignRow(date=date, previous_date=previous, values=row_values))
            y_current = _finite_float(values[spec.dependent][date], date=date,
                                      series_key=dependent_key)
            y_previous = _finite_float(values[spec.dependent][previous],
                                       date=previous, series_key=dependent_key)
            y_values.append(math.log(y_current) - math.log(y_previous))
            slopes = []
            for variable, key in zip(spec.explanatory, explanatory_keys):
                x_current = _finite_float(values[variable][date], date=date,
                                          series_key=key)
                x_previous = _finite_float(values[variable][previous],
                                           date=previous, series_key=key)
                slopes.append(math.log(x_current) - math.log(x_previous))
            x_values.append(slopes)
    elif baseline == readiness.BASELINE_LEVEL:
        for date in complete_days:
            row_values = {}
            for variable, key in ((spec.dependent, dependent_key),) \
                    + tuple(zip(spec.explanatory, explanatory_keys)):
                value = values[variable][date]
                if value is None:
                    raise FitError(f"missing value for {key} on {date.isoformat()} "
                                   "inside the declared sample; the gate sample and "
                                   "the design disagree")
                if check_positivity:
                    _strictly_positive(value, date=date, series_key=key)
                row_values[key] = {"current": decimal_string(value), "previous": None}
            rows.append(DesignRow(date=date, previous_date=None, values=row_values))
        y_values = [_finite_float(values[spec.dependent][row.date],
                                  date=row.date, series_key=dependent_key)
                    for row in rows]
        x_values = [[_finite_float(values[variable][row.date], date=row.date,
                                   series_key=key)
                     for variable, key in zip(spec.explanatory, explanatory_keys)]
                    for row in rows]
    else:
        raise FitError(f"unknown baseline {baseline!r}")

    columns = expected_columns(spec)
    y = np.asarray(y_values, dtype=np.float64)
    X = np.asarray(x_values, dtype=np.float64)
    if spec.intercept:
        X = np.column_stack([np.ones(X.shape[0], dtype=np.float64), X])
    if y.shape[0] != X.shape[0]:
        raise FitError("design assembly produced mismatched y/X row counts")
    if X.shape[1] != len(columns):
        raise FitError("design assembly produced an unexpected column count")
    if X.shape[0] != evaluation.sample["usable_observations"]:
        raise FitError(
            f"the design assembled {X.shape[0]} observation(s) while the gate "
            f"evaluation reports {evaluation.sample['usable_observations']} usable "
            "observation(s); the sample must match the gate exactly")

    source_document = {
        "baseline": baseline,
        "columns": list(columns),
        "rows": [{"date": row.date.isoformat(),
                  "previous_date": (row.previous_date.isoformat()
                                    if row.previous_date else None),
                  "values": row.values} for row in rows],
    }
    float_document = {
        "columns": list(columns),
        "y_hex": [value.hex() for value in y],
        "X_hex": [[value.hex() for value in row] for row in X],
    }
    return Design(spec=spec, evaluation=evaluation, baseline=baseline,
                  transformations=transformations, columns=columns,
                  rows=tuple(rows), y=y, X=X,
                  source_hash=_sha256_hex(_canonical_json(source_document)),
                  float64_hex_hash=_sha256_hex(_canonical_json(float_document)))


def spec_document_transformations(spec_path: Path) -> dict:
    """Verbatim echo of the specification's declared transformations, read
    from the exact config file the operator pointed the estimator at."""
    document = readiness._load_json(spec_path, context="model spec")
    transformations = document.get("transformations")
    if not isinstance(transformations, dict):
        raise FitError("the specification config has no transformations object")
    return transformations


# --------------------------------------------------------------------------- #
# Pre-estimation checks and estimation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class EstimationResult:
    params: tuple
    bse: tuple
    tvalues: tuple
    pvalues: tuple
    conf_low: tuple
    conf_high: tuple
    nobs: int
    df_resid: int
    r_squared: float
    adj_r_squared: float
    rank: int
    condition_number: float


def check_design_before_estimation(design: Design, policy, fit_config: FitConfig) -> tuple:
    """Intercept, parameter-count, rank/condition and per-parameter sample
    checks. Any failure is a structured error BEFORE anything is fitted."""
    columns = design.columns
    if design.spec.intercept and (not columns or columns[0] != INTERCEPT_COLUMN):
        raise FitError("the specification declares an intercept but the design "
                       "does not lead with the intercept column")
    if not design.spec.intercept and INTERCEPT_COLUMN in columns:
        raise FitError("the design contains an intercept although the "
                       "specification does not declare one")
    if tuple(columns) != expected_columns(design.spec):
        raise FitError("the design columns deviate from the declared "
                       "specification; the estimator never adds, renames or "
                       "drops columns")
    if design.nobs < design.parameters:
        raise FitError(f"the design holds {design.nobs} observation(s) for "
                       f"{design.parameters} parameter(s); nothing to fit")
    min_required = design.spec.parameters_count * policy.min_observations_per_parameter
    if design.nobs < min_required:
        raise FitError(f"the design holds {design.nobs} observation(s), below the "
                       f"project gate of {min_required} ({design.spec.parameters_count} "
                       f"parameter(s) x {policy.min_observations_per_parameter})")
    if fit_config.maxlags >= design.nobs:
        raise FitError(f"HAC maxlags {fit_config.maxlags} is not below the sample "
                       f"size {design.nobs}; the preregistered lag count exceeds "
                       "the available sample")
    rank = int(np.linalg.matrix_rank(design.X))
    if rank != design.parameters:
        offending = ", ".join(
            columns[index] for index in range(design.parameters)
            if int(np.linalg.matrix_rank(design.X[:, :index + 1])) <= index)
        detail = offending or "every column beyond the rank"
        raise FitError(f"design rank deficient: rank {rank} < {design.parameters} "
                       f"column(s) (near-dependence detected in: {detail}); "
                       "refusing to fit — no pseudo-inverse, no column dropping, "
                       "no ridge, no silent repair")
    condition = float(np.linalg.cond(design.X))
    if not math.isfinite(condition):
        raise FitError("design condition number is not finite; refusing to fit")
    return rank, condition


def estimate(design: Design, policy, fit_config: FitConfig) -> EstimationResult:
    """OLS through the locked statsmodels with preregistered HAC covariance."""
    rank, condition = check_design_before_estimation(design, policy, fit_config)
    model = OLS(endog=design.y, exog=design.X)
    base = model.fit()
    robust = base.get_robustcov_results(
        cov_type=fit_config.covariance.covariance_type,
        maxlags=fit_config.maxlags,
        use_correction=fit_config.covariance.use_correction,
        use_t=fit_config.covariance.use_t)
    confidence = np.asarray(robust.conf_int(alpha=0.05), dtype=np.float64)
    return EstimationResult(
        params=tuple(float(value) for value in robust.params),
        bse=tuple(float(value) for value in robust.bse),
        tvalues=tuple(float(value) for value in robust.tvalues),
        pvalues=tuple(float(value) for value in robust.pvalues),
        conf_low=tuple(float(value) for value in confidence[:, 0]),
        conf_high=tuple(float(value) for value in confidence[:, 1]),
        nobs=design.nobs,
        df_resid=int(robust.df_resid),
        r_squared=float(base.rsquared),
        adj_r_squared=float(base.rsquared_adj),
        rank=rank,
        condition_number=condition)


# --------------------------------------------------------------------------- #
# Manifest assembly
# --------------------------------------------------------------------------- #


def _environment_report() -> dict:
    blas_info: dict = {}
    try:
        build = np.__config__.CONFIG.get("Build Dependencies", {})
        blas_info = {"blas": build.get("blas", {}).get("name", "unknown"),
                     "lapack": build.get("lapack", {}).get("name", "unknown")}
    except Exception:
        blas_info = {"blas": "unavailable", "lapack": "unavailable"}
    return {
        "python_version": sys.version.replace("\n", " "),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "statsmodels_version": statsmodels.__version__,
        "blas": blas_info,
        "randomness": "none; the estimator is fully deterministic and needs no seed",
    }


def _dependency_lock_report() -> dict:
    lock_path = REPO_ROOT / "apps" / "api" / "uv.lock"
    if lock_path.is_file():
        digest = hashlib.sha256(lock_path.read_bytes()).hexdigest()
        return {"path": "apps/api/uv.lock", "sha256": digest, "present": True}
    return {"path": "apps/api/uv.lock", "sha256": None, "present": False,
            "note": "the dependency lock hash must be recorded for publication "
                    "(NI-054); it was not found next to this checkout"}


def run_fit(archive_root: Path, spec_path: Path, fit_config_path: Path,
            policy_path: Path, code_commit: str | None) -> dict:
    """Run the estimator end to end and return the deterministic manifest."""
    policy = readiness.load_policy(policy_path)
    spec = readiness.load_spec(spec_path, policy)
    transformations = spec_document_transformations(spec_path)
    fit_config = load_fit_config(fit_config_path)

    # The admitted specification is reused unchanged: the fit config must bind
    # exactly this spec, and the spec file must be the preregistered one.
    if fit_config.spec_id != spec.spec_id:
        raise FitError(f"fit config {fit_config.fit_config_id!r} binds specification "
                       f"{fit_config.spec_id!r} but {spec_path.name} declares "
                       f"{spec.spec_id!r}; the estimator never swaps specifications")
    declared_spec_name = Path(fit_config.spec_config).name
    if spec_path.name != declared_spec_name:
        raise FitError(f"fit config declares spec_config {declared_spec_name!r} but "
                       f"the estimator was pointed at {spec_path.name!r}")
    if spec.declared_target == "protocol_revenue" and spec.family != readiness.FAMILY_TRUE_REVENUE:
        raise FitError("refusing to fit: a non-true-revenue specification may never "
                       "target protocol revenue (defense in depth behind the gate)")

    archive = readiness.load_archive(archive_root, policy)
    table = readiness.build_prepared_table(archive)
    evaluation = readiness.evaluate_spec(spec, table, policy, archive)
    if evaluation.verdict not in (readiness.VERDICT_READY,
                                  readiness.VERDICT_READY_WITH_LIMITS):
        rejecting = [entry["code"] for entry in evaluation.reason_codes
                     if entry["severity"] == readiness.SEVERITY_REJECTING]
        raise FitError(f"the gate verdict for {spec.spec_id} is {evaluation.verdict}; "
                       f"nothing may be fitted (rejecting codes: {rejecting or 'none'})")

    design = build_design(spec, policy, table, evaluation, transformations)
    result = estimate(design, policy, fit_config)

    gate_limit_codes = [entry["code"] for entry in evaluation.reason_codes
                        if entry["severity"] == readiness.SEVERITY_LIMIT]
    manifest = {
        "manifest_type": MANIFEST_TYPE,
        "fit_version": FIT_VERSION,
        "model": {
            "model_id": spec.spec_id,
            "model_version": spec.spec_version,
            "specification": spec.as_report(),
        },
        "admission": {
            "verdict": evaluation.verdict,
            "reason_codes": list(evaluation.reason_codes),
            "note": "the NI-051 readiness gate admitted this specification; the "
                    "estimator re-evaluated the same specification on the same "
                    "archive and refuses anything else",
        },
        "fit_config": fit_config.as_report(),
        "gate_policy": {
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "config_hash": policy.config_hash,
        },
        "sample": {
            "window": {"start": spec.sample_start.isoformat(),
                       "end_exclusive": spec.sample_end_exclusive.isoformat()},
            "nobs": result.nobs,
            "first_design_date": design.rows[0].date.isoformat() if design.rows else None,
            "last_design_date": design.rows[-1].date.isoformat() if design.rows else None,
            "gate_evaluation": evaluation.sample,
            "exclusion_policy": "the gate exclusion table is authoritative; the "
                                "design never joins a missing day away and never "
                                "differences across a gap",
        },
        "design": {
            "baseline": design.baseline,
            "transformations": design.transformations,
            "columns": list(design.columns),
            "rows": result.nobs,
            "rank": result.rank,
            "condition_number": result.condition_number,
            "source_hash": design.source_hash,
            "source_hash_note": DESIGN_SOURCE_HASH_NOTE,
            "float64_hex_sha256": design.float64_hex_hash,
            "float64_hash_note": DESIGN_FLOAT_HASH_NOTE,
        },
        "estimation": {
            "estimator": fit_config.estimator,
            "method": "OLS",
            "covariance": fit_config.covariance.as_report(),
            "nobs": result.nobs,
            "df_resid": result.df_resid,
            "r_squared": result.r_squared,
            "adj_r_squared": result.adj_r_squared,
            "p_value_usage": P_VALUE_USAGE_NOTE,
        },
        "coefficients": [
            {"name": name, "estimate": estimate_value, "std_error": std_error,
             "t_stat": t_stat, "p_value": p_value,
             "ci95_low": conf_low, "ci95_high": conf_high}
            for name, estimate_value, std_error, t_stat, p_value, conf_low, conf_high
            in zip(design.columns, result.params, result.bse, result.tvalues,
                   result.pvalues, result.conf_low, result.conf_high)],
        "diagnostics": {
            "note": "the full residual/ACF/Ljung-Box/heteroskedasticity/influence "
                    "battery and stationarity tests belong to NI-053; only the "
                    "design and fit summaries are recorded here",
        },
        "limitations": {
            "prohibited_labels": list(spec.prohibited_labels),
            "spec_limitation_notes": list(spec.limitation_notes),
            "gate_limit_codes": gate_limit_codes,
            "attachment_policy": "the specification notes and every gate limit code "
                                 "are attached verbatim to this manifest and to the "
                                 "CLI output; the mechanical fee-volume warning is "
                                 "displayed before any coefficient interpretation",
        },
        "environment": _environment_report(),
        "inputs": {
            "archive_root_name": archive_root.name,
            "files": [{"name": item["name"], "cohort": item["cohort"],
                       "path": item["path"], "bytes": item["bytes"],
                       "sha256": item["sha256"]} for item in archive.files],
            "spec_config": {"path": f"research/models/configs/{spec_path.name}",
                            "config_hash": spec.config_hash},
            "fit_config_path": fit_config_path.name,
            "gate_policy_path": policy_path.name,
            "code_commit": code_commit,
            "code_commit_note": "recorded from the operator-provided --code-commit "
                                "argument; publication requires it (NI-054)",
            "dependency_lock": _dependency_lock_report(),
        },
        "reproduction": {
            "command": REPRODUCTION_COMMAND,
            "coefficient_rtol": decimal_string(fit_config.coefficient_rtol),
            "coefficient_atol": decimal_string(fit_config.coefficient_atol),
            "determinism": "no wall-clock fields; inputs pinned by SHA-256; exact "
                           "decimal source values hashed for the design; fitted "
                           "floats compared under the declared tolerances",
        },
        "invariants": {},
    }
    _check_invariants(manifest, spec, fit_config, evaluation, design)
    return manifest


def _check_invariants(manifest: dict, spec, fit_config: FitConfig,
                      evaluation, design: Design) -> None:
    """Fail closed if the assembled manifest violates a project invariant."""
    # 1. The admitted specification is reused unchanged.
    if manifest["model"]["model_id"] != spec.spec_id:
        raise FitError("invariant violated: the manifest does not name the admitted "
                       "specification")
    if fit_config.spec_id != spec.spec_id:
        raise FitError("invariant violated: the fit config binds another "
                       "specification")
    manifest["invariants"]["spec_reused_unchanged"] = True
    # 2. Gate admission is verified, not assumed.
    if manifest["admission"]["verdict"] not in (readiness.VERDICT_READY,
                                                readiness.VERDICT_READY_WITH_LIMITS):
        raise FitError("invariant violated: the manifest records an unadmitted "
                       "verdict")
    manifest["invariants"]["gate_admission_verified"] = True
    # 3. No p-value-driven search: the design is exactly the declared one and
    # the covariance lag rule is fixed (structural, asserted after assembly).
    if tuple(manifest["design"]["columns"]) != expected_columns(spec):
        raise FitError("invariant violated: design columns deviate from the "
                       "declared specification")
    if manifest["design"]["rows"] != manifest["sample"]["nobs"]:
        raise FitError("invariant violated: the design row count deviates from the "
                       "recorded sample size")
    if fit_config.covariance.maxlags_rule != MAXLAGS_RULE_FIXED:
        raise FitError("invariant violated: the covariance lag rule is not fixed")
    manifest["invariants"]["no_p_value_driven_search"] = True
    # 4. Limitations travel with the result, verbatim.
    recorded = manifest["limitations"]["spec_limitation_notes"]
    for note in spec.limitation_notes:
        if note not in recorded:
            raise FitError("invariant violated: a specification limitation note is "
                           "missing from the manifest")
    if manifest["limitations"]["prohibited_labels"] != list(spec.prohibited_labels):
        raise FitError("invariant violated: prohibited labels are not attached "
                       "verbatim")
    manifest["invariants"]["limitations_attached"] = True
    # 5. The fitted sample is the gate sample.
    if manifest["sample"]["nobs"] != evaluation.sample["usable_observations"]:
        raise FitError("invariant violated: the fitted sample deviates from the "
                       "gate evaluation")
    manifest["invariants"]["sample_matches_gate"] = True


# --------------------------------------------------------------------------- #
# Rendering (deterministic JSON + human-readable markdown)
# --------------------------------------------------------------------------- #


def render_manifest_json(manifest: dict) -> str:
    return json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def render_manifest_markdown(manifest: dict) -> str:
    lines = []
    model = manifest["model"]
    lines.append(f"# Model fit manifest (fit v{manifest['fit_version']})")
    lines.append("")
    lines.append(f"Model: `{model['model_id']}` (specification v{model['model_version']}); "
                 f"gate admission **{manifest['admission']['verdict']}**.")
    lines.append("")
    lines.append("This manifest records one deterministic fit of the admitted "
                 "specification. It is not a claim of economic truth: read the "
                 "limitations before any coefficient.")
    lines.append("")
    lines.append("## Specification (reused unchanged from the NI-051 gate)")
    lines.append("")
    spec = model["specification"]
    lines.append(f"- baseline: `{spec['baseline']}`; dependent variable: "
                 f"`{spec['dependent_variable']['metric_id']}` "
                 f"({spec['dependent_variable']['dimension']}); explanatory: "
                 + ", ".join(f"`{item['metric_id']}` ({item['dimension']}, "
                             f"role {item['role']})"
                             for item in spec["explanatory_variables"]))
    lines.append(f"- config hash: `{spec['config_hash']}`")
    lines.append("")
    lines.append("## Sample")
    lines.append("")
    sample = manifest["sample"]
    lines.append(f"Window {sample['window']['start']} .. (exclusive) "
                 f"{sample['window']['end_exclusive']}; nobs {sample['nobs']}; "
                 f"complete days {sample['gate_evaluation']['complete_days']}; "
                 "excluded day entries "
                 f"{sample['gate_evaluation']['excluded_days_count']}.")
    lines.append("")
    lines.append("## Design")
    lines.append("")
    design = manifest["design"]
    lines.append(f"- columns: {', '.join(f'`{name}`' for name in design['columns'])}")
    lines.append(f"- rank {design['rank']} / {len(design['columns'])} columns; "
                 f"condition number {design['condition_number']!r}")
    lines.append(f"- source hash: `{design['source_hash']}`")
    lines.append(f"- float64 hex digest: `{design['float64_hex_sha256']}`")
    lines.append("")
    lines.append("## Estimation")
    lines.append("")
    estimation = manifest["estimation"]
    covariance = estimation["covariance"]
    lines.append(f"OLS with {covariance['type']} covariance "
                 f"({covariance['kernel']} kernel, maxlags {covariance['maxlags']}, "
                 f"maxlags_rule {covariance['maxlags_rule']}, use_correction "
                 f"{covariance['use_correction']!r}, use_t {covariance['use_t']!r}); "
                 f"nobs {estimation['nobs']}, df_resid {estimation['df_resid']}, "
                 f"R² {estimation['r_squared']!r}.")
    lines.append("")
    lines.append("## Coefficients (HAC)")
    lines.append("")
    lines.append("| column | estimate | std error | t | p (advisory) | 95% CI |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for coefficient in manifest["coefficients"]:
        lines.append(
            f"| `{coefficient['name']}` | {coefficient['estimate']!r} | "
            f"{coefficient['std_error']!r} | {coefficient['t_stat']!r} | "
            f"{coefficient['p_value']!r} | [{coefficient['ci95_low']!r}, "
            f"{coefficient['ci95_high']!r}] |")
    lines.append("")
    lines.append(estimation["p_value_usage"])
    lines.append("")
    lines.append("## Limitations (attached verbatim)")
    lines.append("")
    for note in manifest["limitations"]["spec_limitation_notes"]:
        lines.append(f"- {note}")
    for code in manifest["limitations"]["gate_limit_codes"]:
        lines.append(f"- Gate limit code: `{code}`")
    lines.append(f"- Prohibited labels: "
                 + ", ".join(f"`{label}`" for label
                             in manifest["limitations"]["prohibited_labels"]))
    lines.append("")
    lines.append("## Reproduction")
    lines.append("")
    reproduction = manifest["reproduction"]
    lines.append(f"Command: `{reproduction['command']}`")
    lines.append("")
    lines.append(f"Fitted values reproduce within rtol {reproduction['coefficient_rtol']} / "
                 f"atol {reproduction['coefficient_atol']} for the same input, config "
                 "and lock. The real-archive run itself is operator-side evidence; "
                 "this manifest carries no wall-clock field and re-renders "
                 "byte-identically on the same platform.")
    lines.append("")
    return "\n".join(lines)


def write_manifest(manifest: dict, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "fit_manifest.json"
    markdown_path = out_dir / "fit_manifest.md"
    json_path.write_text(render_manifest_json(manifest), encoding="utf-8")
    markdown_path.write_text(render_manifest_markdown(manifest), encoding="utf-8")
    return json_path, markdown_path


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archive-root", type=Path, required=True,
                        help="read-only research archive root")
    parser.add_argument("--spec", type=Path, default=None,
                        help="admitted specification config "
                             "(default: <script dir>/configs/"
                             "gross_fee_activity_v1.json)")
    parser.add_argument("--fit-config", type=Path, default=None,
                        help="preregistered estimator config (default: <script dir>/"
                             "fit_configs/gross_fee_activity_v1_fit.json)")
    parser.add_argument("--policy", type=Path, default=None,
                        help="gate policy JSON (default: <script dir>/configs/"
                             "readiness_gate_policy_v1.json)")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="write fit_manifest.json/.md here (default: stdout)")
    parser.add_argument("--code-commit", type=str, default=None,
                        help="git commit of the code producing this manifest "
                             "(required for publication; recorded verbatim)")
    arguments = parser.parse_args(argv)
    script_dir = Path(__file__).resolve().parent
    spec_path = (arguments.spec or script_dir / "configs"
                 / "gross_fee_activity_v1.json").resolve()
    fit_config_path = (arguments.fit_config or script_dir / "fit_configs"
                       / "gross_fee_activity_v1_fit.json").resolve()
    policy_path = (arguments.policy or script_dir / "configs"
                   / "readiness_gate_policy_v1.json").resolve()
    try:
        manifest = run_fit(archive_root=arguments.archive_root, spec_path=spec_path,
                           fit_config_path=fit_config_path, policy_path=policy_path,
                           code_commit=arguments.code_commit)
    except (FitError, readiness.ReadinessGateError, MetricComputationError) as error:
        print(f"fit contract failure: {error}", file=sys.stderr)
        return EXIT_CONTRACT
    if arguments.out_dir is not None:
        json_path, markdown_path = write_manifest(manifest, arguments.out_dir)
        print(f"model: {manifest['model']['model_id']}; "
              f"admission: {manifest['admission']['verdict']}; "
              f"nobs: {manifest['sample']['nobs']}")
        for note in manifest["limitations"]["spec_limitation_notes"][:1]:
            print(f"limitation: {note}")
        print(f"manifest: {json_path}")
        print(f"manifest: {markdown_path}")
    else:
        sys.stdout.write(render_manifest_json(manifest))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
