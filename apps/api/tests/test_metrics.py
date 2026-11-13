"""NI-029 tests: exact metric computations, quality and registry.

Offline classes run everywhere; DB classes need scripts/run-db-tests.py and
real-archive classes need NI_REAL_ARCHIVE_ROOT pointing at a read-only
handoff of the research archive. A skip is never integration evidence.

All archive bytes, accounts, amounts and providers in the offline fixtures
are synthetic. The real-archive tests only READ the handed-off archive and
reconcile the computations against its own saved summary totals exactly
(Decimal equality for amounts; equality at the NUMERIC(78,30) storage scale
for non-terminating ratios).
"""

import datetime as dt
import json
import os
import shutil
import tempfile
import unittest
import uuid
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from pathlib import Path
from uuid import UUID, uuid4

from near_api.datasets.canonical import decimal_string
from near_api.datasets.manifest import parse_manifest_document
from near_api.datasets.service import _validate_version_content
from near_api.db.session import create_runtime_engine, user_transaction
from near_api.metrics import registry as metric_registry
from near_api.metrics.compute import (
    COMPUTE_CONTEXT,
    MetricComputationError,
    effective_fee_bps,
    observation_value,
    price_series,
    provider_series,
    ratio_at_storage_scale,
)
from near_api.metrics.emit import build_all_manifests, build_manifest, DatasetSpec, ManifestInputSpec
from near_api.metrics.events import (
    ConversionDay,
    EventContractError,
    EventQuarantineError,
    NativeTransfer,
    PayoutMatchingError,
    WithdrawalEvent,
    aggregate_purchases,
    day_period,
    match_payouts,
    parse_yocto_amount,
)
from near_api.metrics.inputs import (
    CoverageDay,
    DailyFlowRow,
    FlowRecords,
    MetricInputs,
    PriceSeries,
    ProviderDay,
    ProviderSeries,
    QualityDay,
    SupplyBoundary,
    SupplyWindow,
    TreasuryBalance,
)
from near_api.metrics.loaders import (
    load_daily_flows,
    load_longitudinal_flows,
    load_metric_inputs,
    load_supply_summary,
    load_treasury_summary,
)

getcontext().prec = 200

WINDOW_START = dt.date(2026, 1, 10)
WINDOW_END = dt.date(2026, 1, 13)  # three days: 10, 11, 12
TREASURIES = ("buybacks.multisignature.near", "fefundsadmin.sputnik-dao.near",
              "1csfundsadmin.sputnik-dao.near")
COLLECTOR = "collector.testnet"
COLLECTOR_2 = "collector2.testnet"
YOCTO = Decimal(10) ** 24


def ts(day: dt.date, second: int = 0, micro: int = 0) -> dt.datetime:
    return dt.datetime.combine(day, dt.time.min, tzinfo=dt.timezone.utc) + \
        dt.timedelta(seconds=second, microseconds=micro)


def day_bounds(day: dt.date):
    return day_period(day)


# --------------------------------------------------------------------------- #
# Synthetic canonical fixtures
# --------------------------------------------------------------------------- #


def conversion(date: dt.date, account: str = COLLECTOR, buy_raw: str = "1000000000000000000000000",
               buy_events: int = 2) -> ConversionDay:
    return ConversionDay(block_date=date, account_id=account, wrap_diff_events=buy_events,
                         distinct_intent_hashes=buy_events, invalid_wrap_amounts=0,
                         buy_events=buy_events, buy_raw=Decimal(buy_raw), sell_events=0,
                         sell_raw=Decimal(0), other_events=0)


def transfer(day: dt.date, amount_raw: str, *, receipt: str | None = None, second: int = 10,
             predecessor: str = "intents.near", receiver: str = TREASURIES[0],
             status: str = "SUCCESS_VALUE", action_index: int = 0,
             micro: int = 0) -> NativeTransfer:
    return NativeTransfer(
        block_date=day, timestamp=ts(day, second, micro), block_height=1000 + second,
        receipt_id=receipt
        or f"transfer-{day.isoformat()}-{second}-{amount_raw[:6]}-{action_index}",
        action_index=action_index, predecessor=predecessor, receiver=receiver,
        amount_raw=Decimal(amount_raw), status=status)


def withdrawal(day: dt.date, amount_raw: str, *, receipt: str | None = None, second: int = 0,
               receiver: str = TREASURIES[0], account: str = COLLECTOR,
               intent: str = "intent-hash", micro: int = 0) -> WithdrawalEvent:
    return WithdrawalEvent(
        block_date=day, timestamp=ts(day, second, micro), receipt_id=receipt or
        f"withdraw-{day.isoformat()}-{second}-{amount_raw[:6]}", log_index=0, item_index=0,
        account_id=account, receiver_id=receiver, amount_raw=Decimal(amount_raw),
        intent_hash=intent)


