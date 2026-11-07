"""NI-052 tests: the fixed deterministic econometric estimator.

Everything here is invented synthetic data written into disposable
temporary directories; the real research archive is never touched and no
fitted real-data result is claimed anywhere (the real-archive run is
operator-side evidence, like the NI-051 gate run). Synthetic known-behavior
cases are kept strictly separate from the actual archive: a constructed
series with a known exact relationship must be recovered, rank failures
and zero policies must fail closed, and the CLI must be idempotent and
byte-identical on repeated runs.

The DB cluster runner executes this module without database use: the
estimator is offline research code.
"""

import contextlib
import dataclasses
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from statsmodels.regression.linear_model import OLS as DirectOLS

from test_models_readiness import (  # synthetic fixture reuse, no duplication
    CONFIGS_DIR,
    WINDOW_START,
    _copy_spec_configs,
    _tree_digest,
    build_synthetic_archive,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MODELS_DIR = REPO_ROOT / "research" / "models"
FIT_CONFIG_PATH = MODELS_DIR / "fit_configs" / "gross_fee_activity_v1_fit.json"
SPEC_PATH = CONFIGS_DIR / "gross_fee_activity_v1.json"
POLICY_PATH = CONFIGS_DIR / "readiness_gate_policy_v1.json"


def _load_fit_module():
    spec = importlib.util.spec_from_file_location("ni052_fit", MODELS_DIR / "fit.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


fit = _load_fit_module()


def _varying_volume(index: int) -> Decimal:
    """Deterministic integer-arithmetic pseudo-variation (no randomness)."""
    state = (1103515245 * (index + 7) + 12345) % 2147483648
    return Decimal(1_000_000 + (state % 400_000) + 97 * index)


def build_varying_archive(root: Path, *, days: int = 90,
                          zero_volume_days: tuple = (),
                          missing_volume_days: tuple = (),
                          missing_daily_rows: tuple = (),
                          constant: bool = False):
    """A synthetic archive whose provider series vary by day; fees are an
    exact 1.5% construction over volume, so the admitted log-difference
    specification has the exactly known coefficients intercept 0 / slope 1."""
    archive = build_synthetic_archive(root, days=days,
                                      missing_daily_rows=missing_daily_rows)
    daily_path = archive / "near-dollar" / "analysis" / "daily.json"
    rows = json.loads(daily_path.read_text(encoding="utf-8"))
    for index, row in enumerate(rows):
        date = dt.date.fromisoformat(row["date"])
        if date in missing_daily_rows:
            continue
        if date in missing_volume_days:
            volume = fees = None
        elif date in zero_volume_days:
            volume, fees = Decimal(0), Decimal(0)
        elif constant:
            volume, fees = Decimal("1000000"), Decimal("15000")
        else:
            volume = _varying_volume(index)
            fees = volume * Decimal("0.015")
        row["volume_usd"] = None if volume is None else str(volume)
        row["gross_fees_usd"] = None if fees is None else str(fees)
        row["dashboard_volume_usd"] = (None if volume is None
                                       else str(volume + Decimal("100000")))
        row["dashboard_gross_fees_usd"] = (None if fees is None
                                           else str(fees + Decimal("1500")))
    daily_path.write_text(json.dumps(rows), encoding="utf-8")
    return archive


class FitRunTestCase(unittest.TestCase):
    """Shared fixture handling; never writes inside the research directory."""

    def setUp(self):
        base = os.environ.get("NI_TEST_TMP_DIR")
        self.tmp = Path(tempfile.mkdtemp(prefix="ni052-", dir=base) if base
                        else tempfile.mkdtemp(prefix="ni052-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.archive = build_varying_archive(self.tmp / "archive-a")
        self.archive_digest = _tree_digest(self.archive)
        self.out = self.tmp / "out"

    def run_fit(self, *, archive=None, spec=SPEC_PATH, fit_config=FIT_CONFIG_PATH,
                policy=POLICY_PATH, code_commit="0f9e8d7c" + "0" * 56):
        return fit.run_fit(archive_root=archive or self.archive, spec_path=spec,
                           fit_config_path=fit_config, policy_path=policy,
                           code_commit=code_commit)

    def assert_archive_untouched(self):
        self.assertEqual(_tree_digest(self.archive), self.archive_digest,
                         "the estimator modified the read-only archive")

    def manifest_paths(self, directory: Path) -> tuple[Path, Path]:
        return directory / "fit_manifest.json", directory / "fit_manifest.md"


class KnownBehaviorTests(FitRunTestCase):

    def test_exact_relationship_recovers_known_coefficients(self):
        manifest = self.run_fit()
        self.assertEqual(manifest["model"]["model_id"], "gross_fee_activity_v1")
        self.assertEqual(manifest["admission"]["verdict"], "READY_WITH_LIMITS")
        coefficients = {item["name"]: item for item in manifest["coefficients"]}
        self.assertEqual(list(coefficients),
                         ["const", "dlog(provider_intents_volume_usd|SRC-LLAMA)"])
        # fees = 0.015 * volume exactly: dlog(fees) = dlog(volume) + dlog(0.015)
        # and dlog(0.015) = 0, so the true intercept is 0 and the true slope 1.
        self.assertAlmostEqual(coefficients["const"]["estimate"], 0.0,
                               delta=1e-10, msg="intercept must recover 0")
        self.assertAlmostEqual(
            coefficients["dlog(provider_intents_volume_usd|SRC-LLAMA)"]["estimate"],
            1.0, delta=1e-10, msg="slope must recover 1")
        self.assertEqual(manifest["sample"]["nobs"], 89)
        self.assertEqual(manifest["design"]["rows"], 89)
        self.assert_archive_untouched()

    def test_estimator_matches_a_direct_statsmodels_hac_call(self):
        # The wrapper must reach the same numbers as a direct statsmodels OLS +
        # HAC call on the same design (the locked library stays the source).
        policy = fit.readiness.load_policy(POLICY_PATH)
        spec = fit.readiness.load_spec(SPEC_PATH, policy)
        archive = fit.readiness.load_archive(self.archive, policy)
        table = fit.readiness.build_prepared_table(archive)
        evaluation = fit.readiness.evaluate_spec(spec, table, policy, archive)
        transformations = fit.spec_document_transformations(SPEC_PATH)
        design = fit.build_design(spec, policy, table, evaluation, transformations)
        fit_config = fit.load_fit_config(FIT_CONFIG_PATH)
        result = fit.estimate(design, policy, fit_config)
        direct = DirectOLS(design.y, design.X).fit().get_robustcov_results(
            cov_type="HAC", maxlags=7, use_correction=True, use_t=True)
        for index in range(design.parameters):
            self.assertAlmostEqual(result.params[index], float(direct.params[index]),
                                   delta=1e-15)
            self.assertAlmostEqual(result.bse[index], float(direct.bse[index]),
                                   delta=1e-15)

    def test_hac_settings_are_serialized_from_the_config(self):
        manifest = self.run_fit()
        covariance = manifest["estimation"]["covariance"]
        self.assertEqual(covariance["type"], "HAC")
        self.assertEqual(covariance["kernel"], "bartlett")
        self.assertEqual(covariance["maxlags"], 7)
        self.assertEqual(covariance["maxlags_rule"], "fixed")
        self.assertTrue(covariance["use_correction"])
        self.assertTrue(covariance["use_t"])
        self.assertIn("weekly", covariance["rationale"])
        self.assertEqual(manifest["reproduction"]["coefficient_rtol"],
                         fit.decimal_string(fit.load_fit_config(FIT_CONFIG_PATH)
                                            .coefficient_rtol))

    def test_maxlags_change_standard_errors_never_coefficients(self):
        baseline = self.run_fit()
        sensitive = json.loads(FIT_CONFIG_PATH.read_text(encoding="utf-8"))
        sensitive["covariance"]["maxlags"] = 3
        sensitive_path = self.tmp / "fit-config-lags3.json"
        sensitive_path.write_text(json.dumps(sensitive), encoding="utf-8")
        variant = self.run_fit(fit_config=sensitive_path)
        # The point estimates come from OLS and must not move with the
        # covariance setting; only the standard errors do.
        self.assertEqual([item["estimate"] for item in baseline["coefficients"]],
                         [item["estimate"] for item in variant["coefficients"]])
        self.assertEqual(variant["estimation"]["covariance"]["maxlags"], 3)
        baseline_se = [item["std_error"] for item in baseline["coefficients"]]
        variant_se = [item["std_error"] for item in variant["coefficients"]]
        self.assertNotEqual(baseline_se, variant_se)
        for before, after in zip(baseline_se, variant_se):
            self.assertGreater(after, before * 0.01)


class DesignFailureTests(FitRunTestCase):

    def test_constant_series_rank_failure_refuses_to_fit(self):
        # A constant provider series produces an all-zero difference column:
        # the design is rank deficient and NOTHING is fitted (no
        # pseudo-inverse, no column dropping).
        archive = build_varying_archive(self.tmp / "archive-constant", constant=True)
        with self.assertRaises(fit.FitError) as caught:
            self.run_fit(archive=archive)
        self.assertIn("rank deficient", str(caught.exception))
        self.assertIn("refusing to fit", str(caught.exception))

    def test_zero_volume_is_gate_rejected_and_never_epsiloned(self):
        zero_day = WINDOW_START + dt.timedelta(days=30)
        archive = build_varying_archive(self.tmp / "archive-zero",
                                        zero_volume_days=(zero_day,))
        with self.assertRaises(fit.FitError) as caught:
            self.run_fit(archive=archive)
        message = str(caught.exception)
        self.assertIn("gate verdict", message)
        self.assertIn("ZERO_VALUES_EXCLUDE_LOG_SPEC", message)
        self.assert_archive_untouched()

    def test_design_builder_enforces_strict_positivity_directly(self):
        # Even with an admitting gate evaluation, a doctored zero inside the
        # prepared table must fail the design builder itself.
        policy = fit.readiness.load_policy(POLICY_PATH)
        spec = fit.readiness.load_spec(SPEC_PATH, policy)
        archive = fit.readiness.load_archive(self.archive, policy)
        table = fit.readiness.build_prepared_table(archive)
        evaluation = fit.readiness.evaluate_spec(spec, table, policy, archive)
        doctored_days = []
        poisoned_date = WINDOW_START + dt.timedelta(days=40)
        for day in table["days"]:
            if day.date == poisoned_date:
                fees = dict(day.provider_fees)
                fees["SRC-LLAMA"] = Decimal(0)
                day = dataclasses.replace(day, provider_fees=fees)
            doctored_days.append(day)
        doctored = {**table, "days": tuple(doctored_days)}
        transformations = fit.spec_document_transformations(SPEC_PATH)
        with self.assertRaises(fit.FitError) as caught:
            fit.build_design(spec, policy, doctored, evaluation, transformations)
        self.assertIn("strict positivity violated", str(caught.exception))
        self.assertIn("never", str(caught.exception))

    def test_missing_day_drops_pairs_exactly_like_the_gate(self):
        gap_day = WINDOW_START + dt.timedelta(days=45)
        archive = build_varying_archive(self.tmp / "archive-gap",
                                        missing_volume_days=(gap_day,))
        manifest = self.run_fit(archive=archive)
        self.assertEqual(manifest["sample"]["nobs"], 87)
        self.assertEqual(manifest["sample"]["gate_evaluation"]["usable_observations"],
                         87)
        self.assertEqual(manifest["sample"]["gate_evaluation"]["nonadjacent_dropped_pairs"],
                         2)
        excluded = {(item["date"], item["series"], item["reason"])
                    for item in manifest["sample"]["gate_evaluation"]["excluded_days"]}
        self.assertIn((gap_day.isoformat(), "provider_intents_volume_usd|SRC-LLAMA",
                       "missing_value"), excluded)
        # The gap day itself and its pair across the gap are outside the design:
        # first design date must stay the day after the gap's pair start.
        self.assertEqual(manifest["sample"]["first_design_date"],
                         (WINDOW_START + dt.timedelta(days=1)).isoformat())


class SpecGuardTests(FitRunTestCase):

    def test_fit_config_binding_another_specification_is_refused(self):
        config = json.loads(FIT_CONFIG_PATH.read_text(encoding="utf-8"))
        config["spec_id"] = "purchases_activity_v1"
        path = self.tmp / "fit-config-wrong-spec.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaises(fit.FitError) as caught:
            self.run_fit(fit_config=path)
        self.assertIn("never swaps specifications", str(caught.exception))

    def test_tampered_proxy_targeting_protocol_revenue_is_refused(self):
        tampered = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
        tampered["declared_target"] = "protocol_revenue"
        path = self.tmp / "gross_fee_activity_v1.json"
        path.write_text(json.dumps(tampered), encoding="utf-8")
        with self.assertRaises(fit.FitError) as caught:
            self.run_fit(spec=path)
        # The estimator's own defense-in-depth fires before the gate: a proxy
        # specification may never target protocol revenue.
        self.assertIn("never target protocol revenue", str(caught.exception))

    def test_slope_count_mismatch_is_refused_at_design_time(self):
        tampered = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
        tampered["parameters"]["substantive_slopes"] = 2
        path = self.tmp / "gross_fee_activity_v1.json"
        path.write_text(json.dumps(tampered), encoding="utf-8")
        with self.assertRaises(fit.FitError) as caught:
            self.run_fit(spec=path)
        self.assertIn("declared parameter count", str(caught.exception))

    def test_unknown_field_in_fit_config_is_refused(self):
        config = json.loads(FIT_CONFIG_PATH.read_text(encoding="utf-8"))
        config["auto_select_regressors"] = True
        path = self.tmp / "fit-config-unknown.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaises(fit.FitError) as caught:
            self.run_fit(fit_config=path)
        self.assertIn("unknown fields", str(caught.exception))

    def test_pvalue_driven_lag_rule_is_refused(self):
        config = json.loads(FIT_CONFIG_PATH.read_text(encoding="utf-8"))
        config["covariance"]["maxlags_rule"] = "select_from_data"
        path = self.tmp / "fit-config-greedy-lags.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaises(fit.FitError) as caught:
            self.run_fit(fit_config=path)
        self.assertIn("lag selection is forbidden", str(caught.exception))

    def test_limitations_are_attached_verbatim(self):
        manifest = self.run_fit()
        spec_notes = json.loads(SPEC_PATH.read_text(encoding="utf-8"))["limitation_notes"]
        self.assertEqual(manifest["limitations"]["spec_limitation_notes"], spec_notes)
        self.assertIn("Mechanical construction warning", spec_notes[0])
        for code in ("MECHANICAL_FEE_VOLUME_RELATIONSHIP", "PROXY_NOT_PROTOCOL_REVENUE",
                     "OQ02_JUDGING_ACCEPTANCE_RISK", "SINGLE_PROVIDER_LINEAGE_NOT_INDEPENDENT",
                     "SHORT_SAMPLE_NO_LONG_RUN_CLAIM", "NO_CAUSAL_IDENTIFICATION"):
            self.assertIn(code, manifest["limitations"]["gate_limit_codes"], code)
        self.assertEqual(manifest["limitations"]["prohibited_labels"],
                         json.loads(SPEC_PATH.read_text())["prohibited_labels"])
        markdown = fit.render_manifest_markdown(manifest)
        self.assertIn("Mechanical construction warning", markdown)

    def test_manifest_pins_inputs_and_environment(self):
        manifest = self.run_fit()
        pinned = {item["path"]: item["sha256"]
                  for item in manifest["inputs"]["files"]}
        for relative, digest in pinned.items():
            actual = hashlib.sha256(
                (self.archive / relative).read_bytes()).hexdigest()
            self.assertEqual(digest, actual)
        lock = manifest["inputs"]["dependency_lock"]
        self.assertTrue(lock["present"])
        self.assertEqual(lock["sha256"],
                         hashlib.sha256(
                             (REPO_ROOT / "apps" / "api" / "uv.lock")
                             .read_bytes()).hexdigest())
        self.assertEqual(manifest["inputs"]["code_commit"], "0f9e8d7c" + "0" * 56)
        environment = manifest["environment"]
        self.assertIn("numpy_version", environment)
        self.assertIn("statsmodels_version", environment)
        self.assertIn("blas", environment)
        self.assertIn("python_version", environment)


class DeterminismAndCliTests(FitRunTestCase):

    def test_double_run_is_byte_identical(self):
        first = self.run_fit()
        second = self.run_fit()
        self.assertEqual(fit.render_manifest_json(first),
                         fit.render_manifest_json(second))
        self.assertEqual(fit.render_manifest_markdown(first),
                         fit.render_manifest_markdown(second))
        json_a, markdown_a = fit.write_manifest(first, self.tmp / "run-a")
        json_b, markdown_b = fit.write_manifest(second, self.tmp / "run-b")
        self.assertEqual(json_a.read_bytes(), json_b.read_bytes())
        self.assertEqual(markdown_a.read_bytes(), markdown_b.read_bytes())
        document = json.loads(json_a.read_text(encoding="utf-8"))
        self.assertEqual(document["manifest_type"], "model_fit_run")
        self.assertNotIn("generated_at", document)
        self.assertNotIn("timestamp", document)

    def test_cli_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(fit.main(["--archive-root", str(self.archive),
                                       "--out-dir", str(self.out)]), 0)
        self.assertIn("manifest:", stdout.getvalue())
        self.assertIn("Mechanical construction warning", stdout.getvalue())
        json_path, markdown_path = self.manifest_paths(self.out)
        self.assertTrue(json_path.is_file() and markdown_path.is_file())
        # Contract failure: the zero-day archive is gate-rejected.
        zero_archive = build_varying_archive(self.tmp / "archive-cli-zero",
                                             zero_volume_days=(WINDOW_START,))
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(fit.main(["--archive-root", str(zero_archive)]), 4)
        self.assertIn("fit contract failure", stderr.getvalue())
        # Usage failure: argparse exits with 2.
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                fit.main(["--archive-root"])
        self.assertEqual(caught.exception.code, 2)
        self.assert_archive_untouched()

    def test_cli_manifest_matches_the_library_manifest(self):
        manifest = self.run_fit()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(fit.main(["--archive-root", str(self.archive),
                                       "--out-dir", str(self.out),
                                       "--code-commit", "0f9e8d7c" + "0" * 56]), 0)
        json_path, _ = self.manifest_paths(self.out)
        self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")),
                         json.loads(fit.render_manifest_json(manifest)))

    def test_near_api_research_wrapper_subprocess(self):
        environment = {**os.environ}
        # --help reaches the forwarded module and exits 0.
        helped = subprocess.run(
            [sys.executable, "-m", "near_api.research", "fit", "--help"],
            cwd=REPO_ROOT, env=environment, capture_output=True, text=True,
            timeout=180)
        self.assertEqual(helped.returncode, 0, helped.stderr)
        self.assertIn("--archive-root", helped.stdout)
        # A full run through the wrapper writes the same byte-identical
        # manifests as the library call.
        for suffix in ("wrapper-a", "wrapper-b"):
            completed = subprocess.run(
                [sys.executable, "-m", "near_api.research", "fit",
                 "--archive-root", str(self.archive),
                 "--out-dir", str(self.tmp / suffix),
                 "--code-commit", "0f9e8d7c" + "0" * 56],
                cwd=REPO_ROOT, env=environment, capture_output=True, text=True,
                timeout=180)
            self.assertEqual(completed.returncode, 0, completed.stderr)
        left, _ = self.manifest_paths(self.tmp / "wrapper-a")
        right, _ = self.manifest_paths(self.tmp / "wrapper-b")
        self.assertEqual(left.read_bytes(), right.read_bytes())
        # A missing archive is a contract failure with exit code 4.
        missing = subprocess.run(
            [sys.executable, "-m", "near_api.research", "fit",
             "--archive-root", str(self.tmp / "does-not-exist")],
            cwd=REPO_ROOT, env=environment, capture_output=True, text=True,
            timeout=180)
        self.assertEqual(missing.returncode, 4, missing.stderr)
        self.assertIn("fit contract failure", missing.stderr)
        # An unknown command is a usage failure with exit code 2.
        unknown = subprocess.run(
            [sys.executable, "-m", "near_api.research", "transmogrify"],
            cwd=REPO_ROOT, env=environment, capture_output=True, text=True,
            timeout=180)
        self.assertEqual(unknown.returncode, 2)
        self.assert_archive_untouched()

    def test_out_dir_receives_only_the_manifests(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(fit.main(["--archive-root", str(self.archive),
                                       "--out-dir", str(self.out)]), 0)
        written = sorted(path.relative_to(self.tmp).as_posix()
                         for path in self.tmp.rglob("*") if path.is_file())
        for relative in written:
            self.assertTrue(relative.startswith("out/") or
                            relative.startswith("archive-a/"),
                            f"unexpected file outside sanctioned directories: "
                            f"{relative}")
        self.assert_archive_untouched()


if __name__ == "__main__":
    unittest.main()
