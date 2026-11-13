"""NI-061 offline oracle tests: independent recomputation vs the pipeline.

The oracle (:mod:`integration.oracles`) recomputes the expected values from
the raw synthetic extract with plain-integer arithmetic and a different code
path from ``near_api.metrics``; these tests compare the two exactly on the
same synthetic bundle and reconcile the emitted prepared manifests against
the oracle. Database delivery of the same bundle is covered by
``test_invariants_db_chain.py`` on the disposable cluster.
"""

import datetime as dt
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from integration import invariant_fixtures as fixtures
from integration.oracles import OraclePayoutError, YOCTO_PER_NEAR, near_string

from near_api.main import app
from near_api.metrics.compute import MetricComputationError
from near_api.metrics.emit import DatasetSpec, ManifestInputSpec, build_all_manifests
from near_api.metrics.events import (
    PayoutMatchingError,
    aggregate_purchases,
    match_payouts,
)
from near_api.metrics.loaders import load_longitudinal_flows
from near_api.metrics.registry import definition_by_metric_id_version

YOCTO = Decimal(YOCTO_PER_NEAR)
D1, D2, D3 = fixtures.DAYS
D4 = fixtures.WINDOW_END_EXCLUSIVE


def emitted(inputs, manifest_inputs):
    return build_all_manifests(
        inputs,
        dataset_spec=DatasetSpec(pipeline_version="ni061-synthetic",
                                 quality={"notes": "synthetic NI-061 fixture"}),
        manifest_inputs=manifest_inputs)


def values(document: dict, metric_id: str, version: int = 1) -> list[dict]:
    definition = definition_by_metric_id_version(metric_id, version)
    return [record for record in document["observations"]
            if UUID(record["metric_definition_id"]) == definition.id]


def records_by_day_and_dimensions(records: list[dict]) -> dict:
    index: dict[tuple, dict] = {}
    for record in records:
        index[(record["period_start"][:10], json.dumps(record["dimensions"],
                                                       sort_keys=True))] = record
    return index