def synthetic_inputs() -> MetricInputs:
    """Three-day bundle with one verified-zero day and matched payouts."""
    conversions = (
        conversion(WINDOW_START, buy_raw="1500000000000000000000000", buy_events=3),
        conversion(WINDOW_START, account=COLLECTOR_2, buy_raw="500000000000000000000000",
                   buy_events=1),
        conversion(WINDOW_START + dt.timedelta(days=1), buy_raw="2000000000000000000000000",
                   buy_events=4),
        # day 3 has no conversion records: verified zero
    )
    # payouts: two matched pairs on day 1, one on day 3 (day 2 verified zero)
    pair_amounts = (
        (WINDOW_START, "610992154105948148261773753", 10),
        (WINDOW_START, "300000000000000000000000", 20),
        (WINDOW_START + dt.timedelta(days=2), "250000000000000000000000", 5),
    )
    withdrawals, transfers = [], []
    for day, amount, second in pair_amounts:
        withdrawals.append(withdrawal(day, amount, second=second))
        transfers.append(transfer(day, amount, second=second + 2))
    # excluded on purpose: internal hop, other sender, failed, out-of-window
    transfers.append(transfer(WINDOW_START, "502793000000000000000000000", second=30,
                              predecessor=TREASURIES[2], receiver=TREASURIES[0],
                              receipt="internal-hop"))
    transfers.append(transfer(WINDOW_START, "7751000000000000000000000", second=40,
                              predecessor="someone.else.near", receipt="other-sender"))
    transfers.append(transfer(WINDOW_START, "999000000000000000000000", second=50,
                              status="FAILURE", receipt="failed-transfer"))
    transfers.append(transfer(WINDOW_END, "123000000000000000000000", second=0,
                              receipt="out-of-window"))
    coverage = tuple(CoverageDay(block_date=WINDOW_START + dt.timedelta(days=index),
                                 intents_outcomes=1000 + index, successful_intents_outcomes=900,
                                 first_timestamp=ts(WINDOW_START + dt.timedelta(days=index), 1),
                                 last_timestamp=ts(WINDOW_START + dt.timedelta(days=index), 86399))
                     for index in range(3))
    quality = tuple(QualityDay(block_date=WINDOW_START + dt.timedelta(days=index),
                               event_json_logs=100, json_parse_errors=0)
                    for index in range(3))
    prices = PriceSeries(by_day={
        (WINDOW_START, "start"): Decimal("1.6978914247582741"),
        (WINDOW_START, "end"): Decimal("1.6563050316183050"),
        # day 2 has no price points at all: its USD estimate goes missing
        (WINDOW_START + dt.timedelta(days=2), "start"): Decimal("2.5"),
        (WINDOW_START + dt.timedelta(days=2), "end"): Decimal("2.6"),
    })
    providers = ProviderSeries(by_source={
        "SRC-LLAMA": {
            WINDOW_START: ProviderDay(volume_usd=Decimal("3135599249"),
                                      gross_fees_usd=Decimal("4115978")),
            WINDOW_START + dt.timedelta(days=1): ProviderDay(
                volume_usd=Decimal("1000000"), gross_fees_usd=Decimal("15000")),
            WINDOW_START + dt.timedelta(days=2): ProviderDay(
                volume_usd=Decimal("2000000"), gross_fees_usd=Decimal("26000")),
        },
        "SRC-DASHBOARD": {
            WINDOW_START: ProviderDay(volume_usd=Decimal("3533927934.471786945"),
                                      gross_fees_usd=Decimal("4347632.654090667434")),
            WINDOW_START + dt.timedelta(days=1): ProviderDay(
                volume_usd=Decimal("1100000"), gross_fees_usd=Decimal("16000")),
            WINDOW_START + dt.timedelta(days=2): ProviderDay(
                volume_usd=Decimal("2100000"), gross_fees_usd=Decimal("27000")),
        },
    })
    # boundary layout mirrors the real archive: the opening boundary is the
    # close of the day before the window, the closing boundary the close of
    # the day before the window end
    boundary_dates = (WINDOW_START - dt.timedelta(days=1), WINDOW_START,
                      WINDOW_START + dt.timedelta(days=1),
                      WINDOW_START + dt.timedelta(days=2))
    boundaries = tuple(
        SupplyBoundary(date=day, block_height=200000 + index, block_hash=f"hash{index}",
                       timestamp_ns=str(1785974399657403069 + index),
                       supply_near=Decimal("1000000.123456789012345678901234")
                       + Decimal(1000 * index))
        for index, day in enumerate(boundary_dates))
    supply_windows = (
        SupplyWindow(start=WINDOW_START, end_exclusive=WINDOW_START + dt.timedelta(days=1),
                     opening_date=boundary_dates[0], closing_date=boundary_dates[1],
                     positive_supply_changes_near=Decimal("50000.5"),
                     negative_supply_changes_near=Decimal("500.25"),
                     verified_simultaneous_burn_near=Decimal("0.0355821760331987"),
                     mint_headers_verified=1, mint_headers_target=1,
                     gross_issuance_and_burn_complete=False),
        SupplyWindow(start=WINDOW_START + dt.timedelta(days=1),
                     end_exclusive=WINDOW_START + dt.timedelta(days=2),
                     opening_date=boundary_dates[1], closing_date=boundary_dates[2],
                     positive_supply_changes_near=Decimal("60000.75"),
                     negative_supply_changes_near=Decimal("600.5"),
                     verified_simultaneous_burn_near=Decimal("0.0355821760331987"),
                     mint_headers_verified=1, mint_headers_target=1,
                     gross_issuance_and_burn_complete=False),
    )
    treasury = TreasuryBalance(
        as_of=ts(WINDOW_END, 41500), block_height=300000, block_hash="treasury-hash",
        total_near=Decimal("4140077.369748916078007362148128"),
        accounts=((TREASURIES[0], Decimal("2167847.131051440139635213430792")),))
    return MetricInputs(window_start=WINDOW_START, window_end_exclusive=WINDOW_END,
                        flows=FlowRecords(conversions=tuple(conversions),
                                          native_transfers=tuple(transfers),
                                          withdrawals=tuple(withdrawals),
                                          coverage=coverage, quality=quality),
                        daily_flows=(), prices=prices, providers=providers,
                        supply_boundaries=boundaries, supply_windows=supply_windows,
                        treasury_balance=treasury)


DATASET_SPEC = DatasetSpec(pipeline_version="ni029-test",
                           quality={"notes": "synthetic fixture"})


