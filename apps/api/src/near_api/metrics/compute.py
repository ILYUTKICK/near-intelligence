"""Exact metric computations for NI-029 (pure Decimal, no floats).

Every function here is deterministic: the same canonical inputs always
produce the same Decimal outputs, and the emitted observation records
satisfy the strict NI-028 observation schema. The rules implemented are the
ones the NI-029 acceptance criteria name:

- Amounts reconcile at full precision: yoctoNEAR sums are exact Decimals
  (24 fractional digits, inside the NUMERIC(78,30) storage scale); derived
  USD products are exact at compute precision and stored explicitly rounded
  to the 30-decimal storage scale with the exact string preserved in the
  observation quality metadata and the hash-pinned manifest artifact.
- Missing is never zero: a missing price makes the USD estimate missing and
  the window aggregate unavailable with the missing dates listed; gated
  metrics (protocol revenue, capture rate, fee-funded buybacks) are null
  with a reason on every period.
- Purchases are never deducted from supply: net supply change is exactly
  ``closing - opening`` and the purchase sum is reported alongside, never
  subtracted.
- Bound quality propagates: the purchases/issuance ratio over an issuance
  LOWER bound is emitted as an UPPER bound; issuance/burn stay lower bounds
  and never enter exact accounting identities.
- Denominators: zero, negative or missing denominators produce unavailable
  (null) observations with reasons, never zero.

All divisions run in a documented high-precision context (100 significant
digits, ROUND_HALF_EVEN); sums and products of the real input magnitudes
stay exact well below it. The FORMULA_REGISTRY binds every registered
``formula_key`` (see :mod:`near_api.metrics.registry`) to one fixed
function; no SQL or eval anywhere.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Context, Decimal, ROUND_HALF_EVEN
from typing import Callable, Sequence

from near_api.datasets.canonical import canonical_timestamp, decimal_string, dump_canonical, sha256_hex
from near_api.metrics import registry as metric_registry
from near_api.metrics.events import (
    COMPUTE_CONTEXT,
    COMPUTE_PRECISION,
    DailyFlows,
    MATCHER_VERSION,
    PayoutAggregate,
    PAYOUT_MATCH_TOLERANCE_SECONDS,
    YOCTO_PER_NEAR,
    aggregate_purchases,
    exact_arithmetic,
    match_payouts,
    day_period,
)
from near_api.metrics.inputs import (
    MetricInputs,
    PriceSeries,
    ProviderSeries,
    SupplyBoundary,
    SupplyWindow,
    TreasuryBalance,
)

# Divisions and every other arithmetic step use the shared exact context
# imported from events (100 significant digits, ROUND_HALF_EVEN); products
# and sums of the real input magnitudes stay exact far below it. The
# remaining imports of Context/localcontext stay at the top for the storage
# quantization below.

# Observation values are stored NUMERIC(78,30): anything finer is explicitly
# rounded (never silently) and the exact string is preserved in the
# observation quality metadata.
STORAGE_SCALE = Decimal("1e-30")

# The saved supply analysis subtracts this tolerance from BigQuery FLOAT64
# block-change sums so the published bounds stay conservative.
SUPPLY_FLOAT_TOLERANCE_NEAR = Decimal("0.01")

PRICE_BASES = ("start", "end")
PROVIDER_SOURCES = ("SRC-LLAMA", "SRC-DASHBOARD")

TREASURY_ACCOUNTS = ("buybacks.multisignature.near", "fefundsadmin.sputnik-dao.near",
                     "1csfundsadmin.sputnik-dao.near")

_QUALITY_LIMIT = 4096


class MetricComputationError(ValueError):
    """Inputs or state make an honest computation impossible."""


def observation_value(value: Decimal) -> str:
    """Canonical storage-scale decimal string (explicit ROUND_HALF_EVEN)."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise MetricComputationError("observation values must be finite Decimals")
    quantized = value.quantize(STORAGE_SCALE, rounding=ROUND_HALF_EVEN, context=COMPUTE_CONTEXT)
    if quantized == 0:
        return "0"
    return decimal_string(quantized)


def ratio_at_storage_scale(value: Decimal) -> Decimal:
    """Quantize a non-terminating ratio to the storage scale for comparison."""
    return value.quantize(STORAGE_SCALE, rounding=ROUND_HALF_EVEN, context=COMPUTE_CONTEXT)


def near_amount(amount_raw: Decimal) -> Decimal:
    """Exact yoctoNEAR -> NEAR (a power-of-ten division never rounds).

    Runs in the compute context because the ambient default precision (28)
    would silently round amounts of 29+ significant digits.
    """
    return COMPUTE_CONTEXT.divide(amount_raw, YOCTO_PER_NEAR)


def dimensions_hash(dimensions: dict) -> str:
    return sha256_hex(dump_canonical(dimensions))


def _quality_bounded(quality: dict, *, context: str) -> dict:
    if len(dump_canonical(quality)) > _QUALITY_LIMIT:
        raise MetricComputationError(
            f"{context}: quality metadata exceeds {_QUALITY_LIMIT} bytes")
    return quality


