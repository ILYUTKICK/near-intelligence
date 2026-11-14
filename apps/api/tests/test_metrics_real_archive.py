"""Real-archive reconciliation tests (operator-local verification).

These cases read the actual archive handoff (research aggregates from
2026-08..11) and therefore run only where NI_REAL_ARCHIVE_ROOT is set —
the operator's machine. CI and fresh clones have no archive bytes by
design (docs/COLLABORATION.md), so this file is NOT in the cluster
runner's discovery list; run it locally with:

  NI_REAL_ARCHIVE_ROOT=/path/to/research uv run --project apps/api \
      python -m unittest discover -s apps/api/tests -p test_metrics_real_archive.py -v

Synthetic coverage lives in test_metrics.py (always runs).
"""

import os
import unittest
from pathlib import Path


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


REAL_ARCHIVE = Path(os.environ["NI_REAL_ARCHIVE_ROOT"]).resolve() \
    if os.environ.get("NI_REAL_ARCHIVE_ROOT") else None


@unittest.skipUnless(REAL_ARCHIVE and REAL_ARCHIVE.is_dir(),
                     "real archive handoff not present (NI_REAL_ARCHIVE_ROOT)")
class RealArchiveReconciliationTests(unittest.TestCase):
    """Reconcile the computations with the archive's own saved summaries.

    The archive is opened READ-ONLY. Amounts reconcile exactly (Decimal);
    non-terminating ratios reconcile at the NUMERIC(78,30) storage scale.
    """

    @classmethod
    def setUpClass(cls):
        cls.inputs = load_metric_inputs(
            window_start=dt.date(2026, 8, 6), window_end_exclusive=dt.date(2026, 11, 4),
            flows_path=REAL_ARCHIVE / "near-longitudinal/data/flows_90d_raw.json",
            daily_flows_path=REAL_ARCHIVE / "near-dollar/analysis/daily.json",
            supply_path=REAL_ARCHIVE / "near-supply/analysis/summary.json",
            treasury_path=REAL_ARCHIVE / "near-treasury/data/summary.json")
        cls.dollar = json.loads(
            (REAL_ARCHIVE / "near-dollar/analysis/summary.json").read_text())
        cls.supply = json.loads(
            (REAL_ARCHIVE / "near-supply/analysis/summary.json").read_text())

    def test_payout_matching_reproduces_the_archive_exactly(self):
        payouts = match_payouts(self.inputs.flows.withdrawals, self.inputs.flows.native_transfers,
                                treasury_accounts=TREASURIES, window_start=dt.date(2026, 8, 6),
                                window_end_exclusive=dt.date(2026, 11, 4))
        self.assertEqual(payouts.total_count, 3165)
        self.assertEqual(decimal_string(payouts.total / YOCTO),
                         "1405659.135989071036891726256814")
        self.assertEqual(payouts.internal_hop_count, 2)
        self.assertEqual(decimal_string(payouts.internal_hop_total / YOCTO), "502794")
        self.assertEqual(decimal_string(payouts.other_sender_total / YOCTO),
                         "7751.94972615998997116")
        self.assertEqual(payouts.failed_transfer_count, 0)
        self.assertEqual(payouts.out_of_window_transfer_count, 14)

    def test_buy_total_reconciles_exactly(self):
        purchases = aggregate_purchases(self.inputs.flows.conversions,
                                        window_start=dt.date(2026, 8, 6),
                                        window_end_exclusive=dt.date(2026, 11, 4))
        self.assertEqual(decimal_string(purchases.total / YOCTO),
                         "524480.127692882832410490617319")
        self.assertEqual(purchases.total_events, 54991)

    def test_usd_estimates_reconcile_exactly(self):
        from near_api.metrics.compute import estimate_purchase_usd

        for basis, key in (("start", "buy_usd_start"), ("end", "buy_usd_end")):
            estimate = estimate_purchase_usd(aggregate_purchases(
                self.inputs.flows.conversions, window_start=dt.date(2026, 8, 6),
                window_end_exclusive=dt.date(2026, 11, 4)),
                self.inputs.prices, basis=basis, window_start=dt.date(2026, 8, 6),
                window_end_exclusive=dt.date(2026, 11, 4))
            self.assertEqual(estimate.missing_days, ())
            self.assertEqual(decimal_string(estimate.window_total),
                             self.dollar["total"][key])

    def test_fee_bps_reconciles_at_storage_scale(self):
        llama = effective_fee_bps(Decimal(self.dollar["total"]["volume_usd"]),
                                  Decimal(self.dollar["total"]["gross_fees_usd"]))
        self.assertEqual(decimal_string(ratio_at_storage_scale(llama)),
                         decimal_string(ratio_at_storage_scale(
                             Decimal(self.dollar["total"]["gross_fee_bps"]))))
        dashboard = effective_fee_bps(Decimal(self.dollar["total"]["dashboard_volume_usd"]),
                                      Decimal(self.dollar["total"]["dashboard_gross_fees_usd"]))
        self.assertEqual(decimal_string(ratio_at_storage_scale(dashboard)),
                         decimal_string(ratio_at_storage_scale(
                             Decimal(self.dollar["total"]["dashboard_gross_fee_bps"]))))

    def test_supply_values_reconcile_exactly(self):
        windows = {window.start.isoformat(): window for window in self.inputs.supply_windows
                   if not window.is_total}
        for period in self.supply["periods"]:
            saved = windows[period["start"]]
            self.assertEqual(saved.positive_supply_changes_near,
                             Decimal(period["positive_supply_changes_near"]))
            self.assertEqual(saved.end_exclusive.isoformat(), period["end_exclusive"])
        boundaries = {boundary.date: boundary for boundary in self.inputs.supply_boundaries}
        self.assertEqual(decimal_string(boundaries[dt.date(2026, 8, 5)].supply_near),
                         self.supply["periods"][0]["opening"]["supply_near"])
        self.assertEqual(decimal_string(boundaries[dt.date(2026, 11, 3)].supply_near),
                         self.supply["periods"][2]["closing"]["supply_near"])

    def test_treasury_balance_reconciles(self):
        self.assertEqual(decimal_string(self.inputs.treasury_balance.total_near),
                         "4140077.369748916078007362148128")
        self.assertEqual(self.inputs.treasury_balance.block_height, 223010763)

    def test_emitted_real_manifests_reconcile_with_summaries(self):
        manifests = build_all_manifests(self.inputs, dataset_spec=DatasetSpec(
            pipeline_version="ni029-verify",
            quality={"notes": "real archive reconciliation"}), manifest_inputs=())
        flows = manifests["metrics.flows.daily"]
        windows = manifests["metrics.windows.snapshot"]

        def records(document, metric_id):
            definition = metric_registry.definition_by_metric_id(metric_id)
            return [record for record in document["observations"]
                    if UUID(record["metric_definition_id"]) == definition.id]

        self.assertEqual(decimal_string(sum(Decimal(r["value"])
                                            for r in records(flows, "observed_near_purchases"))),
                         self.dollar["total"]["buy_near"])
        self.assertEqual(decimal_string(sum(Decimal(r["value"])
                                            for r in records(flows, "treasury_payouts_near"))),
                         self.dollar["total"]["payout_near"])
        self.assertEqual(decimal_string(sum(
            Decimal(r["quality"].get("exact_value", r["value"]))
            for r in records(flows, "estimated_purchase_usd")
            if r["dimensions"]["price_basis"] == "start_of_day")),
            self.dollar["total"]["buy_usd_start"])
        for record, period in zip(records(windows, "net_supply_change_near"),
                                  self.supply["periods"]):
            self.assertEqual(Decimal(record["value"]),
                             Decimal(period["net_supply_increase_near"]))
        for record, period in zip(records(windows, "purchases_to_issuance_upper_pct"),
                                  self.supply["periods"]):
            self.assertEqual(record["bound_kind"], "upper")
            self.assertEqual(decimal_string(ratio_at_storage_scale(
                Decimal(record["quality"]["exact_value"]))),
                decimal_string(ratio_at_storage_scale(
                    Decimal(period["purchases_to_issuance_upper_bound_pct"]))))