class FlowOracleAgreementTests(unittest.TestCase):
    """The production aggregators and the independent oracle agree exactly."""

    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="ni061-oracle-")
        cls.addClassCleanup(cls.directory.cleanup)
        cls.paths = fixtures.write_bundle(Path(cls.directory.name))
        cls.oracle, _supply = fixtures.oracle_for(cls.paths["flows"])
        records = load_longitudinal_flows(cls.paths["flows"])
        cls.purchases = aggregate_purchases(
            records.conversions, window_start=fixtures.WINDOW_START,
            window_end_exclusive=fixtures.WINDOW_END_EXCLUSIVE)
        cls.payouts = match_payouts(
            records.withdrawals, records.native_transfers,
            treasury_accounts=fixtures.TREASURIES,
            window_start=fixtures.WINDOW_START,
            window_end_exclusive=fixtures.WINDOW_END_EXCLUSIVE)

    def test_purchases_agree_exactly_per_day_and_in_total(self):
        oracle = self.oracle
        # near_api aggregates already carry exact yoctoNEAR Decimal amounts
        self.assertEqual(self.purchases.total, Decimal(oracle.purchase_total_yocto))
        self.assertEqual(self.purchases.total_events, oracle.purchase_total_events)
        for day in fixtures.DAYS:
            expected = Decimal(oracle.purchase_yocto_by_day.get(day, 0))
            self.assertEqual(self.purchases.by_day.get(day, Decimal(0)), expected,
                             f"{day}: purchases diverge from the oracle")
            self.assertEqual(self.purchases.events_by_day.get(day, 0),
                             oracle.purchase_events_by_day.get(day, 0))

    def test_payouts_agree_exactly_per_day_and_in_total(self):
        oracle = self.oracle
        self.assertEqual(self.payouts.total, Decimal(oracle.payout_total_yocto))
        self.assertEqual(self.payouts.total_count, oracle.payout_total_count)
        self.assertEqual(self.payouts.total_count, oracle.matched_pairs)
        for day in fixtures.DAYS:
            self.assertEqual(self.payouts.by_day.get(day, Decimal(0)),
                             Decimal(oracle.payout_yocto_by_day.get(day, 0)),
                             f"{day}: payout amounts diverge from the oracle")
            self.assertEqual(self.payouts.count_by_day.get(day, 0),
                             oracle.payout_count_by_day.get(day, 0))

    def test_exclusions_and_duplicates_agree_with_the_oracle(self):
        oracle = self.oracle
        # The withdrawal intent for the midnight-crossing payout sits on D1,
        # its matching receipt on D2: the cash-receipt day buckets it to D2.
        self.assertEqual(oracle.payout_count_by_day.get(D2), 2)
        self.assertEqual(oracle.payout_count_by_day.get(D1), 1)
        self.assertEqual(self.payouts.internal_hop_count, oracle.internal_hop_count)
        self.assertEqual(self.payouts.internal_hop_total,
                         Decimal(oracle.internal_hop_total_yocto))
        self.assertEqual(self.payouts.other_sender_count, oracle.other_sender_count)
        self.assertEqual(self.payouts.other_sender_total,
                         Decimal(oracle.other_sender_total_yocto))
        self.assertEqual(self.payouts.failed_transfer_count, oracle.failed_transfer_count)
        self.assertEqual(self.payouts.out_of_window_transfer_count,
                         oracle.out_of_window_transfer_count)
        self.assertEqual(self.payouts.out_of_window_withdrawal_count,
                         oracle.out_of_window_withdrawal_count)
        self.assertEqual(self.purchases.excluded_out_of_window,
                         oracle.out_of_window_conversion_count)
        self.assertEqual(self.purchases.duplicate_records
                         + self.payouts.duplicate_records, oracle.duplicate_records)
        self.assertEqual(oracle.duplicate_records, 2)

    def test_internal_hops_and_failures_are_never_payouts(self):
        excluded = (self.payouts.internal_hop_total + self.payouts.other_sender_total)
        matched_plus_excluded_plus_failed = self.payouts.total + excluded
        transferred = Decimal(fixtures.INTERNAL_HOP) + \
            Decimal(fixtures.OTHER_SENDER_INFLOW) + \
            Decimal(fixtures.PAYOUT_NEXT_DAY) + Decimal(fixtures.PAYOUT_MIDDAY) + \
            Decimal(fixtures.PAYOUT_LAST_DAY) + Decimal(fixtures.PAYOUT_EXACT_TOLERANCE)
        # every in-window successful treasury transfer is either a matched
        # payout, a reported internal hop or a reported other-sender inflow —
        # the failed receipt and the out-of-window transfer contribute nothing
        self.assertEqual(matched_plus_excluded_plus_failed, transferred)
        self.assertEqual(self.payouts.failed_transfer_count, 1)
        self.assertEqual(self.payouts.out_of_window_transfer_count, 1)