def observation_record(definition: metric_registry.MetricDefinition, *,
                       period_start: dt.datetime, period_end: dt.datetime,
                       dimensions: dict, value: Decimal | None, bound_kind: str | None,
                       quality_status: str, quality: dict,
                       source_record_ref: str | None = None) -> dict:
    """Build one strict NI-028 observation record dict.

    The value/quality/bound invariants mirror the database constraints:
    missing/unavailable implies a null value with a reason, ``bound_kind``
    exists exactly when a value exists, and every quality document stays
    inside the storage size limit.
    """
    if period_end <= period_start:
        raise MetricComputationError("observation periods are half-open and non-empty")
    if (quality_status in ("missing", "unavailable")) != (value is None):
        raise MetricComputationError(
            f"{definition.metric_id}: missing/unavailable quality implies a null value")
    if (bound_kind is None) != (value is None):
        raise MetricComputationError(
            f"{definition.metric_id}: bound_kind is required exactly when a value exists")
    if value is None and "reason" not in quality:
        raise MetricComputationError(f"{definition.metric_id}: a null value requires a reason")
    if value is not None:
        exact = decimal_string(value)
        stored = observation_value(value)
        if stored != exact and "exact_value" not in quality:
            # The stored value is explicitly rounded to the NUMERIC(78,30)
            # scale; the exact computation result is preserved in the row
            # quality metadata and the hash-pinned manifest artifact.
            quality = {**quality, "exact_value": exact}
    else:
        stored = None
    return {
        "metric_definition_id": str(definition.id),
        "period_start": canonical_timestamp(period_start),
        "period_end": canonical_timestamp(period_end),
        "dimensions": dimensions,
        "value": stored,
        "quality_status": quality_status,
        "bound_kind": bound_kind,
        "source_record_ref": source_record_ref,
        "quality": _quality_bounded(quality, context=definition.metric_id),
    }


def gated_null_record(definition: metric_registry.MetricDefinition, *,
                      period_start: dt.datetime, period_end: dt.datetime,
                      reason: str, dimensions: dict | None = None) -> dict:
    """An explicitly unavailable observation: null with a reason, never zero."""
    return observation_record(
        definition, period_start=period_start, period_end=period_end,
        dimensions=dimensions or {}, value=None, bound_kind=None,
        quality_status="unavailable",
        quality={"reason": reason, "availability": "gated"})


def day_periods(window_start: dt.date, window_end_exclusive: dt.date
                ) -> list[tuple[dt.datetime, dt.datetime]]:
    """The daily half-open UTC grid of a window."""
    periods: list[tuple[dt.datetime, dt.datetime]] = []
    day = window_start
    while day < window_end_exclusive:
        periods.append(day_period(day))
        day += dt.timedelta(days=1)
    return periods


def window_period(window_start: dt.date, window_end_exclusive: dt.date
                  ) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime.combine(window_start, dt.time.min, tzinfo=dt.timezone.utc)
    end = dt.datetime.combine(window_end_exclusive, dt.time.min, tzinfo=dt.timezone.utc)
    return start, end


def _day_of(period: tuple[dt.datetime, dt.datetime]) -> dt.date:
    return period[0].astimezone(dt.timezone.utc).date()


# --------------------------------------------------------------------------- #
# Shared flow aggregation (one matcher run per call, deterministic)
# --------------------------------------------------------------------------- #


@exact_arithmetic
def purchases_by_day(inputs: MetricInputs) -> DailyFlows:
    """Independent event aggregation of the observed purchases."""
    return aggregate_purchases(inputs.flows.conversions,
                               window_start=inputs.window_start,
                               window_end_exclusive=inputs.window_end_exclusive)


@exact_arithmetic
def payout_aggregate(inputs: MetricInputs) -> PayoutAggregate:
    """Independent payout matching over the declared window."""
    return match_payouts(inputs.flows.withdrawals, inputs.flows.native_transfers,
                         treasury_accounts=TREASURY_ACCOUNTS,
                         window_start=inputs.window_start,
                         window_end_exclusive=inputs.window_end_exclusive)


def require_daily_coverage(inputs: MetricInputs) -> None:
    """Every window day needs the extract's coverage proof before zeros."""
    covered = {row.block_date for row in inputs.flows.coverage}
    for row in inputs.flows.quality:
        if row.json_parse_errors:
            raise MetricComputationError(
                f"extract day {row.block_date} reports {row.json_parse_errors} JSON parse "
                "errors; unvalidated logs cannot feed metrics")
    day = inputs.window_start
    while day < inputs.window_end_exclusive:
        if day not in covered:
            raise MetricComputationError(
                f"extract day {day} has no coverage row; zero activity is not assumed "
                "without coverage proof")
        day += dt.timedelta(days=1)


# --------------------------------------------------------------------------- #
# Price and provider input views
# --------------------------------------------------------------------------- #


def price_series(inputs: MetricInputs) -> PriceSeries:
    """The saved price points carried by the canonical inputs."""
    return inputs.prices


def provider_series(inputs: MetricInputs) -> ProviderSeries:
    """The saved provider series carried by the canonical inputs."""
    return inputs.providers


def point_instant(day: dt.date, basis: str) -> dt.datetime:
    if basis == "start":
        return dt.datetime.combine(day, dt.time.min, tzinfo=dt.timezone.utc)
    if basis == "end":
        return dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min,
                                   tzinfo=dt.timezone.utc)
    raise MetricComputationError(f"unknown price basis {basis!r}")


