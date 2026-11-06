"""Canonical NEAR event aggregation for NI-029 metrics.

Event identity follows docs/DATA_PIPELINE.md: network + receipt_id + log
index + item index + event type (tx hash is lineage, never the identity).
The aggregators in this module are the independent computation path for the
treasury-linked flow metrics:

- identical canonical events collapse once (counted as duplicates);
- conflicting payloads under one identity are a quarantine error, never a
  silent merge;
- only successful execution (``SUCCESS_VALUE``) can establish a credit or
  transfer; a failed receipt contributes nothing and is reported;
- transfers between the treasury accounts (internal hops) and inflows from
  senders other than ``intents.near`` are excluded from payouts and
  reported separately;
- payout matching pairs a DIP4 native_withdraw with the UNIQUE successful
  native transfer of equal receiver and exact yoctoNEAR amount within the
  documented tolerance (300 s), using every transfer receipt action at most
  once; an in-window withdrawal with zero or several candidates is an
  error, never an assumed zero;
- period assignment uses half-open UTC days ``[00:00, next 00:00)`` of the
  event execution timestamp; records whose partition date contradicts their
  timestamp are a contract error;
- amounts are exact integers in yoctoNEAR carried as Decimal; floats are
  rejected everywhere.
"""

from __future__ import annotations

import datetime as dt
import functools
from dataclasses import dataclass
from decimal import Context, Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
from typing import Iterable, Sequence

from near_api.datasets.canonical import canonical_timestamp, decimal_string

NETWORK = "near-mainnet"
YOCTO_PER_NEAR = Decimal(10) ** 24
PAYOUT_MATCH_TOLERANCE_SECONDS = 300
MATCHER_VERSION = "ni029-amount-receiver-300s-v1"
SUCCESS_STATUS = "SUCCESS_VALUE"
INTENTS_CONTRACT = "intents.near"

# The metrics package performs every arithmetic operation in this explicit
# high-precision context: the ambient default precision (28 significant
# digits) would silently round yoctoNEAR sums and USD products. Division
# results repeat beyond 100 digits only for ratios, which are explicitly
# quantized to the NUMERIC(78,30) storage scale.
COMPUTE_PRECISION = 100
COMPUTE_CONTEXT = Context(prec=COMPUTE_PRECISION, rounding=ROUND_HALF_EVEN)


def exact_arithmetic(func):
    """Run a computation with the package's exact Decimal context active."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with localcontext(COMPUTE_CONTEXT):
            return func(*args, **kwargs)

    return wrapper


class EventContractError(ValueError):
    """Input records violate the canonical event contract."""


class EventQuarantineError(EventContractError):
    """Conflicting payloads share one canonical event identity."""


class PayoutMatchingError(EventContractError):
    """An in-window withdrawal has zero or several candidate transfers."""


def parse_yocto_amount(value, *, context: str) -> Decimal:
    """Parse an exact yoctoNEAR integer amount (floats and decimals rejected)."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise EventContractError(f"{context}: amounts must be integer strings, got {type(value).__name__}")
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped.isdigit():
            raise EventContractError(f"{context}: {value!r} is not a non-negative integer string")
        try:
            return Decimal(stripped)
        except InvalidOperation:  # pragma: no cover - isdigit guarantees parseability
            raise EventContractError(f"{context}: {value!r} is not a decimal") from None
    return Decimal(value)


def parse_utc_timestamp(value, *, context: str) -> dt.datetime:
    if not isinstance(value, str):
        raise EventContractError(f"{context}: timestamps must be strings")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise EventContractError(f"{context}: {value!r} is not an ISO-8601 timestamp") from None
    if parsed.tzinfo is None:
        raise EventContractError(f"{context}: {value!r} requires an explicit timezone")
    return parsed.astimezone(dt.timezone.utc)