# --------------------------------------------------------------------------- #
# Real PostgreSQL suite (scripts/run-db-tests.py)
# --------------------------------------------------------------------------- #


def write_synthetic_archive(directory: Path) -> dict[str, Path]:
    """Write the synthetic canonical inputs in the real aggregate shapes."""
    directory.mkdir(parents=True, exist_ok=True)
    flows_rows = []
    for record in (conversion(WINDOW_START, buy_raw="1500000000000000000000000", buy_events=3),
                   conversion(WINDOW_START, account=COLLECTOR_2,
                              buy_raw="500000000000000000000000", buy_events=1),
                   conversion(WINDOW_START + dt.timedelta(days=1),
                              buy_raw="2000000000000000000000000", buy_events=4)):
        flows_rows.append({"kind": "conversion_daily", "payload": json.dumps({
            "block_date": record.block_date.isoformat(), "account_id": record.account_id,
            "wrap_diff_events": record.wrap_diff_events,
            "distinct_intent_hashes": record.distinct_intent_hashes,
            "invalid_wrap_amounts": record.invalid_wrap_amounts,
            "buy_events": record.buy_events, "buy_raw": str(record.buy_raw),
            "sell_events": record.sell_events, "sell_raw": str(record.sell_raw),
            "other_events": record.other_events})})
    pair_amounts = ((WINDOW_START, "610992154105948148261773753", 10),
                    (WINDOW_START, "300000000000000000000000", 20),
                    (WINDOW_START + dt.timedelta(days=2), "250000000000000000000000", 5))
    for day, amount, second in pair_amounts:
        wd = withdrawal(day, amount, second=second)
        tr = transfer(day, amount, second=second + 2)
        flows_rows.append({"kind": "withdrawal", "payload": json.dumps({
            "block_date": wd.block_date.isoformat(),
            "block_timestamp_utc": wd.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "block_height": 2000, "receipt_id": wd.receipt_id, "log_index": 0, "item_index": 0,
            "account_id": wd.account_id, "receiver_id": wd.receiver_id,
            "amount_raw": str(wd.amount_raw), "intent_hash": wd.intent_hash})})
        flows_rows.append({"kind": "native", "payload": json.dumps({
            "block_date": tr.block_date.isoformat(),
            "block_timestamp_utc": tr.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "block_height": 2001, "receipt_id": tr.receipt_id,
            "index_in_action_receipt": tr.action_index,
            "receipt_predecessor_account_id": tr.predecessor,
            "receipt_receiver_account_id": tr.receiver, "amount_raw": str(tr.amount_raw),
            "status": tr.status})})
    for index in range(3):
        day = WINDOW_START + dt.timedelta(days=index)
        flows_rows.append({"kind": "coverage", "payload": json.dumps({
            "block_date": day.isoformat(), "intents_outcomes": 1000 + index,
            "successful_intents_outcomes": 900,
            "first_timestamp": ts(day, 1).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "last_timestamp": ts(day, 86399).strftime("%Y-%m-%dT%H:%M:%S.%fZ")})})
        flows_rows.append({"kind": "quality", "payload": json.dumps({
            "block_date": day.isoformat(), "event_json_logs": 100, "json_parse_errors": 0})})
    flows_path = directory / "flows_90d_raw.json"
    flows_path.write_text(json.dumps(flows_rows, indent=1))
    daily_path = directory / "daily.json"
    daily_path.write_text(json.dumps([
        {"date": WINDOW_START.isoformat(), "buy_near": "2",
         "buy_events": 4, "payout_near": "0.910992154105948148261773753",
         "price_start_utc": "1.6978914247582741", "price_end_utc": "1.6563050316183050",
         "buy_usd_start": "3.3957828495165482", "buy_usd_end": "3.3126100632366100",
         "payout_usd_start": "1.5463572434238593", "payout_usd_end": "1.5086256735286332",
         "volume_usd": "3135599249", "gross_fees_usd": "4115978",
         "dashboard_volume_usd": "3533927934.471786945",
         "dashboard_gross_fees_usd": "4347632.654090667434"},
        {"date": (WINDOW_START + dt.timedelta(days=1)).isoformat(), "buy_near": "2",
         "buy_events": 4, "payout_near": "0",
         "volume_usd": "1000000", "gross_fees_usd": "15000",
         "dashboard_volume_usd": "1100000", "dashboard_gross_fees_usd": "16000"},
        {"date": (WINDOW_START + dt.timedelta(days=2)).isoformat(), "buy_near": "0",
         "buy_events": 0, "payout_near": "0.25",
         "price_start_utc": "2.5", "price_end_utc": "2.6",
         "volume_usd": "2000000", "gross_fees_usd": "26000",
         "dashboard_volume_usd": "2100000", "dashboard_gross_fees_usd": "27000"},
    ]))
    def boundary(day: dt.date, index: int) -> dict:
        return {"date": day.isoformat(), "block_height": 200000 + index,
                "block_hash": f"hash{index}", "timestamp_ns": str(1785974399657403069 + index),
                "supply_near": decimal_string(Decimal("1000000.123456789012345678901234")
                                              + Decimal(1000 * index))}
    def boundary_by_index(index: int) -> dict:
        return boundary(WINDOW_START - dt.timedelta(days=1) + dt.timedelta(days=index), index)

    def window_row(start: dt.date, end: dt.date, opening_index: int, closing_index: int,
                   positive: str, negative: str) -> dict:
        burn = "0.0355821760331987"
        issuance = decimal_string(Decimal(positive) + Decimal(burn) - Decimal("0.01"))
        burn_bound = decimal_string(Decimal(negative) + Decimal(burn) - Decimal("0.01"))
        return {"start": start.isoformat(), "end_exclusive": end.isoformat(), "days": 1,
                "opening": boundary_by_index(opening_index),
                "closing": boundary_by_index(closing_index),
                "blocks": 100, "positive_change_blocks": 1,
                "positive_supply_changes_near": positive,
                "negative_supply_changes_near": negative,
                "verified_simultaneous_burn_near": burn, "verified_mint_headers": 1,
                "issuance_lower_bound_near": issuance, "burn_lower_bound_near": burn_bound,
                "net_supply_increase_near": "0", "purchases_near": "2",
                "purchases_to_issuance_upper_bound_pct": "1",
                "purchases_to_net_increase_pct": "1",
                "net_increase_minus_purchases_hypothetical": "0",
                "purchase_multiplier_to_equal_net_increase": "1", "supply_growth_pct": "0",
                "gross_issuance_and_burn_complete": False}
    supply_path = directory / "supply.json"
    supply_path.write_text(json.dumps({
        "method": "synthetic fixture", "coverage_days": 3, "broken_links": 0,
        "mint_headers_verified": 2, "mint_headers_target": 2, "missing_mint_headers": 0,
        "periods": [
            window_row(WINDOW_START, WINDOW_START + dt.timedelta(days=1), 0, 1,
                       "50000.5", "500.25"),
            window_row(WINDOW_START + dt.timedelta(days=1),
                       WINDOW_START + dt.timedelta(days=2), 1, 2, "60000.75", "600.5")],
        "total": window_row(WINDOW_START, WINDOW_START + dt.timedelta(days=2), 0, 2,
                            "110051.25", "1100.75")}))
    treasury_path = directory / "treasury.json"
    treasury_path.write_text(json.dumps({
        "pinned_rpc_block_height": 300000, "pinned_rpc_block_hash": "treasury-hash",
        "pinned_rpc_time_utc": "2026-01-12T11:31:03.179856+00:00",
        "native_balance_total_near": "4140077.369748916078007362148128",
        "snapshots": [{"account_id": TREASURIES[0],
                       "native_balance_near": "2167847.131051440139635213430792"}]}))
    return {"flows": flows_path, "daily_flows": daily_path, "supply": supply_path,
            "treasury": treasury_path}