class PayoutFailureOracleAgreementTests(unittest.TestCase):
    """Zero and ambiguous matches are errors in BOTH implementations."""

    def _run_case(self, rows: list[dict]):
        directory = tempfile.TemporaryDirectory(prefix="ni061-failure-")
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "flows-failure-synthetic.json"
        path.write_text(json.dumps(rows), encoding="utf-8")
        records = load_longitudinal_flows(path)
        payloads = fixtures.payloads_from_extract(path)
        with self.assertRaises(PayoutMatchingError):
            match_payouts(records.withdrawals, records.native_transfers,
                          treasury_accounts=fixtures.TREASURIES,
                          window_start=fixtures.WINDOW_START,
                          window_end_exclusive=fixtures.WINDOW_END_EXCLUSIVE)
        with self.assertRaises(OraclePayoutError):
            from integration.oracles import aggregate_flows
            aggregate_flows(payloads, window_start=fixtures.WINDOW_START,
                            window_end_exclusive=fixtures.WINDOW_END_EXCLUSIVE,
                            treasury_accounts=fixtures.TREASURIES)

    def _withdrawal(self, receipt: str, amount: str,
                    day: dt.date | None = None) -> dict:
        return fixtures._row("withdrawal", {
            "block_date": (day or D1).isoformat(),
            "block_timestamp_utc": fixtures.ts(day or D1, 12 * 3600),
            "block_height": 47000100, "receipt_id": receipt, "log_index": 0,
            "item_index": 0, "account_id": fixtures.COLLECTOR,
            "receiver_id": fixtures.TREASURIES[0], "amount_raw": amount,
            "intent_hash": f"synthetic-intent-{receipt}",
        })

    def _transfer(self, receipt: str, amount: str, *, second: int = 12 * 3600 + 60,
                  day: dt.date | None = None) -> dict:
        return fixtures._row("native", {
            "block_date": (day or D1).isoformat(),
            "block_timestamp_utc": fixtures.ts(day or D1, second),
            "block_height": 47000200, "receipt_id": receipt,
            "index_in_action_receipt": 0,
            "receipt_predecessor_account_id": fixtures.INTENTS,
            "receipt_receiver_account_id": fixtures.TREASURIES[0],
            "amount_raw": amount, "status": "SUCCESS_VALUE",
        })

    def test_withdrawal_without_a_candidate_is_refused(self):
        self._run_case([self._withdrawal("synthetic-orphan-w", fixtures.PAYOUT_MIDDAY)])

    def test_withdrawal_with_ambiguous_candidates_is_refused(self):
        self._run_case([
            self._withdrawal("synthetic-ambiguous-w", fixtures.PAYOUT_MIDDAY),
            self._transfer("synthetic-ambiguous-t1", fixtures.PAYOUT_MIDDAY,
                           second=12 * 3600),
            self._transfer("synthetic-ambiguous-t2", fixtures.PAYOUT_MIDDAY,
                           second=12 * 3600 + 120),
        ])

    def test_single_use_receipt_leaves_the_second_withdrawal_unmatched(self):
        # Two equal withdrawals share one unique transfer: the first match
        # consumes the receipt action, so the second has zero candidates.
        self._run_case([
            self._withdrawal("synthetic-reuse-w1", fixtures.PAYOUT_MIDDAY),
            self._withdrawal("synthetic-reuse-w2", fixtures.PAYOUT_MIDDAY,
                             day=D2),
            self._transfer("synthetic-reuse-t", fixtures.PAYOUT_MIDDAY),
        ])


