"""Loaders from the saved research aggregates to canonical NI-029 inputs.

Each loader parses one saved aggregate file of the read-only research
archive into the typed canonical inputs of :mod:`near_api.metrics.inputs`.
The loaders are strict: unknown payload keys, floats in amount fields,
missing required fields and unprovable quality (JSON parse errors, missing
coverage) are contract errors, because a computation fed by silently
dropped fields would not be reproducible. No loader ever writes; no network
call happens anywhere.

Real archive shapes loaded here (verified against the November 2026
handoff):

- ``near-longitudinal/data/flows_90d_raw.json``: rows of
  ``{"kind", "payload": "<json text>"}`` with kinds conversion_daily /
  native / withdrawal / quality / coverage;
- ``near-dollar/analysis/daily.json``: one daily row with saved CoinGecko
  price points and the two provider (SRC-LLAMA, SRC-DASHBOARD) series;
- ``near-supply/analysis/summary.json``: pinned boundary stocks plus
  per-window conservative gross bounds;
- ``near-treasury/data/summary.json``: pinned RPC treasury stock snapshot.
"""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

from near_api.datasets.canonical import decimal_string, parse_timestamp
from near_api.metrics.compute import MetricComputationError
from near_api.metrics.events import (
    ConversionDay,
    NativeTransfer,
    WithdrawalEvent,
    parse_utc_timestamp,
    parse_yocto_amount,
)
from near_api.metrics.inputs import (
    CoverageDay,
    DailyFlowRow,
    FlowRecords,
    MetricInputs,
    QualityDay,
    SupplyBoundary,
    SupplyWindow,
    TreasuryBalance,
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MetricComputationError(message)


def _decimal_field(payload: dict, key: str, *, context: str, required: bool = True) -> Decimal | None:
    value = payload.get(key)
    if value is None:
        _require(not required, f"{context}: missing required field {key!r}")
        return None
    _require(isinstance(value, str) and not isinstance(value, bool),
             f"{context}: {key} must be a decimal string, never a number")
    try:
        return Decimal(value)
    except Exception:
        raise MetricComputationError(f"{context}: {key}={value!r} is not a decimal string") from None


def _int_field(payload: dict, key: str, *, context: str, required: bool = True) -> int | None:
    value = payload.get(key)
    if value is None:
        _require(not required, f"{context}: missing required field {key!r}")
        return None
    _require(isinstance(value, int) and not isinstance(value, bool),
             f"{context}: {key} must be an integer")
    return value


def _date_field(payload: dict, key: str, *, context: str, required: bool = True) -> dt.date | None:
    value = payload.get(key)
    if value is None:
        _require(not required, f"{context}: missing required field {key!r}")
        return None
    _require(isinstance(value, str), f"{context}: {key} must be a date string")
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        raise MetricComputationError(f"{context}: {key}={value!r} is not an ISO date") from None


def _reject_unknown(payload: dict, allowed: set[str], *, context: str) -> None:
    unknown = sorted(set(payload) - allowed)
    _require(not unknown, f"{context}: unknown fields {unknown}")


def load_longitudinal_flows(path: Path) -> FlowRecords:
    """Parse the saved longitudinal extract into canonical event records."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise MetricComputationError(f"cannot read flows extract {path}: {error}") from None
    except json.JSONDecodeError as error:
        raise MetricComputationError(f"flows extract {path} is not valid JSON: {error}") from None
    _require(isinstance(document, list), f"{path}: the extract must be a list of rows")
    conversions: list[ConversionDay] = []
    transfers: list[NativeTransfer] = []
    withdrawals: list[WithdrawalEvent] = []
    coverage: list[CoverageDay] = []
    quality: list[QualityDay] = []
    for index, row in enumerate(document):
        context = f"{path.name}[{index}]"
        _require(isinstance(row, dict) and set(row) == {"kind", "payload"},
                 f"{context}: rows are {{kind, payload}} objects")
        kind = row["kind"]
        _require(isinstance(row["payload"], str), f"{context}: payload must be a JSON string")
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError as error:
            raise MetricComputationError(f"{context}: payload is not valid JSON: {error}") from None
        _require(isinstance(payload, dict), f"{context}: payload must be an object")
        if kind == "conversion_daily":
            _reject_unknown(payload, {"block_date", "account_id", "wrap_diff_events",
                                      "distinct_intent_hashes", "invalid_wrap_amounts",
                                      "buy_events", "buy_raw", "sell_events", "sell_raw",
                                      "other_events", "largest_buy_raw"}, context=context)
            conversions.append(ConversionDay(
                block_date=_date_field(payload, "block_date", context=context),
                account_id=str(payload["account_id"]),
                wrap_diff_events=_int_field(payload, "wrap_diff_events", context=context),
                distinct_intent_hashes=_int_field(payload, "distinct_intent_hashes",
                                                  context=context),
                invalid_wrap_amounts=_int_field(payload, "invalid_wrap_amounts", context=context),
                buy_events=_int_field(payload, "buy_events", context=context),
                buy_raw=parse_yocto_amount(payload["buy_raw"], context=f"{context}.buy_raw"),
                sell_events=_int_field(payload, "sell_events", context=context),
                sell_raw=parse_yocto_amount(payload["sell_raw"], context=f"{context}.sell_raw"),
                other_events=_int_field(payload, "other_events", context=context)))
        elif kind == "native":
            _reject_unknown(payload, {"block_date", "block_timestamp_utc", "block_height",
                                      "receipt_id", "index_in_action_receipt",
                                      "receipt_predecessor_account_id",
                                      "receipt_receiver_account_id", "amount_raw", "status"},
                            context=context)
            transfers.append(NativeTransfer(
                block_date=_date_field(payload, "block_date", context=context),
                timestamp=parse_utc_timestamp(payload["block_timestamp_utc"],
                                              context=f"{context}.block_timestamp_utc"),
                block_height=_int_field(payload, "block_height", context=context),
                receipt_id=str(payload["receipt_id"]),
                action_index=_int_field(payload, "index_in_action_receipt", context=context),
                predecessor=str(payload["receipt_predecessor_account_id"]),
                receiver=str(payload["receipt_receiver_account_id"]),
                amount_raw=parse_yocto_amount(payload["amount_raw"], context=f"{context}.amount_raw"),
                status=str(payload["status"])))
        elif kind == "withdrawal":
            _reject_unknown(payload, {"block_date", "block_timestamp_utc", "block_height",
                                      "receipt_id", "log_index", "item_index", "account_id",
                                      "receiver_id", "amount_raw", "intent_hash"},
                            context=context)
            withdrawals.append(WithdrawalEvent(
                block_date=_date_field(payload, "block_date", context=context),
                timestamp=parse_utc_timestamp(payload["block_timestamp_utc"],
                                              context=f"{context}.block_timestamp_utc"),
                receipt_id=str(payload["receipt_id"]),
                log_index=_int_field(payload, "log_index", context=context),
                item_index=_int_field(payload, "item_index", context=context),
                account_id=str(payload["account_id"]),
                receiver_id=str(payload["receiver_id"]),
                amount_raw=parse_yocto_amount(payload["amount_raw"], context=f"{context}.amount_raw"),
                intent_hash=str(payload["intent_hash"])))
        elif kind == "quality":
            _reject_unknown(payload, {"block_date", "event_json_logs", "json_parse_errors"},
                            context=context)
            quality.append(QualityDay(
                block_date=_date_field(payload, "block_date", context=context),
                event_json_logs=_int_field(payload, "event_json_logs", context=context),
                json_parse_errors=_int_field(payload, "json_parse_errors", context=context)))
        elif kind == "coverage":
            _reject_unknown(payload, {"block_date", "intents_outcomes",
                                      "successful_intents_outcomes", "first_timestamp",
                                      "last_timestamp"}, context=context)
            coverage.append(CoverageDay(
                block_date=_date_field(payload, "block_date", context=context),
                intents_outcomes=_int_field(payload, "intents_outcomes", context=context),
                successful_intents_outcomes=_int_field(payload, "successful_intents_outcomes",
                                                       context=context),
                first_timestamp=parse_timestamp(payload["first_timestamp"],
                                                context=f"{context}.first_timestamp"),
                last_timestamp=parse_timestamp(payload["last_timestamp"],
                                               context=f"{context}.last_timestamp")))
        else:
            raise MetricComputationError(f"{context}: unknown row kind {kind!r}")
    _require(conversions or withdrawals, f"{path}: the extract holds no flow records")
    return FlowRecords(conversions=tuple(conversions), native_transfers=tuple(transfers),
                       withdrawals=tuple(withdrawals), coverage=tuple(coverage),
                       quality=tuple(quality))


def load_daily_flows(path: Path) -> tuple[DailyFlowRow, ...]:
    """Parse the saved dollar-analysis daily rows (prices and provider series)."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise MetricComputationError(f"cannot read daily flows {path}: {error}") from None
    except json.JSONDecodeError as error:
        raise MetricComputationError(f"daily flows {path} is not valid JSON: {error}") from None
    _require(isinstance(document, list), f"{path}: daily flows must be a list")
    rows: list[DailyFlowRow] = []
    for index, payload in enumerate(document):
        context = f"{path.name}[{index}]"
        _require(isinstance(payload, dict), f"{context}: daily rows must be objects")
        _reject_unknown(payload, {"date", "price_start_utc", "price_end_utc", "buy_near",
                                  "buy_events", "payout_near", "buy_usd_start", "buy_usd_end",
                                  "payout_usd_start", "payout_usd_end", "volume_usd",
                                  "gross_fees_usd", "dashboard_volume_usd",
                                  "dashboard_gross_fees_usd"}, context=context)
        rows.append(DailyFlowRow(
            date=_date_field(payload, "date", context=context),
            buy_near=_decimal_field(payload, "buy_near", context=context),
            buy_events=_int_field(payload, "buy_events", context=context),
            payout_near=_decimal_field(payload, "payout_near", context=context),
            price_start_utc=_decimal_field(payload, "price_start_utc", context=context,
                                           required=False),
            price_end_utc=_decimal_field(payload, "price_end_utc", context=context,
                                         required=False),
            buy_usd_start=_decimal_field(payload, "buy_usd_start", context=context,
                                         required=False),
            buy_usd_end=_decimal_field(payload, "buy_usd_end", context=context, required=False),
            payout_usd_start=_decimal_field(payload, "payout_usd_start", context=context,
                                            required=False),
            payout_usd_end=_decimal_field(payload, "payout_usd_end", context=context,
                                          required=False),
            volume_usd=_decimal_field(payload, "volume_usd", context=context, required=False),
            gross_fees_usd=_decimal_field(payload, "gross_fees_usd", context=context,
                                          required=False),
            dashboard_volume_usd=_decimal_field(payload, "dashboard_volume_usd",
                                                context=context, required=False),
            dashboard_gross_fees_usd=_decimal_field(payload, "dashboard_gross_fees_usd",
                                                    context=context, required=False)))
    _require(rows, f"{path}: no daily rows")
    for previous, current in zip(rows, rows[1:]):
        _require(current.date > previous.date,
                 f"{path}: daily rows must be strictly ascending by date")
    return tuple(rows)


def load_supply_summary(path: Path) -> tuple[tuple[SupplyBoundary, ...], tuple[SupplyWindow, ...]]:
    """Parse the saved supply analysis (pinned boundaries and window bounds)."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise MetricComputationError(f"cannot read supply summary {path}: {error}") from None
    except json.JSONDecodeError as error:
        raise MetricComputationError(f"supply summary {path} is not valid JSON: {error}") from None
    _require(isinstance(document, dict), f"{path}: supply summary must be an object")
    _reject_unknown(document, {"method", "coverage_days", "broken_links",
                               "mint_headers_verified", "mint_headers_target",
                               "missing_mint_headers", "periods", "total"}, context=str(path))
    _require(document.get("broken_links") == 0, f"{path}: broken_links must be zero")
    _require(document.get("gross_issuance_and_burn_complete") is None
             or document.get("gross_issuance_and_burn_complete") is False,
             f"{path}: gross issuance/burn bounds are not declared complete")

    def boundary(payload: dict, context: str) -> SupplyBoundary:
        _reject_unknown(payload, {"date", "block_height", "block_hash", "timestamp_ns",
                                  "supply_near"}, context=context)
        supply = _decimal_field(payload, "supply_near", context=context)
        timestamp_ns = payload.get("timestamp_ns")
        _require(isinstance(timestamp_ns, str) and timestamp_ns.isdigit(),
                 f"{context}: timestamp_ns must be an integer string")
        return SupplyBoundary(
            date=_date_field(payload, "date", context=context),
            block_height=_int_field(payload, "block_height", context=context),
            block_hash=str(payload["block_hash"]),
            timestamp_ns=timestamp_ns,
            supply_near=supply)

    def window(payload: dict, context: str, *, is_total: bool = False) -> SupplyWindow:
        allowed = {"start", "end_exclusive", "days", "opening", "closing", "blocks",
                   "positive_change_blocks", "positive_supply_changes_near",
                   "negative_supply_changes_near", "verified_simultaneous_burn_near",
                   "verified_mint_headers", "issuance_lower_bound_near",
                   "burn_lower_bound_near", "net_supply_increase_near", "purchases_near",
                   "purchases_to_issuance_upper_bound_pct", "purchases_to_net_increase_pct",
                   "net_increase_minus_purchases_hypothetical",
                   "purchase_multiplier_to_equal_net_increase", "supply_growth_pct",
                   "gross_issuance_and_burn_complete"}
        _reject_unknown(payload, allowed, context=context)
        return SupplyWindow(
            start=_date_field(payload, "start", context=context),
            end_exclusive=_date_field(payload, "end_exclusive", context=context),
            opening_date=_date_field(payload["opening"], "date", context=f"{context}.opening"),
            closing_date=_date_field(payload["closing"], "date", context=f"{context}.closing"),
            positive_supply_changes_near=_decimal_field(
                payload, "positive_supply_changes_near", context=context),
            negative_supply_changes_near=_decimal_field(
                payload, "negative_supply_changes_near", context=context),
            verified_simultaneous_burn_near=_decimal_field(
                payload, "verified_simultaneous_burn_near", context=context),
            mint_headers_verified=_int_field(payload, "verified_mint_headers", context=context),
            mint_headers_target=int(document["mint_headers_target"]),
            gross_issuance_and_burn_complete=payload["gross_issuance_and_burn_complete"],
            is_total=is_total)

    boundaries: list[SupplyBoundary] = []
    windows: list[SupplyWindow] = []
    for index, payload in enumerate(document["periods"]):
        context = f"{path.name}.periods[{index}]"
        _require(isinstance(payload, dict), f"{context}: period rows must be objects")
        windows.append(window(payload, context))
        boundaries.append(boundary(payload["opening"], f"{context}.opening"))
        boundaries.append(boundary(payload["closing"], f"{context}.closing"))
    total = document["total"]
    _require(isinstance(total, dict), f"{path}: total must be an object")
    windows.append(window(total, f"{path.name}.total", is_total=True))
    boundaries.append(boundary(total["opening"], f"{path.name}.total.opening"))
    boundaries.append(boundary(total["closing"], f"{path.name}.total.closing"))
    # A boundary reused between windows must carry identical exact values.
    unique: dict[dt.date, SupplyBoundary] = {}
    for item in boundaries:
        previous = unique.get(item.date)
        _require(previous is None or previous == item,
                 f"{path}: boundary {item.date} appears with conflicting values")
        unique[item.date] = item
    _require(windows, f"{path}: no supply windows")
    return tuple(sorted(unique.values(), key=lambda item: item.date)), tuple(windows)


def load_treasury_summary(path: Path) -> TreasuryBalance:
    """Parse the pinned treasury stock snapshot."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise MetricComputationError(f"cannot read treasury summary {path}: {error}") from None
    except json.JSONDecodeError as error:
        raise MetricComputationError(f"treasury summary {path} is not valid JSON: {error}") from None
    _require(isinstance(document, dict), f"{path}: treasury summary must be an object")
    for key in ("pinned_rpc_block_height", "pinned_rpc_block_hash", "pinned_rpc_time_utc",
                "native_balance_total_near", "snapshots"):
        _require(key in document, f"{path}: missing required key {key!r}")
    accounts = tuple((snapshot["account_id"],
                      _decimal_field(snapshot, "native_balance_near",
                                     context=f"{path.name}.snapshot"))
                     for snapshot in document["snapshots"])
    _require(accounts, f"{path}: the snapshot lists no accounts")
    return TreasuryBalance(
        as_of=parse_timestamp(document["pinned_rpc_time_utc"],
                              context=f"{path.name}.pinned_rpc_time_utc"),
        block_height=int(document["pinned_rpc_block_height"]),
        block_hash=str(document["pinned_rpc_block_hash"]),
        total_near=_decimal_field(document, "native_balance_total_near", context=str(path)),
        accounts=accounts)


def load_metric_inputs(*, window_start: dt.date, window_end_exclusive: dt.date,
                       flows_path: Path, daily_flows_path: Path,
                       supply_path: Path | None = None,
                       treasury_path: Path | None = None) -> MetricInputs:
    """Load the canonical bundle and validate daily/window coverage shape."""
    flows = load_longitudinal_flows(flows_path)
    daily = load_daily_flows(daily_flows_path)
    covered = {row.block_date for row in flows.coverage}
    missing = []
    day = window_start
    while day < window_end_exclusive:
        if day not in covered:
            missing.append(day)
        day += dt.timedelta(days=1)
    _require(not missing,
             f"the extract lacks coverage rows for {len(missing)} window day(s) "
             f"(first {missing[0] if missing else None})")
    dates = [row.date for row in daily]
    _require(dates and dates[0] == window_start
             and len(dates) == (window_end_exclusive - window_start).days,
             f"daily flows hold {len(dates)} rows but the window needs "
             f"{(window_end_exclusive - window_start).days} ascending rows starting "
             f"{window_start.isoformat()}")
    boundaries: tuple[SupplyBoundary, ...] = ()
    windows: tuple[SupplyWindow, ...] = ()
    if supply_path is not None:
        boundaries, windows = load_supply_summary(supply_path)
    treasury = load_treasury_summary(treasury_path) if treasury_path is not None else None
    return MetricInputs(
        window_start=window_start, window_end_exclusive=window_end_exclusive, flows=flows,
        daily_flows=daily, prices=price_series_from(daily),
        providers=provider_series_from(daily), supply_boundaries=boundaries,
        supply_windows=windows, treasury_balance=treasury)


def price_series_from(daily: tuple[DailyFlowRow, ...]) -> "PriceSeries":
    from near_api.metrics.inputs import PriceSeries

    by_day: dict[tuple[dt.date, str], Decimal] = {}
    for row in daily:
        if row.price_start_utc is not None:
            by_day[(row.date, "start")] = row.price_start_utc
        if row.price_end_utc is not None:
            by_day[(row.date, "end")] = row.price_end_utc
    return PriceSeries(by_day=by_day)


def provider_series_from(daily: tuple[DailyFlowRow, ...]) -> "ProviderSeries":
    from near_api.metrics.inputs import ProviderDay, ProviderSeries

    by_source: dict[str, dict[dt.date, ProviderDay]] = {}
    for row in daily:
        if row.volume_usd is not None and row.gross_fees_usd is not None:
            by_source.setdefault("SRC-LLAMA", {})[row.date] = ProviderDay(
                volume_usd=row.volume_usd, gross_fees_usd=row.gross_fees_usd)
        if row.dashboard_volume_usd is not None and row.dashboard_gross_fees_usd is not None:
            by_source.setdefault("SRC-DASHBOARD", {})[row.date] = ProviderDay(
                volume_usd=row.dashboard_volume_usd, gross_fees_usd=row.dashboard_gross_fees_usd)
    return ProviderSeries(by_source=by_source)
