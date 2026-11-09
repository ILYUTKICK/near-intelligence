"""Synthetic NI-061 fixture bundle: raw saved-extract files and pipeline input.

Every account, receipt id, amount, hash and dataset key here is invented test
data (files, keys and quality notes carry visible ``synthetic`` labels; the
treasury account names are the registry's documented constant because the
delivery filters validate against it). Nothing is read from or written to the
research archives, the collectors or any provider — the builder only writes
fresh files into a caller-owned temporary directory.
"""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

from integration.oracles import aggregate_flows, supply_expectations

from near_api.metrics.loaders import load_metric_inputs

WINDOW_START = dt.date(2026, 6, 1)
WINDOW_END_EXCLUSIVE = dt.date(2026, 6, 4)  # three days: 06-01, 06-02, 06-03
BOUNDARY_DAY = WINDOW_START - dt.timedelta(days=1)  # 2026-05-31 pinned stock

TREASURIES = ("buybacks.multisignature.near", "fefundsadmin.sputnik-dao.near",
              "1csfundsadmin.sputnik-dao.near")
INTENTS = "intents.near"
OTHER_SENDER = "someone-else.synthetic.near"

# Synthetic yoctoNEAR amounts (plain integer strings).
BUY_D1_A = "1500000000000000000000000"   # 1.5 NEAR, collector A
BUY_D1_B = "500000000000000000000000"    # 0.5 NEAR, collector B
BUY_D2_A = "2250000000000000000000000"   # 2.25 NEAR, collector A
BUY_OUT_OF_WINDOW = "800000000000000000000000"
PAYOUT_NEXT_DAY = "610992154105948148261773753"  # receipt on the next UTC date
PAYOUT_MIDDAY = "300000000000000000000000"
PAYOUT_LAST_DAY = "250000000000000000000000"
PAYOUT_EXACT_TOLERANCE = "175000000000000000000000"  # matched at exactly 300 s
INTERNAL_HOP = "502793000000000000000000000"
OTHER_SENDER_INFLOW = "7751000000000000000000000"
FAILED_TRANSFER = "999000000000000000000000"
OUT_OF_WINDOW_TRANSFER = "123000000000000000000000"

COLLECTOR = "collector.synthetic.near"
COLLECTOR_2 = "collector-two.synthetic.near"

SUPPLY_D0 = "1000000.123456789012345678901234"
SUPPLY_D1 = "1050000.623456789012345678901234"
SUPPLY_D2 = "1110501.373456789012345678901234"
SUPPLY_D3 = "1170502.123456789012345678901234"

DATASET_SPEC = {
    "pipeline_version": "ni061-synthetic",
    "quality": {"notes": "synthetic NI-061 invariant fixture; no research data"},
}


def ts(day: dt.date, second: int = 0, micro: int = 0) -> str:
    instant = dt.datetime.combine(day, dt.time.min, tzinfo=dt.timezone.utc) + \
        dt.timedelta(seconds=second, microseconds=micro)
    return instant.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _row(kind: str, payload: dict) -> dict:
    return {"kind": kind, "payload": json.dumps(payload, sort_keys=True)}


# --------------------------------------------------------------------------- #
# Raw saved-extract rows (the canonical {"kind","payload"} file shape)
# --------------------------------------------------------------------------- #


