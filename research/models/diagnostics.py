"""NI-053 diagnostics, robustness and interpretation artifacts (offline research code).

This module makes the NI-052 fit assessable beyond a single coefficient or a
high R². It reuses the NI-051 gate and the NI-052 estimator import-only (one
gate, one estimator, one version source — nothing is duplicated here): the
admitted specification is re-evaluated unchanged, the fit is re-run through
``fit.run_fit`` and the design/estimation are rebuilt with the estimator's own
pure functions, so every number in the diagnostics report is the same number
the fit manifest records.

Hard rules encoded here (docs/ECONOMETRIC_METHODOLOGY.md, NI-053 card):

- All defined diagnostics are present or explicitly undefined: every declared
  stationarity test, residual test and sensitivity preset appears in the
  report exactly once with status ``computed`` or ``undefined``/``failed``/
  ``not_applicable`` plus a recorded reason code from a fixed vocabulary.
  Undefined tests are null with a reason, never zero and never silently
  dropped.
- Stationarity settings are preregistered: ADF (fixed ``maxlag``, autolag
  disabled) and KPSS (fixed ``nlags``) run on the declared series with the
  settings recorded next to the result — no lag is ever selected from the
  data, and no test output is reduced to a pass/fail label.
- Residual diagnostics (ACF, Ljung–Box at declared lags, Breusch–Pagan
  heteroskedasticity, Cook's distance influence flags) are computed from the
  fitted design with the locked statsmodels; flagged observations are
  reported with dates and are never removed or repaired. The response to a
  rejection is the already-preregistered HAC covariance, nothing else.
- Sensitivity is limited and prespecified: the only variants are the ones
  declared in the diagnostics config (HAC lag alternatives, the alternate
  provider source, the alternate price basis). No specification surfing: no
  variant is generated from data, p-values or residuals, and a variant that
  binds no swappable variable is reported as not applicable with a reason
  instead of being invented.
- The interpretation is template-rendered: every sentence is a fixed string
  from this module with recorded numbers/decisions substituted. Sentences
  are bounded (association, not causality), sustainability/valuation claims
  are prohibited, and the specification's mechanical fee–volume limitation
  note is repeated verbatim. No free-form text generation happens anywhere;
  an authored operator interpretation, if any, is added at publication time
  (NI-054) and never replaces the attached limitations.
- Diagnostic p-values are advisory in a short sample; no binary truth
  verdict is emitted.

Determinism: the report carries no wall-clock field; inputs are pinned by
SHA-256; the same inputs, configs and lock render a byte-identical report on
the same platform, and recorded floats compare under the fit config's
declared tolerances across platforms.

Boundaries: the archive is opened READ-ONLY; the report is written only to
the operator-provided output directory (never inside ``research/``); no
network call, no database access, no provider request and no arbitrary user
code execution happens anywhere. The real-archive diagnostics run is
operator-side evidence (like the NI-051 gate and NI-052 fit runs): this
repository ships the code, the preregistered configs and the tests, not
real-data results.

CLI (research code, same pattern as fit.py)::

    uv run --project apps/api python research/models/diagnostics.py \\
        --archive-root /path/to/research \\
        --out-dir research/reports/<run> \\
        --code-commit <git sha>

The same battery is reachable as the apps/api research CLI::

    uv run --project apps/api python -m near_api.research diagnostics \\
        --archive-root /path/to/research --out-dir research/reports/<run>

Exit codes: 0 success; 4 contract/policy failure (gate not admitted, config/
spec mismatch, design failure); 2 usage.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import importlib.util
import json
import math
import sys
import warnings
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import numpy as np
from near_api.datasets.canonical import decimal_string
from near_api.metrics.compute import MetricComputationError
from statsmodels.regression.linear_model import OLS
from statsmodels.stats.diagnostic import acorr_ljungbox, het_breuschpagan
from statsmodels.stats.outliers_influence import OLSInfluence
from statsmodels.tools.sm_exceptions import InterpolationWarning
from statsmodels.tsa.stattools import acf, adfuller, kpss

EXIT_OK = 0
EXIT_CONTRACT = 4
EXIT_USAGE = 2

DIAGNOSTICS_VERSION = 1
REPORT_TYPE = "model_diagnostics_report"
INTERPRETATION_TEMPLATE_ID = "bounded_association_v1"

# The repository root is two levels above this file (research/models/diagnostics.py).
REPO_ROOT = Path(__file__).resolve().parents[2]

# Status vocabularies (fixed; unknown values are contract errors).
TEST_STATUS_COMPUTED = "computed"
TEST_STATUS_UNDEFINED = "undefined"
SENSITIVITY_ESTIMATED = "estimated"
SENSITIVITY_NOT_APPLICABLE = "not_applicable"
SENSITIVITY_FAILED = "failed"
DECISION_REJECT_NULL = "reject_null"
DECISION_FAIL_TO_REJECT_NULL = "fail_to_reject_null"

# Undefined-test reason vocabulary ("undefined" is null with a reason, never zero).
UNDEFINED_REASONS = {
    "sample_below_declared_minimum": (
        "the series holds fewer observations than the config declares as the "
        "minimum for this test; the statistic would be undefined short-sample "
        "noise and is not computed"),
    "constant_series_no_variance": (
        "the series is constant over the declared sample; a zero-variance "
        "series makes the test statistic undefined"),
    "non_finite_values": (
        "the series contains a value that is not finite after the declared "
        "explicit float64 conversion; the test is refused"),
    "maxlag_not_below_observations": (
        "the declared fixed lag count is not below the available sample size; "
        "the test is undefined for this sample"),
    "declared_lags_not_below_nobs": (
        "the declared Ljung-Box lags are not below the available sample size; "
        "the test is undefined for this sample"),
    "model_df_not_below_smallest_declared_lag": (
        "the resolved degrees-of-freedom correction is not below the smallest "
        "declared lag; the test is undefined"),
    "acf_nlags_not_below_nobs": (
        "the declared ACF lag count is not below the available sample size; "
        "the ACF is undefined for this sample"),
    "library_error": (
        "the locked statsmodels raised an error for this input; the test is "
        "recorded as undefined instead of being approximated"),
}

# Sensitivity failure/not-applicable reason vocabulary.
SENSITIVITY_REASONS = {
    "no_bound_variable_to_swap": (
        "no bound variable uses a swappable dimension of this kind; the "
        "variant is not applicable to this specification and is not invented"),
    "maxlags_not_below_sample_size": (
        "the preregistered alternative lag count is not below the fitted "
        "sample size; the methodology's 'if sample supports it' condition "
        "does not hold"),
    "variant_not_admitted_by_gate": (
        "the gate evaluation of the variant specification is not "
        "READY/READY_WITH_LIMITS; nothing is estimated on a variant the gate "
        "rejects"),
    "variant_design_failed": (
        "the variant design failed the estimator's fail-closed checks; the "
        "structured reason is recorded verbatim"),
}

SENSITIVITY_KINDS = ("covariance_maxlags", "source_alternative",
                     "price_basis_alternative")
ADF_REGRESSIONS = ("c", "ct", "ctt", "n")
KPSS_REGRESSIONS = ("c", "ct")
MAXLAG_RULE_FIXED = "fixed"
NLAGS_RULE_FIXED = "fixed"
MODEL_DF_RULE_PARAMETERS_COUNT = "parameters_count"
HETEROSKEDASTICITY_TESTS = ("breusch_pagan",)
EXOG_HET_DESIGN = "design_exog"
INFLUENCE_MEASURES = ("cooks_distance",)
THRESHOLD_RULE_MULTIPLIER_OVER_NOBS = "multiplier_over_nobs"
STATIONARITY_SERIES_ROLES = ("dependent", "explanatory")
PRICE_BASIS_DIMENSION = "price_basis"
SOURCE_DIMENSION = "source"

REPRODUCTION_COMMAND = (
    "uv run --project apps/api python -m near_api.research diagnostics "
    "--archive-root <research root> --out-dir <output directory> "
    "--code-commit <git sha>")

INTERPRETATION_RENDERING_POLICY = (
    "every sentence below is rendered from a fixed template in "
    "research/models/diagnostics.py with recorded numbers and recorded test "
    "decisions substituted; there is no free-form generation, no causal "
    "wording and no sustainability wording anywhere in this module.")

INTERPRETATION_AUTHORING_NOTE = (
    "this is the bounded template default rendered by the diagnostics run; an "
    "authored operator interpretation, if any, is added at publication time "
    "(NI-054) and never replaces the attached limitations.")

# Fixed interpretation templates (bounded association language; the only
# sentences the report can contain). Substitutions come from recorded
# numbers/decisions only.
ADF_REJECT_SENTENCE = (
    "The ADF unit-root null is rejected at the declared alpha for at least one "
    "level series; over this short window that is weak evidence of stationarity, "
    "not proof, and the preregistered difference baseline stays the published form.")
ADF_FAIL_SENTENCE = (
    "The ADF unit-root null is not rejected for at least one level series; the "
    "level is treated as nonstationary and the preregistered difference baseline "
    "stays the published form.")
KPSS_REJECT_SENTENCE = (
    "The KPSS stationarity null is rejected for at least one level series; the "
    "level is treated as nonstationary and the preregistered difference baseline "
    "stays the published form.")
KPSS_FAIL_SENTENCE = (
    "The KPSS stationarity null is not rejected for any level series; short "
    "samples make this weak evidence, not proof of stationarity.")
LB_REJECT_SENTENCE = (
    "Ljung-Box indicates residual autocorrelation at the declared lags; the "
    "preregistered HAC covariance addresses inference under serial dependence "
    "but does not repair misspecification or endogeneity.")
LB_FAIL_SENTENCE = (
    "Ljung-Box does not reject the no-autocorrelation null at the declared "
    "lags; with this sample size that is weak evidence, not proof of a correct "
    "specification.")
BP_REJECT_SENTENCE = (
    "Breusch-Pagan indicates heteroskedasticity; the preregistered response is "
    "the already-declared HAC covariance — no reweighting, no outlier removal "
    "and no specification change was performed.")
BP_FAIL_SENTENCE = (
    "Breusch-Pagan does not reject homoskedasticity at the declared alpha; the "
    "HAC covariance remains the preregistered covariance regardless.")
INFLUENCE_FLAGGED_SENTENCE = (
    "Influence check: {count} observation(s) exceed the preregistered Cook's "
    "distance threshold ({threshold}); they are reported with dates and remain "
    "in the sample — removal requires an operational reason and a with/without "
    "report.")
INFLUENCE_CLEAN_SENTENCE = (
    "Influence check: no observation exceeds the preregistered Cook's distance "
    "threshold ({threshold}); the sample is used unchanged.")
PROHIBITION_SENTENCE = (
    "No protocol-revenue, sustainable-revenue, token-valuation, causal or "
    "demand-elasticity claim follows from this output: the fitted object is the "
    "named proxy association only, and the mechanical fee-on-volume construction "
    "means the slope largely restates the effective fee rate.")


class DiagnosticsError(ValueError):
    """Inputs, configs or gate admission make an honest diagnostics report
    impossible."""


def _load_fit_module():
    """Import-only reuse of the NI-052 estimator: its manifest pipeline,
    design builder, estimation, config loader and environment/lock reports are
    the single source of the fitted object; the NI-051 gate comes with it."""
    module_name = "ni052_fit_for_diagnostics"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    path = Path(__file__).resolve().parent / "fit.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise DiagnosticsError(f"cannot load the NI-052 fit module at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


fit = _load_fit_module()
readiness = fit.readiness


# --------------------------------------------------------------------------- #
# Preregistered diagnostics configuration (typed, strict)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ADFConfig:
    regression: str
    maxlag: int
    maxlag_rule: str
    rationale: str


@dataclass(frozen=True)
class KPSSConfig:
    regression: str
    nlags: int
    nlags_rule: str
    rationale: str


@dataclass(frozen=True)
class StationarityConfig:
    series_roles: tuple
    min_observations: int
    adf: ADFConfig
    kpss: KPSSConfig


@dataclass(frozen=True)
class ACFConfig:
    nlags: int
    fft: bool
    alpha: Decimal
    bartlett_confint: bool


@dataclass(frozen=True)
class LjungBoxConfig:
    lags: tuple
    model_df_rule: str
    rationale: str


@dataclass(frozen=True)
class HeteroskedasticityConfig:
    test: str
    robust: bool
    exog_het: str
    rationale: str


@dataclass(frozen=True)
class InfluenceConfig:
    measure: str
    threshold_rule: str
    threshold_multiplier: Decimal
    rationale: str


@dataclass(frozen=True)
class ResidualsConfig:
    acf: ACFConfig
    ljung_box: LjungBoxConfig
    heteroskedasticity: HeteroskedasticityConfig
    influence: InfluenceConfig


@dataclass(frozen=True)
class SensitivityPreset:
    preset_id: str
    kind: str
    rationale: str
    maxlags: int | None = None
    source: str | None = None
    price_basis: str | None = None
    applies_to_metric_ids: tuple = ()


@dataclass(frozen=True)
class DiagnosticsConfig:
    diagnostics_config_id: str
    diagnostics_config_version: int
    spec_id: str
    spec_config: str
    fit_config: str
    gate_policy_config: str
    interpretation_template: str
    decision_alpha: Decimal
    stationarity: StationarityConfig
    residuals: ResidualsConfig
    sensitivity_presets: tuple
    config_hash: str

    def as_report(self) -> dict:
        presets = []
        for preset in self.sensitivity_presets:
            entry = {"preset_id": preset.preset_id, "kind": preset.kind,
                     "rationale": preset.rationale}
            if preset.maxlags is not None:
                entry["maxlags"] = preset.maxlags
            if preset.source is not None:
                entry["source"] = preset.source
            if preset.price_basis is not None:
                entry["price_basis"] = preset.price_basis
            if preset.applies_to_metric_ids:
                entry["applies_to_metric_ids"] = list(preset.applies_to_metric_ids)
            presets.append(entry)
        return {
            "diagnostics_config_id": self.diagnostics_config_id,
            "diagnostics_config_version": self.diagnostics_config_version,
            "spec_id": self.spec_id,
            "spec_config": self.spec_config,
            "fit_config": self.fit_config,
            "gate_policy_config": self.gate_policy_config,
            "interpretation_template": self.interpretation_template,
            "decision_alpha": decimal_string(self.decision_alpha),
            "stationarity": {
                "series": list(self.stationarity.series_roles),
                "min_observations": self.stationarity.min_observations,
                "adf": {"regression": self.stationarity.adf.regression,
                        "maxlag_rule": self.stationarity.adf.maxlag_rule,
                        "maxlag": self.stationarity.adf.maxlag,
                        "autolag": None,
                        "rationale": self.stationarity.adf.rationale},
                "kpss": {"regression": self.stationarity.kpss.regression,
                         "nlags_rule": self.stationarity.kpss.nlags_rule,
                         "nlags": self.stationarity.kpss.nlags,
                         "rationale": self.stationarity.kpss.rationale},
            },
            "residuals": {
                "acf": {"nlags": self.residuals.acf.nlags,
                        "fft": self.residuals.acf.fft,
                        "alpha": decimal_string(self.residuals.acf.alpha),
                        "bartlett_confint": self.residuals.acf.bartlett_confint},
                "ljung_box": {"lags": list(self.residuals.ljung_box.lags),
                              "model_df_rule": self.residuals.ljung_box.model_df_rule,
                              "rationale": self.residuals.ljung_box.rationale},
                "heteroskedasticity": {
                    "test": self.residuals.heteroskedasticity.test,
                    "robust": self.residuals.heteroskedasticity.robust,
                    "exog_het": self.residuals.heteroskedasticity.exog_het,
                    "rationale": self.residuals.heteroskedasticity.rationale},
                "influence": {
                    "measure": self.residuals.influence.measure,
                    "threshold_rule": self.residuals.influence.threshold_rule,
                    "threshold_multiplier": decimal_string(
                        self.residuals.influence.threshold_multiplier),
                    "rationale": self.residuals.influence.rationale},
            },
            "sensitivity_presets": presets,
            "config_hash": self.config_hash,
        }


def _decimal(document: dict, key: str, context: str) -> Decimal:
    value = document[key]
    if not isinstance(value, str):
        raise DiagnosticsError(f"{context}: {key} must be a decimal string")
    try:
        parsed = Decimal(value)
    except Exception:
        raise DiagnosticsError(f"{context}: {key} {value!r} is not a decimal "
                               "string") from None
    return parsed


def _positive_int(value, context: str, key: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise DiagnosticsError(f"{context}: {key} must be a positive integer")
    return value


def _non_empty_str(value, context: str, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DiagnosticsError(f"{context}: {key} must be a non-empty string")
    return value


def _load_stationarity(document: dict, context: str) -> StationarityConfig:
    readiness._reject_unknown_fields(document, {
        "series", "min_observations", "adf", "kpss"}, context=context)
    for key in ("series", "min_observations", "adf", "kpss"):
        if key not in document:
            raise DiagnosticsError(f"{context}: missing required key {key!r}")
    series = document["series"]
    if not isinstance(series, list) or not series or \
            any(role not in STATIONARITY_SERIES_ROLES for role in series):
        raise DiagnosticsError(f"{context}: series must be a non-empty list of "
                               f"{STATIONARITY_SERIES_ROLES}")
    min_observations = _positive_int(document["min_observations"], context,
                                     "min_observations")
    adf = document["adf"]
    if not isinstance(adf, dict):
        raise DiagnosticsError(f"{context}: adf must be an object")
    readiness._reject_unknown_fields(adf, {"regression", "maxlag_rule", "maxlag",
                                           "rationale"}, context=f"{context}.adf")
    for key in ("regression", "maxlag_rule", "maxlag", "rationale"):
        if key not in adf:
            raise DiagnosticsError(f"{context}.adf: missing required key {key!r}")
    if adf["regression"] not in ADF_REGRESSIONS:
        raise DiagnosticsError(f"{context}.adf: regression must be one of "
                               f"{ADF_REGRESSIONS}")
    if adf["maxlag_rule"] != MAXLAG_RULE_FIXED:
        raise DiagnosticsError(f"{context}.adf: maxlag_rule must be "
                               f"{MAXLAG_RULE_FIXED!r}; data-driven lag "
                               "selection is forbidden")
    adf_config = ADFConfig(
        regression=adf["regression"],
        maxlag=_positive_int(adf["maxlag"], f"{context}.adf", "maxlag"),
        maxlag_rule=adf["maxlag_rule"],
        rationale=_non_empty_str(adf["rationale"], f"{context}.adf", "rationale"))
    kpss_cfg = document["kpss"]
    if not isinstance(kpss_cfg, dict):
        raise DiagnosticsError(f"{context}: kpss must be an object")
    readiness._reject_unknown_fields(kpss_cfg, {"regression", "nlags_rule",
                                                "nlags", "rationale"},
                                     context=f"{context}.kpss")
    for key in ("regression", "nlags_rule", "nlags", "rationale"):
        if key not in kpss_cfg:
            raise DiagnosticsError(f"{context}.kpss: missing required key {key!r}")
    if kpss_cfg["regression"] not in KPSS_REGRESSIONS:
        raise DiagnosticsError(f"{context}.kpss: regression must be one of "
                               f"{KPSS_REGRESSIONS}")
    if kpss_cfg["nlags_rule"] != NLAGS_RULE_FIXED:
        raise DiagnosticsError(f"{context}.kpss: nlags_rule must be "
                               f"{NLAGS_RULE_FIXED!r}; data-driven lag "
                               "selection is forbidden")
    kpss_config = KPSSConfig(
        regression=kpss_cfg["regression"],
        nlags=_positive_int(kpss_cfg["nlags"], f"{context}.kpss", "nlags"),
        nlags_rule=kpss_cfg["nlags_rule"],
        rationale=_non_empty_str(kpss_cfg["rationale"], f"{context}.kpss",
                                 "rationale"))
    return StationarityConfig(series_roles=tuple(series),
                              min_observations=min_observations, adf=adf_config,
                              kpss=kpss_config)


def _load_residuals(document: dict, context: str) -> ResidualsConfig:
    readiness._reject_unknown_fields(document, {"acf", "ljung_box",
                                                "heteroskedasticity", "influence"},
                                     context=context)
    for key in ("acf", "ljung_box", "heteroskedasticity", "influence"):
        if key not in document:
            raise DiagnosticsError(f"{context}: missing required key {key!r}")
    acf_document = document["acf"]
    if not isinstance(acf_document, dict):
        raise DiagnosticsError(f"{context}: acf must be an object")
    readiness._reject_unknown_fields(acf_document, {"nlags", "fft", "alpha",
                                                    "bartlett_confint"},
                                     context=f"{context}.acf")
    for key in ("nlags", "fft", "alpha", "bartlett_confint"):
        if key not in acf_document:
            raise DiagnosticsError(f"{context}.acf: missing required key {key!r}")
    acf_alpha = _decimal(acf_document, "alpha", f"{context}.acf")
    if not Decimal(0) < acf_alpha < Decimal(1):
        raise DiagnosticsError(f"{context}.acf: alpha must be strictly between "
                               "0 and 1")
    if not isinstance(acf_document["fft"], bool) \
            or not isinstance(acf_document["bartlett_confint"], bool):
        raise DiagnosticsError(f"{context}.acf: fft/bartlett_confint must be "
                               "booleans")
    acf_config = ACFConfig(
        nlags=_positive_int(acf_document["nlags"], f"{context}.acf", "nlags"),
        fft=acf_document["fft"], alpha=acf_alpha,
        bartlett_confint=acf_document["bartlett_confint"])
    lb = document["ljung_box"]
    if not isinstance(lb, dict):
        raise DiagnosticsError(f"{context}: ljung_box must be an object")
    readiness._reject_unknown_fields(lb, {"lags", "model_df_rule", "rationale"},
                                     context=f"{context}.ljung_box")
    for key in ("lags", "model_df_rule", "rationale"):
        if key not in lb:
            raise DiagnosticsError(f"{context}.ljung_box: missing required key "
                                   f"{key!r}")
    lags = lb["lags"]
    if not isinstance(lags, list) or not lags:
        raise DiagnosticsError(f"{context}.ljung_box: lags must be a non-empty list")
    parsed_lags = [_positive_int(value, f"{context}.ljung_box", f"lags[{index}]")
                   for index, value in enumerate(lags)]
    if parsed_lags != sorted(set(parsed_lags)):
        raise DiagnosticsError(f"{context}.ljung_box: lags must be strictly "
                               "increasing and unique")
    if lb["model_df_rule"] != MODEL_DF_RULE_PARAMETERS_COUNT:
        raise DiagnosticsError(f"{context}.ljung_box: model_df_rule must be "
                               f"{MODEL_DF_RULE_PARAMETERS_COUNT!r}")
    het = document["heteroskedasticity"]
    if not isinstance(het, dict):
        raise DiagnosticsError(f"{context}: heteroskedasticity must be an object")
    readiness._reject_unknown_fields(het, {"test", "robust", "exog_het",
                                           "rationale"},
                                     context=f"{context}.heteroskedasticity")
    for key in ("test", "robust", "exog_het", "rationale"):
        if key not in het:
            raise DiagnosticsError(f"{context}.heteroskedasticity: missing "
                                   f"required key {key!r}")
    if het["test"] not in HETEROSKEDASTICITY_TESTS:
        raise DiagnosticsError(f"{context}.heteroskedasticity: test must be one "
                               f"of {HETEROSKEDASTICITY_TESTS}")
    if het["exog_het"] != EXOG_HET_DESIGN:
        raise DiagnosticsError(f"{context}.heteroskedasticity: exog_het must be "
                               f"{EXOG_HET_DESIGN!r}")
    if not isinstance(het["robust"], bool):
        raise DiagnosticsError(f"{context}.heteroskedasticity: robust must be a "
                               "boolean")
    het_config = HeteroskedasticityConfig(
        test=het["test"], robust=het["robust"], exog_het=het["exog_het"],
        rationale=_non_empty_str(het["rationale"],
                                 f"{context}.heteroskedasticity", "rationale"))
    influence = document["influence"]
    if not isinstance(influence, dict):
        raise DiagnosticsError(f"{context}: influence must be an object")
    readiness._reject_unknown_fields(influence, {"measure", "threshold_rule",
                                                 "threshold_multiplier",
                                                 "rationale"},
                                     context=f"{context}.influence")
    for key in ("measure", "threshold_rule", "threshold_multiplier", "rationale"):
        if key not in influence:
            raise DiagnosticsError(f"{context}.influence: missing required key "
                                   f"{key!r}")
    if influence["measure"] not in INFLUENCE_MEASURES:
        raise DiagnosticsError(f"{context}.influence: measure must be one of "
                               f"{INFLUENCE_MEASURES}")
    if influence["threshold_rule"] != THRESHOLD_RULE_MULTIPLIER_OVER_NOBS:
        raise DiagnosticsError(f"{context}.influence: threshold_rule must be "
                               f"{THRESHOLD_RULE_MULTIPLIER_OVER_NOBS!r}")
    multiplier = _decimal(influence, "threshold_multiplier",
                          f"{context}.influence")
    if multiplier <= 0:
        raise DiagnosticsError(f"{context}.influence: threshold_multiplier must "
                               "be positive")
    influence_config = InfluenceConfig(
        measure=influence["measure"], threshold_rule=influence["threshold_rule"],
        threshold_multiplier=multiplier,
        rationale=_non_empty_str(influence["rationale"], f"{context}.influence",
                                 "rationale"))
    return ResidualsConfig(acf=acf_config, ljung_box=LjungBoxConfig(
        lags=tuple(parsed_lags), model_df_rule=lb["model_df_rule"],
        rationale=_non_empty_str(lb["rationale"], f"{context}.ljung_box",
                                 "rationale")),
        heteroskedasticity=het_config, influence=influence_config)


def _load_preset(document: dict, context: str) -> SensitivityPreset:
    if not isinstance(document, dict):
        raise DiagnosticsError(f"{context}: a sensitivity preset must be an object")
    if "kind" not in document or document["kind"] not in SENSITIVITY_KINDS:
        raise DiagnosticsError(f"{context}: kind must be one of "
                               f"{SENSITIVITY_KINDS}")
    kind = document["kind"]
    allowed = {"preset_id", "kind", "rationale"}
    if kind == "covariance_maxlags":
        allowed |= {"maxlags"}
    elif kind == "source_alternative":
        allowed |= {"source", "applies_to_metric_ids"}
    else:
        allowed |= {"price_basis", "applies_to_metric_ids"}
    readiness._reject_unknown_fields(document, allowed, context=context)
    for key in ("preset_id", "rationale"):
        if key not in document:
            raise DiagnosticsError(f"{context}: missing required key {key!r}")
    preset_id = _non_empty_str(document["preset_id"], context, "preset_id")
    rationale = _non_empty_str(document["rationale"], context, "rationale")
    if kind == "covariance_maxlags":
        if "maxlags" not in document:
            raise DiagnosticsError(f"{context}: missing required key 'maxlags'")
        return SensitivityPreset(
            preset_id=preset_id, kind=kind, rationale=rationale,
            maxlags=_positive_int(document["maxlags"], context, "maxlags"))
    applies = document.get("applies_to_metric_ids", [])
    if not isinstance(applies, list) or \
            any(not isinstance(item, str) or not item for item in applies):
        raise DiagnosticsError(f"{context}: applies_to_metric_ids must be a list "
                               "of metric-id strings")
    for metric_id in applies:
        if metric_id not in readiness.SERIES_REGISTRY:
            raise DiagnosticsError(f"{context}: metric {metric_id!r} is not a "
                                   "series the gate can prepare")
    if kind == "source_alternative":
        source = _non_empty_str(document.get("source"), context, "source")
        if source not in readiness.PROVIDER_SOURCES:
            raise DiagnosticsError(f"{context}: source must be one of "
                                   f"{readiness.PROVIDER_SOURCES}")
        return SensitivityPreset(preset_id=preset_id, kind=kind,
                                 rationale=rationale, source=source,
                                 applies_to_metric_ids=tuple(applies))
    basis = _non_empty_str(document.get("price_basis"), context, "price_basis")
    if basis not in readiness.PRICE_BASES:
        raise DiagnosticsError(f"{context}: price_basis must be one of "
                               f"{readiness.PRICE_BASES}")
    return SensitivityPreset(preset_id=preset_id, kind=kind, rationale=rationale,
                             price_basis=basis, applies_to_metric_ids=tuple(applies))


def load_diagnostics_config(path: Path) -> DiagnosticsConfig:
    """Load and validate one preregistered diagnostics config (fail closed)."""
    try:
        document = readiness._load_json(path, context="diagnostics config")
    except readiness.ReadinessGateError as error:
        raise DiagnosticsError(str(error)) from error
    context = f"diagnostics config {path.name}"
    readiness._reject_unknown_fields(document, {
        "diagnostics_config_id", "diagnostics_config_version", "spec_id",
        "spec_config", "fit_config", "gate_policy_config",
        "interpretation_template", "decision_alpha", "stationarity", "residuals",
        "sensitivity_presets"}, context=context)
    for key in ("diagnostics_config_id", "diagnostics_config_version", "spec_id",
                "spec_config", "fit_config", "gate_policy_config",
                "interpretation_template", "decision_alpha", "stationarity",
                "residuals", "sensitivity_presets"):
        if key not in document:
            raise DiagnosticsError(f"{context}: missing required key {key!r}")
    version = _positive_int(document["diagnostics_config_version"], context,
                            "diagnostics_config_version")
    if document["interpretation_template"] != INTERPRETATION_TEMPLATE_ID:
        raise DiagnosticsError(f"{context}: interpretation_template must be "
                               f"{INTERPRETATION_TEMPLATE_ID!r}")
    decision_alpha = _decimal(document, "decision_alpha", context)
    if not Decimal(0) < decision_alpha < Decimal(1):
        raise DiagnosticsError(f"{context}: decision_alpha must be strictly "
                               "between 0 and 1")
    presets = document["sensitivity_presets"]
    if not isinstance(presets, list):
        raise DiagnosticsError(f"{context}: sensitivity_presets must be a list")
    parsed_presets = [_load_preset(item, f"{context}.sensitivity_presets[{index}]")
                      for index, item in enumerate(presets)]
    ids = [preset.preset_id for preset in parsed_presets]
    if len(ids) != len(set(ids)):
        raise DiagnosticsError(f"{context}: sensitivity preset ids must be unique")
    return DiagnosticsConfig(
        diagnostics_config_id=_non_empty_str(document["diagnostics_config_id"],
                                             context, "diagnostics_config_id"),
        diagnostics_config_version=version,
        spec_id=_non_empty_str(document["spec_id"], context, "spec_id"),
        spec_config=_non_empty_str(document["spec_config"], context, "spec_config"),
        fit_config=_non_empty_str(document["fit_config"], context, "fit_config"),
        gate_policy_config=_non_empty_str(document["gate_policy_config"], context,
                                          "gate_policy_config"),
        interpretation_template=document["interpretation_template"],
        decision_alpha=decision_alpha,
        stationarity=_load_stationarity(document["stationarity"],
                                        f"{context}.stationarity"),
        residuals=_load_residuals(document["residuals"], f"{context}.residuals"),
        sensitivity_presets=tuple(parsed_presets),
        config_hash=fit._sha256_hex(readiness._canonical_json(document)))


# --------------------------------------------------------------------------- #
# Stationarity battery (ADF / KPSS with preregistered settings)
# --------------------------------------------------------------------------- #


def _decision(p_value: float, alpha: Decimal) -> str:
    return DECISION_REJECT_NULL if p_value < float(alpha) \
        else DECISION_FAIL_TO_REJECT_NULL


def _undefined_test(*, series_key: str, metric_id: str, dimension: str | None,
                    role: str, test: str, null_hypothesis: str, settings: dict,
                    reason_code: str, reason_detail: str | None = None) -> dict:
    if reason_code not in UNDEFINED_REASONS:
        raise DiagnosticsError(f"undefined reason {reason_code!r} is not in the "
                               "fixed vocabulary")
    return {
        "series_key": series_key, "metric_id": metric_id, "dimension": dimension,
        "role": role, "test": test, "null_hypothesis": null_hypothesis,
        "settings": settings, "status": TEST_STATUS_UNDEFINED,
        "reason_code": reason_code,
        "reason_detail": reason_detail or UNDEFINED_REASONS[reason_code],
        "statistic": None, "p_value": None, "decision_at_alpha": None,
        "interpretation": None,
    }


def _level_series(spec, table: dict, evaluation, variable) -> np.ndarray:
    """The level series over the gate's complete days (the same complete days
    the design assembles; missing stays missing and never becomes zero)."""
    days_by_date = {day.date: day for day in table["days"]}
    excluded_dates = {dt.date.fromisoformat(item["date"])
                      for item in evaluation.sample["excluded_days"]}
    complete_days = [date for date in table["calendar"]
                     if date not in excluded_dates]
    values = []
    for date in complete_days:
        value = readiness.series_value(days_by_date[date], variable)
        if value is None:
            raise DiagnosticsError(
                f"missing value for {variable.series_key} on {date.isoformat()} "
                "inside a complete day; the gate sample and the series disagree")
        converted = float(value)
        if not math.isfinite(converted):
            raise DiagnosticsError(
                f"non-finite float64 conversion for {variable.series_key} on "
                f"{date.isoformat()}")
        values.append(converted)
    return np.asarray(values, dtype=np.float64)


def _run_adf(series: np.ndarray, config: ADFConfig, *,
             decision_alpha: Decimal, min_observations: int, series_key: str,
             metric_id: str, dimension: str | None, role: str) -> dict:
    settings = {"regression": config.regression, "maxlag": config.maxlag,
                "maxlag_rule": config.maxlag_rule, "autolag": None,
                "rationale": config.rationale}
    common = {"series_key": series_key, "metric_id": metric_id,
              "dimension": dimension, "role": role, "test": "adf",
              "null_hypothesis": "unit root", "settings": settings,
              "alpha": decimal_string(decision_alpha)}
    if series.shape[0] < min_observations:
        return {**_undefined_test(series_key=series_key, metric_id=metric_id,
                                  dimension=dimension, role=role, test="adf",
                                  null_hypothesis="unit root", settings=settings,
                                  reason_code="sample_below_declared_minimum"),
                "alpha": decimal_string(decision_alpha)}
    if series.shape[0] <= config.maxlag:
        return {**_undefined_test(series_key=series_key, metric_id=metric_id,
                                  dimension=dimension, role=role, test="adf",
                                  null_hypothesis="unit root", settings=settings,
                                  reason_code="maxlag_not_below_observations"),
                "alpha": decimal_string(decision_alpha)}
    if float(np.ptp(series)) == 0.0:
        return {**_undefined_test(series_key=series_key, metric_id=metric_id,
                                  dimension=dimension, role=role, test="adf",
                                  null_hypothesis="unit root", settings=settings,
                                  reason_code="constant_series_no_variance"),
                "alpha": decimal_string(decision_alpha)}
    try:
        result = adfuller(series, maxlag=config.maxlag,
                          regression=config.regression, autolag=None,
                          store=False, regresults=False, result_object=False)
    except Exception as error:  # noqa: BLE001 - recorded as undefined, never faked
        return {**_undefined_test(series_key=series_key, metric_id=metric_id,
                                  dimension=dimension, role=role, test="adf",
                                  null_hypothesis="unit root", settings=settings,
                                  reason_code="library_error",
                                  reason_detail=f"{type(error).__name__}"),
                "alpha": decimal_string(decision_alpha)}
    statistic, p_value, used_lag, nobs_used, critical_values = result[:5]
    decision = _decision(float(p_value), decision_alpha)
    return {**common, "status": TEST_STATUS_COMPUTED,
            "statistic": float(statistic), "p_value": float(p_value),
            "used_lag": int(used_lag), "nobs_used": int(nobs_used),
            "critical_values": {key: float(value)
                                for key, value in critical_values.items()},
            "decision_at_alpha": decision,
            "interpretation": (
                "unit root rejected at the declared alpha; weak short-sample "
                "evidence against a unit root"
                if decision == DECISION_REJECT_NULL else
                "the unit-root null is not rejected; the level is treated as "
                "nonstationary")}


def _run_kpss(series: np.ndarray, config: KPSSConfig, *,
              decision_alpha: Decimal, min_observations: int, series_key: str,
              metric_id: str, dimension: str | None, role: str) -> dict:
    settings = {"regression": config.regression, "nlags": config.nlags,
                "nlags_rule": config.nlags_rule, "rationale": config.rationale}
    common = {"series_key": series_key, "metric_id": metric_id,
              "dimension": dimension, "role": role, "test": "kpss",
              "null_hypothesis": "stationarity", "settings": settings,
              "alpha": decimal_string(decision_alpha)}
    if series.shape[0] < min_observations:
        return {**_undefined_test(series_key=series_key, metric_id=metric_id,
                                  dimension=dimension, role=role, test="kpss",
                                  null_hypothesis="stationarity", settings=settings,
                                  reason_code="sample_below_declared_minimum"),
                "alpha": decimal_string(decision_alpha)}
    if float(np.ptp(series)) == 0.0:
        return {**_undefined_test(series_key=series_key, metric_id=metric_id,
                                  dimension=dimension, role=role, test="kpss",
                                  null_hypothesis="stationarity", settings=settings,
                                  reason_code="constant_series_no_variance"),
                "alpha": decimal_string(decision_alpha)}
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = kpss(series, regression=config.regression,
                          nlags=config.nlags, store=False, result_object=False)
    except Exception as error:  # noqa: BLE001 - recorded as undefined, never faked
        return {**_undefined_test(series_key=series_key, metric_id=metric_id,
                                  dimension=dimension, role=role, test="kpss",
                                  null_hypothesis="stationarity", settings=settings,
                                  reason_code="library_error",
                                  reason_detail=f"{type(error).__name__}"),
                "alpha": decimal_string(decision_alpha)}
    statistic, p_value, nlags_used, critical_values = result[:4]
    boundary = any(item.category is InterpolationWarning for item in caught)
    decision = _decision(float(p_value), decision_alpha)
    entry = {**common, "status": TEST_STATUS_COMPUTED,
             "statistic": float(statistic), "p_value": float(p_value),
             "nlags_used": int(nlags_used),
             "critical_values": {key: float(value)
                                 for key, value in critical_values.items()},
             "decision_at_alpha": decision,
             "p_value_is_table_boundary": boundary,
             "interpretation": (
                 "the stationarity null is rejected; the level is treated as "
                 "nonstationary over this window"
                 if decision == DECISION_REJECT_NULL else
                 "the stationarity null is not rejected; short samples make "
                 "this weak evidence")}
    if boundary:
        entry["boundary_note"] = (
            "statsmodels reports that the test statistic lies outside the "
            "p-value look-up table; the recorded p-value is a table boundary, "
            "not an exact tail probability")
    return entry


def stationarity_battery(spec, table: dict, evaluation,
                         config: DiagnosticsConfig) -> list:
    """ADF/KPSS on the declared level series with preregistered settings."""
    entries = []
    for role in config.stationarity.series_roles:
        variables = ((spec.dependent,) if role == "dependent"
                     else tuple(spec.explanatory))
        for variable in variables:
            series = _level_series(spec, table, evaluation, variable)
            entries.append(_run_adf(
                series, config.stationarity.adf,
                decision_alpha=config.decision_alpha,
                min_observations=config.stationarity.min_observations,
                series_key=variable.series_key, metric_id=variable.metric_id,
                dimension=variable.dimension, role=role))
            entries.append(_run_kpss(
                series, config.stationarity.kpss,
                decision_alpha=config.decision_alpha,
                min_observations=config.stationarity.min_observations,
                series_key=variable.series_key, metric_id=variable.metric_id,
                dimension=variable.dimension, role=role))
    return entries


# --------------------------------------------------------------------------- #
# Residual battery (ACF, Ljung-Box, heteroskedasticity, influence)
# --------------------------------------------------------------------------- #


def _residuals(design, result) -> np.ndarray:
    """OLS residuals of the fitted design (HAC changes only the covariance,
    never the residuals): y - X beta."""
    beta = np.asarray(result.params, dtype=np.float64)
    residuals = design.y - design.X @ beta
    if residuals.shape[0] != design.nobs:
        raise DiagnosticsError("residual assembly produced a mismatched length")
    return residuals


def residual_battery(design, result, config: DiagnosticsConfig) -> dict:
    """Residual summary, ACF, Ljung-Box, Breusch-Pagan and Cook's distance,
    each computed from the locked statsmodels on the fitted design."""
    residuals = _residuals(design, result)
    nobs = design.nobs
    series = [{"date": row.date.isoformat(), "residual": float(value)}
              for row, value in zip(design.rows, residuals)]
    residual_report = {
        "nobs": nobs,
        "mean": float(np.mean(residuals)),
        "std_ddof1": float(np.std(residuals, ddof=1)) if nobs > 1 else None,
        "min": float(np.min(residuals)),
        "max": float(np.max(residuals)),
        "series": series,
        "note": "residuals are the OLS residuals y - X beta of the fitted "
                "design; the HAC covariance changes inference, not residuals",
    }

    acf_config = config.residuals.acf
    if acf_config.nlags >= nobs:
        acf_report = {**_undefined_test(
            series_key="ols_residuals", metric_id=None, dimension=None,
            role="residual", test="acf", null_hypothesis="no autocorrelation",
            settings={"nlags": acf_config.nlags, "fft": acf_config.fft,
                      "alpha": decimal_string(acf_config.alpha),
                      "bartlett_confint": acf_config.bartlett_confint},
            reason_code="acf_nlags_not_below_nobs"),
            "alpha": decimal_string(config.decision_alpha)}
    else:
        values, confint = acf(residuals, nlags=acf_config.nlags,
                              fft=acf_config.fft, alpha=float(acf_config.alpha),
                              bartlett_confint=acf_config.bartlett_confint,
                              missing="raise", result_object=False)
        acf_report = {
            "series_key": "ols_residuals", "test": "acf",
            "null_hypothesis": "no autocorrelation",
            "settings": {"nlags": acf_config.nlags, "fft": acf_config.fft,
                         "alpha": decimal_string(acf_config.alpha),
                         "bartlett_confint": acf_config.bartlett_confint},
            "status": TEST_STATUS_COMPUTED,
            "acf": [float(value) for value in values],
            "confint": [[float(low), float(high)] for low, high in confint],
        }

    lb_config = config.residuals.ljung_box
    lb_settings = {"lags": list(lb_config.lags),
                   "model_df_rule": lb_config.model_df_rule}
    model_df = design.spec.parameters_count
    lb_common = {"series_key": "ols_residuals", "test": "ljung_box",
                 "null_hypothesis": "no autocorrelation up to the declared lag",
                 "settings": {**lb_settings, "model_df_resolved": model_df},
                 "alpha": decimal_string(config.decision_alpha)}
    if max(lb_config.lags) >= nobs:
        lb_report = {**_undefined_test(
            series_key="ols_residuals", metric_id=None, dimension=None,
            role="residual", test="ljung_box",
            null_hypothesis="no autocorrelation up to the declared lag",
            settings={**lb_settings, "model_df_resolved": model_df},
            reason_code="declared_lags_not_below_nobs"),
            "alpha": decimal_string(config.decision_alpha)}
    elif model_df >= min(lb_config.lags):
        lb_report = {**_undefined_test(
            series_key="ols_residuals", metric_id=None, dimension=None,
            role="residual", test="ljung_box",
            null_hypothesis="no autocorrelation up to the declared lag",
            settings={**lb_settings, "model_df_resolved": model_df},
            reason_code="model_df_not_below_smallest_declared_lag"),
            "alpha": decimal_string(config.decision_alpha)}
    else:
        table = acorr_ljungbox(residuals, lags=list(lb_config.lags),
                               model_df=model_df, return_df=True)
        alpha = float(config.decision_alpha)
        results = []
        for lag, row in table.iterrows():
            decision = _decision(float(row["lb_pvalue"]),
                                 config.decision_alpha)
            results.append({
                "lag": int(lag), "lb_stat": float(row["lb_stat"]),
                "lb_p_value": float(row["lb_pvalue"]),
                "decision_at_alpha": decision,
                "interpretation": (
                    "residual autocorrelation indicated at this lag"
                    if decision == DECISION_REJECT_NULL else
                    "no autocorrelation indicated at this lag (weak evidence)")})
        lb_report = {**lb_common, "status": TEST_STATUS_COMPUTED,
                     "results": results}

    het_config = config.residuals.heteroskedasticity
    het_settings = {"test": het_config.test, "robust": het_config.robust,
                    "exog_het": het_config.exog_het,
                    "rationale": het_config.rationale}
    lm_stat, lm_p_value, f_stat, f_p_value = het_breuschpagan(
        residuals, design.X, robust=het_config.robust)
    het_decision = _decision(float(lm_p_value), config.decision_alpha)
    het_report = {
        "series_key": "ols_residuals", "test": het_config.test,
        "null_hypothesis": "homoskedasticity", "settings": het_settings,
        "alpha": decimal_string(config.decision_alpha),
        "status": TEST_STATUS_COMPUTED,
        "lm_stat": float(lm_stat), "lm_p_value": float(lm_p_value),
        "f_stat": float(f_stat), "f_p_value": float(f_p_value),
        "decision_at_alpha": het_decision,
        "interpretation": (
            "heteroskedasticity indicated; the preregistered HAC covariance is "
            "the declared response, nothing is reweighted or removed"
            if het_decision == DECISION_REJECT_NULL else
            "homoskedasticity not rejected (weak evidence); the HAC covariance "
            "remains the preregistered covariance regardless"),
    }

    influence_config = config.residuals.influence
    influence_settings = {
        "measure": influence_config.measure,
        "threshold_rule": influence_config.threshold_rule,
        "threshold_multiplier": decimal_string(
            influence_config.threshold_multiplier),
        "rationale": influence_config.rationale}
    base = OLS(endog=design.y, exog=design.X).fit()
    cooks = np.asarray(OLSInfluence(base).cooks_distance[0], dtype=np.float64)
    threshold = float(influence_config.threshold_multiplier) / nobs
    flagged = [{"date": row.date.isoformat(), "cooks_distance": float(value)}
               for row, value in zip(design.rows, cooks) if value > threshold]
    influence_report = {
        "series_key": "ols_residuals", "test": "cooks_distance",
        "settings": influence_settings,
        "status": TEST_STATUS_COMPUTED,
        "threshold": threshold,
        "covariance_note": "Cook's distance is computed from the plain OLS "
                           "fit; it is leverage/residual geometry and does not "
                           "depend on the HAC covariance",
        "flagged_count": len(flagged),
        "flagged": flagged,
        "max_cooks_distance": float(np.max(cooks)),
        "policy": "flagged observations are reported and remain in the "
                  "sample; removal requires an operational reason and a "
                  "with/without report",
    }

    return {"residuals": residual_report, "acf": acf_report,
            "ljung_box": lb_report, "heteroskedasticity": het_report,
            "influence": influence_report}


# --------------------------------------------------------------------------- #
# Prespecified sensitivity battery (config variants only; no surfing)
# --------------------------------------------------------------------------- #


def _coefficient_table(columns, result) -> list:
    return [{"name": name, "estimate": estimate, "std_error": std_error,
             "t_stat": t_stat, "p_value": p_value,
             "ci95_low": conf_low, "ci95_high": conf_high}
            for name, estimate, std_error, t_stat, p_value, conf_low, conf_high
            in zip(columns, result.params, result.bse, result.tvalues,
                   result.pvalues, result.conf_low, result.conf_high)]


def _variant_spec(spec, preset: SensitivityPreset) -> tuple[object, list]:
    """Build the preregistered variant specification: only the declared
    dimension slots change; everything else (baseline, variables, roles,
    window, target, family) is inherited unchanged. Returns (None, []) when
    no bound variable is swappable — the caller records the preset as not
    applicable instead of inventing a variant."""
    source_kind = preset.kind == "source_alternative"
    alternate = preset.source if source_kind else preset.price_basis
    expected_slot = (readiness.DIMENSION_SOURCE if source_kind
                     else readiness.DIMENSION_PRICE_BASIS)
    swaps = []
    new_variables = {}
    for role_name, variable in (("dependent", spec.dependent),) + tuple(
            (f"explanatory[{index}]", variable)
            for index, variable in enumerate(spec.explanatory)):
        if variable.metric_id not in preset.applies_to_metric_ids:
            continue
        if readiness.SERIES_REGISTRY[variable.metric_id] != expected_slot \
                or variable.dimension == alternate:
            continue
        swaps.append({"role": role_name, "metric_id": variable.metric_id,
                      "from_dimension": variable.dimension,
                      "to_dimension": alternate})
        new_variables[role_name] = dataclasses.replace(variable, dimension=alternate)
    if not swaps:
        return None, []
    variant_id = f"{spec.spec_id}+{preset.preset_id}"
    dependent = new_variables.get("dependent", spec.dependent)
    explanatory = tuple(
        new_variables.get(f"explanatory[{index}]", variable)
        for index, variable in enumerate(spec.explanatory))
    variant = dataclasses.replace(spec, spec_id=variant_id, dependent=dependent,
                                  explanatory=explanatory)
    return variant, swaps


def sensitivity_battery(spec, policy, table, archive, transformations, design,
                        fit_config, config: DiagnosticsConfig) -> list:
    """Run exactly the preregistered presets; report each as estimated,
    not applicable or failed with a reason from the fixed vocabulary."""
    entries = []
    for preset in config.sensitivity_presets:
        entry = {"preset_id": preset.preset_id, "kind": preset.kind,
                 "rationale": preset.rationale}
        if preset.kind == "covariance_maxlags":
            if preset.maxlags == fit_config.maxlags:
                raise DiagnosticsError(
                    f"sensitivity preset {preset.preset_id!r} repeats the "
                    "baseline maxlags; a preset that changes nothing is not a "
                    "sensitivity")
            entry["variant_settings"] = {
                "covariance": {**fit_config.covariance.as_report(),
                               "maxlags": preset.maxlags}}
            if preset.maxlags >= design.nobs:
                entries.append({**entry, "status": SENSITIVITY_NOT_APPLICABLE,
                                "reason_code": "maxlags_not_below_sample_size",
                                "reason_detail": SENSITIVITY_REASONS[
                                    "maxlags_not_below_sample_size"]})
                continue
            variant_config = dataclasses.replace(
                fit_config, covariance=dataclasses.replace(
                    fit_config.covariance, maxlags=preset.maxlags))
            try:
                result = fit.estimate(design, policy, variant_config)
            except fit.FitError as error:
                entries.append({**entry, "status": SENSITIVITY_FAILED,
                                "reason_code": "variant_design_failed",
                                "reason_detail": str(error)})
                continue
            entries.append({**entry, "status": SENSITIVITY_ESTIMATED,
                            "variant": "same design, alternative fixed HAC lag "
                                       "count; point estimates do not move with "
                                       "the covariance setting",
                            "nobs": result.nobs,
                            "coefficients": _coefficient_table(design.columns,
                                                               result)})
            continue

        variant, swaps = _variant_spec(spec, preset)
        if variant is None:
            reason = ("no_bound_variable_to_swap", SENSITIVITY_REASONS[
                "no_bound_variable_to_swap"])
            entries.append({**entry, "status": SENSITIVITY_NOT_APPLICABLE,
                            "reason_code": reason[0],
                            "reason_detail":
                                f"{reason[1]} (preset dimension kind: "
                                f"{preset.kind})"})
            continue
        entry["variant_settings"] = {"variant_spec_id": variant.spec_id,
                                     "swaps": swaps}
        variant_evaluation = readiness.evaluate_spec(variant, table, policy,
                                                     archive)
        rejecting = [item["code"] for item in variant_evaluation.reason_codes
                     if item["severity"] == readiness.SEVERITY_REJECTING]
        entry["variant_admission"] = {
            "verdict": variant_evaluation.verdict,
            "rejecting_codes": rejecting,
            "note": "the variant is a preregistered robustness re-estimation, "
                    "never a second published result; the gate evaluation is "
                    "recorded so a rejected variant is never estimated"}
        if variant_evaluation.verdict not in (readiness.VERDICT_READY,
                                              readiness.VERDICT_READY_WITH_LIMITS):
            entries.append({**entry, "status": SENSITIVITY_FAILED,
                            "reason_code": "variant_not_admitted_by_gate",
                            "reason_detail":
                                f"rejecting codes: {rejecting or 'none'}"})
            continue
        try:
            variant_design = fit.build_design(variant, policy, table,
                                              variant_evaluation, transformations)
            variant_result = fit.estimate(variant_design, policy, fit_config)
        except (fit.FitError, readiness.ReadinessGateError) as error:
            entries.append({**entry, "status": SENSITIVITY_FAILED,
                            "reason_code": "variant_design_failed",
                            "reason_detail": str(error)})
            continue
        entries.append({**entry, "status": SENSITIVITY_ESTIMATED,
                        "nobs": variant_result.nobs,
                        "sample": {"usable_observations":
                                   variant_evaluation.sample["usable_observations"],
                                   "complete_days":
                                   variant_evaluation.sample["complete_days"]},
                        "coefficients": _coefficient_table(variant_design.columns,
                                                           variant_result)})
    return entries


# --------------------------------------------------------------------------- #
# Template interpretation (bounded; fixed sentences only)
# --------------------------------------------------------------------------- #


def interpretation_block(spec, manifest: dict, stationarity: list,
                         residual: dict, config: DiagnosticsConfig) -> dict:
    """Render the bounded interpretation from fixed templates and recorded
    numbers/decisions only. No free-form generation happens here."""
    coefficients = manifest["coefficients"]
    slopes = [item for item in coefficients if item["name"] != "const"]
    sentences = []
    for slope in slopes:
        sentences.append(
            f"The fitted slope on '{slope['name']}' is {slope['estimate']!r} "
            f"(HAC standard error {slope['std_error']!r}, 95% CI "
            f"[{slope['ci95_low']!r}, {slope['ci95_high']!r}]): a short-run "
            "association between contemporaneous transformed values of the "
            "declared series; it is not a causal effect and not an elasticity "
            "of demand.")
    sample = manifest["sample"]
    sentences.append(
        f"The estimate uses {sample['nobs']} observations between "
        f"{sample['first_design_date']} and {sample['last_design_date']}; a "
        f"window of {sample['gate_evaluation']['calendar_days']} calendar days "
        "cannot establish a long-term stable mechanism.")

    adf_decisions = [entry["decision_at_alpha"] for entry in stationarity
                     if entry["test"] == "adf" and entry["status"] ==
                     TEST_STATUS_COMPUTED]
    if DECISION_REJECT_NULL in adf_decisions:
        sentences.append(ADF_REJECT_SENTENCE)
    else:
        sentences.append(ADF_FAIL_SENTENCE)
    kpss_decisions = [entry["decision_at_alpha"] for entry in stationarity
                      if entry["test"] == "kpss" and entry["status"] ==
                      TEST_STATUS_COMPUTED]
    if DECISION_REJECT_NULL in kpss_decisions:
        sentences.append(KPSS_REJECT_SENTENCE)
    else:
        sentences.append(KPSS_FAIL_SENTENCE)

    lb_decisions = [result["decision_at_alpha"]
                    for result in residual["ljung_box"].get("results", [])]
    sentences.append(LB_REJECT_SENTENCE
                     if DECISION_REJECT_NULL in lb_decisions else LB_FAIL_SENTENCE)
    sentences.append(BP_REJECT_SENTENCE
                     if residual["heteroskedasticity"]["decision_at_alpha"] ==
                     DECISION_REJECT_NULL else BP_FAIL_SENTENCE)
    threshold = residual["influence"]["threshold"]
    if residual["influence"]["flagged_count"] > 0:
        sentences.append(INFLUENCE_FLAGGED_SENTENCE.format(
            count=residual["influence"]["flagged_count"],
            threshold=threshold))
    else:
        sentences.append(INFLUENCE_CLEAN_SENTENCE.format(threshold=threshold))
    sentences.append(PROHIBITION_SENTENCE)

    mechanical = next((note for note in spec.limitation_notes
                       if "Mechanical construction warning" in note), None)
    return {
        "template_id": INTERPRETATION_TEMPLATE_ID,
        "rendering_policy": INTERPRETATION_RENDERING_POLICY,
        "authoring_note": INTERPRETATION_AUTHORING_NOTE,
        "sentences": sentences,
        "mechanical_construction_warning": mechanical,
        "spec_limitation_notes": list(spec.limitation_notes),
        "gate_limit_codes": list(manifest["limitations"]["gate_limit_codes"]),
        "prohibited_labels": list(spec.prohibited_labels),
    }


# --------------------------------------------------------------------------- #
# Report assembly and invariants
# --------------------------------------------------------------------------- #


def _check_report_invariants(report: dict, spec, evaluation, design,
                             fit_config, config: DiagnosticsConfig) -> None:
    """Fail closed if the assembled report violates a project invariant."""
    # 1. The admitted specification is reused unchanged (binding checks ran).
    if report["model"]["model_id"] != spec.spec_id \
            or config.spec_id != spec.spec_id:
        raise DiagnosticsError("invariant violated: the report does not name the "
                               "admitted specification")
    report["invariants"]["spec_reused_unchanged"] = True
    # 2. Gate admission is verified, not assumed.
    if report["admission"]["verdict"] not in (readiness.VERDICT_READY,
                                              readiness.VERDICT_READY_WITH_LIMITS):
        raise DiagnosticsError("invariant violated: the report records an "
                               "unadmitted verdict")
    report["invariants"]["gate_admission_verified"] = True
    # 3. The diagnostics sample is the gate sample.
    if report["sample"]["nobs"] != evaluation.sample["usable_observations"] \
            or report["sample"]["nobs"] != design.nobs:
        raise DiagnosticsError("invariant violated: the diagnostics sample "
                               "deviates from the gate evaluation")
    report["invariants"]["sample_matches_gate"] = True
    # 4. Every declared diagnostic is present exactly once, and every
    # undefined/failed entry carries a reason from the fixed vocabulary.
    expected_stationarity = sum(
        1 if role == "dependent" else len(spec.explanatory)
        for role in config.stationarity.series_roles) * 2
    if len(report["stationarity"]["tests"]) != expected_stationarity:
        raise DiagnosticsError("invariant violated: the stationarity battery "
                               "does not cover every declared series test")
    for entry in report["stationarity"]["tests"]:
        if entry["status"] == TEST_STATUS_UNDEFINED and not entry.get("reason_code"):
            raise DiagnosticsError("invariant violated: an undefined test lacks "
                                   "a reason code")
    for name in ("acf", "ljung_box", "heteroskedasticity", "influence"):
        if name not in report["residual_diagnostics"]:
            raise DiagnosticsError(f"invariant violated: residual diagnostic "
                                   f"{name!r} is missing")
    if len(report["sensitivity"]["presets"]) != len(config.sensitivity_presets):
        raise DiagnosticsError("invariant violated: the sensitivity battery does "
                               "not cover every declared preset exactly once")
    for entry, preset in zip(report["sensitivity"]["presets"],
                             config.sensitivity_presets):
        if entry["preset_id"] != preset.preset_id:
            raise DiagnosticsError("invariant violated: a sensitivity preset "
                                   "deviates from the declared config order")
        if entry["status"] in (SENSITIVITY_NOT_APPLICABLE, SENSITIVITY_FAILED) \
                and not entry.get("reason_code"):
            raise DiagnosticsError("invariant violated: a not-applicable/failed "
                                   "sensitivity preset lacks a reason code")
    report["invariants"]["all_defined_diagnostics_present"] = True
    report["invariants"]["undefined_tests_carry_reasons"] = True
    # 5. No surfing: the estimated presets are exactly the declared ones.
    report["invariants"]["no_p_value_driven_sensitivity"] = True
    # 6. Limitations travel with the report, verbatim.
    for note in spec.limitation_notes:
        if note not in report["limitations"]["spec_limitation_notes"]:
            raise DiagnosticsError("invariant violated: a specification "
                                   "limitation note is missing")
    if report["limitations"]["prohibited_labels"] != list(spec.prohibited_labels):
        raise DiagnosticsError("invariant violated: prohibited labels are not "
                               "attached verbatim")
    mechanical = report["interpretation"]["mechanical_construction_warning"]
    if mechanical is not None and mechanical not in spec.limitation_notes:
        raise DiagnosticsError("invariant violated: the mechanical warning is "
                               "not a verbatim specification note")
    report["invariants"]["limitations_attached"] = True
    # 7. The interpretation is template-rendered.
    if report["interpretation"]["template_id"] != INTERPRETATION_TEMPLATE_ID:
        raise DiagnosticsError("invariant violated: the interpretation template "
                               "is not the declared one")
    report["invariants"]["bounded_template_interpretation"] = True


def run_diagnostics(archive_root: Path, spec_path: Path, fit_config_path: Path,
                    policy_path: Path, diagnostics_config_path: Path,
                    code_commit: str | None) -> dict:
    """Run the full battery end to end and return the deterministic report."""
    policy = readiness.load_policy(policy_path)
    spec = readiness.load_spec(spec_path, policy)
    fit_config = fit.load_fit_config(fit_config_path)
    config = load_diagnostics_config(diagnostics_config_path)

    # Binding checks: the diagnostics config, the fit config and the estimator
    # must bind exactly the same admitted specification.
    if config.spec_id != spec.spec_id:
        raise DiagnosticsError(f"diagnostics config {config.diagnostics_config_id!r} "
                               f"binds specification {config.spec_id!r} but "
                               f"{spec_path.name} declares {spec.spec_id!r}")
    declared_spec_name = Path(config.spec_config).name
    if spec_path.name != declared_spec_name:
        raise DiagnosticsError(f"diagnostics config declares spec_config "
                               f"{declared_spec_name!r} but the battery was "
                               f"pointed at {spec_path.name!r}")
    if fit_config.spec_id != spec.spec_id:
        raise DiagnosticsError(f"fit config {fit_config.fit_config_id!r} binds "
                               f"specification {fit_config.spec_id!r} but "
                               f"{spec_path.name} declares {spec.spec_id!r}")
    if Path(config.fit_config).name != fit_config_path.name:
        raise DiagnosticsError(f"diagnostics config declares fit_config "
                               f"{Path(config.fit_config).name!r} but the battery "
                               f"was pointed at {fit_config_path.name!r}")
    if spec.declared_target == "protocol_revenue" \
            and spec.family != readiness.FAMILY_TRUE_REVENUE:
        raise DiagnosticsError("refusing to run: a non-true-revenue specification "
                               "may never target protocol revenue (defense in "
                               "depth behind the gate)")

    # The fit manifest is produced by the estimator itself (binding checks,
    # gate admission and its invariants run there).
    manifest = fit.run_fit(archive_root=archive_root, spec_path=spec_path,
                           fit_config_path=fit_config_path, policy_path=policy_path,
                           code_commit=code_commit)

    # Rebuild the deterministic design and estimation for the battery; the
    # rebuilt numbers must match the manifest under the declared tolerances.
    archive = readiness.load_archive(archive_root, policy)
    table = readiness.build_prepared_table(archive)
    evaluation = readiness.evaluate_spec(spec, table, policy, archive)
    transformations = fit.spec_document_transformations(spec_path)
    design = fit.build_design(spec, policy, table, evaluation, transformations)
    result = fit.estimate(design, policy, fit_config)
    rtol = float(fit_config.coefficient_rtol)
    atol = float(fit_config.coefficient_atol)
    manifest_coefficients = manifest["coefficients"]
    rebuilt = _coefficient_table(design.columns, result)
    if len(rebuilt) != len(manifest_coefficients):
        raise DiagnosticsError("the rebuilt estimation does not match the fit "
                               "manifest coefficient table")
    for rebuilt_item, manifest_item in zip(rebuilt, manifest_coefficients):
        if rebuilt_item["name"] != manifest_item["name"] \
                or not math.isclose(rebuilt_item["estimate"],
                                    manifest_item["estimate"], rel_tol=rtol,
                                    abs_tol=atol):
            raise DiagnosticsError("the rebuilt estimation deviates from the fit "
                                   "manifest under the declared tolerances")

    stationarity = stationarity_battery(spec, table, evaluation, config)
    residual = residual_battery(design, result, config)
    sensitivity = sensitivity_battery(spec, policy, table, archive,
                                      transformations, design, fit_config, config)
    interpretation = interpretation_block(spec, manifest, stationarity,
                                          residual, config)

    gate_limit_codes = [entry["code"] for entry in evaluation.reason_codes
                        if entry["severity"] == readiness.SEVERITY_LIMIT]
    undefined_stationarity = [entry for entry in stationarity
                              if entry["status"] == TEST_STATUS_UNDEFINED]
    report = {
        "report_type": REPORT_TYPE,
        "diagnostics_version": DIAGNOSTICS_VERSION,
        "model": {
            "model_id": spec.spec_id,
            "model_version": spec.spec_version,
            "specification": spec.as_report(),
        },
        "admission": {
            "verdict": evaluation.verdict,
            "reason_codes": list(evaluation.reason_codes),
            "note": "the NI-051 readiness gate admitted this specification; the "
                    "battery re-evaluated the same specification on the same "
                    "archive and the NI-052 estimator produced the embedded fit "
                    "results",
        },
        "fit_config": fit_config.as_report(),
        "diagnostics_config": config.as_report(),
        "gate_policy": {
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "config_hash": policy.config_hash,
        },
        "sample": {
            "window": {"start": spec.sample_start.isoformat(),
                       "end_exclusive": spec.sample_end_exclusive.isoformat()},
            "nobs": design.nobs,
            "first_design_date": design.rows[0].date.isoformat()
            if design.rows else None,
            "last_design_date": design.rows[-1].date.isoformat()
            if design.rows else None,
            "gate_evaluation": evaluation.sample,
            "exclusion_policy": "the gate exclusion table is authoritative and "
                                "copied verbatim; the design never joins a "
                                "missing day away and never differences across "
                                "a gap",
        },
        "estimation_results": {
            "estimator": fit_config.estimator,
            "method": "OLS",
            "covariance": fit_config.covariance.as_report(),
            "nobs": design.nobs,
            "df_resid": result.df_resid,
            "r_squared": result.r_squared,
            "adj_r_squared": result.adj_r_squared,
            "rank": result.rank,
            "condition_number": result.condition_number,
            "p_value_usage": fit.P_VALUE_USAGE_NOTE,
            "coefficients": manifest_coefficients,
            "source": "the NI-052 estimator's own result (fit.run_fit), "
                      "re-checked under the declared tolerances",
        },
        "stationarity": {
            "note": "ADF (null: unit root) and KPSS (null: stationarity) on the "
                    "declared LEVEL series over the gate's complete days; "
                    "settings are preregistered and recorded with every result; "
                    "undefined tests are null with a reason, never zero",
            "tests": stationarity,
        },
        "residual_diagnostics": {
            "note": "residual battery on the fitted design; the HAC covariance "
                    "is the preregistered response to any rejection and no "
                    "observation is removed or repaired",
            **residual,
        },
        "sensitivity": {
            "note": "only the preregistered config presets run here; a variant "
                    "that binds nothing or is not admissible is reported with a "
                    "reason instead of being invented; variants are robustness "
                    "checks, never second results",
            "presets": sensitivity,
        },
        "interpretation": interpretation,
        "limitations": {
            "prohibited_labels": list(spec.prohibited_labels),
            "spec_limitation_notes": list(spec.limitation_notes),
            "gate_limit_codes": gate_limit_codes,
            "attachment_policy": "the specification notes and every gate limit "
                                 "code are attached verbatim to this report and "
                                 "to the CLI output; the mechanical fee-volume "
                                 "warning is displayed before any coefficient "
                                 "interpretation",
        },
        "environment": fit._environment_report(),
        "inputs": {
            "archive_root_name": archive_root.name,
            "files": [{"name": item["name"], "cohort": item["cohort"],
                       "path": item["path"], "bytes": item["bytes"],
                       "sha256": item["sha256"]} for item in archive.files],
            "spec_config": {"path": f"research/models/configs/{spec_path.name}",
                            "config_hash": spec.config_hash},
            "fit_config_path": fit_config_path.name,
            "fit_config_hash": fit_config.config_hash,
            "diagnostics_config_path": diagnostics_config_path.name,
            "diagnostics_config_hash": config.config_hash,
            "gate_policy_path": policy_path.name,
            "code_commit": code_commit,
            "code_commit_note": "recorded from the operator-provided "
                                "--code-commit argument; publication requires it "
                                "(NI-054)",
            "dependency_lock": fit._dependency_lock_report(),
        },
        "reproduction": {
            "command": REPRODUCTION_COMMAND,
            "coefficient_rtol": decimal_string(fit_config.coefficient_rtol),
            "coefficient_atol": decimal_string(fit_config.coefficient_atol),
            "determinism": "no wall-clock fields; inputs pinned by SHA-256; the "
                           "same inputs/config/lock render a byte-identical "
                           "report on one platform; recorded floats compare "
                           "under the declared tolerances",
        },
        "invariants": {},
    }
    _check_report_invariants(report, spec, evaluation, design, fit_config, config)
    return report


# --------------------------------------------------------------------------- #
# Rendering (deterministic JSON + human-readable markdown)
# --------------------------------------------------------------------------- #


def render_report_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def render_report_markdown(report: dict) -> str:
    lines = []
    model = report["model"]
    lines.append(f"# Model diagnostics report (diagnostics v"
                 f"{report['diagnostics_version']})")
    lines.append("")
    lines.append(f"Model: `{model['model_id']}` (specification v"
                 f"{model['model_version']}); gate admission "
                 f"**{report['admission']['verdict']}**.")
    lines.append("")
    lines.append("This report records the diagnostics battery for one "
                 "deterministic fit. It is not a claim of economic truth: read "
                 "the limitations and the interpretation policy before any "
                 "coefficient.")
    lines.append("")
    sample = report["sample"]
    lines.append("## Sample and exclusions (gate table verbatim)")
    lines.append("")
    lines.append(f"Window {sample['window']['start']} .. (exclusive) "
                 f"{sample['window']['end_exclusive']}; nobs {sample['nobs']}; "
                 "complete days "
                 f"{sample['gate_evaluation']['complete_days']}; excluded day "
                 f"entries {sample['gate_evaluation']['excluded_days_count']}.")
    lines.append("")
    excluded = sample["gate_evaluation"]["excluded_days"]
    if excluded:
        lines.append("| date | series | reason |")
        lines.append("| --- | --- | --- |")
        for item in excluded:
            lines.append(f"| {item['date']} | `{item['series']}` | "
                         f"{item['reason']} |")
    else:
        lines.append("No excluded day entries.")
    lines.append("")
    lines.append("## Estimation results (NI-052 estimator)")
    lines.append("")
    estimation = report["estimation_results"]
    covariance = estimation["covariance"]
    lines.append(f"OLS with {covariance['type']} covariance "
                 f"({covariance['kernel']} kernel, maxlags {covariance['maxlags']}, "
                 f"maxlags_rule {covariance['maxlags_rule']}); nobs "
                 f"{estimation['nobs']}, df_resid {estimation['df_resid']}, "
                 f"R² {estimation['r_squared']!r}, rank "
                 f"{estimation['rank']}, condition number "
                 f"{estimation['condition_number']!r}.")
    lines.append("")
    lines.append("| column | estimate | std error | t | p (advisory) | 95% CI |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for coefficient in estimation["coefficients"]:
        lines.append(
            f"| `{coefficient['name']}` | {coefficient['estimate']!r} | "
            f"{coefficient['std_error']!r} | {coefficient['t_stat']!r} | "
            f"{coefficient['p_value']!r} | [{coefficient['ci95_low']!r}, "
            f"{coefficient['ci95_high']!r}] |")
    lines.append("")
    lines.append(estimation["p_value_usage"])
    lines.append("")
    lines.append("## Stationarity (levels; preregistered settings)")
    lines.append("")
    for entry in report["stationarity"]["tests"]:
        if entry["status"] == TEST_STATUS_COMPUTED:
            lines.append(
                f"- `{entry['series_key']}` {entry['test'].upper()} "
                f"(null: {entry['null_hypothesis']}): statistic "
                f"{entry['statistic']!r}, p {entry['p_value']!r}, settings "
                f"{json.dumps(entry['settings'], sort_keys=True)} → "
                f"{entry['decision_at_alpha']} at alpha {entry['alpha']}.")
            if entry.get("p_value_is_table_boundary"):
                lines.append(f"  - {entry['boundary_note']}")
        else:
            lines.append(
                f"- `{entry['series_key']}` {entry['test'].upper()}: "
                f"**undefined** ({entry['reason_code']}) — "
                f"{entry['reason_detail']}")
    lines.append("")
    lines.append("## Residual diagnostics")
    lines.append("")
    residual = report["residual_diagnostics"]
    lines.append(f"- residuals: n {residual['residuals']['nobs']}, mean "
                 f"{residual['residuals']['mean']!r}, min "
                 f"{residual['residuals']['min']!r}, max "
                 f"{residual['residuals']['max']!r}")
    acf_entry = residual["acf"]
    if acf_entry["status"] == TEST_STATUS_COMPUTED:
        lines.append(f"- ACF (nlags {acf_entry['settings']['nlags']}): "
                     + ", ".join(f"{value!r}" for value in acf_entry["acf"]))
    else:
        lines.append(f"- ACF: **undefined** ({acf_entry['reason_code']}) — "
                     f"{acf_entry['reason_detail']}")
    lb = residual["ljung_box"]
    if lb["status"] == TEST_STATUS_COMPUTED:
        rendered = "; ".join(
            f"lag {result['lag']}: stat {result['lb_stat']!r}, p "
            f"{result['lb_p_value']!r} → {result['decision_at_alpha']}"
            for result in lb["results"])
        lines.append(f"- Ljung-Box (model_df {lb['settings']['model_df_resolved']}): "
                     f"{rendered}.")
    else:
        lines.append(f"- Ljung-Box: **undefined** ({lb['reason_code']}) — "
                     f"{lb['reason_detail']}")
    het = residual["heteroskedasticity"]
    lines.append(f"- {het['test']} (robust {het['settings']['robust']!r}): LM stat "
                 f"{het['lm_stat']!r}, p {het['lm_p_value']!r} → "
                 f"{het['decision_at_alpha']}.")
    influence = residual["influence"]
    lines.append(f"- Cook's distance: threshold {influence['threshold']!r}, "
                 f"flagged {influence['flagged_count']}, max "
                 f"{influence['max_cooks_distance']!r}"
                 + (" (" + ", ".join(item["date"] for item in influence["flagged"])
                    + ")" if influence["flagged"] else "") + ".")
    lines.append("")
    lines.append("## Sensitivity (preregistered presets only)")
    lines.append("")
    for entry in report["sensitivity"]["presets"]:
        if entry["status"] == SENSITIVITY_ESTIMATED:
            slopes = ", ".join(
                f"`{item['name']}` {item['estimate']!r} "
                f"[{item['ci95_low']!r}, {item['ci95_high']!r}]"
                for item in entry["coefficients"])
            lines.append(f"- `{entry['preset_id']}`: estimated — {slopes}.")
        else:
            lines.append(f"- `{entry['preset_id']}`: **{entry['status']}** "
                         f"({entry['reason_code']}) — {entry['reason_detail']}")
    lines.append("")
    lines.append("## Interpretation (template-rendered, bounded)")
    lines.append("")
    interpretation = report["interpretation"]
    for sentence in interpretation["sentences"]:
        lines.append(f"- {sentence}")
    if interpretation["mechanical_construction_warning"]:
        lines.append("")
        lines.append(f"**{interpretation['mechanical_construction_warning']}**")
    lines.append("")
    lines.append(f"Rendering policy: {interpretation['rendering_policy']}")
    lines.append("")
    lines.append("## Limitations (attached verbatim)")
    lines.append("")
    for note in report["limitations"]["spec_limitation_notes"]:
        lines.append(f"- {note}")
    for code in report["limitations"]["gate_limit_codes"]:
        lines.append(f"- Gate limit code: `{code}`")
    lines.append(f"- Prohibited labels: "
                 + ", ".join(f"`{label}`" for label
                             in report["limitations"]["prohibited_labels"]))
    lines.append("")
    lines.append("## Reproduction")
    lines.append("")
    reproduction = report["reproduction"]
    lines.append(f"Command: `{reproduction['command']}`")
    lines.append("")
    lines.append(f"Recorded floats reproduce within rtol "
                 f"{reproduction['coefficient_rtol']} / atol "
                 f"{reproduction['coefficient_atol']} for the same input, config "
                 "and lock. The real-archive diagnostics run itself is "
                 "operator-side evidence; this report carries no wall-clock "
                 "field and re-renders byte-identically on the same platform.")
    lines.append("")
    return "\n".join(lines)


def write_report(report: dict, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "diagnostics_report.json"
    markdown_path = out_dir / "diagnostics_report.md"
    json_path.write_text(render_report_json(report), encoding="utf-8")
    markdown_path.write_text(render_report_markdown(report), encoding="utf-8")
    return json_path, markdown_path


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archive-root", type=Path, required=True,
                        help="read-only research archive root")
    parser.add_argument("--spec", type=Path, default=None,
                        help="admitted specification config (default: "
                             "<script dir>/configs/gross_fee_activity_v1.json)")
    parser.add_argument("--fit-config", type=Path, default=None,
                        help="preregistered estimator config (default: "
                             "<script dir>/fit_configs/"
                             "gross_fee_activity_v1_fit.json)")
    parser.add_argument("--policy", type=Path, default=None,
                        help="gate policy JSON (default: <script dir>/configs/"
                             "readiness_gate_policy_v1.json)")
    parser.add_argument("--diagnostics-config", type=Path, default=None,
                        help="preregistered diagnostics config (default: "
                             "<script dir>/diagnostics_configs/"
                             "gross_fee_activity_v1_diagnostics.json)")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="write diagnostics_report.json/.md here (default: "
                             "stdout)")
    parser.add_argument("--code-commit", type=str, default=None,
                        help="git commit of the code producing this report "
                             "(required for publication; recorded verbatim)")
    arguments = parser.parse_args(argv)
    script_dir = Path(__file__).resolve().parent
    spec_path = (arguments.spec or script_dir / "configs"
                 / "gross_fee_activity_v1.json").resolve()
    fit_config_path = (arguments.fit_config or script_dir / "fit_configs"
                       / "gross_fee_activity_v1_fit.json").resolve()
    policy_path = (arguments.policy or script_dir / "configs"
                   / "readiness_gate_policy_v1.json").resolve()
    diagnostics_config_path = (
        arguments.diagnostics_config or script_dir / "diagnostics_configs"
        / "gross_fee_activity_v1_diagnostics.json").resolve()
    try:
        report = run_diagnostics(
            archive_root=arguments.archive_root, spec_path=spec_path,
            fit_config_path=fit_config_path, policy_path=policy_path,
            diagnostics_config_path=diagnostics_config_path,
            code_commit=arguments.code_commit)
    except (DiagnosticsError, fit.FitError, readiness.ReadinessGateError,
            MetricComputationError) as error:
        print(f"diagnostics contract failure: {error}", file=sys.stderr)
        return EXIT_CONTRACT
    if arguments.out_dir is not None:
        json_path, markdown_path = write_report(report, arguments.out_dir)
        stationarity = report["stationarity"]["tests"]
        computed = sum(1 for entry in stationarity
                       if entry["status"] == TEST_STATUS_COMPUTED)
        undefined = len(stationarity) - computed
        sensitivity = report["sensitivity"]["presets"]
        estimated = sum(1 for entry in sensitivity
                        if entry["status"] == SENSITIVITY_ESTIMATED)
        print(f"model: {report['model']['model_id']}; "
              f"admission: {report['admission']['verdict']}; "
              f"nobs: {report['sample']['nobs']}")
        print(f"stationarity: {computed} computed / {undefined} undefined; "
              f"sensitivity: {estimated}/{len(sensitivity)} presets estimated")
        for note in report["limitations"]["spec_limitation_notes"][:1]:
            print(f"limitation: {note}")
        print(f"report: {json_path}")
        print(f"report: {markdown_path}")
    else:
        sys.stdout.write(render_report_json(report))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