class EmittedManifestReconciliationTests(unittest.TestCase):
    """The emitted prepared manifests reconcile with the oracle exactly."""

    @classmethod
    def setUpClass(cls):
        directory = tempfile.TemporaryDirectory(prefix="ni061-emit-")
        cls.addClassCleanup(directory.cleanup)
        cls.paths = fixtures.write_bundle(Path(directory.name))
        cls.oracle, cls.supply = fixtures.oracle_for(cls.paths["flows"])
        roles = {"flows": "raw", "daily": "price", "supply": "normalized",
                 "treasury": "normalized"}
        inputs = tuple(ManifestInputSpec(name=name, path=path, role=roles[name])
                       for name, path in cls.paths.items())
        manifests = emitted(fixtures.pipeline_inputs(cls.paths), inputs)
        cls.flows = manifests["metrics.flows.daily"]
        cls.windows = manifests["metrics.windows.snapshot"]

    def test_purchases_and_conversions_reconcile_per_day(self):
        purchases = records_by_day_and_dimensions(values(self.flows,
                                                         "observed_near_purchases"))
        conversions = records_by_day_and_dimensions(values(self.flows,
                                                           "conversion_count"))
        for day in fixtures.DAYS:
            key = (day.isoformat(), "{}")
            self.assertEqual(Decimal(purchases[key]["value"]) * YOCTO,
                             self.oracle.purchase_yocto_by_day.get(day, 0),
                             f"{day}: delivered purchases diverge from the oracle")
            self.assertEqual(int(conversions[key]["value"]),
                             self.oracle.purchase_events_by_day.get(day, 0))
            self.assertEqual(purchases[key]["bound_kind"], "exact")
        # the out-of-window conversion never becomes an observation
        self.assertNotIn((D4.isoformat(), "{}"), purchases)

    def test_payouts_reconcile_per_day_with_next_date_receipt_and_hops(self):
        payouts = records_by_day_and_dimensions(values(self.flows,
                                                       "treasury_payouts_near"))
        counts = records_by_day_and_dimensions(values(self.flows,
                                                      "treasury_payout_count"))
        expected_days = {D1: fixtures.PAYOUT_MIDDAY,
                         D2: int(fixtures.PAYOUT_NEXT_DAY)
                             + int(fixtures.PAYOUT_EXACT_TOLERANCE),
                         D3: int(fixtures.PAYOUT_LAST_DAY)}
        for day, amount in expected_days.items():
            key = (day.isoformat(), "{}")
            self.assertEqual(Decimal(payouts[key]["value"]) * YOCTO, Decimal(amount),
                             f"{day}: delivered payouts diverge from the oracle")
            self.assertEqual(payouts[key]["bound_kind"], "exact")
        # the internal hop, other-sender inflow, failed receipt and the
        # out-of-window transfer never appear in any day's payout total
        self.assertEqual(sum(int(Decimal(record["value"]) * YOCTO)
                             for record in payouts.values()),
                         self.oracle.payout_total_yocto)
        for day in fixtures.DAYS:
            key = (day.isoformat(), "{}")
            self.assertEqual(int(counts[key]["value"]),
                             self.oracle.payout_count_by_day.get(day, 0))

    def test_missing_price_day_is_missing_and_never_zero(self):
        estimates = records_by_day_and_dimensions(values(self.flows,
                                                         "estimated_purchase_usd"))
        gap_start = (D2.isoformat(), '{"price_basis": "start"}')
        record = estimates[gap_start]
        self.assertIsNone(record["value"])
        self.assertEqual(record["quality_status"], "missing")
        self.assertIn("missing, not zero", record["quality"]["reason"])
        # the priced days carry exact estimates: 2.0 NEAR x 3.25 USD and the
        # verified-zero day valued at exactly zero
        day1 = estimates[(D1.isoformat(), '{"price_basis": "start"}')]
        self.assertEqual(Decimal(day1["quality"]["exact_value"]),
                         Decimal("2") * Decimal("3.25"))
        day3 = estimates[(D3.isoformat(), '{"price_basis": "start"}')]
        self.assertEqual(Decimal(day3["value"]), Decimal(0))
        self.assertEqual(day3["quality_status"], "verified")

    def test_gated_metrics_stay_null_with_recorded_reasons(self):
        for document, metric_id, reason in (
                (self.flows, "protocol_revenue_usd", "OQ-01"),
                (self.flows, "protocol_capture_rate", "OQ-11"),
                (self.windows, "fee_funded_buybacks_near", "OQ-08")):
            for record in values(document, metric_id):
                self.assertIsNone(record["value"], metric_id)
                self.assertIn(reason, record["quality"]["reason"], metric_id)

    def test_supply_stocks_and_net_changes_reconcile_with_the_oracle(self):
        stocks = records_by_day_and_dimensions(values(self.windows,
                                                      "total_supply_near"))
        self.assertEqual(len(stocks), len(self.supply.stock_by_date))
        for day, stock in self.supply.stock_by_date.items():
            record = stocks[(day.isoformat(), "{}")]
            self.assertEqual(Decimal(record["value"]), stock)
            self.assertEqual(record["bound_kind"], "exact")
        changes = {record["period_start"][:10]: record
                   for record in values(self.windows, "net_supply_change_near")}
        # only the atomic windows are observations; the full-span total is a
        # range reference recorded in quality metadata
        self.assertEqual(set(changes), {D1.isoformat(), D2.isoformat()})
        self.assertEqual(Decimal(changes[D1.isoformat()]["value"]),
                         self.supply.net_change_by_window[(D1, D2)])
        self.assertEqual(Decimal(changes[D2.isoformat()]["value"]),
                         self.supply.net_change_by_window[(D2, D3)])
        for record in changes.values():
            self.assertEqual(record["bound_kind"], "exact")
            self.assertIn("never deducted", record["quality"]["purchase_policy"])

    def test_bounds_stay_bounds_and_purchases_stay_separate(self):
        for metric_id, kind in (("issuance_lower_bound_near", "lower"),
                                ("burns_lower_bound_near", "lower")):
            records = values(self.windows, metric_id)
            self.assertTrue(records, metric_id)
            for record in records:
                self.assertEqual(record["bound_kind"], kind, metric_id)
                self.assertIsNotNone(record["value"], metric_id)
        # the issuance ratio carries the upper bound because its denominator
        # is a lower bound; the direction is recorded, never implied
        for record in values(self.windows, "purchases_to_issuance_upper_pct"):
            self.assertEqual(record["bound_kind"], "upper")
            self.assertIn("upper bound", record["quality"]["direction"])
        # every atomic window also reports the observed purchases alongside
        for record in values(self.windows, "net_supply_change_near"):
            self.assertIn("observed_purchases_near", record["quality"])
            self.assertIn("purchase_policy", record["quality"])

    def test_window_summary_quality_reconciles_with_the_oracle(self):
        aggregates = self.windows["quality"]["window_aggregates"]
        self.assertEqual(Decimal(aggregates["observed_purchases_total_near"]) * YOCTO,
                         self.oracle.purchase_total_yocto)
        self.assertEqual(Decimal(aggregates["matched_payout_total_near"]) * YOCTO,
                         self.oracle.payout_total_yocto)
        self.assertEqual(aggregates["matched_payout_count"], self.oracle.matched_pairs)
        self.assertEqual(Decimal(aggregates["excluded_internal_hops_near"]) * YOCTO,
                         self.oracle.internal_hop_total_yocto)
        self.assertEqual(Decimal(aggregates["excluded_other_senders_near"]) * YOCTO,
                         self.oracle.other_sender_total_yocto)
        self.assertEqual(aggregates["observed_purchase_events"],
                         self.oracle.purchase_total_events)

    def test_provider_series_are_source_qualified_and_exact(self):
        volume = records_by_day_and_dimensions(values(
            self.flows, "provider_intents_volume_usd"))
        day1 = volume[(D1.isoformat(), '{"source": "SRC-LLAMA"}')]
        self.assertEqual(Decimal(day1["value"]), Decimal("3135599249"))
        dashboard = volume[(D1.isoformat(), '{"source": "SRC-DASHBOARD"}')]
        self.assertEqual(Decimal(dashboard["value"]),
                         Decimal("3533927934.471786945"))
        # the two sources are never summed into one value
        self.assertEqual(len(volume), 6)