# --------------------------------------------------------------------------- #
# Registered formulas: one fixed function per formula_key
# --------------------------------------------------------------------------- #


def _shape_periods(inputs: MetricInputs, shape: str) -> list[tuple]:
    """The canonical observation periods for a dataset shape.

    ``daily`` tiles the declared window with half-open UTC days; ``windows``
    uses the atomic (non-total) analysis windows. Every formula derives its
    own periods from this helper, so an emitted observation can never sit on
    a period its dataset does not declare.
    """
    if shape == "daily":
        return day_periods(inputs.window_start, inputs.window_end_exclusive)
    if shape == "windows":
        return sorted(active_supply_window_periods(inputs))
    raise MetricComputationError(f"unknown dataset shape {shape!r}")


def _flow_day_records(definition, periods,
                      by_day_fn: Callable, *, unit_note: str) -> list[dict]:
    """One verified observation per day period for a flow metric."""
    records: list[dict] = []
    for start, end in periods:
        day = _day_of((start, end))
        raw_amount, count = by_day_fn(day)
        quality: dict = {}
        if raw_amount is None and count is None:
            quality["verified_zero"] = (
                "the extract covers this day (coverage row present) and holds no "
                f"qualifying records; {unit_note} is a proven zero")
            raw_amount, count = Decimal(0), 0
        if unit_note == "events":
            value = Decimal(count)
        else:
            value = near_amount(raw_amount)
        records.append(observation_record(
            definition, period_start=start, period_end=end, dimensions={}, value=value,
            bound_kind="exact", quality_status="verified", quality=quality))
    return records


@exact_arithmetic
def formula_observed_near_purchases_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    require_daily_coverage(inputs)
    flows = purchases_by_day(inputs)

    def by_day(day):
        if day in flows.by_day:
            return flows.by_day[day], flows.events_by_day.get(day, 0)
        return None, None

    definition = metric_registry.definition_by_metric_id("observed_near_purchases")
    return _flow_day_records(definition, _shape_periods(inputs, shape), by_day,
                             unit_note="purchases")


@exact_arithmetic
def formula_conversion_count_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    require_daily_coverage(inputs)
    flows = purchases_by_day(inputs)

    def by_day(day):
        if day in flows.by_day:
            return flows.by_day[day], flows.events_by_day.get(day, 0)
        return None, None

    definition = metric_registry.definition_by_metric_id("conversion_count")
    return _flow_day_records(definition, _shape_periods(inputs, shape), by_day,
                             unit_note="events")


def _payout_views(inputs: MetricInputs) -> tuple[dict, dict, PayoutAggregate]:
    payouts = payout_aggregate(inputs)
    amounts: dict[dt.date, Decimal] = {}
    counts: dict[dt.date, int] = {}
    for withdrawal, transfer in payouts.matched_pairs:
        day = transfer.timestamp.date()
        amounts[day] = amounts.get(day, Decimal(0)) + transfer.amount_raw
        counts[day] = counts.get(day, 0) + 1
    return amounts, counts, payouts


def _payout_quality(payouts: PayoutAggregate) -> dict:
    quality = {
        "matcher_version": MATCHER_VERSION,
        "tolerance_seconds": PAYOUT_MATCH_TOLERANCE_SECONDS,
        "matched_pairs": payouts.total_count,
        "internal_hops_excluded": payouts.internal_hop_count,
        "internal_hops_excluded_near": decimal_string(near_amount(payouts.internal_hop_total)),
        "other_sender_inflows_excluded": payouts.other_sender_count,
        "other_sender_inflows_excluded_near": decimal_string(
            near_amount(payouts.other_sender_total)),
        "failed_transfers_excluded": payouts.failed_transfer_count,
        "duplicate_records_collapsed": payouts.duplicate_records,
    }
    if payouts.out_of_window_transfer_count:
        quality["out_of_window_transfers_excluded"] = payouts.out_of_window_transfer_count
        quality["out_of_window_transfers_excluded_near"] = decimal_string(
            near_amount(payouts.out_of_window_transfer_total))
    if payouts.out_of_window_withdrawal_count:
        quality["out_of_window_withdrawals_excluded"] = payouts.out_of_window_withdrawal_count
    return quality


@exact_arithmetic
def formula_treasury_payouts_near_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    require_daily_coverage(inputs)
    amounts, counts, payouts = _payout_views(inputs)
    quality = _payout_quality(payouts)
    # The v1 formula must emit observations of the immutable v1 definition,
    # never of a later version of the same metric id.
    definition = metric_registry.definition_by_metric_id_version(
        "treasury_payouts_near", 1)
    records: list[dict] = []
    for start, end in _shape_periods(inputs, shape):
        day = _day_of((start, end))
        raw = amounts.get(day)
        if raw is None:
            raw, note = Decimal(0), {
                "verified_zero": "the extract covers this day and holds no matched "
                                 "payout withdrawal; zero payouts is proven for the "
                                 "matched definition"}
        else:
            note = {}
        records.append(observation_record(
            definition, period_start=start, period_end=end, dimensions={},
            value=near_amount(raw), bound_kind="exact", quality_status="verified",
            quality={**quality, **note}))
    return records


