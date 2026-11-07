"""NI-053 tests: diagnostics, robustness and interpretation artifacts.

Everything here is invented synthetic data written into disposable
temporary directories; the real research archive is never touched and no
real-data diagnostics result is claimed anywhere (the real-archive
diagnostics run is operator-side evidence, like the NI-051 gate and NI-052
fit runs). The battery outputs are compared to direct statsmodels calls on
the same arrays; deliberately nonstationary (log random walk) and
mechanical (fee = rate x volume) synthetics must be honestly marked, and
every undefined test must be null with a reason from the fixed vocabulary.

The DB cluster runner executes this module without database use: the
battery is offline research code.
"""

import contextlib
import datetime as dt
import hashlib
import importlib.util
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from statsmodels.regression.linear_model import OLS as DirectOLS
from statsmodels.stats.diagnostic import acorr_ljungbox, het_breuschpagan
from statsmodels.stats.outliers_influence import OLSInfluence
from statsmodels.tsa.stattools import acf as direct_acf
from statsmodels.tsa.stattools import adfuller as direct_adfuller
from statsmodels.tsa.stattools import kpss as direct_kpss

from test_models_readiness import (  # synthetic fixture reuse, no duplication
    CONFIGS_DIR,
    WINDOW_START,
    _tree_digest,
)
from test_models_fit import (  # synthetic fixture reuse, no duplication
    FIT_CONFIG_PATH,
    build_varying_archive,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MODELS_DIR = REPO_ROOT / "research" / "models"
DIAG_CONFIG_PATH = (MODELS_DIR / "diagnostics_configs"
                    / "gross_fee_activity_v1_diagnostics.json")
SPEC_PATH = CONFIGS_DIR / "gross_fee_activity_v1.json"
POLICY_PATH = CONFIGS_DIR / "readiness_gate_policy_v1.json"


def _load_diagnostics_module():
    spec = importlib.util.spec_from_file_location(
        "ni053_diagnostics", MODELS_DIR / "diagnostics.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


diag = _load_diagnostics_module()


def _pseudo_noise(index: int) -> float:
    """Deterministic integer-arithmetic pseudo-variation (no randomness)."""
    state = (1103515245 * (index + 11) + 12345) % 2147483648
    return (state / 2147483648.0) - 0.5


def build_random_walk_archive(root: Path, *, days: int = 90) -> Path:
    """A deliberately nonstationary synthetic archive: provider volume follows
    a drift-dominated log random walk (a unit-root-looking level) while fees
    remain the exact mechanical construction 0.015 x volume, so one archive
    exercises both the nonstationary marking and the mechanical warning."""
    archive = build_varying_archive(root, days=days)
    daily_path = archive / "near-dollar" / "analysis" / "daily.json"
    rows = json.loads(daily_path.read_text(encoding="utf-8"))
    level = 1_000_000.0
    for index, row in enumerate(rows):
        level *= math.exp(0.02 + 0.02 * _pseudo_noise(index))
        volume = Decimal(f"{level:.6f}")
        fees = volume * Decimal("0.015")
        row["volume_usd"] = str(volume)
        row["gross_fees_usd"] = str(fees)
        row["dashboard_volume_usd"] = str(volume + Decimal("100000"))
        row["dashboard_gross_fees_usd"] = str(fees + Decimal("1500"))
    daily_path.write_text(json.dumps(rows), encoding="utf-8")
    return archive


def _tiny_design(nobs: int, parameters_count: int):
    """A fabricated design/results pair for the undefined-reason branches the
    admitted-sample CLI cannot reach (a gate-admitted sample always exceeds
    the declared lags)."""
    x = np.array([1.0 + 0.3 * index for index in range(nobs)])
    y = 0.5 + 0.2 * x + np.array([_pseudo_noise(index) for index in range(nobs)])
    design = SimpleNamespace(
        y=y, X=np.column_stack([np.ones(nobs), x]), nobs=nobs,
        rows=tuple(SimpleNamespace(date=WINDOW_START + dt.timedelta(days=index))
                   for index in range(nobs)),
        spec=SimpleNamespace(parameters_count=parameters_count))
    result = SimpleNamespace(params=np.array([0.5, 0.2]))
    return design, result


class DiagnosticsRunTestCase(unittest.TestCase):
    """Shared fixture handling; never writes inside the research directory."""

    def setUp(self):
        base = os.environ.get("NI_TEST_TMP_DIR")
        self.tmp = Path(tempfile.mkdtemp(prefix="ni053-", dir=base) if base
                        else tempfile.mkdtemp(prefix="ni053-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.archive = build_varying_archive(self.tmp / "archive-a")
        self.archive_digest = _tree_digest(self.archive)
        self.out = self.tmp / "out"

    def run_diagnostics(self, *, archive=None, spec=SPEC_PATH,
                        fit_config=FIT_CONFIG_PATH, policy=POLICY_PATH,
                        diagnostics_config=DIAG_CONFIG_PATH,
                        code_commit="1a2b3c4d" + "0" * 56):
        return diag.run_diagnostics(
            archive_root=archive or self.archive, spec_path=spec,
            fit_config_path=fit_config, policy_path=policy,
            diagnostics_config_path=diagnostics_config, code_commit=code_commit)

    def rebuilt_pipeline(self, *, archive=None):
        """The gate/design/estimation objects behind the fit, for direct
        statsmodels comparisons."""
        policy = diag.readiness.load_policy(POLICY_PATH)
        spec = diag.readiness.load_spec(SPEC_PATH, policy)
        loaded = diag.readiness.load_archive(archive or self.archive, policy)
        table = diag.readiness.build_prepared_table(loaded)
        evaluation = diag.readiness.evaluate_spec(spec, table, policy, loaded)
        transformations = diag.fit.spec_document_transformations(SPEC_PATH)
        design = diag.fit.build_design(spec, policy, table, evaluation,
                                       transformations)
        fit_config = diag.fit.load_fit_config(FIT_CONFIG_PATH)
        result = diag.fit.estimate(design, policy, fit_config)
        return policy, spec, table, evaluation, design, result

    def assert_archive_untouched(self):
        self.assertEqual(_tree_digest(self.archive), self.archive_digest,
                         "the battery modified the read-only archive")

    def report_paths(self, directory: Path) -> tuple[Path, Path]:
        return (directory / "diagnostics_report.json",
                directory / "diagnostics_report.md")

    def stationarity_entry(self, report, test, role="dependent"):
        for entry in report["stationarity"]["tests"]:
            if entry["test"] == test and entry["role"] == role:
                return entry
        self.fail(f"{test} entry for role {role} missing")


class StationarityEquivalenceTests(DiagnosticsRunTestCase):

    def test_adf_kpss_match_direct_statsmodels_calls(self):
        report = self.run_diagnostics()
        _, spec, table, evaluation, _, _ = self.rebuilt_pipeline()
        variables = {"dependent": (spec.dependent,),
                     "explanatory": tuple(spec.explanatory)}
        for entry in report["stationarity"]["tests"]:
            variable = variables[entry["role"]][0] if entry["role"] == "dependent" \
                else variables["explanatory"][
                    [v.series_key for v in spec.explanatory]
                    .index(entry["series_key"])]
            series = diag._level_series(spec, table, evaluation, variable)
            if entry["test"] == "adf":
                direct = direct_adfuller(series, maxlag=7, regression="c",
                                         autolag=None, store=False,
                                         regresults=False, result_object=False)
                self.assertAlmostEqual(entry["statistic"], float(direct[0]),
                                       delta=1e-12)
                self.assertAlmostEqual(entry["p_value"], float(direct[1]),
                                       delta=1e-12)
                self.assertEqual(entry["used_lag"], int(direct[2]))
                self.assertEqual(entry["nobs_used"], int(direct[3]))
            else:
                direct = direct_kpss(series, regression="c", nlags=7,
                                     store=False, result_object=False)
                self.assertAlmostEqual(entry["statistic"], float(direct[0]),
                                       delta=1e-12)
                self.assertAlmostEqual(entry["p_value"], float(direct[1]),
                                       delta=1e-12)
            self.assertEqual(entry["status"], "computed")
            self.assertIn(entry["decision_at_alpha"],
                          ("reject_null", "fail_to_reject_null"))

    def test_settings_are_recorded_not_autoselected(self):
        report = self.run_diagnostics()
        for entry in report["stationarity"]["tests"]:
            settings = entry["settings"]
            if entry["test"] == "adf":
                self.assertEqual(settings["maxlag_rule"], "fixed")
                self.assertEqual(settings["maxlag"], 7)
                self.assertIsNone(settings["autolag"])
                self.assertEqual(entry["used_lag"], 7)
            else:
                self.assertEqual(settings["nlags_rule"], "fixed")
                self.assertEqual(settings["nlags"], 7)


class ResidualEquivalenceTests(DiagnosticsRunTestCase):

    def test_residual_battery_matches_direct_statsmodels_calls(self):
        report = self.run_diagnostics()
        _, _, _, _, design, result = self.rebuilt_pipeline()
        residuals = diag._residuals(design, result)
        direct_fit = DirectOLS(design.y, design.X).fit()
        np.testing.assert_allclose(residuals, direct_fit.resid, rtol=0,
                                   atol=1e-12)
        battery = report["residual_diagnostics"]
        self.assertEqual(battery["residuals"]["nobs"], design.nobs)
        # ACF
        acf_values, acf_confint = direct_acf(residuals, nlags=7, fft=False,
                                             alpha=0.05,
                                             bartlett_confint=True,
                                             missing="raise",
                                             result_object=False)
        np.testing.assert_allclose(battery["acf"]["acf"], acf_values,
                                   rtol=0, atol=1e-12)
        np.testing.assert_allclose(battery["acf"]["confint"], acf_confint,
                                   rtol=0, atol=1e-12)
        # Ljung-Box (model_df = the design's parameter count)
        direct_lb = acorr_ljungbox(residuals, lags=[3, 7], model_df=2,
                                   return_df=True)
        for row, (lag, direct_row) in zip(battery["ljung_box"]["results"],
                                          direct_lb.iterrows()):
            self.assertEqual(row["lag"], int(lag))
            self.assertAlmostEqual(row["lb_stat"], float(direct_row["lb_stat"]),
                                   delta=1e-9)
            self.assertAlmostEqual(row["lb_p_value"],
                                   float(direct_row["lb_pvalue"]), delta=1e-12)
        # Breusch-Pagan
        lm, lm_p, f_stat, f_p = het_breuschpagan(residuals, design.X,
                                                 robust=True)
        self.assertAlmostEqual(battery["heteroskedasticity"]["lm_stat"],
                               float(lm), delta=1e-9)
        self.assertAlmostEqual(battery["heteroskedasticity"]["lm_p_value"],
                               float(lm_p), delta=1e-12)
        self.assertAlmostEqual(battery["heteroskedasticity"]["f_stat"],
                               float(f_stat), delta=1e-9)
        self.assertAlmostEqual(battery["heteroskedasticity"]["f_p_value"],
                               float(f_p), delta=1e-12)
        # Cook's distance from the plain OLS fit
        cooks = OLSInfluence(direct_fit).cooks_distance[0]
        self.assertAlmostEqual(battery["influence"]["max_cooks_distance"],
                               float(np.max(cooks)), delta=1e-12)
        self.assertAlmostEqual(battery["influence"]["threshold"], 4 / design.nobs,
                               delta=1e-15)

    def test_estimation_results_match_the_fit_manifest(self):
        report = self.run_diagnostics()
        manifest = diag.fit.run_fit(archive_root=self.archive,
                                    spec_path=SPEC_PATH,
                                    fit_config_path=FIT_CONFIG_PATH,
                                    policy_path=POLICY_PATH,
                                    code_commit="1a2b3c4d" + "0" * 56)
        self.assertEqual(report["estimation_results"]["coefficients"],
                         manifest["coefficients"])
        self.assertEqual(report["sample"]["nobs"], manifest["sample"]["nobs"])
        self.assertEqual(report["sample"]["gate_evaluation"],
                         manifest["sample"]["gate_evaluation"])


class NonstationaryAndMechanicalTests(DiagnosticsRunTestCase):

    def setUp(self):
        super().setUp()
        self.walk_archive = build_random_walk_archive(self.tmp / "archive-walk")
        self.walk_digest = _tree_digest(self.walk_archive)

    def run_walk_diagnostics(self):
        return self.run_diagnostics(archive=self.walk_archive)

    def test_random_walk_levels_are_honestly_marked_nonstationary(self):
        report = self.run_walk_diagnostics()
        adf = self.stationarity_entry(report, "adf")
        kpss_entry = self.stationarity_entry(report, "kpss")
        self.assertEqual(adf["status"], "computed")
        self.assertEqual(adf["decision_at_alpha"], "fail_to_reject_null",
                         "a drift-dominated random walk must not pass ADF")
        self.assertGreater(adf["p_value"], 0.5)
        self.assertEqual(kpss_entry["status"], "computed")
        self.assertEqual(kpss_entry["decision_at_alpha"], "reject_null",
                         "KPSS must reject stationarity for a random walk")
        self.assertTrue(kpss_entry["p_value_is_table_boundary"])
        self.assertIn("table boundary", kpss_entry["boundary_note"])
        self.assert_archive_untouched()

    def test_walk_interpretation_stays_bounded(self):
        report = self.run_walk_diagnostics()
        interpretation = report["interpretation"]
        spec_notes = json.loads(SPEC_PATH.read_text(encoding="utf-8"))[
            "limitation_notes"]
        self.assertEqual(interpretation["mechanical_construction_warning"],
                         spec_notes[0])
        self.assertIn("not a causal effect",
                      " ".join(interpretation["sentences"]))
        self.assertIn("cannot establish a long-term stable mechanism",
                      " ".join(interpretation["sentences"]))
        self.assertEqual(interpretation["prohibited_labels"],
                         json.loads(SPEC_PATH.read_text())["prohibited_labels"])
        for label in ("protocol_revenue", "sustainable_revenue", "causal_effect"):
            self.assertIn(label, interpretation["prohibited_labels"])

    def test_mechanical_construction_is_marked_not_passed(self):
        report = self.run_walk_diagnostics()
        # fees = 0.015 x volume: the mechanical fee-volume warning travels
        # verbatim and the Ljung-Box rejection renders the bounded sentence.
        mechanical = report["interpretation"]["mechanical_construction_warning"]
        self.assertIn("Mechanical construction warning", mechanical)
        self.assertIn("must be displayed before any coefficient interpretation",
                      mechanical)
        lb_decisions = [row["decision_at_alpha"]
                        for row in report["residual_diagnostics"]["ljung_box"]
                        ["results"]]
        self.assertIn("reject_null", lb_decisions)
        sentences = " ".join(report["interpretation"]["sentences"])
        self.assertIn("Ljung-Box indicates residual autocorrelation", sentences)
        self.assertIn("does not repair misspecification", sentences)

    def test_influence_flags_are_reported_not_removed(self):
        report = self.run_walk_diagnostics()
        influence = report["residual_diagnostics"]["influence"]
        self.assertIn(influence["flagged_count"], (0, 1, 2, 3, 4, 5, 6, 7, 8, 9))
        for item in influence["flagged"]:
            self.assertGreater(item["cooks_distance"], influence["threshold"])
            self.assertRegex(item["date"], r"\d{4}-\d{2}-\d{2}")
        self.assertIn("remain in the sample", influence["policy"])


class UndefinedReasonTests(DiagnosticsRunTestCase):

    def test_short_and_constant_series_are_undefined_with_reasons(self):
        short = np.array([1.0, 2.0, 3.0])
        entry = diag._run_adf(short, diag.ADFConfig("c", 7, "fixed", "r"),
                              decision_alpha=Decimal("0.05"),
                              min_observations=20, series_key="s", metric_id="m",
                              dimension=None, role="dependent")
        self.assertEqual(entry["status"], "undefined")
        self.assertEqual(entry["reason_code"], "sample_below_declared_minimum")
        self.assertIsNone(entry["statistic"])
        self.assertIsNone(entry["p_value"])
        constant = np.full(25, 2.0)
        entry = diag._run_adf(constant, diag.ADFConfig("c", 7, "fixed", "r"),
                              decision_alpha=Decimal("0.05"),
                              min_observations=20, series_key="s", metric_id="m",
                              dimension=None, role="dependent")
        self.assertEqual(entry["status"], "undefined")
        self.assertEqual(entry["reason_code"], "constant_series_no_variance")
        entry = diag._run_kpss(constant, diag.KPSSConfig("c", 7, "fixed", "r"),
                               decision_alpha=Decimal("0.05"),
                               min_observations=20, series_key="s", metric_id="m",
                               dimension=None, role="dependent")
        self.assertEqual(entry["status"], "undefined")
        self.assertEqual(entry["reason_code"], "constant_series_no_variance")
        # a declared fixed lag at or above the sample size is undefined too
        tiny = np.array([1.0 + index for index in range(7)])
        entry = diag._run_adf(tiny, diag.ADFConfig("c", 7, "fixed", "r"),
                              decision_alpha=Decimal("0.05"),
                              min_observations=5, series_key="s", metric_id="m",
                              dimension=None, role="dependent")
        self.assertEqual(entry["status"], "undefined")
        self.assertEqual(entry["reason_code"], "maxlag_not_below_observations")
        with self.assertRaises(diag.DiagnosticsError):
            diag._undefined_test(series_key="s", metric_id="m", dimension=None,
                                 role="dependent", test="adf",
                                 null_hypothesis="unit root", settings={},
                                 reason_code="invented_reason")

    def test_residual_battery_undefined_branches(self):
        config = diag.load_diagnostics_config(DIAG_CONFIG_PATH)
        # nobs 6 < the declared acf/ljung-box lags: both undefined with reasons.
        design, result = _tiny_design(6, 2)
        battery = diag.residual_battery(design, result, config)
        self.assertEqual(battery["acf"]["status"], "undefined")
        self.assertEqual(battery["acf"]["reason_code"],
                         "acf_nlags_not_below_nobs")
        self.assertIsNone(battery["acf"].get("acf"))
        self.assertEqual(battery["ljung_box"]["status"], "undefined")
        self.assertEqual(battery["ljung_box"]["reason_code"],
                         "declared_lags_not_below_nobs")
        # a parameter count at the smallest declared lag makes the adjusted
        # dof non-positive: undefined instead of a NaN statistic.
        design, result = _tiny_design(12, 3)
        battery = diag.residual_battery(design, result, config)
        self.assertEqual(battery["ljung_box"]["status"], "undefined")
        self.assertEqual(battery["ljung_box"]["reason_code"],
                         "model_df_not_below_smallest_declared_lag")
        self.assertIsNone(battery["ljung_box"].get("results"))

    def test_report_undefined_entries_never_zero_and_carry_reasons(self):
        report = self.run_diagnostics()
        for entry in report["stationarity"]["tests"]:
            if entry["status"] == "undefined":
                self.assertTrue(entry["reason_code"])
                self.assertIsNone(entry["statistic"])
        for preset in report["sensitivity"]["presets"]:
            if preset["status"] in ("not_applicable", "failed"):
                self.assertTrue(preset["reason_code"])
                self.assertNotIn("coefficients", preset)


class SensitivityTests(DiagnosticsRunTestCase):

    def test_maxlags_presets_move_standard_errors_never_estimates(self):
        report = self.run_diagnostics()
        baseline = {item["name"]: item
                    for item in report["estimation_results"]["coefficients"]}
        presets = {entry["preset_id"]: entry
                   for entry in report["sensitivity"]["presets"]}
        for preset_id in ("hac_maxlags_3", "hac_maxlags_14"):
            self.assertEqual(presets[preset_id]["status"], "estimated")
            self.assertEqual(presets[preset_id]["variant_settings"]["covariance"]
                             ["maxlags_rule"], "fixed")
            for coefficient in presets[preset_id]["coefficients"]:
                self.assertEqual(coefficient["estimate"],
                                 baseline[coefficient["name"]]["estimate"])
                self.assertGreater(coefficient["std_error"], 0)
        self.assertEqual(presets["hac_maxlags_3"]["variant_settings"]
                         ["covariance"]["maxlags"], 3)
        self.assertEqual(presets["hac_maxlags_14"]["variant_settings"]
                         ["covariance"]["maxlags"], 14)

    def test_maxlags_beyond_sample_is_not_applicable_with_reason(self):
        config = json.loads(DIAG_CONFIG_PATH.read_text(encoding="utf-8"))
        config["sensitivity_presets"] = [
            {"preset_id": "hac_maxlags_200", "kind": "covariance_maxlags",
             "maxlags": 200, "rationale": "beyond the sample on purpose"}]
        path = self.tmp / "diag-lags200.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        report = self.run_diagnostics(diagnostics_config=path)
        presets = report["sensitivity"]["presets"]
        self.assertEqual(len(presets), 1)
        self.assertEqual(presets[0]["status"], "not_applicable")
        self.assertEqual(presets[0]["reason_code"],
                         "maxlags_not_below_sample_size")

    def test_source_preset_reruns_on_the_dashboard_series(self):
        report = self.run_diagnostics()
        presets = {entry["preset_id"]: entry
                   for entry in report["sensitivity"]["presets"]}
        entry = presets["source_dashboard"]
        self.assertEqual(entry["status"], "estimated")
        swaps = entry["variant_settings"]["swaps"]
        self.assertEqual({swap["to_dimension"] for swap in swaps},
                         {"SRC-DASHBOARD"})
        self.assertEqual(len(swaps), 2)
        names = {coefficient["name"] for coefficient in entry["coefficients"]}
        self.assertTrue(any("SRC-DASHBOARD" in name for name in names))
        self.assertIn(entry["variant_admission"]["verdict"],
                      ("READY", "READY_WITH_LIMITS"))

    def test_price_basis_preset_is_not_applicable_with_reason(self):
        report = self.run_diagnostics()
        presets = {entry["preset_id"]: entry
                   for entry in report["sensitivity"]["presets"]}
        entry = presets["price_basis_end"]
        self.assertEqual(entry["status"], "not_applicable")
        self.assertEqual(entry["reason_code"], "no_bound_variable_to_swap")
        self.assertIn("price_basis", entry["reason_detail"])

    def test_preset_repeating_the_baseline_maxlags_is_refused(self):
        config = json.loads(DIAG_CONFIG_PATH.read_text(encoding="utf-8"))
        config["sensitivity_presets"] = [
            {"preset_id": "hac_maxlags_7", "kind": "covariance_maxlags",
             "maxlags": 7, "rationale": "identical to the baseline"}]
        path = self.tmp / "diag-same-lags.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaises(diag.DiagnosticsError) as caught:
            self.run_diagnostics(diagnostics_config=path)
        self.assertIn("not a sensitivity", str(caught.exception))


class ConfigGuardTests(DiagnosticsRunTestCase):

    def guard_config(self, mutate):
        config = json.loads(DIAG_CONFIG_PATH.read_text(encoding="utf-8"))
        mutate(config)
        path = self.tmp / "diag-guard.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def test_unknown_field_is_refused(self):
        def mutate(config):
            config["auto_select_diagnostics"] = True
        with self.assertRaises(diag.DiagnosticsError) as caught:
            diag.load_diagnostics_config(self.guard_config(mutate))
        self.assertIn("unknown fields", str(caught.exception))

    def test_data_driven_lag_rules_are_refused(self):
        def mutate(config):
            config["stationarity"]["adf"]["maxlag_rule"] = "select_from_data"
        with self.assertRaises(diag.DiagnosticsError) as caught:
            diag.load_diagnostics_config(self.guard_config(mutate))
        self.assertIn("maxlag_rule", str(caught.exception))

        def mutate_kpss(config):
            config["stationarity"]["kpss"]["nlags_rule"] = "auto"
        with self.assertRaises(diag.DiagnosticsError) as caught:
            diag.load_diagnostics_config(self.guard_config(mutate_kpss))
        self.assertIn("nlags_rule", str(caught.exception))

    def test_alpha_out_of_range_is_refused(self):
        def mutate(config):
            config["decision_alpha"] = "1.5"
        with self.assertRaises(diag.DiagnosticsError) as caught:
            diag.load_diagnostics_config(self.guard_config(mutate))
        self.assertIn("decision_alpha", str(caught.exception))

    def test_unknown_interpretation_template_is_refused(self):
        def mutate(config):
            config["interpretation_template"] = "free_form_v9"
        with self.assertRaises(diag.DiagnosticsError) as caught:
            diag.load_diagnostics_config(self.guard_config(mutate))
        self.assertIn("interpretation_template", str(caught.exception))

    def test_binding_another_specification_is_refused(self):
        def mutate(config):
            config["spec_id"] = "purchases_activity_v1"
        path = self.guard_config(mutate)
        with self.assertRaises(diag.DiagnosticsError) as caught:
            self.run_diagnostics(diagnostics_config=path)
        self.assertIn("binds specification", str(caught.exception))

    def test_pointing_at_another_spec_config_is_refused(self):
        # The same spec_id under a different file name must be refused by the
        # declared spec_config binding (the estimator never swaps files).
        renamed_spec = self.tmp / "gross_fee_activity_v1_copy.json"
        shutil.copy(CONFIGS_DIR / "gross_fee_activity_v1.json", renamed_spec)
        with self.assertRaises(diag.DiagnosticsError) as caught:
            self.run_diagnostics(spec=renamed_spec)
        self.assertIn("declares spec_config", str(caught.exception))

    def test_binding_check_fires_for_a_different_spec_file(self):
        other_spec = self.tmp / "purchases_activity_v1.json"
        shutil.copy(CONFIGS_DIR / "purchases_activity_v1.json", other_spec)
        with self.assertRaises(diag.DiagnosticsError) as caught:
            self.run_diagnostics(spec=other_spec)
        self.assertIn("binds specification", str(caught.exception))


class ReportContractTests(DiagnosticsRunTestCase):

    def test_double_run_is_byte_identical(self):
        first = self.run_diagnostics()
        second = self.run_diagnostics()
        self.assertEqual(diag.render_report_json(first),
                         diag.render_report_json(second))
        self.assertEqual(diag.render_report_markdown(first),
                         diag.render_report_markdown(second))
        json_a, markdown_a = diag.write_report(first, self.tmp / "run-a")
        json_b, markdown_b = diag.write_report(second, self.tmp / "run-b")
        self.assertEqual(json_a.read_bytes(), json_b.read_bytes())
        self.assertEqual(markdown_a.read_bytes(), markdown_b.read_bytes())
        document = json.loads(json_a.read_text(encoding="utf-8"))
        self.assertEqual(document["report_type"], "model_diagnostics_report")
        self.assertNotIn("generated_at", document)
        self.assertNotIn("timestamp", document)

    def test_sample_and_exclusion_table_is_the_gate_table_verbatim(self):
        gap_day = WINDOW_START + dt.timedelta(days=45)
        archive = build_varying_archive(self.tmp / "archive-gap",
                                        missing_volume_days=(gap_day,))
        report = self.run_diagnostics(archive=archive)
        policy = diag.readiness.load_policy(POLICY_PATH)
        spec = diag.readiness.load_spec(SPEC_PATH, policy)
        loaded = diag.readiness.load_archive(archive, policy)
        table = diag.readiness.build_prepared_table(loaded)
        evaluation = diag.readiness.evaluate_spec(spec, table, policy, loaded)
        self.assertEqual(report["sample"]["gate_evaluation"],
                         evaluation.sample)
        excluded = {(item["date"], item["series"], item["reason"])
                    for item in evaluation.sample["excluded_days"]}
        self.assertIn((gap_day.isoformat(),
                       "provider_intents_volume_usd|SRC-LLAMA", "missing_value"),
                      excluded)
        self.assertEqual(report["sample"]["nobs"],
                         evaluation.sample["usable_observations"])

    def test_inputs_are_pinned_and_environment_recorded(self):
        report = self.run_diagnostics()
        pinned = {item["path"]: item["sha256"]
                  for item in report["inputs"]["files"]}
        for relative, digest in pinned.items():
            actual = hashlib.sha256(
                (self.archive / relative).read_bytes()).hexdigest()
            self.assertEqual(digest, actual)
        self.assertEqual(report["inputs"]["diagnostics_config_hash"],
                         diag.load_diagnostics_config(DIAG_CONFIG_PATH)
                         .config_hash)
        lock = report["inputs"]["dependency_lock"]
        self.assertTrue(lock["present"])
        self.assertEqual(lock["sha256"], hashlib.sha256(
            (REPO_ROOT / "apps" / "api" / "uv.lock").read_bytes()).hexdigest())
        self.assertEqual(report["inputs"]["code_commit"], "1a2b3c4d" + "0" * 56)
        for key in ("python_version", "numpy_version", "statsmodels_version",
                    "blas"):
            self.assertIn(key, report["environment"])

    def test_reports_land_only_in_the_output_directory(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(diag.main(["--archive-root", str(self.archive),
                                        "--out-dir", str(self.out)]), 0)
        written = sorted(path.relative_to(self.tmp).as_posix()
                         for path in self.tmp.rglob("*") if path.is_file())
        for relative in written:
            self.assertTrue(relative.startswith("out/") or
                            relative.startswith("archive-a/"),
                            f"unexpected file outside sanctioned directories: "
                            f"{relative}")
        self.assert_archive_untouched()


class CliTests(DiagnosticsRunTestCase):

    def test_cli_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(diag.main(["--archive-root", str(self.archive),
                                        "--out-dir", str(self.out)]), 0)
        self.assertIn("report:", stdout.getvalue())
        self.assertIn("stationarity:", stdout.getvalue())
        self.assertIn("Mechanical construction warning", stdout.getvalue())
        json_path, markdown_path = self.report_paths(self.out)
        self.assertTrue(json_path.is_file() and markdown_path.is_file())
        # Contract failure: the zero-day archive is gate-rejected.
        zero_archive = build_varying_archive(self.tmp / "archive-cli-zero",
                                             zero_volume_days=(WINDOW_START,))
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(diag.main(["--archive-root",
                                        str(zero_archive)]), 4)
        self.assertIn("diagnostics contract failure", stderr.getvalue())
        # Usage failure: argparse exits with 2.
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                diag.main(["--archive-root"])
        self.assertEqual(caught.exception.code, 2)
        self.assert_archive_untouched()

    def test_cli_report_matches_the_library_report(self):
        report = self.run_diagnostics()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(diag.main(["--archive-root", str(self.archive),
                                        "--out-dir", str(self.out),
                                        "--code-commit",
                                        "1a2b3c4d" + "0" * 56]), 0)
        json_path, _ = self.report_paths(self.out)
        self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")),
                         json.loads(diag.render_report_json(report)))

    def test_near_api_research_wrapper_subprocess(self):
        environment = {**os.environ}
        helped = subprocess.run(
            [sys.executable, "-m", "near_api.research", "diagnostics", "--help"],
            cwd=REPO_ROOT, env=environment, capture_output=True, text=True,
            timeout=300)
        self.assertEqual(helped.returncode, 0, helped.stderr)
        self.assertIn("--archive-root", helped.stdout)
        # A full run through the wrapper writes byte-identical reports.
        for suffix in ("wrapper-a", "wrapper-b"):
            completed = subprocess.run(
                [sys.executable, "-m", "near_api.research", "diagnostics",
                 "--archive-root", str(self.archive),
                 "--out-dir", str(self.tmp / suffix),
                 "--code-commit", "1a2b3c4d" + "0" * 56],
                cwd=REPO_ROOT, env=environment, capture_output=True, text=True,
                timeout=300)
            self.assertEqual(completed.returncode, 0, completed.stderr)
        left, _ = self.report_paths(self.tmp / "wrapper-a")
        right, _ = self.report_paths(self.tmp / "wrapper-b")
        self.assertEqual(left.read_bytes(), right.read_bytes())
        # A missing archive is a contract failure with exit code 4.
        missing = subprocess.run(
            [sys.executable, "-m", "near_api.research", "diagnostics",
             "--archive-root", str(self.tmp / "does-not-exist")],
            cwd=REPO_ROOT, env=environment, capture_output=True, text=True,
            timeout=300)
        self.assertEqual(missing.returncode, 4, missing.stderr)
        self.assertIn("diagnostics contract failure", missing.stderr)
        # An unknown command is still a usage failure with exit code 2.
        unknown = subprocess.run(
            [sys.executable, "-m", "near_api.research", "transmogrify"],
            cwd=REPO_ROOT, env=environment, capture_output=True, text=True,
            timeout=300)
        self.assertEqual(unknown.returncode, 2)
        self.assert_archive_untouched()


if __name__ == "__main__":
    unittest.main()
