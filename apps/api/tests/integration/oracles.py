"""Independent NI-061 oracles for the financial invariants.

This module recomputes the expected aggregates straight from the raw
saved-extract payload rows (the ``{"kind", "payload"}`` shape of the
longitudinal extract) using a deliberately different implementation from
``near_api.metrics``: every yoctoNEAR amount stays a plain Python ``int`` and
the matching is a straight-line loop, so a defect in the production Decimal
or deduplication path cannot hide behind shared code. The only Decimal use is
the exact power-of-ten yoctoNEAR -> NEAR division for comparisons.

Semantics implemented here mirror the DOCUMENTED contract (docs/DATA_PIPELINE
and the registry definitions), not the code: identical canonical events count
once, failed receipts establish nothing, transfers between the named
treasuries are internal hops, only ``intents.near`` payouts are matched
(receiver + exact amount within 300 s, every transfer receipt action used at
most once), a payout is bucketed on the day of its matched transfer receipt
(cash receipt day, which may follow the withdrawal intent date), and an
in-window withdrawal with zero or several candidates is an error — never an
assumed zero.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

YOCTO_PER_NEAR = 10 ** 24
MATCH_TOLERANCE_SECONDS = 300
SUCCESS_STATUS = "SUCCESS_VALUE"
INTENTS_CONTRACT = "intents.near"


class OraclePayoutError(ValueError):
    """A withdrawal has zero or several candidate transfers (matching refused)."""


def _iso_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value[:10])


def _iso_timestamp(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    return parsed.astimezone(dt.timezone.utc)


@dataclass
class OracleFlows:
    """Expected per-day and total values computed independently."""

    purchase_yocto_by_day: dict[dt.date, int] = field(default_factory=dict)
    purchase_events_by_day: dict[dt.date, int] = field(default_factory=dict)
    payout_yocto_by_day: dict[dt.date, int] = field(default_factory=dict)
    payout_count_by_day: dict[dt.date, int] = field(default_factory=dict)
    purchase_total_yocto: int = 0
    purchase_total_events: int = 0
    payout_total_yocto: int = 0
    payout_total_count: int = 0
    internal_hop_total_yocto: int = 0
    internal_hop_count: int = 0
    other_sender_total_yocto: int = 0
    other_sender_count: int = 0
    failed_transfer_count: int = 0
    out_of_window_transfer_count: int = 0
    out_of_window_withdrawal_count: int = 0
    out_of_window_conversion_count: int = 0
    duplicate_records: int = 0
    matched_pairs: int = 0

    def purchase_near(self, day: dt.date) -> Decimal:
        return _near(self.purchase_yocto_by_day.get(day, 0))

    def payout_near(self, day: dt.date) -> Decimal:
        return _near(self.payout_yocto_by_day.get(day, 0))


def _near(yocto: int) -> Decimal:
    return Decimal(yocto) / Decimal(YOCTO_PER_NEAR)


def near_string(yocto: int) -> str:
    """Canonical exact NEAR decimal string for a yoctoNEAR integer."""
    value = _near(yocto)
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def aggregate_flows(payloads: list[dict], *, window_start: dt.date,
                    window_end_exclusive: dt.date,
                    treasury_accounts: tuple[str, ...],
                    tolerance_seconds: int = MATCH_TOLERANCE_SECONDS) -> OracleFlows:
    """Recompute purchases and payouts from raw extract payload dicts."""
    treasuries = set(treasury_accounts)
    result = OracleFlows()

    # -- conversions: identical (block_date, account) rows collapse once ----- #
    conversions: dict[tuple[str, str], dict] = {}
    for payload in payloads.get("conversion_daily", ()):
        key = (payload["block_date"], str(payload["account_id"]))
        if key in conversions:
            if conversions[key] != payload:
                raise ValueError("oracle: conflicting conversion payloads are a "
                                 "quarantine error, never a merge")
            result.duplicate_records += 1
            continue
        conversions[key] = payload
    for (block_date, _account), payload in conversions.items():
        day = _iso_date(block_date)
        if payload["invalid_wrap_amounts"]:
            raise ValueError("oracle: invalid wrap amounts are refused")
        if not (window_start <= day < window_end_exclusive):
            result.out_of_window_conversion_count += 1
            continue
        amount = int(payload["buy_raw"])
        result.purchase_yocto_by_day[day] = \
            result.purchase_yocto_by_day.get(day, 0) + amount
        result.purchase_events_by_day[day] = result.purchase_events_by_day.get(day, 0) \
            + int(payload["buy_events"])
        result.purchase_total_yocto += amount
        result.purchase_total_events += int(payload["buy_events"])

    # -- native transfers: dedupe on (receipt_id, action_index) -------------- #
    transfers: dict[tuple[str, int], dict] = {}
    for payload in payloads.get("native", ()):
        key = (str(payload["receipt_id"]), int(payload["index_in_action_receipt"]))
        if key in transfers:
            if transfers[key] != payload:
                raise ValueError("oracle: conflicting transfer payloads are a "
                                 "quarantine error, never a merge")
            result.duplicate_records += 1
            continue
        transfers[key] = payload

    pool: list[dict] = []
    for payload in transfers.values():
        day = _iso_date(payload["block_date"])
        timestamp = _iso_timestamp(payload["block_timestamp_utc"])
        if day != timestamp.date():
            raise ValueError("oracle: partition date contradicts the execution "
                             "timestamp")
        if payload["status"] != SUCCESS_STATUS:
            result.failed_transfer_count += 1
            continue
        if not (window_start <= timestamp.date() < window_end_exclusive):
            result.out_of_window_transfer_count += 1
            continue
        receiver = str(payload["receipt_receiver_account_id"])
        predecessor = str(payload["receipt_predecessor_account_id"])
        if receiver not in treasuries:
            raise ValueError("oracle: transfer outside the declared treasury scope")
        if predecessor in treasuries:
            result.internal_hop_total_yocto += int(payload["amount_raw"])
            result.internal_hop_count += 1
        elif predecessor == INTENTS_CONTRACT:
            pool.append(payload)
        else:
            result.other_sender_total_yocto += int(payload["amount_raw"])
            result.other_sender_count += 1

    # -- withdrawals: dedupe on (receipt_id, log_index, item_index) ---------- #
    withdrawals: dict[tuple[str, int, int], dict] = {}
    for payload in payloads.get("withdrawal", ()):
        key = (str(payload["receipt_id"]), int(payload["log_index"]),
               int(payload["item_index"]))
        if key in withdrawals:
            if withdrawals[key] != payload:
                raise ValueError("oracle: conflicting withdrawal payloads are a "
                                 "quarantine error, never a merge")
            result.duplicate_records += 1
            continue
        withdrawals[key] = payload

    used: set[tuple[str, int]] = set()
    for payload in withdrawals.values():
        timestamp = _iso_timestamp(payload["block_timestamp_utc"])
        if _iso_date(payload["block_date"]) != timestamp.date():
            raise ValueError("oracle: withdrawal partition contradicts timestamp")
        if not (window_start <= timestamp.date() < window_end_exclusive):
            result.out_of_window_withdrawal_count += 1
            continue
        amount = int(payload["amount_raw"])
        receiver = str(payload["receiver_id"])
        candidates = [transfer for transfer in pool
                      if (str(transfer["receipt_id"]),
                          int(transfer["index_in_action_receipt"])) not in used
                      and str(transfer["receipt_receiver_account_id"]) == receiver
                      and int(transfer["amount_raw"]) == amount
                      and abs((_iso_timestamp(transfer["block_timestamp_utc"])
                               - timestamp).total_seconds()) <= tolerance_seconds]
        if len(candidates) != 1:
            raise OraclePayoutError(
                f"oracle: withdrawal {payload['receipt_id']} matched "
                f"{len(candidates)} candidate transfers; exactly one is required")
        match = candidates[0]
        used.add((str(match["receipt_id"]), int(match["index_in_action_receipt"])))
        day = _iso_timestamp(match["block_timestamp_utc"]).date()
        result.payout_yocto_by_day[day] = result.payout_yocto_by_day.get(day, 0) + amount
        result.payout_count_by_day[day] = result.payout_count_by_day.get(day, 0) + 1
        result.payout_total_yocto += amount
        result.payout_total_count += 1
        result.matched_pairs += 1
    return result


@dataclass(frozen=True)
class SupplyExpectation:
    """Expected supply stocks and per-window net changes (yocto-scaled)."""

    stock_by_date: dict[dt.date, Decimal]
    net_change_by_window: dict[tuple[dt.date, dt.date], Decimal]


def supply_expectations(supply_document: dict) -> SupplyExpectation:
    """Recompute supply stocks and window net changes from the saved summary.

    ``supply_near`` values are exact 24-decimal strings; the differences are
    taken on the Decimal values directly (subtraction of finite decimals is
    exact — no quantization is involved anywhere in this oracle). Net changes
    are keyed by the half-open window ``[start, end_exclusive)``.
    """
    stocks: dict[dt.date, Decimal] = {}

    def boundary(payload: dict) -> Decimal:
        day = _iso_date(payload["date"])
        stocks[day] = Decimal(payload["supply_near"])
        return stocks[day]

    windows: dict[tuple[dt.date, dt.date], Decimal] = {}
    for window in list(supply_document["periods"]) + [supply_document["total"]]:
        opening = boundary(window["opening"])
        closing = boundary(window["closing"])
        windows[(_iso_date(window["start"]), _iso_date(window["end_exclusive"]))] = \
            closing - opening
    return SupplyExpectation(stock_by_date=stocks, net_change_by_window=windows)