@exact_arithmetic
def formula_treasury_payouts_near_v2(inputs: MetricInputs, *, shape: str) -> list[dict]:
    """Per-recipient payouts (NI-071): the v1 matcher run split by receiver.

    Mechanically derived from the same matched pairs as the v1 aggregate:
    one verified observation per day and per named treasury, with
    ``dimensions.recipient`` carrying the verified transfer receiver. A day
    with no matched payout for a recipient is a proven zero under the same
    coverage proof as v1 — never a silent gap and never an invented value.
    """
    require_daily_coverage(inputs)
    payouts = payout_aggregate(inputs)
    amounts: dict[tuple[dt.date, str], Decimal] = {}
    for withdrawal, transfer in payouts.matched_pairs:
        key = (transfer.timestamp.date(), transfer.receiver)
        amounts[key] = amounts.get(key, Decimal(0)) + transfer.amount_raw
    quality = _payout_quality(payouts)
    definition = metric_registry.definition_by_metric_id_version(
        "treasury_payouts_near", 2)
    records: list[dict] = []
    for start, end in _shape_periods(inputs, shape):
        day = _day_of((start, end))
        for receiver in TREASURY_ACCOUNTS:
            raw = amounts.get((day, receiver))
            if raw is None:
                raw, note = Decimal(0), {
                    "verified_zero": "the extract covers this day and holds no matched "
                                     f"payout withdrawal to {receiver}; zero payouts is "
                                     "proven for the matched definition"}
            else:
                note = {}
            records.append(observation_record(
                definition, period_start=start, period_end=end,
                dimensions={"recipient": receiver},
                value=near_amount(raw), bound_kind="exact", quality_status="verified",
                quality={**quality, **note, "recipient": receiver}))
    return records


@exact_arithmetic
def formula_treasury_payout_count_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    require_daily_coverage(inputs)
    amounts, counts, payouts = _payout_views(inputs)
    quality = _payout_quality(payouts)
    definition = metric_registry.definition_by_metric_id_version(
        "treasury_payout_count", 1)
    records: list[dict] = []
    for start, end in _shape_periods(inputs, shape):
        day = _day_of((start, end))
        count = counts.get(day)
        if count is None:
            count, note = 0, {
                "verified_zero": "the extract covers this day and holds no matched "
                                 "payout withdrawal; zero payouts is proven for the "
                                 "matched definition"}
        else:
            note = {}
        records.append(observation_record(
            definition, period_start=start, period_end=end, dimensions={},
            value=Decimal(count), bound_kind="exact", quality_status="verified",
            quality={**quality, **note}))
    return records


@exact_arithmetic
def formula_near_price_usd_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    """Saved price points per day and basis; only defined on the daily grid."""
    if shape != "daily":
        return []
    prices = price_series(inputs)
    definition = metric_registry.definition_by_metric_id("near_price_usd")
    records: list[dict] = []
    for start, end in _shape_periods(inputs, shape):
        day = _day_of((start, end))
        for basis in PRICE_BASES:
            value = prices.by_day.get((day, basis))
            dimensions = {"price_basis": basis}
            if value is None:
                records.append(observation_record(
                    definition, period_start=start, period_end=end, dimensions=dimensions,
                    value=None, bound_kind=None, quality_status="missing",
                    quality={"reason": f"no saved NEAR/USD point at "
                                       f"{canonical_timestamp(point_instant(day, basis))} "
                                       f"(basis {basis}); no forward fill"}))
                continue
            records.append(observation_record(
                definition, period_start=start, period_end=end, dimensions=dimensions,
                value=value, bound_kind="estimate", quality_status="verified",
                source_record_ref=f"SRC-PRICE@{canonical_timestamp(point_instant(day, basis))}",
                quality={"price_instant": canonical_timestamp(point_instant(day, basis)),
                         "basis": basis}))
    return records


@exact_arithmetic
def formula_estimated_purchase_usd_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    """Daily or window purchases valued at the saved price of one basis.

    A missing price makes the period missing (daily) or the window sum
    unavailable with the missing dates listed - never zero, never filled.
    """
    prices = price_series(inputs)
    flows = purchases_by_day(inputs)
    definition = metric_registry.definition_by_metric_id("estimated_purchase_usd")
    records: list[dict] = []
    for start, end in _shape_periods(inputs, shape):
        for basis in PRICE_BASES:
            dimensions = {"price_basis": basis}
            missing_days: list[dt.date] = []
            total = Decimal(0)
            cursor = start.date()
            while cursor < end.date():
                price = prices.by_day.get((cursor, basis))
                if price is None:
                    missing_days.append(cursor)
                else:
                    total += COMPUTE_CONTEXT.multiply(
                        near_amount(flows.by_day.get(cursor, Decimal(0))), price)
                cursor += dt.timedelta(days=1)
            if missing_days:
                if end - start == dt.timedelta(days=1):
                    records.append(observation_record(
                        definition, period_start=start, period_end=end, dimensions=dimensions,
                        value=None, bound_kind=None, quality_status="missing",
                        quality={"reason": f"no saved NEAR/USD price at "
                                           f"{canonical_timestamp(point_instant(start.date(), basis))} "
                                           f"(basis {basis}); the USD value is missing, "
                                           "not zero"}))
                else:
                    records.append(observation_record(
                        definition, period_start=start, period_end=end, dimensions=dimensions,
                        value=None, bound_kind=None, quality_status="unavailable",
                        quality={"reason": "the period USD estimate requires a price for "
                                           f"every day; {len(missing_days)} day(s) lack a "
                                           f"saved point (basis {basis})",
                                 "missing_days": [day.isoformat() for day in missing_days[:20]]}))
                continue
            records.append(observation_record(
                definition, period_start=start, period_end=end, dimensions=dimensions,
                value=total, bound_kind="estimate", quality_status="verified",
                quality={"price_basis": basis, "exact_value": decimal_string(total),
                         "rounding": "stored at the NUMERIC(78,30) scale; the exact value "
                                     "is preserved here and in the manifest artifact"}))
    return records


