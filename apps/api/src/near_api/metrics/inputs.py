"""Canonical input bundles for NI-029 metric computations.

These dataclasses are the typed boundary between the saved research
aggregates (loaded by :mod:`near_api.metrics.loaders`) and the exact
computations (:mod:`near_api.metrics.compute`). Everything monetary is an
exact ``Decimal`` (floats never reach this layer); every timestamp is an
aware UTC datetime; every amount keeps its raw precision.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from near_api.metrics.events import ConversionDay, NativeTransfer, WithdrawalEvent


@dataclass(frozen=True)
class CoverageDay:
    """One day's extract coverage proof (the basis for verified zeros)."""

    block_date: dt.date
    intents_outcomes: int
    successful_intents_outcomes: int
    first_timestamp: dt.datetime
    last_timestamp: dt.datetime


@dataclass(frozen=True)
class QualityDay:
    """One day's extract quality counters (JSON parse errors must be zero)."""

    block_date: dt.date
    event_json_logs: int
    json_parse_errors: int


@dataclass(frozen=True)
class FlowRecords:
    """Canonical event and aggregate records of the longitudinal extract."""

    conversions: tuple[ConversionDay, ...]
    native_transfers: tuple[NativeTransfer, ...]
    withdrawals: tuple[WithdrawalEvent, ...]
    coverage: tuple[CoverageDay, ...]
    quality: tuple[QualityDay, ...]


@dataclass(frozen=True)
class DailyFlowRow:
    """One saved daily flow row (price/provider inputs + reconciliation)."""

    date: dt.date
    buy_near: Decimal
    buy_events: int
    payout_near: Decimal
    price_start_utc: Decimal | None
    price_end_utc: Decimal | None
    buy_usd_start: Decimal | None
    buy_usd_end: Decimal | None
    payout_usd_start: Decimal | None
    payout_usd_end: Decimal | None
    volume_usd: Decimal | None
    gross_fees_usd: Decimal | None
    dashboard_volume_usd: Decimal | None
    dashboard_gross_fees_usd: Decimal | None


@dataclass(frozen=True)
class PriceSeries:
    """Saved provider price points per UTC day and basis ("start"/"end")."""

    by_day: dict  # (date, basis) -> Decimal


@dataclass(frozen=True)
class ProviderDay:
    """One provider's reported volume and gross fees for one UTC day."""

    volume_usd: Decimal
    gross_fees_usd: Decimal


@dataclass(frozen=True)
class ProviderSeries:
    """Reported provider series per source and day; absence means missing."""

    by_source: dict  # source_id -> {date -> ProviderDay}

    def day(self, source: str, day: dt.date) -> ProviderDay | None:
        return self.by_source.get(source, {}).get(day)


@dataclass(frozen=True)
class SupplyBoundary:
    """One pinned boundary stock value (exact integer FastNear rows)."""

    date: dt.date
    block_height: int
    block_hash: str
    timestamp_ns: str
    supply_near: Decimal


@dataclass(frozen=True)
class SupplyWindow:
    """One boundary window with the documented conservative gross bounds."""

    start: dt.date
    end_exclusive: dt.date
    opening_date: dt.date
    closing_date: dt.date
    positive_supply_changes_near: Decimal
    negative_supply_changes_near: Decimal
    verified_simultaneous_burn_near: Decimal
    mint_headers_verified: int
    mint_headers_target: int
    gross_issuance_and_burn_complete: bool
    is_total: bool = False


@dataclass(frozen=True)
class TreasuryBalance:
    """Pinned treasury stock snapshot."""

    as_of: dt.datetime
    block_height: int
    block_hash: str
    total_near: Decimal
    accounts: tuple  # (account_id, Decimal) pairs


@dataclass(frozen=True)
class MetricInputs:
    """The complete canonical input bundle for one computation run."""

    window_start: dt.date
    window_end_exclusive: dt.date
    flows: FlowRecords
    daily_flows: tuple[DailyFlowRow, ...]
    prices: PriceSeries
    providers: ProviderSeries
    supply_boundaries: tuple[SupplyBoundary, ...] = ()
    supply_windows: tuple[SupplyWindow, ...] = ()
    treasury_balance: TreasuryBalance | None = None

    def __post_init__(self):
        if self.window_end_exclusive <= self.window_start:
            raise ValueError("the metric window is a non-empty half-open interval")