def manifest_inputs(paths: dict[str, Path]) -> tuple[ManifestInputSpec, ...]:
    roles = {"flows": "raw", "daily_flows": "price", "supply": "normalized",
             "treasury": "normalized"}
    return tuple(ManifestInputSpec(name=name, path=path, role=roles[name])
                 for name, path in paths.items() if path is not None)


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


class MetricRegistryTests(unittest.TestCase):
    def test_definitions_are_complete_and_deterministic(self):
        from near_api.metrics.compute import FORMULA_REGISTRY

        metric_registry.validate_registry(FORMULA_REGISTRY)
        ids = {definition.id for definition in metric_registry.DEFINITIONS}
        self.assertEqual(len(ids), len(metric_registry.DEFINITIONS))
        for definition in metric_registry.DEFINITIONS:
            expected = uuid.uuid5(metric_registry.REGISTRY_NAMESPACE,
                                  f"{definition.metric_id}:v{definition.version}")
            self.assertEqual(definition.id, expected)
            self.assertTrue(metric_registry.METRIC_ID_PATTERN.match(definition.metric_id))
            self.assertTrue(definition.name and definition.unit and definition.economic_scope)
            self.assertIn(definition.definition["availability"], metric_registry.AVAILABILITY_CODES)
        # the P0 catalog set named by the task card is registered (NI-071
        # supersedes treasury_payouts_near with the per-recipient v2, so its
        # latest registered version is 2)
        for metric_id, latest_version in (
                ("observed_near_purchases", 1), ("conversion_count", 1),
                ("treasury_payouts_near", 2), ("treasury_payout_count", 1),
                ("near_price_usd", 1), ("estimated_purchase_usd", 1),
                ("provider_intents_volume_usd", 1), ("provider_gross_fees_usd", 1),
                ("effective_gross_fee_bps", 1), ("total_supply_near", 1),
                ("net_supply_change_near", 1), ("issuance_lower_bound_near", 1),
                ("burns_lower_bound_near", 1), ("purchases_to_net_supply_pct", 1),
                ("purchases_to_issuance_upper_pct", 1), ("treasury_balance_near", 1),
                ("protocol_revenue_usd", 1), ("protocol_capture_rate", 1),
                ("fee_funded_buybacks_near", 1)):
            definition = metric_registry.definition_by_metric_id(metric_id)
            self.assertEqual(definition.version, latest_version)

    def test_unimplemented_formula_is_rejected(self):
        with self.assertRaises(metric_registry.MetricRegistryError):
            metric_registry.validate_registry({})

    def test_gated_definitions_have_null_semantics_and_no_source(self):
        for metric_id in ("protocol_revenue_usd", "protocol_capture_rate",
                          "fee_funded_buybacks_near"):
            definition = metric_registry.definition_by_metric_id(metric_id)
            self.assertIsNone(definition.source_id)
            self.assertEqual(definition.definition["availability"], "G")
            self.assertIn("null_semantics", definition.quality_rules)


# --------------------------------------------------------------------------- #
# Event aggregation: duplicates, failures, internal transfers, UTC bounds
# --------------------------------------------------------------------------- #