@exact_arithmetic
def formula_provider_intents_volume_usd_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    if shape != "daily":
        return []
    return _provider_day_records(inputs, _shape_periods(inputs, shape),
                                 "provider_intents_volume_usd")


@exact_arithmetic
def formula_provider_gross_fees_usd_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    if shape != "daily":
        return []
    return _provider_day_records(inputs, _shape_periods(inputs, shape),
                                 "provider_gross_fees_usd")


def _provider_day_records(inputs: MetricInputs, periods, metric_id: str) -> list[dict]:
    series = provider_series(inputs)
    definition = metric_registry.definition_by_metric_id(metric_id)
    records: list[dict] = []
    for start, end in periods:
        day = _day_of((start, end))
        for source in PROVIDER_SOURCES:
            reported = series.day(source, day)
            dimensions = {"source": source}
            if reported is None:
                records.append(observation_record(
                    definition, period_start=start, period_end=end, dimensions=dimensions,
                    value=None, bound_kind=None, quality_status="missing",
                    quality={"reason": f"no saved {source} report for this day; missing "
                                       "is never zero and providers are never summed"}))
                continue
            value = (reported.volume_usd if metric_id == "provider_intents_volume_usd"
                     else reported.gross_fees_usd)
            records.append(observation_record(
                definition, period_start=start, period_end=end, dimensions=dimensions,
                value=value, bound_kind="estimate", quality_status="verified",
                quality={"source": source,
                         "revision_policy": "a provider revision is a new dataset version, "
                                            "never an overwrite"}))
    return records


@exact_arithmetic
def effective_fee_bps(volume_usd: Decimal, gross_fees_usd: Decimal) -> Decimal | None:
    """10,000 x fees / volume as a ratio of sums; a non-positive denominator
    returns None (the caller emits an unavailable observation)."""
    if volume_usd <= 0:
        return None
    return COMPUTE_CONTEXT.divide(COMPUTE_CONTEXT.multiply(Decimal(10000), gross_fees_usd),
                                  volume_usd)


@dataclass(frozen=True)
class PurchaseEstimate:
    """Exact USD valuation of a purchase flow over one span and basis."""

    by_day: dict
    missing_days: tuple
    window_total: Decimal | None


@exact_arithmetic
def estimate_purchase_usd(purchases: DailyFlows, prices: PriceSeries, *, basis: str,
                          window_start: dt.date,
                          window_end_exclusive: dt.date) -> PurchaseEstimate:
    """Exact range valuation used for reconciliations and range queries.

    The daily product is the exact Decimal product; a missing price makes the
    day missing and the span total unavailable - never zero, never filled.
    """
    if basis not in PRICE_BASES:
        raise MetricComputationError(f"unknown price basis {basis!r}")
    by_day: dict[dt.date, Decimal] = {}
    missing: list[dt.date] = []
    total = Decimal(0)
    day = window_start
    while day < window_end_exclusive:
        price = prices.by_day.get((day, basis))
        if price is None:
            missing.append(day)
        else:
            product = COMPUTE_CONTEXT.multiply(near_amount(purchases.by_day.get(day, Decimal(0))),
                                               price)
            by_day[day] = product
            total += product
        day += dt.timedelta(days=1)
    return PurchaseEstimate(by_day=by_day, missing_days=tuple(missing),
                            window_total=None if missing else total)


@exact_arithmetic
def _fee_bps_for_period(series: ProviderSeries, source: str, start: dt.datetime,
                        end: dt.datetime) -> tuple[Decimal | None, dict]:
    """Ratio of sums over one period for one source (never averaged dailies)."""
    volume = Decimal(0)
    fees = Decimal(0)
    missing_days: list[dt.date] = []
    day = start.date()
    while day < end.date():
        reported = series.day(source, day)
        if reported is None:
            missing_days.append(day)
        else:
            volume += reported.volume_usd
            fees += reported.gross_fees_usd
        day += dt.timedelta(days=1)
    if missing_days:
        return None, {"reason": f"the ratio requires a complete {source} series; "
                                f"{len(missing_days)} day(s) are missing",
                      "missing_days": [day.isoformat() for day in missing_days[:20]]}, "missing"
    ratio = effective_fee_bps(volume, fees)
    if ratio is None:
        return None, {"reason": f"zero or negative {source} volume denominator over the "
                                "period; the ratio is unavailable, not zero",
                      "volume_usd": decimal_string(volume)}, "unavailable"
    return ratio, {"source": source, "exact_value": decimal_string(ratio),
                   "rounding": "stored at the NUMERIC(78,30) scale",
                   "method": "ratio of sums over the period"}, "verified"


