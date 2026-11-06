"""NI-051 tests: the model dataset readiness gate over synthetic fixtures.

Everything here is invented test data written into disposable temporary
directories; the real research archive is never touched (the real-archive
cases live in test_models_readiness_real_archive.py and run only with
NI_REAL_ARCHIVE_ROOT set). The DB cluster runner executes this module
without database use: the gate is offline research code.
"""

import contextlib
import datetime as dt
import hashlib
import importlib.util
import io
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
    spec = importlib.util.spec_from_file_location("ni051_readiness",
                                                  MODELS_DIR / "readiness.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


readiness = _load_readiness_module()

WINDOW_START = dt.date(2026, 8, 6)
YOCTO_NEAR = "1000000000000000000000000"


def _day(index: int) -> dt.date:
    return WINDOW_START + dt.timedelta(days=index)


def _iso(day: dt.date) -> str:
    return day.isoformat()


def build_synthetic_archive(root: Path, *, days: int = 90,
                            missing_volume_days: tuple = (),
                            zero_volume_days: tuple = (),
                            missing_daily_rows: tuple = ()) -> Path:
    """Create a disposable synthetic archive tree mirroring the handoff layout."""
    end_exclusive = WINDOW_START + dt.timedelta(days=days)
    research = root / "research"
    longitudinal = research / "near-longitudinal" / "data"
    dollar = research / "near-dollar" / "analysis"
    supply = research / "near-supply" / "analysis"
    treasury = research / "near-treasury" / "data"
    for directory in (longitudinal, dollar, supply, treasury):
        directory.mkdir(parents=True, exist_ok=True)

    calendar = [_day(index) for index in range(days)]

    # --- daily flows (prices + provider series) ------------------------------
    daily_rows = []
    for day in calendar:
        if day in missing_daily_rows:
            continue
        zero = day in zero_volume_days
        absent = day in missing_volume_days
        daily_rows.append({
            "date": _iso(day),
            "price_start_utc": "1.7",
            "price_end_utc": "1.8",
            "buy_near": "1000.5",
            "buy_events": 10,
            "payout_near": "2000.25",
            "volume_usd": None if absent else ("0" if zero else "1000000"),
            "gross_fees_usd": None if absent else "15000",
            "dashboard_volume_usd": None if absent else ("0" if zero else "1100000"),
            "dashboard_gross_fees_usd": None if absent else "16000",
        })
    (dollar / "daily.json").write_text(json.dumps(daily_rows), encoding="utf-8")

    # --- longitudinal extract (coverage, quality, one conversion) ------------
    rows = []
    for day in calendar:
        rows.append({"kind": "coverage", "payload": json.dumps({
            "block_date": _iso(day), "intents_outcomes": 1000,
            "successful_intents_outcomes": 900,
            "first_timestamp": f"{_iso(day)}T00:00:00.000001Z",
            "last_timestamp": f"{_iso(day)}T23:59:58.999999Z"})})
        rows.append({"kind": "quality", "payload": json.dumps({
            "block_date": _iso(day), "event_json_logs": 100, "json_parse_errors": 0})})
    rows.append({"kind": "conversion_daily", "payload": json.dumps({
        "block_date": _iso(calendar[0]), "account_id": "collector.testnet",
        "wrap_diff_events": 2, "distinct_intent_hashes": 2, "invalid_wrap_amounts": 0,
        "buy_events": 2, "buy_raw": YOCTO_NEAR, "sell_events": 0, "sell_raw": "0",
        "other_events": 0})})
    (longitudinal / "flows_90d_raw.json").write_text(json.dumps(rows), encoding="utf-8")

    # --- supply summary (one atomic window + total, partial audit) -----------
    # A boundary's bytes are a pure function of its date: the loader rejects
    # the same date appearing with conflicting values.
    def boundary(day: dt.date) -> dict:
        height = 200000 + (day.toordinal() % 1000)
        return {"date": _iso(day), "block_height": height,
                "block_hash": f"hash-{height}",
                "timestamp_ns": str(1785974399657403069 + height),
                "supply_near": "1000000.123456789012345678901234"}

    atomic_end = min(end_exclusive, WINDOW_START + dt.timedelta(days=min(days, 30)))
    window_payload = {
        "start": _iso(WINDOW_START), "end_exclusive": _iso(atomic_end),
        "days": (atomic_end - WINDOW_START).days,
        "opening": boundary(WINDOW_START - dt.timedelta(days=1)),
        "closing": boundary(atomic_end - dt.timedelta(days=1)),
        "positive_supply_changes_near": "50000.5",
        "negative_supply_changes_near": "500.25",
        "verified_simultaneous_burn_near": "0.0355821760331987",
        "verified_mint_headers": 1,
        "gross_issuance_and_burn_complete": False,
    }
    total_payload = {
        "start": _iso(WINDOW_START), "end_exclusive": _iso(end_exclusive),
        "days": days,
        "opening": boundary(WINDOW_START - dt.timedelta(days=1)),
        "closing": boundary(end_exclusive - dt.timedelta(days=1)),
        "positive_supply_changes_near": "150000.5",
        "negative_supply_changes_near": "1500.25",
        "verified_simultaneous_burn_near": "0.0355821760331987",
        "verified_mint_headers": 1,
        "gross_issuance_and_burn_complete": False,
    }
    supply_summary = {
        "method": "synthetic fixture",
        "coverage_days": days, "broken_links": 0,
        "mint_headers_verified": 1, "mint_headers_target": 3, "missing_mint_headers": 2,
        "periods": [window_payload], "total": total_payload,
    }
    (supply / "summary.json").write_text(json.dumps(supply_summary), encoding="utf-8")

    # --- treasury snapshot ----------------------------------------------------
    (treasury / "summary.json").write_text(json.dumps({
        "pinned_rpc_block_height": 300000,
        "pinned_rpc_block_hash": "treasury-hash",
        "pinned_rpc_time_utc": f"{_iso(end_exclusive - dt.timedelta(days=1))}T23:59:59Z",
        "native_balance_total_near": "4140077.369748916078007362148128",
        "snapshots": [{"account_id": "buybacks.multisignature.near",
                       "native_balance_near": "2167847.131051440139635213430792"}],
    }), encoding="utf-8")
    return research


def _tree_digest(root: Path) -> dict:
    state = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            state[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return state


def _copy_spec_configs(destination: Path) -> None:
    """Copy only specification configs; the gate policy is never a spec."""
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(CONFIGS_DIR.glob("*.json")):
        if path.name == "readiness_gate_policy_v1.json":
            continue
        shutil.copy(path, destination / path.name)


class ReadinessGateTestCase(unittest.TestCase):
    """Shared fixture handling; never writes inside the research directory."""

    def setUp(self):
        base = os.environ.get("NI_TEST_TMP_DIR")
        self.tmp = Path(tempfile.mkdtemp(prefix="ni051-", dir=base) if base
                        else tempfile.mkdtemp(prefix="ni051-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.archive = build_synthetic_archive(self.tmp / "archive-a")
        self.archive_digest = _tree_digest(self.archive)
        self.out = self.tmp / "out"
        self.policy = CONFIGS_DIR / "readiness_gate_policy_v1.json"

    def run_gate(self, *, archive: Path | None = None, policy: Path | None = None,
                 configs: Path | None = None) -> dict:
        return readiness.run_readiness_gate(
            archive_root=archive or self.archive,
            configs_dir=configs or CONFIGS_DIR,
            policy_path=policy or self.policy)

    def evaluation(self, report: dict, spec_id: str) -> dict:
        for evaluation in report["spec_evaluations"]:
            if evaluation["spec"]["spec_id"] == spec_id:
                return evaluation
        self.fail(f"spec {spec_id} missing from the report")

    def codes(self, evaluation: dict) -> set:
        return {entry["code"] for entry in evaluation["reason_codes"]}

    def assert_archive_untouched(self):
        self.assertEqual(_tree_digest(self.archive), self.archive_digest,
                         "the gate modified the read-only archive")


class GateVerdictTests(ReadinessGateTestCase):

    def test_full_sample_admits_named_proxy_with_limits_only(self):
        report = self.run_gate()
        self.assertEqual(report["selection"]["overall_verdict"],
                         "PROXY_ONLY_READY_WITH_LIMITS")
        self.assertEqual(report["selection"]["selected_spec"], "gross_fee_activity_v1")
        self.assertFalse(report["selection"]["protocol_revenue_ready"])
        proxy = self.evaluation(report, "gross_fee_activity_v1")
        self.assertEqual(proxy["verdict"], "READY_WITH_LIMITS")
        self.assertEqual(proxy["sample"]["complete_days"], 90)
        self.assertEqual(proxy["sample"]["usable_observations"], 89)
        self.assertIn("MECHANICAL_FEE_VOLUME_RELATIONSHIP", self.codes(proxy))
        self.assertIn("OQ02_JUDGING_ACCEPTANCE_RISK", self.codes(proxy))
        self.assertIn("PROXY_NOT_PROTOCOL_REVENUE", self.codes(proxy))
        self.assertIn("SHORT_SAMPLE_NO_LONG_RUN_CLAIM", self.codes(proxy))
        self.assert_archive_untouched()

    def test_true_revenue_is_not_ready_with_oq01_reasons(self):
        report = self.run_gate()
        true_revenue = self.evaluation(report, "true_revenue_daily_v1")
        self.assertEqual(true_revenue["verdict"], "NOT_READY")
        expected = {"GATED_METRIC_NO_OBSERVATIONS",
                    "PROTOCOL_REVENUE_NOT_ESTABLISHED_OQ01"}
        self.assertTrue(expected <= self.codes(true_revenue),
                        self.codes(true_revenue))
        self.assertEqual(self.evaluation(report, "true_revenue_daily_v1")
                         ["sample"]["usable_observations"], 0)

    def test_lower_bound_supply_spec_is_rejected(self):
        report = self.run_gate()
        supply = self.evaluation(report, "supply_bounds_activity_v1")
        self.assertEqual(supply["verdict"], "REJECTED")
        expected = {"LOWER_BOUND_SERIES_NOT_EXACT_OUTCOME", "WINDOW_AGGREGATE_NOT_DAILY",
                    "MINT_HEADER_AUDIT_INCOMPLETE"}
        self.assertTrue(expected <= self.codes(supply), self.codes(supply))
        detail = " ".join(entry["detail"] for entry in supply["reason_codes"])
        self.assertIn("1 of 3", detail)

    def test_mislabeled_proxy_targeting_protocol_revenue_is_always_rejected(self):
        configs = self.tmp / "configs"
        _copy_spec_configs(configs)
        mislabeled = json.loads((CONFIGS_DIR / "gross_fee_activity_v1.json").read_text())
        mislabeled["spec_id"] = "mislabeled_proxy_v1"
        mislabeled["declared_target"] = "protocol_revenue"
        (configs / "mislabeled_proxy_v1.json").write_text(json.dumps(mislabeled))
        policy_document = json.loads(self.policy.read_text())
        policy_document["spec_evaluation_order"] = list(
            policy_document["spec_evaluation_order"]) + ["mislabeled_proxy_v1"]
        policy = self.tmp / "policy.json"
        policy.write_text(json.dumps(policy_document))
        report = self.run_gate(policy=policy, configs=configs)
        rejected = self.evaluation(report, "mislabeled_proxy_v1")
        self.assertEqual(rejected["verdict"], "REJECTED")
        self.assertIn("PROXY_CANNOT_PASS_AS_PROTOCOL_REVENUE", self.codes(rejected))
        self.assertNotEqual(report["selection"]["selected_spec"], "mislabeled_proxy_v1")
        self.assertTrue(report["invariants"]["no_proxy_passes_as_protocol_revenue"])

    def test_overparameterized_spec_cannot_register(self):
        configs = self.tmp / "configs"
        _copy_spec_configs(configs)
        greedy = json.loads((CONFIGS_DIR / "gross_fee_activity_v1.json").read_text())
        greedy["spec_id"] = "greedy_v1"
        greedy["parameters"]["substantive_slopes"] = 5
        (configs / "greedy_v1.json").write_text(json.dumps(greedy))
        with self.assertRaises(readiness.ReadinessGateError) as caught:
            self.run_gate(configs=configs)
        self.assertIn("project maximum", str(caught.exception))

    def test_spec_with_unknown_metric_is_rejected_at_load(self):
        configs = self.tmp / "configs"
        _copy_spec_configs(configs)
        bogus = json.loads((CONFIGS_DIR / "gross_fee_activity_v1.json").read_text())
        bogus["spec_id"] = "bogus_v1"
        bogus["dependent_variable"]["metric_id"] = "invented_revenue_metric"
        (configs / "bogus_v1.json").write_text(json.dumps(bogus))
        with self.assertRaises(readiness.ReadinessGateError) as caught:
            self.run_gate(configs=configs)
        self.assertIn("not a series the gate can prepare", str(caught.exception))


class GapAndQualityTests(ReadinessGateTestCase):

    def test_missing_provider_day_is_explicit_and_nonadjacent(self):
        gap_day = _day(45)
        archive = build_synthetic_archive(self.tmp / "archive-gap",
                                          missing_volume_days=(gap_day,))
        report = self.run_gate(archive=archive)
        proxy = self.evaluation(report, "gross_fee_activity_v1")
        # 89 complete days; the two adjacent-day pairs across the gap drop.
        self.assertEqual(proxy["sample"]["complete_days"], 89)
        self.assertEqual(proxy["sample"]["usable_observations"], 87)
        self.assertEqual(proxy["sample"]["nonadjacent_dropped_pairs"], 2)
        self.assertIn("NONADJACENT_DAYS_FOR_DIFFERENCING", self.codes(proxy))
        excluded = {(item["date"], item["series"], item["reason"])
                    for item in proxy["sample"]["excluded_days"]}
        self.assertIn((_iso(gap_day), "provider_intents_volume_usd|SRC-LLAMA",
                       "missing_value"), excluded)
        profile = next(series for series in report["prepared_table"]["series"]
                       if series["series_key"] == "provider_intents_volume_usd|SRC-LLAMA")
        self.assertEqual(profile["missing_days"], [_iso(gap_day)])
        self.assertEqual(profile["calendar_gaps"],
                         [{"after": _iso(gap_day - dt.timedelta(days=1)),
                           "before": _iso(gap_day + dt.timedelta(days=1)),
                           "missing_calendar_days": 1}])
        self.assertEqual(proxy["verdict"], "READY_WITH_LIMITS")

    def test_absent_daily_row_creates_a_calendar_gap(self):
        absent = _day(10)
        archive = build_synthetic_archive(self.tmp / "archive-row",
                                          missing_daily_rows=(absent,))
        report = self.run_gate(archive=archive)
        self.assertEqual(report["prepared_table"]["daily_rows_present"], 89)
        proxy = self.evaluation(report, "gross_fee_activity_v1")
        excluded = {(item["date"], item["reason"])
                    for item in proxy["sample"]["excluded_days"]}
        self.assertIn((_iso(absent), "calendar_day_absent_from_daily_rows"), excluded)
        self.assertIn("NONADJACENT_DAYS_FOR_DIFFERENCING", self.codes(proxy))
        self.assertEqual(proxy["sample"]["nonadjacent_dropped_pairs"], 2)

    def test_zero_volume_rejects_log_specifications_fail_closed(self):
        zero_day = _day(30)
        archive = build_synthetic_archive(self.tmp / "archive-zero",
                                          zero_volume_days=(zero_day,))
        report = self.run_gate(archive=archive)
        for spec_id in ("gross_fee_activity_v1", "purchases_activity_v1"):
            evaluation = self.evaluation(report, spec_id)
            self.assertEqual(evaluation["verdict"], "REJECTED", spec_id)
            self.assertIn("ZERO_VALUES_EXCLUDE_LOG_SPEC", self.codes(evaluation))
        self.assertEqual(report["selection"]["selected_spec"], None)
        self.assertEqual(report["selection"]["overall_verdict"], "NOT_READY_NO_MODEL")
        profile = next(series for series in report["prepared_table"]["series"]
                       if series["series_key"] == "provider_intents_volume_usd|SRC-LLAMA")
        self.assertEqual(profile["zero_days"], [_iso(zero_day)])

    def test_short_window_is_rejected_for_daily_long_run_inference(self):
        archive = build_synthetic_archive(self.tmp / "archive-short", days=7)
        configs = self.tmp / "configs-short"
        _copy_spec_configs(configs)
        policy_document = json.loads(self.policy.read_text())
        policy_document["window"] = {"start": _iso(WINDOW_START),
                                     "end_exclusive": _iso(_day(7))}
        policy = self.tmp / "policy-short.json"
        policy.write_text(json.dumps(policy_document))
        report = self.run_gate(archive=archive, policy=policy, configs=configs)
        self.assertEqual(report["window"]["days"], 7)
        proxy = self.evaluation(report, "gross_fee_activity_v1")
        self.assertEqual(proxy["verdict"], "REJECTED")
        expected = {"SHORT_ATTRIBUTION_WINDOW", "INSUFFICIENT_COMPLETE_OBSERVATIONS",
                    "INSUFFICIENT_OBSERVATIONS_PER_PARAMETER"}
        self.assertTrue(expected <= self.codes(proxy), self.codes(proxy))
        self.assertEqual(report["selection"]["selected_spec"], None)
        self.assertEqual(report["selection"]["overall_verdict"], "NOT_READY_NO_MODEL")
        self.assertTrue(report["invariants"]["short_attribution_rejected"])

    def test_uncovered_extract_day_is_not_a_verified_zero(self):
        # A day with no conversion records but a coverage row is a proven zero;
        # the cohort profile records verified zeros explicitly.
        report = self.run_gate()
        profile = next(series for series in report["prepared_table"]["series"]
                       if series["series_key"] == "observed_near_purchases|")
        # The synthetic extract holds one conversion on day 0; days 1.. are
        # covered and therefore proven zeros, never silent zeros.
        self.assertEqual(len(profile["zero_days"]), 89)
        cohort = self.evaluation(report, "purchases_activity_v1")
        self.assertEqual(cohort["sample"]["verified_zero_days"].__len__(), 89)
        self.assertIn("VERIFIED_ZERO_DAYS_PRESENT", self.codes(cohort))
        # Verified zeros are genuine zeros: the strict log baseline is rejected.
        self.assertEqual(cohort["verdict"], "REJECTED")
        self.assertIn("ZERO_VALUES_EXCLUDE_LOG_SPEC", self.codes(cohort))


class ReportContractTests(ReadinessGateTestCase):

    def test_double_run_is_byte_identical(self):
        first = self.run_gate()
        second = self.run_gate()
        self.assertEqual(readiness.render_report_json(first),
                         readiness.render_report_json(second))
        self.assertEqual(readiness.render_report_markdown(first),
                         readiness.render_report_markdown(second))
        self.out.mkdir(parents=True, exist_ok=True)
        json_a, markdown_a = readiness.write_report(first, self.out / "a")
        json_b, markdown_b = readiness.write_report(second, self.out / "b")
        self.assertEqual(json_a.read_bytes(), json_b.read_bytes())
        self.assertEqual(markdown_a.read_bytes(), markdown_b.read_bytes())

    def test_report_is_cataloged_and_input_pinned(self):
        report = self.run_gate()
        for evaluation in report["spec_evaluations"]:
            for entry in evaluation["reason_codes"]:
                self.assertIn(entry["code"], readiness.REASON_CATALOG)
                self.assertEqual(entry["severity"],
                                 readiness.REASON_CATALOG[entry["code"]][0])
        pinned = {item["path"]: item["sha256"] for item in report["inputs"]["files"]}
        for relative, digest in pinned.items():
            actual = hashlib.sha256((self.archive / relative).read_bytes()).hexdigest()
            self.assertEqual(digest, actual)
        self.assertEqual(len(pinned), 4)

    def test_reports_land_only_in_the_output_directory(self):
        self.out.mkdir(parents=True, exist_ok=True)
        readiness.write_report(self.run_gate(), self.out)
        written = sorted(path.relative_to(self.tmp).as_posix()
                         for path in self.tmp.rglob("*") if path.is_file())
        for relative in written:
            self.assertTrue(relative.startswith("out/") or
                            relative.startswith("archive-a/"),
                            f"unexpected file outside sanctioned directories: {relative}")
        self.assert_archive_untouched()

    def test_metric_definitions_come_from_the_versioned_registry(self):
        report = self.run_gate()
        definitions = report["inputs"]["metric_definitions"]
        self.assertIn("protocol_revenue_usd", definitions)
        self.assertEqual(definitions["protocol_revenue_usd"]["availability"], "G")
        self.assertEqual(definitions["provider_gross_fees_usd"]["frequency"], "daily")
        for metric_id, definition in definitions.items():
            registered = readiness.metric_registry.definition_by_metric_id(metric_id)
            self.assertEqual(definition["version"], registered.version)

    def test_cli_writes_reports_and_exits_zero(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = readiness.main([
                "--archive-root", str(self.archive),
                "--configs-dir", str(CONFIGS_DIR),
                "--policy", str(self.policy),
                "--out-dir", str(self.out),
            ])
        self.assertEqual(exit_code, readiness.EXIT_OK)
        self.assertIn("PROXY_ONLY_READY_WITH_LIMITS", stdout.getvalue())
        self.assertTrue((self.out / "readiness_report.json").is_file())
        self.assertTrue((self.out / "readiness_report.md").is_file())

    def test_cli_contract_failure_exits_four(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            exit_code = readiness.main([
                "--archive-root", str(self.tmp / "does-not-exist"),
                "--configs-dir", str(CONFIGS_DIR),
                "--policy", str(self.policy),
            ])
        self.assertEqual(exit_code, readiness.EXIT_CONTRACT)
        self.assertIn("contract failure", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
