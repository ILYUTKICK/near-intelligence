"""NI-054 tests: the operator publication gate and the offline verifier.

Synthetic, offline, no database: every bundle here is constructed from the
committed preregistered configs plus synthetic archive identities — no real
archive, no provider, no network, no fit re-run. The real publication flow
stays an operator step exactly like the NI-051/NI-052/NI-053 artifact runs.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import UUID, uuid5

from near_api.research.publication import (
    APPROVAL_TYPE,
    BUNDLE_VERSION,
    BUNDLE_TYPE,
    DECISION_APPROVE,
    MANIFEST_KEYS,
    REPO_ROOT,
    PublicationGateError,
    bundle_document,
    canonical_artifact_hash,
    derive_run_id,
    load_bundle,
    publication_payload,
    render_canonical,
    verify_bundle,
)

REPO = Path(__file__).resolve().parents[3]
SPEC_CONFIG = "research/models/configs/gross_fee_activity_v1.json"
FIT_CONFIG = "research/models/fit_configs/gross_fee_activity_v1_fit.json"
DIAGNOSTICS_CONFIG = "research/models/diagnostics_configs/gross_fee_activity_v1_diagnostics.json"
POLICY_CONFIG = "research/models/configs/readiness_gate_policy_v1.json"

CODE_COMMIT = "a" * 64
SYNTHETIC_FILE = {"name": "saved-responses/daily.json", "cohort": "daily",
                  "path": "data/daily.json", "bytes": 4096,
                  "sha256": "b" * 64}

WINDOW = {"start": "2026-08-06", "end_exclusive": "2026-11-04"}
SPECIFICATION = {
    "spec_id": "gross_fee_activity_v1",
    "spec_version": 1,
    "family": "proxy",
    "declared_target": "gross_provider_fees",
    "frequency": "daily",
    "dependent_variable": {"metric_id": "provider_gross_fees_usd",
                           "dimension": "SRC-LLAMA"},
    "explanatory_variables": [{"metric_id": "provider_intents_volume_usd",
                               "dimension": "SRC-LLAMA", "role": "activity"}],
    "baseline": "difference_log",
    "substantive_slopes": 1,
    "intercept": True,
    "config_hash": "c" * 64,
}
COLUMNS = ["const", "dlog_provider_intents_volume_usd"]
COEFFICIENTS = [
    {"name": "const", "estimate": 0.00123, "std_error": 0.0045, "t_stat": 0.273,
     "p_value": 0.785, "ci95_low": -0.0076, "ci95_high": 0.0101},
    {"name": "dlog_provider_intents_volume_usd", "estimate": 0.98765,
     "std_error": 0.0321, "t_stat": 30.77, "p_value": 1.2e-45,
     "ci95_low": 0.9243, "ci95_high": 1.051},
]
LIMITATION_NOTES = [
    "Mechanical construction warning (docs/ECONOMETRIC_METHODOLOGY.md): provider "
    "gross fees are reported as a fee applied to the same provider's reported volume.",
    "Both variables share one provider lineage (Dune).",
]
PROHIBITED = ["protocol_revenue", "token_valuation", "causal_effect"]
LIMIT_CODES = ["MECHANICAL_FEE_VOLUME_RELATION", "SINGLE_PROVIDER_LINEAGE",
               "SHORT_SAMPLE_ASSOCIATION_ONLY"]


def config_hash(path: str) -> str:
    document = json.loads((REPO / path).read_text(encoding="utf-8"))
    return hashlib.sha256(json.dumps(document, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def fit_config_block() -> dict:
    document = json.loads((REPO / FIT_CONFIG).read_text(encoding="utf-8"))
    document["config_hash"] = config_hash(FIT_CONFIG)
    return document


def diagnostics_config_block() -> dict:
    document = json.loads((REPO / DIAGNOSTICS_CONFIG).read_text(encoding="utf-8"))
    document["config_hash"] = config_hash(DIAGNOSTICS_CONFIG)
    return document


def gate_policy_block() -> dict:
    """The committed policy rendered as readiness.GatePolicy.as_report()."""
    document = json.loads((REPO / POLICY_CONFIG).read_text(encoding="utf-8"))
    window = document["window"]
    report = {
        "policy_id": document["policy_id"],
        "policy_version": document["policy_version"],
        "window": {**window, "days": 90},
        "min_complete_daily_observations": document["min_complete_daily_observations"],
        "min_observations_per_parameter": document["min_observations_per_parameter"],
        "max_substantive_slopes": document["max_substantive_slopes"],
        "intercept_required": document["intercept_required"],
        "long_run_min_days": document["long_run_min_days"],
        "fee_bps_regime_tolerance_pct": document["fee_bps_regime_tolerance_pct"],
        "spec_evaluation_order": document["spec_evaluation_order"],
        "config_hash": config_hash(POLICY_CONFIG),
    }
    report["window"]["days"] = 90
    return report


def limitations_block() -> dict:
    return {"prohibited_labels": list(PROHIBITED),
            "spec_limitation_notes": list(LIMITATION_NOTES),
            "gate_limit_codes": list(LIMIT_CODES),
            "attachment_policy": "attached verbatim"}


def environment_block() -> dict:
    return {"python_version": "3.13.7 (synthetic)", "python_implementation": "CPython",
            "platform": "synthetic-platform", "numpy_version": "2.5.4",
            "scipy_version": "1.17.0", "statsmodels_version": "0.15.0",
            "blas": {"blas": "Accelerate", "lapack": "Accelerate"},
            "randomness": "none; the estimator is fully deterministic and needs no seed"}


def estimation_block() -> dict:
    return {"estimator": "ols", "method": "OLS",
            "covariance": {"type": "HAC", "kernel": "bartlett", "maxlags": 7,
                           "maxlags_rule": "fixed", "use_correction": True,
                           "use_t": True, "rationale": "baseline weekly timing"},
            "nobs": 60, "df_resid": 58, "r_squared": 0.912, "adj_r_squared": 0.9106,
            "p_value_usage": "p-values are recorded in the contract table only"}


def design_block() -> dict:
    return {"baseline": "difference_log",
            "transformations": {"baseline": "difference_log",
                                "strictly_positive_required": True,
                                "difference_adjacency": "calendar_adjacent_only",
                                "float64_conversion": "explicit_finite_required"},
            "columns": list(COLUMNS), "rows": 60, "rank": 2,
            "condition_number": 3.21, "source_hash": "d" * 64,
            "source_hash_note": "exact decimal design source hash",
            "float64_hex_sha256": "e" * 64,
            "float64_hash_note": "IEEE-754 hex design digest"}


def sample_block(nobs: int = 60) -> dict:
    return {**{"window": dict(WINDOW), "nobs": nobs,
               "first_design_date": "2026-08-07", "last_design_date": "2026-11-03",
               "gate_evaluation": {"usable_observations": nobs},
               "exclusion_policy": "the gate exclusion table is authoritative"},
           **{}}


def inputs_block() -> dict:
    return {"archive_root_name": "research-synthetic", "files": [dict(SYNTHETIC_FILE)],
            "spec_config": {"path": SPEC_CONFIG, "config_hash": config_hash(SPEC_CONFIG)},
            "fit_config_path": "gross_fee_activity_v1_fit.json",
            "gate_policy_path": "readiness_gate_policy_v1.json",
            "code_commit": CODE_COMMIT,
            "code_commit_note": "recorded from the operator-provided --code-commit "
                                "argument; publication requires it (NI-054)",
            "dependency_lock": {"path": "apps/api/uv.lock",
                                "sha256": lock_hash(), "present": True}}


def lock_hash() -> str:
    return hashlib.sha256((REPO / "apps/api/uv.lock").read_bytes()).hexdigest()


def spec_evaluation(spec: dict, verdict: str, codes: list[dict]) -> dict:
    return {"spec": spec, "verdict": verdict, "reason_codes": codes,
            "sample": {"usable_observations": 60}}


def readiness_report() -> dict:
    other_spec = {**SPECIFICATION, "spec_id": "true_revenue_daily_v1",
                  "family": "true_revenue", "declared_target": "protocol_revenue"}
    supply_spec = {**SPECIFICATION, "spec_id": "supply_bounds_activity_v1",
                   "declared_target": "supply_bounds"}
    return {
        "report_type": "model_dataset_readiness",
        "gate_version": 1,
        "policy": gate_policy_block(),
        "window": {**WINDOW, "days": 90},
        "inputs": {"archive_root_name": "research-synthetic",
                   "files": [dict(SYNTHETIC_FILE)],
                   "metric_definitions": {}},
        "prepared_table": {
            "calendar_days": 90, "daily_rows_present": 90, "extract_coverage_days": 90,
            "extract_uncovered_days": [], "extract_parse_error_days": [],
            "series": [{"metric_id": "provider_gross_fees_usd", "dimension": "SRC-LLAMA",
                        "present_days": 90, "missing_days": [], "zero_days": [],
                        "negative_days": [], "calendar_gaps": [],
                        "adjacent_present_pairs": 89, "first_present": WINDOW["start"],
                        "last_present": "2026-11-03", "min": "1.0", "max": "2.0",
                        "float64_finite": True}],
            "supply_windows": {"windows": []},
            "source_comparison": {"agreements": [], "disagreements": []},
            "fee_rate_profile": {"regimes": []},
            "known_caveats": [{"code": "SAVED_ARCHIVE_COHORT", "detail": "synthetic"}],
        },
        "gate_policy": gate_policy_block(),
        "spec_evaluations": [
            spec_evaluation(other_spec, "NOT_READY",
                            [{"code": "TARGET_METRIC_NOT_OBSERVED",
                              "severity": "rejecting", "detail": "OQ-01"}]),
            spec_evaluation(SPECIFICATION, "READY_WITH_LIMITS",
                            [{"code": "MECHANICAL_FEE_VOLUME_RELATION",
                              "severity": "limit", "detail": "fee-on-volume"},
                             {"code": "OQ02_JUDGING_RISK", "severity": "limit",
                              "detail": "proxy acceptance"}]),
            spec_evaluation(supply_spec, "REJECTED",
                            [{"code": "BOUND_ONLY_OUTCOME", "severity": "rejecting",
                              "detail": "lower bounds"}]),
        ],
        "selection": {"selected_spec": "gross_fee_activity_v1",
                      "overall_verdict": "PROXY_ONLY_READY_WITH_LIMITS",
                      "protocol_revenue_ready": False,
                      "rationale": "the named proxy specification is admitted with limits"},
        "oq_register": [{"id": "OQ-01", "status": "open"}],
        "invariants": {},
    }


def fit_manifest() -> dict:
    return {
        "manifest_type": "model_fit_run",
        "fit_version": 1,
        "model": {"model_id": "gross_fee_activity_v1", "model_version": 1,
                  "specification": json.loads(json.dumps(SPECIFICATION))},
        "admission": {"verdict": "READY_WITH_LIMITS", "reason_codes": [],
                      "note": "admitted by the NI-051 gate"},
        "fit_config": fit_config_block(),
        "gate_policy": {"policy_id": "readiness_gate_policy_v1", "policy_version": 1,
                        "config_hash": config_hash(POLICY_CONFIG)},
        "sample": sample_block(),
        "design": design_block(),
        "estimation": estimation_block(),
        "coefficients": json.loads(json.dumps(COEFFICIENTS)),
        "diagnostics": {"note": "the full battery belongs to NI-053"},
        "limitations": limitations_block(),
        "environment": environment_block(),
        "inputs": inputs_block(),
        "reproduction": {"command": "python -m near_api.research fit --archive-root "
                                    "<research root> --out-dir research/models/reports "
                                    "--code-commit <git sha>",
                         "coefficient_rtol": "0.00000001",
                         "coefficient_atol": "0.0000000001",
                         "determinism": "no wall-clock fields; inputs pinned by SHA-256"},
        "invariants": {"spec_reused_unchanged": True, "gate_admission_verified": True,
                       "no_p_value_driven_search": True, "limitations_attached": True,
                       "sample_matches_gate": True},
    }


def diagnostics_report() -> dict:
    manifest = fit_manifest()
    return {
        "report_type": "model_diagnostics_report",
        "diagnostics_version": 1,
        "model": manifest["model"],
        "admission": {"verdict": "READY_WITH_LIMITS", "reason_codes": [],
                      "note": "re-evaluated unchanged"},
        "fit_config": manifest["fit_config"],
        "diagnostics_config": diagnostics_config_block(),
        "gate_policy": manifest["gate_policy"],
        "sample": manifest["sample"],
        "estimation_results": {**estimation_block(), "rank": 2, "condition_number": 3.21,
                               "coefficients": json.loads(json.dumps(COEFFICIENTS)),
                               "source": "the NI-052 estimator's own result"},
        "stationarity": {"note": "ADF/KPSS with preregistered settings",
                         "tests": [
                             {"test": "adf", "series": "dependent", "status": "computed",
                              "statistic": -3.2, "p_value": 0.02,
                              "settings": {"maxlag": 7, "autolag": None}},
                             {"test": "kpss", "series": "explanatory", "status": "computed",
                              "statistic": 0.4, "p_value": 0.06,
                              "settings": {"nlags": 7}},
                         ]},
        "residual_diagnostics": {
            "acf": {"nlags": 7, "values": [0.1, -0.05]},
            "ljung_box": {"lags": [3, 7], "results": [{"lag": 3, "p_value": 0.4}]},
            "heteroskedasticity": {"test": "breusch_pagan", "lm_stat": 1.2,
                                   "p_value": 0.55},
            "influence": {"measure": "cooks_distance", "threshold": "4/nobs",
                          "flagged": []},
        },
        "sensitivity": {"note": "only preregistered presets", "presets": [
            {"preset_id": "hac_maxlags_3", "kind": "covariance_maxlags",
             "status": "estimated"},
            {"preset_id": "hac_maxlags_14", "kind": "covariance_maxlags",
             "status": "estimated"},
            {"preset_id": "source_dashboard", "kind": "source_alternative",
             "status": "estimated"},
            {"preset_id": "price_basis_end", "kind": "price_basis_alternative",
             "status": "not_applicable", "reason_code": "no_bound_variable_to_swap"},
        ]},
        "interpretation": {"template_id": "bounded_association_v1",
                           "sentences": ["The estimated association is bounded and "
                                         "non-causal."],
                           "authoring_note": "an authored interpretation, if any, is "
                                             "added at publication (NI-054)"},
        "limitations": limitations_block(),
        "environment": environment_block(),
        "inputs": {**inputs_block(),
                   "fit_config_hash": config_hash(FIT_CONFIG),
                   "diagnostics_config_path": "gross_fee_activity_v1_diagnostics.json",
                   "diagnostics_config_hash": config_hash(DIAGNOSTICS_CONFIG)},
        "reproduction": manifest["reproduction"],
        "invariants": {},
    }


def approval_document(manifests: dict) -> dict:
    return {
        "approval_type": APPROVAL_TYPE,
        "decision": DECISION_APPROVE,
        "reviewer": "ILYUTKICK (role A agent, synthetic test review)",
        "review_reference": "synthetic test approval — not a real review",
        "reviewed_at": "2026-11-08T00:00:00Z",
        "approved_artifacts": {key: canonical_artifact_hash(manifests[key])
                               for key in MANIFEST_KEYS},
        "notes": "synthetic fixture",
    }


def valid_bundle() -> dict:
    manifests = {"fit_manifest": fit_manifest(),
                 "diagnostics_report": diagnostics_report(),
                 "readiness_report": readiness_report()}
    manifests["publication_approval"] = approval_document(manifests)
    manifests["run_id"] = None
    return manifests


def bundle_dir(root: Path, bundle: dict) -> Path:
    directory = root / "run-bundle"
    directory.mkdir(parents=True, exist_ok=True)
    for key in MANIFEST_KEYS:
        (directory / f"{key}.json").write_text(render_canonical(bundle[key]),
                                               encoding="utf-8")
    (directory / "publication_approval.json").write_text(
        render_canonical(bundle["publication_approval"]), encoding="utf-8")
    return directory


def checks(report) -> dict[str, bool]:
    return {check.check: check.passed for check in report.checks}


class ValidBundleTests(unittest.TestCase):
    """A complete synthetic bundle passes every gate check."""

    @classmethod
    def setUpClass(cls):
        cls.bundle = valid_bundle()
        cls.report = verify_bundle(cls.bundle)

    def test_all_checks_pass(self):
        failures = [f"{check.check}: {check.detail}" for check in self.report.checks
                    if not check.passed]
        self.assertEqual(failures, [])
        self.assertTrue(self.report.passed)

    def test_named_gate_checks_present(self):
        present = set(checks(self.report))
        for expected in ("bundle_completeness", "approval_decision", "approval_binding",
                         "data_manifest", "code_manifest", "lock_manifest",
                         "config_identity", "spec_identity", "sample_identity",
                         "gate_admission", "readiness_report_shape", "design_manifest",
                         "result_manifest", "diagnostics_completeness",
                         "limitations_attached", "tolerances_recorded"):
            self.assertIn(expected, present, f"missing gate check: {expected}")

    def test_run_identity_is_deterministic(self):
        hashes = {key: canonical_artifact_hash(self.bundle[key]) for key in MANIFEST_KEYS}
        run_id = derive_run_id(hashes)
        self.assertIsInstance(run_id, UUID)
        expected = uuid5(UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8"),
                         "near-intelligence:model-run:v1:"
                         + hashlib.sha256(render_canonical(
                             {key: hashes[key] for key in MANIFEST_KEYS}).encode("utf-8")
                         ).hexdigest())
        self.assertEqual(run_id, expected)
        self.assertEqual(derive_run_id(hashes), run_id)
        # The identity ignores the approval: re-approval keeps the same run.
        changed = valid_bundle()
        changed["publication_approval"]["reviewer"] = "another reviewer"
        self.assertEqual(derive_run_id({key: canonical_artifact_hash(changed[key])
                                        for key in MANIFEST_KEYS}), run_id)

    def test_payload_projection_matches_manifests(self):
        hashes = {key: canonical_artifact_hash(self.bundle[key]) for key in MANIFEST_KEYS}
        run_id = derive_run_id(hashes)
        payload = publication_payload(self.bundle, run_id)
        self.assertEqual(payload["spec_id"], "gross_fee_activity_v1")
        self.assertEqual(payload["gate_verdict"], "READY_WITH_LIMITS")
        self.assertEqual(payload["nobs"], 60)
        self.assertEqual(payload["sample_start"], WINDOW["start"])
        self.assertEqual(payload["code_commit"], CODE_COMMIT)
        self.assertEqual(payload["dependency_lock_sha256"], lock_hash())
        self.assertEqual(payload["coefficient_rtol"], "0.00000001")
        self.assertEqual(set(payload["artifacts"]),
                         {"fit_manifest", "diagnostics_report", "readiness_report",
                          "publication_approval"})

    def test_bundle_load_from_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = bundle_dir(Path(tmp), self.bundle)
            loaded = load_bundle(directory)
            report = verify_bundle(loaded)
            self.assertTrue(report.passed,
                            [c.detail for c in report.checks if not c.passed])
            # A served bundle file round-trips with its derived run id.
            hashes = {key: canonical_artifact_hash(loaded[key]) for key in MANIFEST_KEYS}
            run_id = derive_run_id(hashes)
            document = bundle_document(run_id, loaded,
                                       {**hashes,
                                        "publication_approval": canonical_artifact_hash(
                                            loaded["publication_approval"])},
                                       loaded["publication_approval"])
            served = Path(tmp) / "manifest.json"
            served.write_text(render_canonical(document), encoding="utf-8")
            reloaded = load_bundle(served)
            self.assertEqual(reloaded["run_id"], run_id)
            self.assertTrue(verify_bundle(reloaded).passed)


class GateRefusalTests(unittest.TestCase):
    """Every broken component is refused with a named check (fail closed)."""

    def verify_mutated(self, mutate, *, rebind: bool = True):
        bundle = valid_bundle()
        mutate(bundle)
        # Unless the test targets the approval binding itself, re-bind the
        # approval so each mutation exercises its own named check.
        if rebind:
            bundle["publication_approval"]["approved_artifacts"] = {
                key: canonical_artifact_hash(bundle[key]) for key in MANIFEST_KEYS}
        return verify_bundle(bundle)

    def assert_refused(self, report, check_id: str):
        failures = [check for check in report.checks if not check.passed]
        self.assertFalse(report.passed)
        self.assertIn(check_id, {check.check for check in failures},
                      f"expected {check_id} among {[c.check for c in failures]}")

    def test_missing_diagnostics_component(self):
        bundle = valid_bundle()
        bundle["diagnostics_report"] = {"report_type": "something_else"}
        self.assert_refused(verify_bundle(bundle), "bundle_completeness")

    def test_missing_approval(self):
        bundle = valid_bundle()
        del bundle["publication_approval"]
        report = verify_bundle(bundle)
        self.assertFalse(report.passed)

    def test_unreviewed_decision_refused(self):
        def mutate(bundle):
            bundle["publication_approval"]["decision"] = "needs-another-look"
            # Keep the binding hashes consistent so the decision is the failure.
            bundle["publication_approval"]["approved_artifacts"] = {
                key: canonical_artifact_hash(bundle[key]) for key in MANIFEST_KEYS}
        self.assert_refused(self.verify_mutated(mutate), "approval_decision")

    def test_tampered_manifest_breaks_approval_binding(self):
        def mutate(bundle):
            bundle["fit_manifest"]["estimation"]["r_squared"] = 0.999
        self.assert_refused(self.verify_mutated(mutate, rebind=False),
                            "approval_binding")

    def test_wrong_binding_hash_refused(self):
        def mutate(bundle):
            bundle["publication_approval"]["approved_artifacts"]["fit_manifest"] = "0" * 64
        self.assert_refused(self.verify_mutated(mutate, rebind=False),
                            "approval_binding")

    def test_missing_data_manifest(self):
        def mutate(bundle):
            bundle["fit_manifest"]["inputs"]["files"] = []
        self.assert_refused(self.verify_mutated(mutate), "data_manifest")

    def test_diverging_archive_file_sets_refused(self):
        def mutate(bundle):
            bundle["diagnostics_report"]["inputs"]["files"] = [
                {**SYNTHETIC_FILE, "sha256": "f" * 64}]
        self.assert_refused(self.verify_mutated(mutate), "data_manifest")

    def test_bad_input_hash_format_refused(self):
        def mutate(bundle):
            bundle["fit_manifest"]["inputs"]["files"][0]["sha256"] = "not-a-hash"
        self.assert_refused(self.verify_mutated(mutate), "data_manifest")

    def test_missing_code_commit_refused(self):
        def mutate(bundle):
            bundle["fit_manifest"]["inputs"]["code_commit"] = None
        self.assert_refused(self.verify_mutated(mutate), "code_manifest")

    def test_diverging_code_commit_refused(self):
        def mutate(bundle):
            bundle["diagnostics_report"]["inputs"]["code_commit"] = "b" * 40
        self.assert_refused(self.verify_mutated(mutate), "code_manifest")

    def test_missing_lock_identity_refused(self):
        def mutate(bundle):
            bundle["fit_manifest"]["inputs"]["dependency_lock"]["sha256"] = None
        self.assert_refused(self.verify_mutated(mutate), "lock_manifest")

    def test_wrong_lock_hash_refused(self):
        def mutate(bundle):
            bundle["fit_manifest"]["inputs"]["dependency_lock"]["sha256"] = "1" * 64
        self.assert_refused(self.verify_mutated(mutate), "lock_manifest")

    def test_wrong_spec_config_hash_refused(self):
        def mutate(bundle):
            bundle["fit_manifest"]["inputs"]["spec_config"]["config_hash"] = "2" * 64
        self.assert_refused(self.verify_mutated(mutate), "config_identity")

    def test_wrong_diagnostics_config_hash_refused(self):
        def mutate(bundle):
            bundle["diagnostics_report"]["diagnostics_config"]["config_hash"] = "3" * 64
        self.assert_refused(self.verify_mutated(mutate), "config_identity")

    def test_wrong_gate_policy_hash_refused(self):
        def mutate(bundle):
            bundle["readiness_report"]["policy"]["config_hash"] = "4" * 64
        self.assert_refused(self.verify_mutated(mutate), "config_identity")

    def test_spec_identity_mismatch_refused(self):
        def mutate(bundle):
            bundle["diagnostics_report"]["model"]["model_id"] = "purchases_activity_v1"
        self.assert_refused(self.verify_mutated(mutate), "spec_identity")

    def test_unadmitted_verdict_refused(self):
        def mutate(bundle):
            bundle["fit_manifest"]["admission"]["verdict"] = "NOT_READY"
        self.assert_refused(self.verify_mutated(mutate), "gate_admission")

    def test_readiness_verdict_divergence_refused(self):
        def mutate(bundle):
            bundle["readiness_report"]["spec_evaluations"][1]["verdict"] = "REJECTED"
        self.assert_refused(self.verify_mutated(mutate), "gate_admission")

    def test_sample_window_mismatch_refused(self):
        def mutate(bundle):
            bundle["diagnostics_report"]["sample"]["window"]["start"] = "2026-08-07"
        self.assert_refused(self.verify_mutated(mutate), "sample_identity")

    def test_nobs_mismatch_refused(self):
        def mutate(bundle):
            bundle["diagnostics_report"]["sample"]["nobs"] = 59
        self.assert_refused(self.verify_mutated(mutate), "sample_identity")

    def test_design_without_hashes_refused(self):
        def mutate(bundle):
            bundle["fit_manifest"]["design"]["source_hash"] = "short"
        self.assert_refused(self.verify_mutated(mutate), "design_manifest")

    def test_design_rows_deviation_refused(self):
        def mutate(bundle):
            bundle["fit_manifest"]["design"]["rows"] = 61
        self.assert_refused(self.verify_mutated(mutate), "design_manifest")

    def test_non_finite_coefficient_refused(self):
        # An infinite estimate can only enter through hand-written JSON
        # (Python serializes it as the Infinity constant); loading refuses the
        # constant outright, so NaN/Infinity can never become a recorded result.
        bundle = valid_bundle()
        bundle["fit_manifest"]["coefficients"][1]["estimate"] = 1e400
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        for key in MANIFEST_KEYS:
            (directory / f"{key}.json").write_text(
                json.dumps(bundle[key], sort_keys=True, indent=2) + "\n",
                encoding="utf-8")
        (directory / "publication_approval.json").write_text(
            json.dumps(bundle["publication_approval"], sort_keys=True, indent=2) + "\n",
            encoding="utf-8")
        with self.assertRaises(PublicationGateError):
            load_bundle(directory)

    def test_inverted_confidence_interval_refused(self):
        def mutate(bundle):
            bundle["fit_manifest"]["coefficients"][0]["ci95_low"] = 0.5
            bundle["fit_manifest"]["coefficients"][0]["ci95_high"] = 0.1
        self.assert_refused(self.verify_mutated(mutate), "result_manifest")

    def test_estimate_outside_interval_refused(self):
        def mutate(bundle):
            bundle["fit_manifest"]["coefficients"][1]["ci95_high"] = 0.5
        self.assert_refused(self.verify_mutated(mutate), "result_manifest")

    def test_coefficient_table_not_bound_to_design_refused(self):
        def mutate(bundle):
            bundle["fit_manifest"]["coefficients"][1]["name"] = "invented_regressor"
        self.assert_refused(self.verify_mutated(mutate), "result_manifest")

    def test_diagnostics_coefficient_divergence_refused(self):
        def mutate(bundle):
            bundle["diagnostics_report"]["estimation_results"]["coefficients"][1]\
                ["estimate"] = 42.0
        self.assert_refused(self.verify_mutated(mutate), "result_manifest")

    def test_undefined_test_without_reason_refused(self):
        def mutate(bundle):
            bundle["diagnostics_report"]["stationarity"]["tests"][0] = {
                "test": "adf", "status": "undefined"}
        self.assert_refused(self.verify_mutated(mutate), "diagnostics_completeness")

    def test_missing_residual_block_refused(self):
        def mutate(bundle):
            del bundle["diagnostics_report"]["residual_diagnostics"]["ljung_box"]
        self.assert_refused(self.verify_mutated(mutate), "diagnostics_completeness")

    def test_invented_sensitivity_preset_refused(self):
        def mutate(bundle):
            bundle["diagnostics_report"]["sensitivity"]["presets"] = [
                {"preset_id": "data_dredged", "status": "estimated"}]
        self.assert_refused(self.verify_mutated(mutate), "diagnostics_completeness")

    def test_free_form_interpretation_refused(self):
        def mutate(bundle):
            bundle["diagnostics_report"]["interpretation"] = {
                "text": "this model proves the thesis"}
        self.assert_refused(self.verify_mutated(mutate), "diagnostics_completeness")

    def test_missing_limitations_refused(self):
        def mutate(bundle):
            bundle["fit_manifest"]["limitations"]["spec_limitation_notes"] = []
        self.assert_refused(self.verify_mutated(mutate), "limitations_attached")

    def test_edited_limitations_between_artifacts_refused(self):
        def mutate(bundle):
            bundle["diagnostics_report"]["limitations"]["spec_limitation_notes"] = \
                ["softened note"]
        self.assert_refused(self.verify_mutated(mutate), "limitations_attached")

    def test_missing_tolerances_refused(self):
        def mutate(bundle):
            del bundle["fit_manifest"]["reproduction"]["coefficient_rtol"]
        self.assert_refused(self.verify_mutated(mutate), "tolerances_recorded")

    def test_wrong_readiness_shape_refused(self):
        def mutate(bundle):
            bundle["readiness_report"]["selection"]["overall_verdict"] = ""
        self.assert_refused(self.verify_mutated(mutate), "readiness_report_shape")

    def test_tampered_served_bundle_run_identity_refused(self):
        hashes = {key: canonical_artifact_hash(valid_bundle()[key]) for key in MANIFEST_KEYS}
        bundle = valid_bundle()
        document = bundle_document(derive_run_id(hashes), bundle,
                                   {**hashes, "publication_approval":
                                    canonical_artifact_hash(
                                        bundle["publication_approval"])},
                                   bundle["publication_approval"])
        document["run_id"] = "00000000-0000-0000-0000-000000000000"
        with tempfile.TemporaryDirectory() as tmp:
            served = Path(tmp) / "manifest.json"
            served.write_text(render_canonical(document), encoding="utf-8")
            self.assert_refused(verify_bundle(load_bundle(served)), "run_identity")


class LoadAndRenderTests(unittest.TestCase):
    """Bundle loading, canonical rendering and no-network structure."""

    def test_missing_bundle_file_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "incomplete"
            directory.mkdir()
            (directory / "fit_manifest.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(PublicationGateError):
                load_bundle(directory)

    def test_nonexistent_bundle_refused(self):
        with self.assertRaises(PublicationGateError):
            load_bundle(Path(tempfile.gettempdir()) / "ni054-does-not-exist")

    def test_nan_in_bundle_refused(self):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        bundle = valid_bundle()
        bundle["fit_manifest"]["coefficients"][0]["estimate"] = float("nan")
        raw = json.dumps(bundle["fit_manifest"], sort_keys=True, indent=2) + "\n"
        (directory / "fit_manifest.json").write_text(raw, encoding="utf-8")
        with self.assertRaises(PublicationGateError):
            load_bundle(directory)

    def test_canonical_rendering_matches_research_cli_renderers(self):
        # The approval binding is stable only if this renderer is byte-identical
        # to the research CLIs' renderer (same arguments, trailing newline).
        document = {"z": 1, "a": {"c": [1, 2], "b": "текст"}}
        self.assertEqual(render_canonical(document),
                         json.dumps(document, ensure_ascii=False, sort_keys=True,
                                    indent=2) + "\n")

    def test_publication_module_has_no_transport_imports(self):
        # Structural no-network evidence: the gate and its CLI never import a
        # transport library; verification and publication are file/DB work.
        import near_api.research.publication as module
        source = Path(module.__file__).read_text(encoding="utf-8")
        for banned in ("import socket", "import urllib", "import http", "import requests",
                       "import httpx", "urllib.request", "socket.socket"):
            self.assertNotIn(banned, source)

    def test_models_package_never_imports_research(self):
        # Structural no-fit-trigger evidence: the public API's model package
        # imports nothing from near_api.research (only the CLI and the
        # operator store do).
        for path in (REPO / "apps/api/src/near_api/models").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("near_api.research", source, path.name)


class CliContractTests(unittest.TestCase):
    """verify/publish exit codes through the research CLI dispatch."""

    @classmethod
    def setUpClass(cls):
        cls.directory = Path(tempfile.mkdtemp(prefix="ni054-cli-"))
        bundle_dir(cls.directory, valid_bundle())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.directory, ignore_errors=True)

    def verify(self, *arguments):
        return subprocess.run(
            [sys.executable, "-m", "near_api.research", "verify", *arguments],
            cwd=REPO, env={**os.environ}, capture_output=True, text=True, timeout=180)

    def test_verify_without_offline_flag_is_contract_error(self):
        completed = self.verify("--bundle", str(self.directory / "run-bundle"))
        self.assertEqual(completed.returncode, 4)
        self.assertIn("--offline", completed.stderr)

    def test_verify_valid_bundle_exits_zero_and_prints_hashes(self):
        completed = self.verify("--bundle", str(self.directory / "run-bundle"),
                                "--offline")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("PASSED", completed.stdout)
        self.assertIn("approved_artifacts", completed.stdout)
        hashes = json.loads(completed.stdout.split(
            "approved_artifacts):", 1)[1])
        self.assertEqual(hashes["fit_manifest"],
                         canonical_artifact_hash(fit_manifest()))

    def test_verify_tampered_bundle_exits_four(self):
        tampered = self.directory / "tampered"
        shutil.copytree(self.directory / "run-bundle", tampered)
        document = json.loads((tampered / "fit_manifest.json").read_text("utf-8"))
        document["estimation"]["r_squared"] = 0.42
        (tampered / "fit_manifest.json").write_text(
            render_canonical(document), encoding="utf-8")
        completed = self.verify("--bundle", str(tampered), "--offline")
        self.assertEqual(completed.returncode, 4, completed.stdout)
        self.assertIn("approval_binding", completed.stdout)
        self.assertIn("FAILED", completed.stdout + completed.stderr)

    def test_verify_usage_error_exits_two(self):
        completed = self.verify("--bundle")
        self.assertEqual(completed.returncode, 2)

    def test_forwarded_verbs_still_forward(self):
        # The NI-052/NI-053 forwarding contract survives the new verbs:
        # `fit --help` reaches the module's own parser and exit code 2 comes
        # from argparse for an unknown command.
        helped = subprocess.run(
            [sys.executable, "-m", "near_api.research", "fit", "--help"],
            cwd=REPO, env={**os.environ}, capture_output=True, text=True, timeout=180)
        self.assertEqual(helped.returncode, 0, helped.stderr)
        self.assertIn("--archive-root", helped.stdout)
        unknown = subprocess.run(
            [sys.executable, "-m", "near_api.research", "transmogrify"],
            cwd=REPO, env={**os.environ}, capture_output=True, text=True, timeout=180)
        self.assertEqual(unknown.returncode, 2)


if __name__ == "__main__":
    unittest.main()