class EventAggregationTests(unittest.TestCase):
    def test_purchases_aggregate_and_collapse_identical_duplicates(self):
        records = [conversion(WINDOW_START, buy_raw="1000000000000000000000000"),
                   conversion(WINDOW_START, buy_raw="1000000000000000000000000")]
        flows = aggregate_purchases(records, window_start=WINDOW_START,
                                    window_end_exclusive=WINDOW_END)
        self.assertEqual(flows.total, Decimal("1000000000000000000000000"))
        self.assertEqual(flows.total_events, 2)
        self.assertEqual(flows.duplicate_records, 1)
        self.assertEqual(flows.by_day[WINDOW_START], Decimal("1000000000000000000000000"))

    def test_conflicting_duplicate_payload_is_quarantined(self):
        records = [conversion(WINDOW_START, buy_raw="1000000000000000000000000"),
                   conversion(WINDOW_START, buy_raw="2000000000000000000000000")]
        with self.assertRaises(EventQuarantineError):
            aggregate_purchases(records, window_start=WINDOW_START,
                                window_end_exclusive=WINDOW_END)

    def test_invalid_wrap_amounts_fail_closed(self):
        bad = ConversionDay(block_date=WINDOW_START, account_id=COLLECTOR, wrap_diff_events=1,
                            distinct_intent_hashes=1, invalid_wrap_amounts=1, buy_events=1,
                            buy_raw=Decimal("1"), sell_events=0, sell_raw=Decimal(0),
                            other_events=0)
        with self.assertRaises(EventContractError):
            aggregate_purchases([bad], window_start=WINDOW_START, window_end_exclusive=WINDOW_END)

    def test_out_of_window_conversion_rows_are_excluded_and_counted(self):
        flows = aggregate_purchases([conversion(WINDOW_END)], window_start=WINDOW_START,
                                    window_end_exclusive=WINDOW_END)
        self.assertEqual(flows.total, 0)
        self.assertEqual(flows.excluded_out_of_window, 1)

    def test_payout_matching_happy_path_and_exclusions(self):
        inputs = synthetic_inputs()
        payouts = match_payouts(inputs.flows.withdrawals, inputs.flows.native_transfers,
                                treasury_accounts=TREASURIES, window_start=WINDOW_START,
                                window_end_exclusive=WINDOW_END)
        expected = (Decimal("610992154105948148261773753") + Decimal("300000000000000000000000")
                    + Decimal("250000000000000000000000"))
        self.assertEqual(payouts.total, expected)
        self.assertEqual(payouts.total_count, 3)
        self.assertEqual(payouts.internal_hop_count, 1)
        self.assertEqual(payouts.internal_hop_total, Decimal("502793000000000000000000000"))
        self.assertEqual(payouts.other_sender_count, 1)
        self.assertEqual(payouts.other_sender_total, Decimal("7751000000000000000000000"))
        self.assertEqual(payouts.failed_transfer_count, 1)
        self.assertEqual(payouts.out_of_window_transfer_count, 1)
        self.assertEqual(payouts.by_day[WINDOW_START],
                         Decimal("610992154105948148261773753")
                         + Decimal("300000000000000000000000"))
        self.assertNotIn(WINDOW_START + dt.timedelta(days=1), payouts.by_day)

    def test_failed_transfer_never_establishes_credit(self):
        failed = transfer(WINDOW_START, "500000000000000000000000", status="FAILURE",
                          receipt="failed-only")
        transfers = [failed, transfer(WINDOW_START, "500000000000000000000000", second=30,
                                      receipt="success-only")]
        withdrawals = [withdrawal(WINDOW_START, "500000000000000000000000", second=32)]
        payouts = match_payouts(withdrawals, transfers, treasury_accounts=TREASURIES,
                                window_start=WINDOW_START, window_end_exclusive=WINDOW_END)
        # only the successful execution matches; the failed receipt contributes nothing
        self.assertEqual(payouts.total, Decimal("500000000000000000000000"))
        self.assertEqual(payouts.failed_transfer_count, 1)

    def test_unmatched_withdrawal_is_an_error_not_a_zero(self):
        transfers = [transfer(WINDOW_START, "100000000000000000000000", second=10)]
        withdrawals = [withdrawal(WINDOW_START, "100000000000000000000000", second=0),
                       withdrawal(WINDOW_START, "200000000000000000000000", second=1,
                                  receipt="withdraw-2")]
        with self.assertRaises(PayoutMatchingError):
            match_payouts(withdrawals, transfers, treasury_accounts=TREASURIES,
                          window_start=WINDOW_START, window_end_exclusive=WINDOW_END)

    def test_ambiguous_amount_match_is_an_error(self):
        transfers = [transfer(WINDOW_START, "100000000000000000000000", second=10),
                     transfer(WINDOW_START, "100000000000000000000000", second=20,
                              receipt="transfer-2")]
        withdrawals = [withdrawal(WINDOW_START, "100000000000000000000000", second=15)]
        with self.assertRaises(PayoutMatchingError):
            match_payouts(withdrawals, transfers, treasury_accounts=TREASURIES,
                          window_start=WINDOW_START, window_end_exclusive=WINDOW_END)

    def test_tolerance_boundary_is_inclusive_at_300s(self):
        amount = "100000000000000000000000"
        transfers = [transfer(WINDOW_START, amount, second=310)]
        payouts = match_payouts([withdrawal(WINDOW_START, amount, second=10)], transfers,
                                treasury_accounts=TREASURIES, window_start=WINDOW_START,
                                window_end_exclusive=WINDOW_END)
        self.assertEqual(payouts.total_count, 1)
        transfers_late = [transfer(WINDOW_START, amount, second=310, receipt="late")]
        with self.assertRaises(PayoutMatchingError):
            match_payouts([withdrawal(WINDOW_START, amount, second=10)], transfers_late,
                          treasury_accounts=TREASURIES, window_start=WINDOW_START,
                          window_end_exclusive=WINDOW_END, tolerance_seconds=299)

    def test_duplicate_transfer_collapses_and_conflicting_quarantines(self):
        amount = "100000000000000000000000"
        same = transfer(WINDOW_START, amount, second=10)
        payouts = match_payouts([withdrawal(WINDOW_START, amount, second=12)], [same, same],
                                treasury_accounts=TREASURIES, window_start=WINDOW_START,
                                window_end_exclusive=WINDOW_END)
        self.assertEqual(payouts.total_count, 1)
        self.assertEqual(payouts.duplicate_records, 1)
        conflicting = [same, NativeTransfer(
            block_date=WINDOW_START, timestamp=ts(WINDOW_START, 10), block_height=1000,
            receipt_id=same.receipt_id, action_index=0, predecessor="intents.near",
            receiver=TREASURIES[0], amount_raw=Decimal("999000000000000000000000"),
            status="SUCCESS_VALUE")]
        with self.assertRaises(EventQuarantineError):
            match_payouts([withdrawal(WINDOW_START, amount, second=12)], conflicting,
                          treasury_accounts=TREASURIES, window_start=WINDOW_START,
                          window_end_exclusive=WINDOW_END)

    def test_utc_day_boundary_bucketing(self):
        # 23:59:59.999999 belongs to day D, 00:00:00.000001 to day D+1
        late = transfer(WINDOW_START, "100000000000000000000000", second=86399, micro=999999)
        early = transfer(WINDOW_START + dt.timedelta(days=1), "200000000000000000000000",
                         second=0, micro=1, receipt="early")
        withdrawals = [withdrawal(WINDOW_START, "100000000000000000000000", second=86399,
                                  micro=999998),
                       withdrawal(WINDOW_START + dt.timedelta(days=1),
                                  "200000000000000000000000", second=0, micro=0,
                                  receipt="wd-early")]
        payouts = match_payouts(withdrawals, [late, early], treasury_accounts=TREASURIES,
                                window_start=WINDOW_START, window_end_exclusive=WINDOW_END)
        self.assertEqual(payouts.by_day[WINDOW_START], Decimal("100000000000000000000000"))
        self.assertEqual(payouts.by_day[WINDOW_START + dt.timedelta(days=1)],
                         Decimal("200000000000000000000000"))

    def test_partition_date_must_match_execution_timestamp(self):
        bad = NativeTransfer(block_date=WINDOW_START + dt.timedelta(days=1),
                             timestamp=ts(WINDOW_START, 10), block_height=1,
                             receipt_id="mismatch", action_index=0, predecessor="intents.near",
                             receiver=TREASURIES[0], amount_raw=Decimal(1),
                             status="SUCCESS_VALUE")
        with self.assertRaises(EventContractError):
            match_payouts([], [bad], treasury_accounts=TREASURIES, window_start=WINDOW_START,
                          window_end_exclusive=WINDOW_END)

    def test_non_treasury_receiver_is_a_contract_error(self):
        rogue = transfer(WINDOW_START, "1", receiver="attacker.near", receipt="rogue")
        with self.assertRaises(EventContractError):
            match_payouts([], [rogue], treasury_accounts=TREASURIES, window_start=WINDOW_START,
                          window_end_exclusive=WINDOW_END)

    def test_float_amounts_are_rejected(self):
        with self.assertRaises(EventContractError):
            parse_yocto_amount(1.5, context="x")
        with self.assertRaises(EventContractError):
            parse_yocto_amount("1e24", context="x")