def flow_rows() -> list[dict]:
    """Raw extract rows: matched payouts, midnight/next-date pairing, exclusions."""
    rows: list[dict] = []

    def conversion(day: dt.date, account: str, buy_raw: str, buy_events: int) -> None:
        rows.append(_row("conversion_daily", {
            "block_date": day.isoformat(), "account_id": account,
            "wrap_diff_events": buy_events, "distinct_intent_hashes": buy_events,
            "invalid_wrap_amounts": 0, "buy_events": buy_events, "buy_raw": buy_raw,
            "sell_events": 0, "sell_raw": "0", "other_events": 0,
            "largest_buy_raw": buy_raw,
        }))

    def transfer(day: dt.date, second: int, amount_raw: str, *, receipt: str,
                 predecessor: str = INTENTS, receiver: str = TREASURIES[0],
                 status: str = "SUCCESS_VALUE", action_index: int = 0) -> None:
        rows.append(_row("native", {
            "block_date": day.isoformat(), "block_timestamp_utc": ts(day, second),
            "block_height": 47000000 + second, "receipt_id": receipt,
            "index_in_action_receipt": action_index,
            "receipt_predecessor_account_id": predecessor,
            "receipt_receiver_account_id": receiver, "amount_raw": amount_raw,
            "status": status,
        }))

    def withdrawal(day: dt.date, second: int, amount_raw: str, *, receipt: str,
                   receiver: str = TREASURIES[0]) -> None:
        rows.append(_row("withdrawal", {
            "block_date": day.isoformat(), "block_timestamp_utc": ts(day, second),
            "block_height": 47000000 + second, "receipt_id": receipt,
            "log_index": 0, "item_index": 0, "account_id": COLLECTOR,
            "receiver_id": receiver, "amount_raw": amount_raw,
            "intent_hash": f"synthetic-intent-{receipt}",
        }))

    # Conversions: two accounts on D1 (one row later duplicated verbatim),
    # one on D2, none on D3 (verified zero), one out-of-window on D4.
    conversion(WINDOW_START, COLLECTOR, BUY_D1_A, buy_events=2)
    conversion(WINDOW_START, COLLECTOR_2, BUY_D1_B, buy_events=1)
    conversion(WINDOW_START + dt.timedelta(days=1), COLLECTOR, BUY_D2_A, buy_events=3)
    conversion(WINDOW_END_EXCLUSIVE, COLLECTOR, BUY_OUT_OF_WINDOW, buy_events=1)

    # Matched payout pairs. W1: withdrawal intent 23:57 on D1 whose matching
    # receipt lands 00:01 on D2 (240 s apart, cash-receipt day buckets the
    # payout to D2, and both events sit either side of UTC midnight).
    withdrawal(WINDOW_START, 23 * 3600 + 57 * 60, PAYOUT_NEXT_DAY, receipt="synthetic-w1")
    transfer(WINDOW_START + dt.timedelta(days=1), 60, PAYOUT_NEXT_DAY,
             receipt="synthetic-t1")
    # W2: same-day pair on D1; its transfer row is duplicated verbatim below.
    withdrawal(WINDOW_START, 12 * 3600, PAYOUT_MIDDAY, receipt="synthetic-w2")
    transfer(WINDOW_START, 12 * 3600 + 60, PAYOUT_MIDDAY, receipt="synthetic-t2")
    # W3: last window day, second treasury recipient.
    withdrawal(WINDOW_START + dt.timedelta(days=2), 8 * 3600, PAYOUT_LAST_DAY,
               receipt="synthetic-w3", receiver=TREASURIES[1])
    transfer(WINDOW_START + dt.timedelta(days=2), 8 * 3600 + 120, PAYOUT_LAST_DAY,
             receipt="synthetic-t3", receiver=TREASURIES[1])
    # W4: matched at exactly the 300 s tolerance boundary.
    withdrawal(WINDOW_START + dt.timedelta(days=1), 10 * 3600, PAYOUT_EXACT_TOLERANCE,
               receipt="synthetic-w4")
    transfer(WINDOW_START + dt.timedelta(days=1), 10 * 3600 + 300, PAYOUT_EXACT_TOLERANCE,
             receipt="synthetic-t4")

    # Excluded on purpose: internal treasury hop, other-sender inflow, failed
    # execution, out-of-window transfer, verbatim transfer duplicate.
    transfer(WINDOW_START + dt.timedelta(days=1), 20 * 3600, INTERNAL_HOP,
             receipt="synthetic-internal-hop", predecessor=TREASURIES[1])
    transfer(WINDOW_START + dt.timedelta(days=1), 21 * 3600, OTHER_SENDER_INFLOW,
             receipt="synthetic-other-sender", predecessor=OTHER_SENDER)
    transfer(WINDOW_START + dt.timedelta(days=1), 22 * 3600, FAILED_TRANSFER,
             receipt="synthetic-failed", status="Failure")
    transfer(WINDOW_END_EXCLUSIVE, 0, OUT_OF_WINDOW_TRANSFER, receipt="synthetic-late")
    transfer(WINDOW_START, 12 * 3600 + 60, PAYOUT_MIDDAY, receipt="synthetic-t2")

    for index, day in enumerate((WINDOW_START, WINDOW_START + dt.timedelta(days=1),
                                 WINDOW_START + dt.timedelta(days=2))):
        rows.append(_row("coverage", {
            "block_date": day.isoformat(), "intents_outcomes": 1000 + index,
            "successful_intents_outcomes": 900 + index,
            "first_timestamp": ts(day, 1), "last_timestamp": ts(day, 86399, 999999),
        }))
        rows.append(_row("quality", {
            "block_date": day.isoformat(), "event_json_logs": 100,
            "json_parse_errors": 0,
        }))
    return rows