class OpenApiInclusivePathPinTests(unittest.TestCase):
    """The expected route families stay present; additions never break this."""

    EXPECTED_ROUTES = {
        ("GET", "/api/metrics"),
        ("GET", "/api/metrics/{metric_id}"),
        ("GET", "/api/metrics/{metric_id}/series"),
        ("GET", "/api/charts"),
        ("GET", "/api/charts/{chart_id}"),
        ("GET", "/api/charts/{chart_id}/view"),
        ("GET", "/api/data-sources"),
        ("GET", "/api/data-sources/{source_id}"),
        ("GET", "/api/datasets/{version_id}"),
        ("GET", "/api/datasets/{version_id}/manifest"),
        ("POST", "/api/documents"),
        ("GET", "/api/documents"),
        ("GET", "/api/documents/{document_id}"),
        ("PATCH", "/api/documents/{document_id}"),
        ("DELETE", "/api/documents/{document_id}"),
        ("POST", "/api/documents/{document_id}/versions"),
        ("GET", "/api/documents/{document_id}/versions"),
        ("GET", "/api/documents/{document_id}/versions/{version_id}"),
        ("GET", "/api/documents/{document_id}/chart-view"),
        ("POST", "/api/documents/{document_id}/chart-blocks"),
    }

    def test_expected_paths_and_methods_are_present(self):
        document = app.openapi()
        delivered = {(method.upper(), path)
                     for path, operations in document["paths"].items()
                     for method in operations}
        missing = self.EXPECTED_ROUTES - delivered
        self.assertEqual(missing, set(),
                         "expected API routes disappeared from the OpenAPI document")

    def test_removed_mutating_methods_stay_absent_on_public_reads(self):
        document = app.openapi()
        for path, operations in document["paths"].items():
            if path.startswith(("/api/metrics", "/api/charts", "/api/data-sources",
                                "/api/datasets")):
                self.assertEqual(set(operations) - {"parameters"}, {"get"},
                                 f"{path}: public delivery routes stay read-only")