# --------------------------------------------------------------------------- #
# Quality propagation in computations
# --------------------------------------------------------------------------- #


class ComputeQualityTests(unittest.TestCase):
    def setUp(self):
        self.inputs = synthetic_inputs()

    def test_missing_price_is_missing_not_zero(self):
        from near_api.metrics.compute import formula_estimated_purchase_usd_v1

        records = formula_estimated_purchase_usd_v1(self.inputs, shape="daily")
        start_basis = [record for record in records
                       if record["dimensions"]["price_basis"] == "start"]
        by_day = {record["period_start"][:10]: record for record in start_basis}
        gap = by_day[(WINDOW_START + dt.timedelta(days=1)).isoformat()]
        self.assertIsNone(gap["value"])
        self.assertEqual(gap["quality_status"], "missing")
        self.assertIn("missing", gap["quality"]["reason"])
        # the covered days keep exact values
        covered = by_day[WINDOW_START.isoformat()]
        self.assertIsNotNone(covered["value"])
        expected = COMPUTE_CONTEXT.multiply(
            Decimal("2.0"), Decimal("1.6978914247582741"))
        self.assertEqual(Decimal(covered["quality"]["exact_value"]), expected)

    def test_window_usd_estimate_unavailable_with_missing_days(self):
        from near_api.metrics.compute import formula_estimated_purchase_usd_v1

        records = formula_estimated_purchase_usd_v1(self.inputs, shape="windows")
        self.assertEqual(len(records), 4)  # two windows x two price bases
        available = [record for record in records if record["value"] is not None]
        gap = [record for record in records if record["value"] is None]
        self.assertEqual(len(available), 2)  # window 1 has prices
        self.assertEqual(len(gap), 2)        # window 2 is exactly the price gap
        for record in gap:
            # a single-day window is exactly that day's value, so it is missing;
            # a multi-day window would be unavailable with the missing dates
            self.assertEqual(record["quality_status"], "missing")
            self.assertIn("no saved NEAR/USD price", record["quality"]["reason"])

    def test_daily_and_window_bps_ratio_of_sums(self):
        from near_api.metrics.compute import formula_effective_gross_fee_bps_v1

        daily = formula_effective_gross_fee_bps_v1(self.inputs, shape="daily")
        llama = [record for record in daily if record["dimensions"]["source"] == "SRC-LLAMA"]
        first = Decimal(llama[0]["quality"]["exact_value"])
        expected = effective_fee_bps(Decimal("3135599249"), Decimal("4115978"))
        self.assertEqual(first, expected)
        windows = formula_effective_gross_fee_bps_v1(self.inputs, shape="windows")
        self.assertEqual(len(windows), 4)  # two sources x two atomic windows

    def test_zero_volume_denominator_is_unavailable_not_zero(self):
        from near_api.metrics.inputs import ProviderDay

        self.assertEqual(effective_fee_bps(Decimal(0), Decimal("100")), None)
        inputs = self.inputs
        providers = dict(inputs.providers.by_source)
        providers["SRC-LLAMA"] = dict(providers["SRC-LLAMA"])
        providers["SRC-LLAMA"][WINDOW_START] = ProviderDay(volume_usd=Decimal(0),
                                                           gross_fees_usd=Decimal("100"))
        zeroed = MetricInputs(**{**inputs.__dict__, "providers": ProviderSeries(by_source=providers)})
        from near_api.metrics.compute import formula_effective_gross_fee_bps_v1

        daily = formula_effective_gross_fee_bps_v1(zeroed, shape="daily")
        record = next(record for record in daily
                      if record["dimensions"]["source"] == "SRC-LLAMA"
                      and record["period_start"][:10] == WINDOW_START.isoformat())
        self.assertIsNone(record["value"])
        self.assertEqual(record["quality_status"], "unavailable")
        self.assertIn("zero or negative", record["quality"]["reason"])

    def test_upper_bound_ratio_propagates_bound_kind(self):
        from near_api.metrics.compute import formula_purchases_to_issuance_upper_pct_v1

        records = formula_purchases_to_issuance_upper_pct_v1(self.inputs, shape="windows")
        self.assertEqual(len(records), 2)
        for record in records:
            self.assertEqual(record["bound_kind"], "upper")
            self.assertIn("upper bound", record["quality"]["direction"])
        # reconcile against an independently computed ratio
        window = self.inputs.supply_windows[0]
        purchases = Decimal("2.0")  # day 1: 1.5 + 0.5 NEAR
        issuance_lower = (window.positive_supply_changes_near
                          + window.verified_simultaneous_burn_near - Decimal("0.01"))
        expected = COMPUTE_CONTEXT.divide(COMPUTE_CONTEXT.multiply(Decimal(100), purchases),
                                          issuance_lower)
        self.assertEqual(Decimal(records[0]["quality"]["exact_value"]), expected)

    def test_non_positive_net_supply_makes_ratio_unavailable(self):
        from near_api.metrics.compute import formula_purchases_to_net_supply_pct_v1

        window = self.inputs.supply_windows[0]
        narrowed = SupplyWindow(**{**window.__dict__, "start": WINDOW_START,
                                   "end_exclusive": WINDOW_START + dt.timedelta(days=1)})
        boundaries = list(self.inputs.supply_boundaries)
        # closing < opening for the first window
        boundaries[1] = SupplyBoundary(**{**boundaries[1].__dict__,
                                          "supply_near": Decimal("1.5")})
        inputs = MetricInputs(**{**self.inputs.__dict__,
                                 "supply_boundaries": tuple(boundaries),
                                 "supply_windows": (narrowed, self.inputs.supply_windows[1])})
        records = formula_purchases_to_net_supply_pct_v1(inputs, shape="windows")
        self.assertIsNone(records[0]["value"])
        self.assertEqual(records[0]["quality_status"], "unavailable")
        self.assertIn("non-positive", records[0]["quality"]["reason"])
        # the second window keeps its exact ratio
        self.assertIsNotNone(records[1]["value"])

    def test_non_positive_issuance_lower_bound_gives_no_upper(self):
        from near_api.metrics.compute import formula_purchases_to_issuance_upper_pct_v1

        window = self.inputs.supply_windows[0]
        narrowed = SupplyWindow(**{**window.__dict__,
                                   "positive_supply_changes_near": Decimal("0.01"),
                                   "verified_simultaneous_burn_near": Decimal(0)})
        inputs = MetricInputs(**{**self.inputs.__dict__,
                                 "supply_windows": (narrowed, self.inputs.supply_windows[1])})
        records = formula_purchases_to_issuance_upper_pct_v1(inputs, shape="windows")
        self.assertIsNone(records[0]["value"])
        self.assertEqual(records[0]["quality_status"], "unavailable")

    def test_purchases_are_never_deducted_from_supply(self):
        from near_api.metrics.compute import formula_net_supply_change_near_v1

        records = formula_net_supply_change_near_v1(self.inputs, shape="windows")
        boundaries = {boundary.date: boundary for boundary in self.inputs.supply_boundaries}
        for record, window in zip(records, self.inputs.supply_windows):
            expected = boundaries[window.closing_date].supply_near - \
                boundaries[window.opening_date].supply_near
            self.assertEqual(Decimal(record["value"]), expected)
            self.assertEqual(record["bound_kind"], "exact")
            self.assertIn("never", record["quality"]["purchase_policy"])
            purchases = Decimal(record["quality"]["observed_purchases_near"])
            self.assertNotEqual(Decimal(record["value"]),
                                expected - purchases * YOCTO)

    def test_gated_revenue_metrics_are_null_with_reason(self):
        from near_api.metrics.compute import (formula_protocol_capture_rate_v1,
                                              formula_protocol_revenue_usd_v1)

        for formula, metric_id in ((formula_protocol_revenue_usd_v1, "protocol_revenue_usd"),
                                   (formula_protocol_capture_rate_v1, "protocol_capture_rate")):
            records = formula(self.inputs, shape="daily")
            self.assertEqual(len(records), 3)
            for record in records:
                self.assertIsNone(record["value"])
                self.assertEqual(record["quality_status"], "unavailable")
                self.assertIn("reason", record["quality"])
                self.assertEqual(UUID(record["metric_definition_id"]),
                                 metric_registry.definition_by_metric_id(metric_id).id)

    def test_verified_zero_days_are_explicit(self):
        from near_api.metrics.compute import (formula_conversion_count_v1,
                                              formula_observed_near_purchases_v1,
                                              formula_treasury_payouts_near_v1)

        # purchases/conversions have no records on day 3; payouts none on day 2
        cases = ((formula_observed_near_purchases_v1, WINDOW_START + dt.timedelta(days=2)),
                 (formula_conversion_count_v1, WINDOW_START + dt.timedelta(days=2)),
                 (formula_treasury_payouts_near_v1, WINDOW_START + dt.timedelta(days=1)))
        for formula, zero_date in cases:
            records = formula(self.inputs, shape="daily")
            zero = next(record for record in records
                        if record["period_start"][:10] == zero_date.isoformat())
            self.assertEqual(Decimal(zero["value"]), 0)
            self.assertEqual(zero["quality_status"], "verified")
            self.assertIn("verified_zero", zero["quality"])

    def test_storage_scale_quantization_preserves_exact_value(self):
        product = Decimal("5005.727492813834237073998393") * Decimal("1.6978914247582741")
        stored = observation_value(product)
        self.assertEqual(len(stored.split(".")[1]), 30)
        self.assertNotEqual(Decimal(stored), product)
        # the exact value quantizes back to the stored form
        self.assertEqual(ratio_at_storage_scale(product), Decimal(stored))

    def test_coverage_gaps_refuse_computation(self):
        from near_api.metrics.compute import formula_observed_near_purchases_v1

        partial = MetricInputs(**{**self.inputs.__dict__,
                                  "flows": FlowRecords(
                                      conversions=self.inputs.flows.conversions,
                                      native_transfers=self.inputs.flows.native_transfers,
                                      withdrawals=self.inputs.flows.withdrawals,
                                      coverage=self.inputs.flows.coverage[:1],
                                      quality=self.inputs.flows.quality)})
        with self.assertRaises(MetricComputationError):
            formula_observed_near_purchases_v1(partial, shape="daily")

    def test_parse_errors_refuse_computation(self):
        from near_api.metrics.compute import formula_observed_near_purchases_v1

        bad_quality = QualityDay(block_date=WINDOW_START, event_json_logs=10,
                                 json_parse_errors=2)
        inputs = MetricInputs(**{**self.inputs.__dict__,
                                 "flows": FlowRecords(
                                     conversions=self.inputs.flows.conversions,
                                     native_transfers=self.inputs.flows.native_transfers,
                                     withdrawals=self.inputs.flows.withdrawals,
                                     coverage=self.inputs.flows.coverage,
                                     quality=(bad_quality,) + self.inputs.flows.quality[1:])})
        with self.assertRaises(MetricComputationError):
            formula_observed_near_purchases_v1(inputs, shape="daily")