@unittest.skipUnless(os.environ.get("NI_ISOLATED_PG_TEST") == "1", "Use scripts/run-db-tests.py")
class MetricDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from alembic import command
        from alembic.config import Config
        from sqlalchemy import create_engine
        from sqlalchemy.pool import NullPool

        from near_api.datasets.service import create_dataset_operator_engine

        cls.repo = Path(__file__).resolve().parents[3]
        cls.config = Config(str(cls.repo / "apps/api/alembic.ini"))
        cls.operator = create_dataset_operator_engine(os.environ["NI_TEST_OPERATOR_URL"])
        cls.admin = create_engine(os.environ["NI_TEST_ADMIN_URL"], poolclass=NullPool,
                                  hide_parameters=True)
        cls.runtime = create_runtime_engine(os.environ["NI_TEST_RUNTIME_URL"], pool_size=2)
        command.upgrade(cls.config, "head")

    @classmethod
    def tearDownClass(cls):
        cls.operator.dispose()
        cls.admin.dispose()
        cls.runtime.dispose()

    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix="metrics-", dir=os.environ["NI_TEST_TMP_DIR"]))
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)

    def _ensure_sources(self):
        from sqlalchemy import text

        sources = {"SRC-BQ": "BigQuery public export", "SRC-PRICE": "CoinGecko saved prices",
                   "SRC-LLAMA": "DefiLlama saved responses",
                   "SRC-DASHBOARD": "NEAR Dashboard saved snapshots",
                   "SRC-FASTNEAR": "FastNear indexed blocks",
                   "SRC-NEAR-RPC": "NEAR public RPC"}
        with self.operator.begin() as connection:
            for source_id, name in sources.items():
                connection.execute(text("""
                    INSERT INTO app.sources(id, name, access_status, license_status)
                    VALUES (:id, :name, 'documented', 'unverified')
                    ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """), {"id": source_id, "name": name})

    def test_01_migration_round_trip_and_rls_flags(self):
        from alembic import command
        from sqlalchemy import text

        command.downgrade(self.config, "0004_dataset_staging")
        with self.admin.connect() as connection:
            self.assertIsNone(connection.scalar(text(
                "SELECT to_regclass('app.metric_definitions')")))
        command.upgrade(self.config, "head")
        command.check(self.config)
        with self.admin.connect() as connection:
            row = connection.execute(text("""
                SELECT relrowsecurity, relforcerowsecurity, pg_get_userbyid(relowner)
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'app' AND relname = 'metric_definitions'
            """)).one()
        self.assertEqual(tuple(row), (True, True, "near_migrator"))

    def test_02_registration_is_idempotent_and_content_verified(self):
        from sqlalchemy import text

        from near_api.metrics import register_definitions
        from near_api.metrics.registry import MetricRegistryError

        self._ensure_sources()
        with self.operator.begin() as connection:
            summary = register_definitions(connection)
        self.assertEqual(summary["registered"], len(metric_registry.DEFINITIONS))
        with self.operator.begin() as connection:
            again = register_definitions(connection)
        self.assertEqual(again["registered"], 0)
        self.assertEqual(again["existing"], len(metric_registry.DEFINITIONS))
        # a definition row diverging from the code registry is immutable history:
        # registration refuses instead of rewriting
        original = metric_registry.definition_by_metric_id("protocol_revenue_usd").name

        def restore():
            with self.admin.begin() as connection:
                connection.execute(text("""
                    UPDATE app.metric_definitions SET name = :name
                    WHERE metric_id = 'protocol_revenue_usd'
                """), {"name": original})
        self.addCleanup(restore)
        with self.admin.begin() as connection:
            connection.execute(text("""
                UPDATE app.metric_definitions SET name = 'tampered'
                WHERE metric_id = 'protocol_revenue_usd'
            """))
        with self.assertRaises(MetricRegistryError):
            with self.operator.begin() as connection:
                register_definitions(connection)

    def test_03_definitions_readable_by_two_users_never_writable(self):
        from sqlalchemy import text
        from sqlalchemy.exc import DBAPIError

        self._ensure_sources()
        with self.operator.begin() as connection:
            from near_api.metrics import register_definitions

            register_definitions(connection)
        first, second = uuid4(), uuid4()
        for subject in (first, second):
            with user_transaction(self.runtime, subject) as connection:
                count = connection.scalar(text("SELECT count(*) FROM app.metric_definitions"))
                gated = connection.execute(text("""
                    SELECT source_id FROM app.metric_definitions
                    WHERE metric_id = 'protocol_revenue_usd'
                """)).scalar_one()
            self.assertEqual(count, len(metric_registry.DEFINITIONS))
            self.assertIsNone(gated)
        forbidden = (
            "INSERT INTO app.metric_definitions(id, metric_id, version, name, unit, frequency,"
            " economic_scope, formula_key, definition, quality_rules)"
            " VALUES (gen_random_uuid(), 'evil_metric', 1, 'x', 'y', 'daily', 'z', 'f', '{}', '{}')",
            "UPDATE app.metric_definitions SET name = 'x'",
            "DELETE FROM app.metric_definitions",
        )
        for statement in forbidden:
            with self.subTest(statement=statement[:40]):
                with self.assertRaises(DBAPIError) as raised:
                    with user_transaction(self.runtime, first) as connection:
                        connection.execute(text(statement))
                self.assertEqual(raised.exception.orig.sqlstate, "42501")

    def _write_and_stage(self, dataset_key: str, *, storage: str = "storage"):
        from near_api.datasets.service import publish, stage

        files = write_synthetic_archive(self.directory / "inputs")
        inputs = load_metric_inputs(
            window_start=WINDOW_START, window_end_exclusive=WINDOW_END,
            flows_path=files["flows"], daily_flows_path=files["daily_flows"],
            supply_path=files["supply"], treasury_path=files["treasury"])
        document = build_manifest(inputs, dataset_key=dataset_key, dataset_spec=DATASET_SPEC,
                                  manifest_inputs=manifest_inputs(files))
        manifest_path = self.directory / f"{dataset_key}.manifest.json"
        manifest_path.write_text(json.dumps(document, sort_keys=True))
        result = stage(self.operator, manifest_path, self.directory / storage)
        if not result.deduplicated:
            self.assertEqual(result.status, "validated", result.validation)
        publish(self.operator, result.dataset_version_id)
        return document, result

    def test_04_computed_datasets_stage_publish_and_are_readable_by_two_users(self):
        from sqlalchemy import text

        self._ensure_sources()
        with self.operator.begin() as connection:
            from near_api.metrics import register_definitions

            register_definitions(connection)
        expected = {}
        for dataset_key in ("metrics.flows.daily", "metrics.windows.snapshot"):
            document, _result = self._write_and_stage(dataset_key)
            expected[dataset_key] = len(document["observations"])
        first, second = uuid4(), uuid4()
        for subject in (first, second):
            with user_transaction(self.runtime, subject) as connection:
                rows = connection.execute(text("""
                    SELECT v.dataset_key, count(o.*)
                    FROM app.dataset_versions v
                    JOIN app.metric_observations o ON o.dataset_version_id = v.id
                    WHERE v.status = 'approved' AND v.dataset_key LIKE 'metrics.%'
                    GROUP BY v.dataset_key ORDER BY v.dataset_key
                """)).all()
                definitions = connection.scalar(text(
                    "SELECT count(*) FROM app.metric_definitions"))
            self.assertEqual(dict(rows), expected)
            self.assertEqual(definitions, len(metric_registry.DEFINITIONS))

    def test_05_reimport_identical_input_deduplicates(self):
        from near_api.datasets.service import stage

        self._ensure_sources()
        self._write_and_stage("metrics.flows.daily")
        files = write_synthetic_archive(self.directory / "inputs-again")
        inputs = load_metric_inputs(
            window_start=WINDOW_START, window_end_exclusive=WINDOW_END,
            flows_path=files["flows"], daily_flows_path=files["daily_flows"],
            supply_path=files["supply"], treasury_path=files["treasury"])
        document = build_manifest(inputs, dataset_key="metrics.flows.daily",
                                  dataset_spec=DATASET_SPEC,
                                  manifest_inputs=manifest_inputs(files))
        manifest_path = self.directory / "again.manifest.json"
        manifest_path.write_text(json.dumps(document, sort_keys=True))
        result = stage(self.operator, manifest_path, self.directory / "storage-again")
        self.assertTrue(result.deduplicated)
        self.assertEqual(result.status, "approved")

    @unittest.skipUnless(REAL_ARCHIVE and REAL_ARCHIVE.is_dir(),
                         "real archive handoff not present (NI_REAL_ARCHIVE_ROOT)")
    def test_06_real_archive_datasets_stage_publish_and_reconcile(self):
        from sqlalchemy import text

        self._ensure_sources()
        with self.operator.begin() as connection:
            from near_api.metrics import register_definitions

            register_definitions(connection)
        inputs = load_metric_inputs(
            window_start=dt.date(2026, 8, 6), window_end_exclusive=dt.date(2026, 11, 4),
            flows_path=REAL_ARCHIVE / "near-longitudinal/data/flows_90d_raw.json",
            daily_flows_path=REAL_ARCHIVE / "near-dollar/analysis/daily.json",
            supply_path=REAL_ARCHIVE / "near-supply/analysis/summary.json",
            treasury_path=REAL_ARCHIVE / "near-treasury/data/summary.json")
        real_spec = DatasetSpec(pipeline_version="ni029-verify",
                                quality={"notes": "real archive verification"})
        real_inputs = manifest_inputs({
            "flows": REAL_ARCHIVE / "near-longitudinal/data/flows_90d_raw.json",
            "daily_flows": REAL_ARCHIVE / "near-dollar/analysis/daily.json",
            "supply": REAL_ARCHIVE / "near-supply/analysis/summary.json",
            "treasury": REAL_ARCHIVE / "near-treasury/data/summary.json"})
        flows_version_id = None
        for dataset_key in ("metrics.flows.daily", "metrics.windows.snapshot"):
            document = build_manifest(inputs, dataset_key=dataset_key, dataset_spec=real_spec,
                                      manifest_inputs=real_inputs)
            manifest_path = self.directory / f"{dataset_key}.manifest.json"
            manifest_path.write_text(json.dumps(document, sort_keys=True))
            from near_api.datasets.service import publish, stage

            result = stage(self.operator, manifest_path, self.directory / "real-storage")
            if not result.deduplicated:
                self.assertEqual(result.status, "validated", result.validation)
            publish(self.operator, result.dataset_version_id)
            if dataset_key == "metrics.flows.daily":
                flows_version_id = result.dataset_version_id
        # stored approved observations reconcile with the archive summaries exactly
        dollar = json.loads(
            (REAL_ARCHIVE / "near-dollar/analysis/summary.json").read_text())
        subject = uuid4()
        with user_transaction(self.runtime, subject) as connection:
            stored = connection.execute(text("""
                SELECT md.metric_id, sum(o.value) AS total
                FROM app.metric_observations o
                JOIN app.metric_definitions md ON md.id = o.metric_definition_id
                WHERE o.dataset_version_id = :version
                  AND md.metric_id IN ('observed_near_purchases', 'treasury_payouts_near')
                GROUP BY md.metric_id
            """), {"version": flows_version_id}).all()
        totals = {metric_id: Decimal(total) for metric_id, total in stored}
        self.assertEqual(decimal_string(totals["observed_near_purchases"]),
                         dollar["total"]["buy_near"])
        self.assertEqual(decimal_string(totals["treasury_payouts_near"]),
                         dollar["total"]["payout_near"])


if __name__ == "__main__":
    unittest.main()