@exact_arithmetic
def formula_effective_gross_fee_bps_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    """Daily or window fee ratio per source (ratio of sums, never averaged)."""
    series = provider_series(inputs)
    definition = metric_registry.definition_by_metric_id("effective_gross_fee_bps")
    records: list[dict] = []
    for start, end in _shape_periods(inputs, shape):
        for source in PROVIDER_SOURCES:
            ratio, quality, status = _fee_bps_for_period(series, source, start, end)
            records.append(observation_record(
                definition, period_start=start, period_end=end,
                dimensions={"source": source}, value=ratio,
                bound_kind=None if ratio is None else "estimate",
                quality_status=status,
                quality=quality))
    return records


@exact_arithmetic
def formula_total_supply_near_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    if shape != "windows":
        return []
    definition = metric_registry.definition_by_metric_id("total_supply_near")
    records: list[dict] = []
    for boundary in inputs.supply_boundaries:
        start, end = day_period(boundary.date)
        records.append(observation_record(
            definition, period_start=start, period_end=end, dimensions={},
            value=boundary.supply_near, bound_kind="exact", quality_status="verified",
            source_record_ref=f"block {boundary.block_height} {boundary.block_hash}"[:200],
            quality={"block_height": boundary.block_height,
                     "block_hash": boundary.block_hash,
                     "block_timestamp_utc": _iso_from_ns(boundary.timestamp_ns),
                     "timestamp_ns": boundary.timestamp_ns,
                     "kind": "stock at a pinned boundary block"}))
    return records


@exact_arithmetic
def formula_net_supply_change_near_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    if shape != "windows":
        return []
    return _supply_window_records(inputs, "net_supply_change_near")


@exact_arithmetic
def formula_issuance_lower_bound_near_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    if shape != "windows":
        return []
    return _supply_window_records(inputs, "issuance_lower_bound_near")


@exact_arithmetic
def formula_burns_lower_bound_near_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    if shape != "windows":
        return []
    return _supply_window_records(inputs, "burns_lower_bound_near")


@exact_arithmetic
def formula_purchases_to_net_supply_pct_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    if shape != "windows":
        return []
    return _supply_window_records(inputs, "purchases_to_net_supply_pct")


@exact_arithmetic
def formula_purchases_to_issuance_upper_pct_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    if shape != "windows":
        return []
    return _supply_window_records(inputs, "purchases_to_issuance_upper_pct")


@exact_arithmetic
def formula_fee_funded_buybacks_near_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    if shape != "windows":
        return []
    definition = metric_registry.definition_by_metric_id("fee_funded_buybacks_near")
    records: list[dict] = []
    for start, end in _shape_periods(inputs, shape):
        records.append(gated_null_record(
            definition, period_start=start, period_end=end,
            reason="fee attribution is unresolved: pooled funds cannot be traced into "
                   "specific payouts (OQ-08); this metric stays null instead of "
                   "borrowing gross fees, payouts or the narrow provenance equivalent"))
    return records


@exact_arithmetic
def formula_protocol_revenue_usd_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    definition = metric_registry.definition_by_metric_id("protocol_revenue_usd")
    records: list[dict] = []
    for start, end in _shape_periods(inputs, shape):
        records.append(gated_null_record(
            definition, period_start=start, period_end=end,
            reason="no verified daily economically attributable protocol revenue ledger "
                   "exists (OQ-01); gross provider fees, volume and treasury payouts are "
                   "not revenue and are never substituted"))
    return records


@exact_arithmetic
def formula_protocol_capture_rate_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    definition = metric_registry.definition_by_metric_id("protocol_capture_rate")
    records: list[dict] = []
    for start, end in _shape_periods(inputs, shape):
        records.append(gated_null_record(
            definition, period_start=start, period_end=end,
            reason="the revenue numerator is gated (OQ-01) and the compatible fee "
                   "denominator is unresolved (OQ-11); the capture rate stays null "
                   "instead of a clipped or substituted value"))
    return records


@exact_arithmetic
def formula_treasury_balance_near_v1(inputs: MetricInputs, *, shape: str) -> list[dict]:
    if shape != "windows":
        return []
    definition = metric_registry.definition_by_metric_id("treasury_balance_near")
    snapshot = inputs.treasury_balance
    if snapshot is None:
        return []
    start, end = day_period(snapshot.as_of.date())
    return [observation_record(
        definition, period_start=start, period_end=end, dimensions={},
        value=snapshot.total_near, bound_kind="exact", quality_status="verified",
        source_record_ref=f"block {snapshot.block_height} {snapshot.block_hash}"[:200],
        quality={"block_height": snapshot.block_height, "block_hash": snapshot.block_hash,
                 "pinned_at": canonical_timestamp(snapshot.as_of),
                 "accounts": {account: decimal_string(amount)
                              for account, amount in snapshot.accounts},
                 "interpretation": "balance stock, not cumulative revenue and not "
                                   "permanently removed supply"})]