def extract_document() -> list[dict]:
    """The full synthetic extract (one verbatim duplicate conversion row)."""
    rows = flow_rows()
    rows.insert(1, rows[0])  # duplicate conversion row: collapsed, counted once
    return rows


def daily_rows() -> list[dict]:
    """Saved daily rows: prices with one missing day and provider series."""
    days = (WINDOW_START, WINDOW_START + dt.timedelta(days=1),
            WINDOW_START + dt.timedelta(days=2))
    buy = {WINDOW_START: Decimal(BUY_D1_A) + Decimal(BUY_D1_B),
           WINDOW_START + dt.timedelta(days=1): Decimal(BUY_D2_A),
           WINDOW_START + dt.timedelta(days=2): Decimal(0)}
    payout = {WINDOW_START: Decimal(PAYOUT_MIDDAY),
              WINDOW_START + dt.timedelta(days=1):
                  Decimal(PAYOUT_NEXT_DAY) + Decimal(PAYOUT_EXACT_TOLERANCE),
              WINDOW_START + dt.timedelta(days=2): Decimal(PAYOUT_LAST_DAY)}
    prices = {WINDOW_START: ("3.25", "3.10"),
              WINDOW_START + dt.timedelta(days=1): None,
              WINDOW_START + dt.timedelta(days=2): ("1.5", "1.6")}
    providers = {
        WINDOW_START: ("3135599249", "4115978", "3533927934.471786945",
                       "4347632.654090667434"),
        WINDOW_START + dt.timedelta(days=1): ("1000000", "15000", "1100000", "16000"),
        WINDOW_START + dt.timedelta(days=2): ("2000000", "26000", "2100000", "27000"),
    }
    rows = []
    events = {WINDOW_START: 3, WINDOW_START + dt.timedelta(days=1): 3,
              WINDOW_START + dt.timedelta(days=2): 0}
    for day in days:
        start, end = prices[day] or (None, None)
        volume, fees, dash_volume, dash_fees = providers[day]
        rows.append({
            "date": day.isoformat(),
            "buy_near": format(buy[day] / Decimal(10) ** 24, "f"),
            "buy_events": events[day],
            "payout_near": format(payout[day] / Decimal(10) ** 24, "f"),
            "price_start_utc": start, "price_end_utc": end,
            "volume_usd": volume, "gross_fees_usd": fees,
            "dashboard_volume_usd": dash_volume,
            "dashboard_gross_fees_usd": dash_fees,
        })
    return rows


