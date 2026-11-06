"""NI-051 real-archive readiness gate reconciliation (operator-local).

These cases run the readiness gate against the actual archive handoff and
therefore execute only where NI_REAL_ARCHIVE_ROOT is set — the operator's
machine. CI and fresh clones have no archive bytes by design
(docs/COLLABORATION.md), so this file is NOT in the cluster runner's
discovery list; run it locally with:

  NI_REAL_ARCHIVE_ROOT=/path/to/research uv run --project apps/api \
      python -m unittest discover -s apps/api/tests \
      -p test_models_readiness_real_archive.py -v

The archive is opened READ-ONLY; reports are written only to a disposable
temporary directory. The expected verdicts and reason codes below pin the
gate decision for the November 2026 handoff (window 2026-08-06..11-04).
Synthetic coverage lives in test_models_readiness.py (always runs).
"""

import datetime as dt
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODELS_DIR = REPO_ROOT / "research" / "models"
CONFIGS_DIR = MODELS_DIR / "configs"


def _load_readiness_module():
    spec = importlib.util.spec_from_file_location("ni051_readiness_real",
                                                  MODELS_DIR / "readiness.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


readiness = _load_readiness_module()

REAL_ARCHIVE = Path(os.environ["NI_REAL_ARCHIVE_ROOT"]).resolve() \
    if os.environ.get("NI_REAL_ARCHIVE_ROOT") else None

WINDOW_START = dt.date(2026, 8, 6)
WINDOW_END_EXCLUSIVE = dt.date(2026, 11, 4)


def _tree_digest(root: Path) -> dict:
    state = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            state[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return state


@unittest.skipUnless(REAL_ARCHIVE and REAL_ARCHIVE.is_dir(),
                     "real archive handoff not present (NI_REAL_ARCHIVE_ROOT)")
class RealArchiveReadinessTests(unittest.TestCase):
    """Run the gate over the real archive and pin its verdicts."""

    @classmethod
    def setUpClass(cls):
        base = os.environ.get("NI_TEST_TMP_DIR")
        cls.tmp = Path(tempfile.mkdtemp(prefix="ni051-real-", dir=base) if base
                       else tempfile.mkdtemp(prefix="ni051-real-"))
        cls.archive_digest = _tree_digest(REAL_ARCHIVE)
        cls.out = cls.tmp / "out-a"
        cls.report = readiness.run_readiness_gate(
            archive_root=REAL_ARCHIVE, configs_dir=CONFIGS_DIR,
            policy_path=CONFIGS_DIR / "readiness_gate_policy_v1.json")
        cls.replay = readiness.run_readiness_gate(
            archive_root=REAL_ARCHIVE, configs_dir=CONFIGS_DIR,
            policy_path=CONFIGS_DIR / "readiness_gate_policy_v1.json")
        readiness.write_report(cls.report, cls.out)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def evaluation(self, spec_id: str) -> dict:
        for evaluation in self.report["spec_evaluations"]:
            if evaluation["spec"]["spec_id"] == spec_id:
                return evaluation
        self.fail(f"spec {spec_id} missing from the report")

    def codes(self, evaluation: dict) -> set:
        return {entry["code"] for entry in evaluation["reason_codes"]}

    def test_window_covers_the_full_90_day_handoff(self):
        self.assertEqual(self.report["window"],
                         {"start": "2026-08-06", "end_exclusive": "2026-11-04",
                          "days": 90})
        prepared = self.report["prepared_table"]
        self.assertEqual(prepared["calendar_days"], 90)
        self.assertEqual(prepared["daily_rows_present"], 90)
        self.assertEqual(prepared["extract_coverage_days"], 90)
        self.assertEqual(prepared["extract_uncovered_days"], [])
        self.assertEqual(prepared["extract_parse_error_days"], [])
        self.assertEqual(len(self.report["inputs"]["files"]), 4)

    def test_gated_protocol_revenue_is_missing_on_every_day(self):
        profile = next(series for series in self.report["prepared_table"]["series"]
                       if series["series_key"] == "protocol_revenue_usd|")
        self.assertEqual(profile["present_days"], 0)
        self.assertEqual(len(profile["missing_days"]), 90)
        self.assertEqual(profile["availability"], "G")

    def test_provider_series_are_complete_positive_and_adjacent(self):
        for key in ("provider_intents_volume_usd|SRC-LLAMA",
                    "provider_intents_volume_usd|SRC-DASHBOARD",
                    "provider_gross_fees_usd|SRC-LLAMA",
                    "provider_gross_fees_usd|SRC-DASHBOARD"):
            profile = next(series for series in self.report["prepared_table"]["series"]
                           if series["series_key"] == key)
            self.assertEqual(profile["present_days"], 90, key)
            self.assertEqual(profile["missing_days"], [], key)
            self.assertEqual(profile["zero_days"], [], key)
            self.assertEqual(profile["negative_days"], [], key)
            self.assertEqual(profile["adjacent_present_pairs"], 89, key)
            self.assertTrue(profile["float64_finite"], key)

    def test_true_revenue_spec_is_not_ready(self):
        evaluation = self.evaluation("true_revenue_daily_v1")
        self.assertEqual(evaluation["verdict"], "NOT_READY")
        self.assertTrue({"GATED_METRIC_NO_OBSERVATIONS",
                         "PROTOCOL_REVENUE_NOT_ESTABLISHED_OQ01"}
                        <= self.codes(evaluation))
        self.assertEqual(evaluation["sample"]["usable_observations"], 0)

    def test_named_proxy_is_selected_with_limits(self):
        evaluation = self.evaluation("gross_fee_activity_v1")
        self.assertEqual(evaluation["verdict"], "READY_WITH_LIMITS")
        self.assertEqual(self.report["selection"]["selected_spec"],
                         "gross_fee_activity_v1")
        self.assertEqual(self.report["selection"]["overall_verdict"],
                         "PROXY_ONLY_READY_WITH_LIMITS")
        self.assertFalse(self.report["selection"]["protocol_revenue_ready"])
        expected = {"MECHANICAL_FEE_VOLUME_RELATIONSHIP", "PROXY_NOT_PROTOCOL_REVENUE",
                    "OQ02_JUDGING_ACCEPTANCE_RISK", "SINGLE_PROVIDER_LINEAGE_NOT_INDEPENDENT",
                    "SOURCE_REVISIONS_POSSIBLE", "SHORT_SAMPLE_NO_LONG_RUN_CLAIM",
                    "NO_CAUSAL_IDENTIFICATION"}
        self.assertEqual(expected, self.codes(evaluation))
        self.assertEqual(evaluation["sample"]["complete_days"], 90)
        self.assertEqual(evaluation["sample"]["usable_observations"], 89)
        self.assertEqual(evaluation["sample"]["excluded_days_count"], 0)

    def test_supply_bound_spec_is_rejected_with_archive_numbers(self):
        evaluation = self.evaluation("supply_bounds_activity_v1")
        self.assertEqual(evaluation["verdict"], "REJECTED")
        expected = {"LOWER_BOUND_SERIES_NOT_EXACT_OUTCOME", "WINDOW_AGGREGATE_NOT_DAILY",
                    "MINT_HEADER_AUDIT_INCOMPLETE"}
        self.assertTrue(expected <= self.codes(evaluation))
        detail = " ".join(entry["detail"] for entry in evaluation["reason_codes"])
        self.assertIn("6 of 297", detail)
        supply = self.report["prepared_table"]["supply_windows"]
        self.assertEqual(supply["mint_headers_verified_total"], 6)
        self.assertEqual(supply["mint_headers_target_total"], 297)
        self.assertEqual(len(supply["atomic_windows"]), 3)
        for window in supply["atomic_windows"]:
            self.assertFalse(window["gross_issuance_and_burn_complete"])
            self.assertEqual(window["days"], 30)
            self.assertEqual(window["bound_kind"], "lower")

    def test_cohort_spec_is_cohort_limited(self):
        evaluation = self.evaluation("purchases_activity_v1")
        self.assertEqual(evaluation["verdict"], "READY_WITH_LIMITS")
        self.assertIn("COHORT_NOT_MARKET_DEMAND", self.codes(evaluation))
        self.assertIn("PROXY_NOT_PROTOCOL_REVENUE", self.codes(evaluation))
        self.assertNotIn("ZERO_VALUES_EXCLUDE_LOG_SPEC", self.codes(evaluation))
        # The real 90-day window has a purchase observation every day.
        self.assertEqual(evaluation["sample"]["complete_days"], 90)
        self.assertEqual(evaluation["sample"]["verified_zero_days"], [])

    def test_sources_disagree_and_stay_unsummed(self):
        comparison = self.report["prepared_table"]["source_comparison"]
        for name, profile in comparison.items():
            if not isinstance(profile, dict) or "overlapping_days" not in profile:
                continue
            self.assertEqual(profile["overlapping_days"], 90, name)
            self.assertGreater(profile["differing_days"], 0, name)

    def test_invariants_hold_and_oq_register_is_carried(self):
        self.assertEqual(self.report["invariants"], {
            "no_proxy_passes_as_protocol_revenue": True,
            "gaps_and_exclusions_explicit": True,
            "short_attribution_rejected": True,
            "reason_codes_cataloged": True,
        })
        self.assertEqual([item["id"] for item in self.report["oq_register"]],
                         ["OQ-01", "OQ-02", "OQ-08", "OQ-10", "OQ-11"])

    def test_double_run_is_byte_identical_and_archive_untouched(self):
        self.assertEqual(readiness.render_report_json(self.report),
                         readiness.render_report_json(self.replay))
        self.assertEqual(readiness.render_report_markdown(self.report),
                         readiness.render_report_markdown(self.replay))
        self.assertEqual(_tree_digest(REAL_ARCHIVE), self.archive_digest,
                         "the gate modified the read-only archive")
        # The written report files match the in-memory rendering exactly.
        self.assertEqual((self.out / "readiness_report.json").read_text(),
                         readiness.render_report_json(self.report))
        self.assertEqual((self.out / "readiness_report.md").read_text(),
                         readiness.render_report_markdown(self.report))


if __name__ == "__main__":
    unittest.main()