@exact_arithmetic
def _net_and_bounds(inputs: MetricInputs, supply_window: SupplyWindow,
                    boundaries: dict, purchases_total: Decimal) -> tuple:
    """Per-window computations shared by the supply window formulas."""
    opening = boundaries.get(supply_window.opening_date)
    closing = boundaries.get(supply_window.closing_date)
    if opening is None or closing is None:
        raise MetricComputationError(
            f"supply window {supply_window.start}..{supply_window.end_exclusive} "
            "references an unknown boundary")
    net_change = COMPUTE_CONTEXT.subtract(closing.supply_near, opening.supply_near)
    issuance_lower = COMPUTE_CONTEXT.subtract(
        COMPUTE_CONTEXT.add(supply_window.positive_supply_changes_near,
                            supply_window.verified_simultaneous_burn_near),
        SUPPLY_FLOAT_TOLERANCE_NEAR)
    burns_lower = COMPUTE_CONTEXT.subtract(
        COMPUTE_CONTEXT.add(supply_window.negative_supply_changes_near,
                            supply_window.verified_simultaneous_burn_near),
        SUPPLY_FLOAT_TOLERANCE_NEAR)
    if issuance_lower < 0 or burns_lower < 0:
        raise MetricComputationError(
            "conservative supply bounds must not go negative; check the tolerance inputs")
    window_quality = {
        "opening": {"date": opening.date.isoformat(), "block_height": opening.block_height,
                    "block_hash": opening.block_hash},
        "closing": {"date": closing.date.isoformat(), "block_height": closing.block_height,
                    "block_hash": closing.block_hash},
        "observed_purchases_near": decimal_string(near_amount(purchases_total)),
    }
    net_record = observation_record(
        metric_registry.definition_by_metric_id("net_supply_change_near"),
        period_start=window_period(supply_window.start, supply_window.end_exclusive)[0],
        period_end=window_period(supply_window.start, supply_window.end_exclusive)[1],
        dimensions={}, value=net_change, bound_kind="exact", quality_status="verified",
        quality={**window_quality,
                 "purchase_policy": "purchases are reported alongside and are never "
                                    "deducted from the measured supply change"})
    bounds_quality = {
        **window_quality,
        "positive_supply_changes_near": decimal_string(supply_window.positive_supply_changes_near),
        "negative_supply_changes_near": decimal_string(supply_window.negative_supply_changes_near),
        "verified_simultaneous_burn_near": decimal_string(
            supply_window.verified_simultaneous_burn_near),
        "float64_tolerance_near": decimal_string(SUPPLY_FLOAT_TOLERANCE_NEAR),
        "mint_headers_verified": supply_window.mint_headers_verified,
        "mint_headers_target": supply_window.mint_headers_target,
        "gross_issuance_and_burn_complete": supply_window.gross_issuance_and_burn_complete,
    }
    issuance_record = observation_record(
        metric_registry.definition_by_metric_id("issuance_lower_bound_near"),
        period_start=window_period(supply_window.start, supply_window.end_exclusive)[0],
        period_end=window_period(supply_window.start, supply_window.end_exclusive)[1],
        dimensions={}, value=issuance_lower, bound_kind="lower", quality_status="verified",
        quality={**bounds_quality,
                 "interpretation": "gross issuance is at least this value; the unaudited "
                                   "simultaneous offset is unknown and never assumed zero"})
    burns_record = observation_record(
        metric_registry.definition_by_metric_id("burns_lower_bound_near"),
        period_start=window_period(supply_window.start, supply_window.end_exclusive)[0],
        period_end=window_period(supply_window.start, supply_window.end_exclusive)[1],
        dimensions={}, value=burns_lower, bound_kind="lower", quality_status="verified",
        quality={**bounds_quality,
                 "interpretation": "gross burn is at least this value; purchases, staking "
                                   "and treasury movements are not burns"})
    start, end = window_period(supply_window.start, supply_window.end_exclusive)
    purchases_near = COMPUTE_CONTEXT.divide(purchases_total, YOCTO_PER_NEAR)
    if net_change > 0:
        ratio = COMPUTE_CONTEXT.divide(COMPUTE_CONTEXT.multiply(Decimal(100), purchases_near),
                                       net_change)
        net_ratio_record = observation_record(
            metric_registry.definition_by_metric_id("purchases_to_net_supply_pct"),
            period_start=start, period_end=end, dimensions={}, value=ratio,
            bound_kind="exact", quality_status="verified",
            quality={"purchases_near": decimal_string(near_amount(purchases_total)),
                     "net_supply_change_near": decimal_string(net_change),
                     "exact_value": decimal_string(ratio),
                     "rounding": "stored at the NUMERIC(78,30) scale",
                     "interpretation": "scale context, not a deflation or capture rate"})
    else:
        net_ratio_record = observation_record(
            metric_registry.definition_by_metric_id("purchases_to_net_supply_pct"),
            period_start=start, period_end=end, dimensions={}, value=None, bound_kind=None,
            quality_status="unavailable",
            quality={"reason": "net supply change is non-positive; a purchases share of "
                               "a non-positive increase is undefined",
                     "net_supply_change_near": decimal_string(net_change)})
    if issuance_lower > 0:
        ratio = COMPUTE_CONTEXT.divide(COMPUTE_CONTEXT.multiply(Decimal(100), purchases_near),
                                       issuance_lower)
        issuance_ratio_record = observation_record(
            metric_registry.definition_by_metric_id("purchases_to_issuance_upper_pct"),
            period_start=start, period_end=end, dimensions={}, value=ratio,
            bound_kind="upper", quality_status="verified",
            quality={"purchases_near": decimal_string(near_amount(purchases_total)),
                     "issuance_lower_bound_near": decimal_string(issuance_lower),
                     "exact_value": decimal_string(ratio),
                     "rounding": "stored at the NUMERIC(78,30) scale",
                     "direction": "upper bound: the denominator is a lower bound of gross "
                                  "issuance, so the true share is at most this value"})
    else:
        issuance_ratio_record = observation_record(
            metric_registry.definition_by_metric_id("purchases_to_issuance_upper_pct"),
            period_start=start, period_end=end, dimensions={}, value=None, bound_kind=None,
            quality_status="unavailable",
            quality={"reason": "the issuance lower bound is non-positive; no upper bound "
                               "can be derived from it",
                     "issuance_lower_bound_near": decimal_string(issuance_lower)})
    return net_record, issuance_record, burns_record, net_ratio_record, issuance_ratio_record