def day_period(value: dt.date | dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    """Half-open UTC day period ``[00:00, next 00:00)`` containing ``value``."""
    if isinstance(value, dt.datetime):
        value = value.astimezone(dt.timezone.utc).date()
    start = dt.datetime.combine(value, dt.time.min, tzinfo=dt.timezone.utc)
    return start, start + dt.timedelta(days=1)


def in_window(instant: dt.datetime, window_start: dt.date,
              window_end_exclusive: dt.date) -> bool:
    day = instant.astimezone(dt.timezone.utc).date()
    return window_start <= day < window_end_exclusive


@dataclass(frozen=True)
class ConversionDay:
    """One canonical per-account daily conversion aggregate (token_diff)."""

    block_date: dt.date
    account_id: str
    wrap_diff_events: int
    distinct_intent_hashes: int
    invalid_wrap_amounts: int
    buy_events: int
    buy_raw: Decimal
    sell_events: int
    sell_raw: Decimal
    other_events: int

    @property
    def identity(self) -> tuple:
        return (NETWORK, self.block_date.isoformat(), self.account_id, "conversion_daily")


@dataclass(frozen=True)
class NativeTransfer:
    """One canonical native TRANSFER receipt action (credit candidate)."""

    block_date: dt.date
    timestamp: dt.datetime
    block_height: int
    receipt_id: str
    action_index: int
    predecessor: str
    receiver: str
    amount_raw: Decimal
    status: str

    @property
    def identity(self) -> tuple:
        return (NETWORK, self.receipt_id, self.action_index, "native_transfer")

    @property
    def successful(self) -> bool:
        return self.status == SUCCESS_STATUS


@dataclass(frozen=True)
class WithdrawalEvent:
    """One canonical DIP4 native_withdraw event (payout intent side)."""

    block_date: dt.date
    timestamp: dt.datetime
    receipt_id: str
    log_index: int
    item_index: int
    account_id: str
    receiver_id: str
    amount_raw: Decimal
    intent_hash: str

    @property
    def identity(self) -> tuple:
        return (NETWORK, self.receipt_id, self.log_index, self.item_index,
                "dip4_native_withdraw")


@dataclass(frozen=True)
class DailyFlows:
    """Per-day aggregation result for one flow metric family."""

    by_day: dict[dt.date, Decimal]
    events_by_day: dict[dt.date, int]
    total: Decimal
    total_events: int
    duplicate_records: int
    excluded_out_of_window: int


def _dedupe(records: Sequence, *, payload_fn, context: str) -> tuple[list, int]:
    """Collapse identical canonical events; quarantine conflicting payloads."""
    unique: dict[tuple, tuple] = {}
    duplicates = 0
    for record in records:
        payload = payload_fn(record)
        previous = unique.get(record.identity)
        if previous is None:
            unique[record.identity] = (record, payload)
            continue
        if previous[1] != payload:
            raise EventQuarantineError(
                f"{context}: conflicting payloads for canonical identity "
                f"{record.identity}; raw response remains available and the batch "
                "is refused rather than merged")
        duplicates += 1
    return [entry[0] for entry in unique.values()], duplicates


@exact_arithmetic
def aggregate_purchases(records: Iterable[ConversionDay], *, window_start: dt.date,
                        window_end_exclusive: dt.date) -> DailyFlows:
    """Aggregate canonical conversion records into daily purchase flows.

    Records with any invalid wrap amount or a partition/timestamp mismatch
    fail closed. Records outside the declared window are excluded and
    counted (the saved extract may legitimately cover extra boundary days).
    """
    unique, duplicates = _dedupe(
        list(records), payload_fn=lambda r: (r.wrap_diff_events, r.distinct_intent_hashes,
                                             r.invalid_wrap_amounts, r.buy_events, r.buy_raw,
                                             r.sell_events, r.sell_raw, r.other_events),
        context="conversion_daily")
    by_day: dict[dt.date, Decimal] = {}
    events_by_day: dict[dt.date, int] = {}
    excluded = 0
    total = Decimal(0)
    total_events = 0
    for record in unique:
        if record.invalid_wrap_amounts:
            raise EventContractError(
                f"conversion record {record.block_date}/{record.account_id} declares "
                f"{record.invalid_wrap_amounts} invalid wrap amounts; refusing to "
                "aggregate unvalidated amounts")
        if not (window_start <= record.block_date < window_end_exclusive):
            excluded += 1
            continue
        by_day[record.block_date] = by_day.get(record.block_date, Decimal(0)) + record.buy_raw
        events_by_day[record.block_date] = (events_by_day.get(record.block_date, 0)
                                            + record.buy_events)
        total += record.buy_raw
        total_events += record.buy_events
    return DailyFlows(by_day=by_day, events_by_day=events_by_day, total=total,
                      total_events=total_events, duplicate_records=duplicates,
                      excluded_out_of_window=excluded)


@exact_arithmetic
def aggregate_sell_side(records: Iterable[ConversionDay], *, window_start: dt.date,
                        window_end_exclusive: dt.date) -> dict[dt.date, Decimal]:
    """Per-day reverse-exchange (sell) amounts; reported for quality only."""
    by_day: dict[dt.date, Decimal] = {}
    for record in records:
        if not (window_start <= record.block_date < window_end_exclusive):
            continue
        by_day[record.block_date] = (by_day.get(record.block_date, Decimal(0))
                                     + record.sell_raw)
    return by_day


@dataclass(frozen=True)
class PayoutAggregate:
    """Result of the independent payout matching and aggregation."""

    by_day: dict[dt.date, Decimal]
    count_by_day: dict[dt.date, int]
    total: Decimal
    total_count: int
    matched_pairs: tuple[tuple[WithdrawalEvent, NativeTransfer], ...]
    internal_hop_total: Decimal
    internal_hop_count: int
    other_sender_total: Decimal
    other_sender_count: int
    failed_transfer_count: int
    out_of_window_transfer_count: int
    out_of_window_transfer_total: Decimal
    out_of_window_withdrawal_count: int
    duplicate_records: int


@exact_arithmetic
def match_payouts(withdrawals: Iterable[WithdrawalEvent],
                  transfers: Iterable[NativeTransfer], *,
                  treasury_accounts: Sequence[str], window_start: dt.date,
                  window_end_exclusive: dt.date,
                  tolerance_seconds: int = PAYOUT_MATCH_TOLERANCE_SECONDS,
                  intents_contract: str = INTENTS_CONTRACT) -> PayoutAggregate:
    """Match withdrawals to unique successful transfers and aggregate payouts.

    Both sides are deduplicated first. Successful transfers from the intents
    contract to the named treasuries form the candidate pool; transfers
    between treasury accounts are internal hops and transfers from other
    senders are separate excluded inflows; failed executions establish
    nothing. Every in-window withdrawal must match exactly one unused
    in-window candidate.
    """
    treasuries = frozenset(treasury_accounts)
    unique_transfers, transfer_duplicates = _dedupe(
        list(transfers),
        payload_fn=lambda t: (t.block_date.isoformat(), canonical_timestamp(t.timestamp),
                              t.block_height, t.predecessor, t.receiver, t.amount_raw,
                              t.status),
        context="native_transfers")
    unique_withdrawals, withdrawal_duplicates = _dedupe(
        list(withdrawals),
        payload_fn=lambda w: (w.block_date.isoformat(), canonical_timestamp(w.timestamp),
                              w.receipt_id, w.log_index, w.item_index, w.account_id,
                              w.receiver_id, w.amount_raw, w.intent_hash),
        context="withdrawals")

    failed = 0
    internal: list[NativeTransfer] = []
    other = 0
    other_total = Decimal(0)
    out_of_window: list[NativeTransfer] = []
    pool: list[NativeTransfer] = []
    for transfer in unique_transfers:
        if transfer.block_date != transfer.timestamp.date():
            raise EventContractError(
                f"native transfer {transfer.receipt_id} partition date "
                f"{transfer.block_date} contradicts its execution timestamp "
                f"{canonical_timestamp(transfer.timestamp)}")
        if not transfer.successful:
            failed += 1
            continue
        if not in_window(transfer.timestamp, window_start, window_end_exclusive):
            out_of_window.append(transfer)
            continue
        if transfer.receiver not in treasuries:
            # The extract is scoped to the named treasuries; anything else is
            # a contract violation, not a silently droppable row.
            raise EventContractError(
                f"native transfer {transfer.receipt_id} targets non-treasury receiver "
                f"{transfer.receiver!r} outside the declared payout scope")
        if transfer.predecessor in treasuries:
            internal.append(transfer)
        elif transfer.predecessor == intents_contract:
            pool.append(transfer)
        else:
            other += 1
            other_total += transfer.amount_raw

    in_window_withdrawals: list[WithdrawalEvent] = []
    out_withdrawals = 0
    for withdrawal in unique_withdrawals:
        if withdrawal.block_date != withdrawal.timestamp.date():
            raise EventContractError(
                f"withdrawal {withdrawal.receipt_id} partition date "
                f"{withdrawal.block_date} contradicts its execution timestamp "
                f"{canonical_timestamp(withdrawal.timestamp)}")
        if not in_window(withdrawal.timestamp, window_start, window_end_exclusive):
            out_withdrawals += 1
            continue
        in_window_withdrawals.append(withdrawal)

    used: set[tuple] = set()
    matches: list[tuple[WithdrawalEvent, NativeTransfer]] = []
    tolerance = dt.timedelta(seconds=tolerance_seconds)
    for withdrawal in in_window_withdrawals:
        candidates = [transfer for transfer in pool
                      if transfer.identity not in used
                      and transfer.receiver == withdrawal.receiver_id
                      and transfer.amount_raw == withdrawal.amount_raw
                      and abs((transfer.timestamp - withdrawal.timestamp).total_seconds())
                      <= tolerance_seconds]
        if len(candidates) != 1:
            raise PayoutMatchingError(
                f"withdrawal {withdrawal.receipt_id} ({withdrawal.timestamp.date()} "
                f"{withdrawal.amount_raw} yoctoNEAR) matched {len(candidates)} candidate "
                f"transfers within {tolerance_seconds}s; exactly one is required, so the "
                "payout total is refused instead of guessed")
        match = candidates[0]
        used.add(match.identity)
        matches.append((withdrawal, match))

    by_day: dict[dt.date, Decimal] = {}
    count_by_day: dict[dt.date, int] = {}
    total = Decimal(0)
    for withdrawal, transfer in matches:
        day = transfer.timestamp.date()
        by_day[day] = by_day.get(day, Decimal(0)) + transfer.amount_raw
        count_by_day[day] = count_by_day.get(day, 0) + 1
        total += transfer.amount_raw
    internal_total = sum((transfer.amount_raw for transfer in internal), Decimal(0))
    out_total = sum((transfer.amount_raw for transfer in out_of_window), Decimal(0))
    return PayoutAggregate(
        by_day=by_day, count_by_day=count_by_day, total=total, total_count=len(matches),
        matched_pairs=tuple(matches), internal_hop_total=internal_total,
        internal_hop_count=len(internal), other_sender_total=other_total,
        other_sender_count=other, failed_transfer_count=failed,
        out_of_window_transfer_count=len(out_of_window),
        out_of_window_transfer_total=out_total,
        out_of_window_withdrawal_count=out_withdrawals,
        duplicate_records=transfer_duplicates + withdrawal_duplicates)


def near_from_yocto(amount_raw: Decimal) -> Decimal:
    """Exact yoctoNEAR -> NEAR (division by a power of ten never rounds)."""
    return amount_raw / YOCTO_PER_NEAR


def amount_string(amount_raw: Decimal) -> str:
    """Canonical exact NEAR decimal string for a yoctoNEAR amount."""
    return decimal_string(near_from_yocto(amount_raw))