# --------------------------------------------------------------------------- #
# Emission and synthetic summary reconciliation
# --------------------------------------------------------------------------- #


class SyntheticEmissionTests(unittest.TestCase):
    def setUp(self):
        self.inputs = synthetic_inputs()

    @staticmethod
    def values(document, metric_id, version=1):
        definition = metric_registry.definition_by_metric_id_version(metric_id, version)
        return [record for record in document["observations"]
                if UUID(record["metric_definition_id"]) == definition.id]

    def test_emitted_manifests_parse_and_validate(self):
        manifests = build_all_manifests(self.inputs, dataset_spec=DATASET_SPEC, manifest_inputs=())
        self.assertEqual(set(manifests), {"metrics.flows.daily", "metrics.windows.snapshot"})
        for dataset_key, document in manifests.items():
            parsed = parse_manifest_document(document, context=dataset_key)
            report = _validate_version_content(parsed, [])
            self.assertTrue(report["ok"], f"{dataset_key}: {report['errors']}")
            self.assertEqual(report["observation_count"], len(document["observations"]))
            for metric_id in document["member_metrics"]:
                self.assertIn(UUID(metric_id),
                              {definition.id for definition in metric_registry.DEFINITIONS})

    def test_emission_is_reproducible(self):
        first = build_all_manifests(self.inputs, dataset_spec=DATASET_SPEC, manifest_inputs=())
        second = build_all_manifests(self.inputs, dataset_spec=DATASET_SPEC, manifest_inputs=())
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_window_dataset_has_atomic_windows_and_boundary_stocks(self):
        document = build_manifest(self.inputs, dataset_key="metrics.windows.snapshot",
                                  dataset_spec=DATASET_SPEC, manifest_inputs=())
        windows = [record["period_start"][:10] for record in document["observations"]
                   if UUID(record["metric_definition_id"])
                   == metric_registry.definition_by_metric_id("net_supply_change_near").id]
        self.assertEqual(windows, [WINDOW_START.isoformat(),
                                   (WINDOW_START + dt.timedelta(days=1)).isoformat()])
        stocks = [record for record in document["observations"]
                  if UUID(record["metric_definition_id"])
                  == metric_registry.definition_by_metric_id("total_supply_near").id]
        self.assertEqual(len(stocks), 4)
        self.assertTrue(all(record["bound_kind"] == "exact" for record in stocks))

    def test_synthetic_saved_summary_reconciles_exactly(self):
        """Independent expected totals computed straight from the fixture."""
        inputs = self.inputs
        manifests = build_all_manifests(inputs, dataset_spec=DATASET_SPEC, manifest_inputs=())
        flows = manifests["metrics.flows.daily"]
        windows = manifests["metrics.windows.snapshot"]

        # saved summary: totals computed independently from the fixture constants
        saved = {
            "buy_total": Decimal("1500000000000000000000000")
                         + Decimal("500000000000000000000000")
                         + Decimal("2000000000000000000000000"),
            "payout_total": Decimal("610992154105948148261773753")
                            + Decimal("300000000000000000000000")
                            + Decimal("250000000000000000000000"),
            "events_total": 3 + 1 + 4,
            "payout_count_total": 3,
        }
        self.assertEqual(sum(Decimal(r["value"]) for r in self.values(flows, "observed_near_purchases"))
                         * YOCTO, saved["buy_total"])
        self.assertEqual(sum(Decimal(r["value"]) for r in self.values(flows, "treasury_payouts_near"))
                         * YOCTO, saved["payout_total"])
        self.assertEqual(sum(int(r["value"]) for r in self.values(flows, "conversion_count")),
                         saved["events_total"])
        self.assertEqual(sum(int(r["value"]) for r in self.values(flows, "treasury_payout_count")),
                         saved["payout_count_total"])
        # USD window total: day1 2.0 NEAR * price + day2 2.0 * 2.5 (day3 missing -> n/a)
        # here the window estimate is unavailable; the two covered daily values are exact
        usd = self.values(flows, "estimated_purchase_usd")
        exacts = sorted(Decimal(r["quality"].get("exact_value", r["value"])) for r in usd
                        if r["dimensions"]["price_basis"] == "start" and r["value"] is not None)
        self.assertEqual(len(exacts), 2)
        # day 3 purchases are a proven zero, so its USD estimate is exactly zero
        self.assertEqual(exacts[0], 0)
        self.assertEqual(exacts[1], COMPUTE_CONTEXT.multiply(Decimal("2.0"),
                                                             Decimal("1.6978914247582741")))
        # supply: net change equals the independent boundary difference
        boundaries = {boundary.date: boundary for boundary in inputs.supply_boundaries}
        for record, window in zip(self.values(windows, "net_supply_change_near"),
                                  inputs.supply_windows):
            self.assertEqual(Decimal(record["value"]),
                             boundaries[window.closing_date].supply_near
                             - boundaries[window.opening_date].supply_near)

    def test_ni071_per_recipient_payout_emission_reconciles_with_aggregate(self):
        """The v2 per-recipient observations are the v1 matcher run split by
        receiver: per day, the three named treasuries sum exactly to the v1
        aggregate observation, and every recipient row carries its
        dimensions.recipient identity."""
        manifests = build_all_manifests(self.inputs, dataset_spec=DATASET_SPEC,
                                        manifest_inputs=())
        flows = manifests["metrics.flows.daily"]
        from near_api.metrics.compute import TREASURY_ACCOUNTS

        by_day_recipient = {}
        for record in self.values(flows, "treasury_payouts_near", version=2):
            self.assertEqual(set(record["dimensions"]), {"recipient"})
            self.assertIn(record["dimensions"]["recipient"], TREASURY_ACCOUNTS)
            self.assertEqual(record["quality"]["recipient"],
                             record["dimensions"]["recipient"])
            by_day_recipient.setdefault(record["period_start"][:10], {})[
                record["dimensions"]["recipient"]] = record
        for aggregate in self.values(flows, "treasury_payouts_near", version=1):
            day = aggregate["period_start"][:10]
            rows = by_day_recipient.get(day, {})
            self.assertEqual(set(rows), set(TREASURY_ACCOUNTS),
                             f"{day}: the declared universe is incomplete")
            total = sum(Decimal(row["value"]) for row in rows.values())
            self.assertEqual(total, Decimal(aggregate["value"]),
                             f"{day}: per-recipient sum diverges from the aggregate")
            # a proven zero day is emitted per recipient with the coverage note
            if Decimal(aggregate["value"]) == 0:
                self.assertTrue(all("verified_zero" in row["quality"]
                                    for row in rows.values()))