def supply_document() -> dict:
    """Pinned boundary stocks and conservative window bounds (synthetic)."""

    def boundary(day: dt.date, supply: str, height: int) -> dict:
        return {"date": day.isoformat(), "block_height": height,
                "block_hash": f"synthetic-boundary-{height}",
                "timestamp_ns": str(1780000000000000000 + height),
                "supply_near": supply}

    def window(start: dt.date, end_exclusive: dt.date, opening: dict, closing: dict,
               positive: str, negative: str) -> dict:
        return {
            "start": start.isoformat(), "end_exclusive": end_exclusive.isoformat(),
            "days": (end_exclusive - start).days, "opening": opening, "closing": closing,
            "blocks": 200000, "positive_change_blocks": 5,
            "positive_supply_changes_near": positive,
            "negative_supply_changes_near": negative,
            "verified_simultaneous_burn_near": "0.0355821760331987",
            "verified_mint_headers": 1,
            "issuance_lower_bound_near": format(
                Decimal(positive) + Decimal("0.0355821760331987") - Decimal("0.01"), "f"),
            "burn_lower_bound_near": format(
                Decimal(negative) + Decimal("0.0355821760331987") - Decimal("0.01"), "f"),
            "net_supply_increase_near": format(
                Decimal(closing["supply_near"]) - Decimal(opening["supply_near"]), "f"),
            "purchases_near": "4.25", "purchases_to_issuance_upper_bound_pct": "0",
            "purchases_to_net_increase_pct": "0",
            "net_increase_minus_purchases_hypothetical": "0",
            "purchase_multiplier_to_equal_net_increase": "0",
            "supply_growth_pct": "0",
            "gross_issuance_and_burn_complete": False,
        }

    opening = boundary(BOUNDARY_DAY, SUPPLY_D0, 47_000_000)
    middle = boundary(WINDOW_START, SUPPLY_D1, 47_100_000)
    late = boundary(WINDOW_START + dt.timedelta(days=1), SUPPLY_D2, 47_200_000)
    closing = boundary(WINDOW_START + dt.timedelta(days=2), SUPPLY_D3, 47_300_000)
    return {
        "method": "synthetic pinned-boundary stocks (NI-061 fixture)",
        "coverage_days": 3, "broken_links": 0,
        "mint_headers_verified": 1, "mint_headers_target": 1,
        "missing_mint_headers": 0,
        "periods": [
            window(WINDOW_START, WINDOW_START + dt.timedelta(days=1), opening, middle,
                   "50000.5", "500.25"),
            window(WINDOW_START + dt.timedelta(days=1),
                   WINDOW_START + dt.timedelta(days=2), middle, late,
                   "60000.75", "600.5"),
        ],
        "total": window(WINDOW_START, WINDOW_START + dt.timedelta(days=2), opening,
                        closing, "110051.25", "1100.75"),
    }


def treasury_document() -> dict:
    return {
        "pinned_rpc_block_height": 48_000_000,
        "pinned_rpc_block_hash": "synthetic-treasury-block",
        "pinned_rpc_time_utc": ts(WINDOW_START + dt.timedelta(days=2), 86399),
        "native_balance_total_near": "4140077.369748916078007362148128",
        "snapshots": [{"account_id": TREASURIES[0],
                       "native_balance_near": "2167847.131051440139635213430792"}],
    }


def write_bundle(directory: Path) -> dict[str, Path]:
    """Write the four synthetic saved-input files; return their paths."""
    paths = {
        "flows": directory / "flows-synthetic.json",
        "daily": directory / "daily-synthetic.json",
        "supply": directory / "supply-synthetic.json",
        "treasury": directory / "treasury-synthetic.json",
    }
    paths["flows"].write_text(json.dumps(extract_document(), indent=1) + "\n",
                              encoding="utf-8")
    paths["daily"].write_text(json.dumps(daily_rows(), indent=1) + "\n", encoding="utf-8")
    paths["supply"].write_text(json.dumps(supply_document(), indent=1) + "\n",
                               encoding="utf-8")
    paths["treasury"].write_text(json.dumps(treasury_document(), indent=1) + "\n",
                                 encoding="utf-8")
    return paths


def payloads_from_extract(path: Path) -> dict[str, list[dict]]:
    """Parse the raw extract rows into per-kind payload lists for the oracle."""
    payloads: dict[str, list[dict]] = {}
    for row in json.loads(path.read_text(encoding="utf-8")):
        payloads.setdefault(row["kind"], []).append(json.loads(row["payload"]))
    return payloads


def oracle_for(path: Path):
    """The independent expectation recomputed from the raw extract file."""
    payloads = payloads_from_extract(path)
    flows = aggregate_flows(payloads, window_start=WINDOW_START,
                            window_end_exclusive=WINDOW_END_EXCLUSIVE,
                            treasury_accounts=TREASURIES)
    supply = supply_expectations(json.loads(
        (path.parent / "supply-synthetic.json").read_text(encoding="utf-8")))
    return flows, supply


def pipeline_inputs(paths: dict[str, Path]):
    """The same bundle through the production loaders."""
    return load_metric_inputs(
        window_start=WINDOW_START, window_end_exclusive=WINDOW_END_EXCLUSIVE,
        flows_path=paths["flows"], daily_flows_path=paths["daily"],
        supply_path=paths["supply"], treasury_path=paths["treasury"])


DAYS = (WINDOW_START, WINDOW_START + dt.timedelta(days=1),
        WINDOW_START + dt.timedelta(days=2))