def active_supply_window_periods(inputs: MetricInputs) -> set:
    """The half-open periods of the atomic (non-total) supply windows."""
    return {window_period(window.start, window.end_exclusive)
            for window in inputs.supply_windows if not window.is_total}


def _supply_window_records(inputs: MetricInputs, metric_id: str) -> list[dict]:
    """Run the window builder per atomic supply window for one metric."""
    require_daily_coverage(inputs)
    boundaries: dict = {boundary.date: boundary for boundary in inputs.supply_boundaries}
    metric_index = {
        "net_supply_change_near": 0, "issuance_lower_bound_near": 1,
        "burns_lower_bound_near": 2, "purchases_to_net_supply_pct": 3,
        "purchases_to_issuance_upper_pct": 4,
    }[metric_id]
    records: list[dict] = []
    for supply_window in inputs.supply_windows:
        if supply_window.is_total:
            continue
        purchases_total = _purchases_in_span(
            inputs, *window_period(supply_window.start, supply_window.end_exclusive))
        built = _net_and_bounds(inputs, supply_window, boundaries, purchases_total)
        records.append(built[metric_index])
    return records


@exact_arithmetic
def _purchases_in_span(inputs: MetricInputs, start: dt.datetime, end: dt.datetime) -> Decimal:
    """Sum of daily purchases over a span (verified zeros fill gaps)."""
    flows = purchases_by_day(inputs)
    total = Decimal(0)
    day = start.date()
    while day < end.date():
        total += flows.by_day.get(day, Decimal(0))
        day += dt.timedelta(days=1)
    return total


def _iso_from_ns(timestamp_ns: str) -> str:
    """Exact nanosecond epoch -> ISO-8601 UTC (integer arithmetic only)."""
    value = int(timestamp_ns)
    seconds, nanos = divmod(value, 1_000_000_000)
    instant = dt.datetime.fromtimestamp(seconds, tz=dt.timezone.utc)
    return f"{instant.strftime('%Y-%m-%dT%H:%M:%S')}.{nanos:09d}Z"


FORMULA_REGISTRY: dict[str, Callable] = {
    "observed_near_purchases_v1": formula_observed_near_purchases_v1,
    "conversion_count_v1": formula_conversion_count_v1,
    "treasury_payouts_near_v1": formula_treasury_payouts_near_v1,
    "treasury_payouts_near_v2": formula_treasury_payouts_near_v2,
    "treasury_payout_count_v1": formula_treasury_payout_count_v1,
    "near_price_usd_v1": formula_near_price_usd_v1,
    "estimated_purchase_usd_v1": formula_estimated_purchase_usd_v1,
    "provider_intents_volume_usd_v1": formula_provider_intents_volume_usd_v1,
    "provider_gross_fees_usd_v1": formula_provider_gross_fees_usd_v1,
    "effective_gross_fee_bps_v1": formula_effective_gross_fee_bps_v1,
    "total_supply_near_v1": formula_total_supply_near_v1,
    "net_supply_change_near_v1": formula_net_supply_change_near_v1,
    "issuance_lower_bound_near_v1": formula_issuance_lower_bound_near_v1,
    "burns_lower_bound_near_v1": formula_burns_lower_bound_near_v1,
    "purchases_to_net_supply_pct_v1": formula_purchases_to_net_supply_pct_v1,
    "purchases_to_issuance_upper_pct_v1": formula_purchases_to_issuance_upper_pct_v1,
    "treasury_balance_near_v1": formula_treasury_balance_near_v1,
    "protocol_revenue_usd_v1": formula_protocol_revenue_usd_v1,
    "protocol_capture_rate_v1": formula_protocol_capture_rate_v1,
    "fee_funded_buybacks_near_v1": formula_fee_funded_buybacks_near_v1,
}