# --------------------------------------------------------------------------- #
# Loaders on synthetic files (shape contract) and real archive (handed off)
# --------------------------------------------------------------------------- #


class LoaderShapeTests(unittest.TestCase):
    def test_daily_rows_must_ascending_and_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "daily.json"
            path.write_text(json.dumps([
                {"date": "2026-01-11", "buy_near": "1", "buy_events": 1, "payout_near": "1"},
                {"date": "2026-01-10", "buy_near": "1", "buy_events": 1, "payout_near": "1"},
            ]))
            with self.assertRaises(MetricComputationError):
                load_daily_flows(path)

    def test_float_amounts_are_rejected_in_loaders(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "daily.json"
            path.write_text(json.dumps([
                {"date": "2026-01-10", "buy_near": 1.5, "buy_events": 1, "payout_near": "1"},
            ]))
            with self.assertRaises(MetricComputationError):
                load_daily_flows(path)

    def test_unknown_payload_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flows.json"
            rows = [{"kind": "conversion_daily",
                     "payload": json.dumps({"block_date": "2026-01-10", "account_id": "a",
                                            "unexpected": True})}]
            path.write_text(json.dumps(rows))
            with self.assertRaises(MetricComputationError):
                load_longitudinal_flows(path)

    def test_supply_summary_requires_consistent_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "supply.json"
            boundary = {"date": "2026-01-09", "block_height": 1, "block_hash": "h",
                        "timestamp_ns": "1785974399657403069", "supply_near": "1000"}
            other = dict(boundary, supply_near="1001")
            document = {
                "method": "synthetic", "coverage_days": 1, "broken_links": 0,
                "mint_headers_verified": 0, "mint_headers_target": 0, "missing_mint_headers": 0,
                "periods": [{"start": "2026-01-10", "end_exclusive": "2026-01-11", "days": 1,
                             "opening": boundary, "closing": other, "blocks": 1,
                             "positive_change_blocks": 0,
                             "positive_supply_changes_near": "1",
                             "negative_supply_changes_near": "0",
                             "verified_simultaneous_burn_near": "0",
                             "verified_mint_headers": 0,
                             "issuance_lower_bound_near": "0.99",
                             "burn_lower_bound_near": "-0.01",
                             "net_supply_increase_near": "1", "purchases_near": "0",
                             "purchases_to_issuance_upper_bound_pct": "0",
                             "purchases_to_net_increase_pct": "0",
                             "net_increase_minus_purchases_hypothetical": "1",
                             "purchase_multiplier_to_equal_net_increase": "0",
                             "supply_growth_pct": "0",
                             "gross_issuance_and_burn_complete": False}],
                "total": {"start": "2026-01-10", "end_exclusive": "2026-01-11", "days": 1,
                          "opening": boundary, "closing": boundary, "blocks": 1,
                          "positive_change_blocks": 0,
                          "positive_supply_changes_near": "1",
                          "negative_supply_changes_near": "0",
                          "verified_simultaneous_burn_near": "0", "verified_mint_headers": 0,
                          "issuance_lower_bound_near": "0.99",
                          "burn_lower_bound_near": "-0.01", "net_supply_increase_near": "1",
                          "purchases_near": "0", "purchases_to_issuance_upper_bound_pct": "0",
                          "purchases_to_net_increase_pct": "0",
                          "net_increase_minus_purchases_hypothetical": "1",
                          "purchase_multiplier_to_equal_net_increase": "0",
                          "supply_growth_pct": "0", "gross_issuance_and_burn_complete": False},
            }
            path.write_text(json.dumps(document))
            with self.assertRaises(MetricComputationError):
                load_supply_summary(path)

    def test_treasury_snapshot_loads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "treasury.json"
            path.write_text(json.dumps({
                "pinned_rpc_block_height": 1, "pinned_rpc_block_hash": "h",
                "pinned_rpc_time_utc": "2026-01-12T11:31:03.179856+00:00",
                "native_balance_total_near": "10.5",
                "snapshots": [{"account_id": TREASURIES[0], "native_balance_near": "10.5"}]}))
            snapshot = load_treasury_summary(path)
            self.assertEqual(snapshot.total_near, Decimal("10.5"))
            self.assertEqual(snapshot.as_of.date(), dt.date(2026, 1, 12))
