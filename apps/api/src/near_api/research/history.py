"""NI-083 exact descriptive summaries; canonical approved chart views only.

No API route reads local files. Operator preparation is separate in archive.py.
Gross fees and turnover are source-qualified; the ratio is not protocol capture.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field
from sqlalchemy import Connection

from near_api.datasets import delivery
from near_api.datasets.canonical import decimal_string
from near_api.metrics.compute import observation_value
from near_api.metrics.events import exact_arithmetic
from near_api.schemas.common import ContractModel, DecimalString
from near_api.schemas.delivery import ChartViewResponse


class ResearchPeriodSummary(ContractModel):
    start: date
    end: date
    expected_days: int = Field(ge=1, le=730)
    volume_days: int = Field(ge=0)
    fee_days: int = Field(ge=0)
    matched_days: int = Field(ge=0)
    zero_fee_days: int = Field(ge=0)
    volume_usd: DecimalString | None
    gross_fees_usd: DecimalString | None
    matched_volume_usd: DecimalString | None
    matched_gross_fees_usd: DecimalString | None
    effective_gross_fee_bps: DecimalString | None
    complete: bool


class ResearchHistoryResponse(ContractModel):
    volume: ChartViewResponse
    fees: ChartViewResponse
    purchases: ChartViewResponse | None
    summary: ResearchPeriodSummary
    monthly: tuple[ResearchPeriodSummary, ...]
    quarterly: tuple[ResearchPeriodSummary, ...]
    limitations: tuple[str, ...]


def _point_values(view: ChartViewResponse) -> dict[date, Decimal]:
    if len(view.series) != 1:
        raise delivery.DeliveryReferenceInvalid("Research history requires one qualified source")
    return {point.start.date(): Decimal(point.value)
            for point in view.series[0].points if point.value is not None}


@exact_arithmetic
def summarize(volume: dict[date, Decimal], fees: dict[date, Decimal],
              start: date, end: date) -> ResearchPeriodSummary:
    """Observed subtotals with explicit coverage; weighted matched-day fee rate.

    No missing day enters a denominator. Source-reported zero fees remain zeros.
    ``complete`` requires both series on every calendar day of this bucket.
    """
    if not 0 < (end - start).days <= 730:
        raise delivery.DeliveryInvalidFilter("Research range must contain 1–730 days")
    v = {day: value for day, value in volume.items() if start <= day < end}
    f = {day: value for day, value in fees.items() if start <= day < end}
    common = v.keys() & f.keys()
    matched_v = sum((v[day] for day in common), Decimal(0)) if common else None
    matched_f = sum((f[day] for day in common), Decimal(0)) if common else None
    rate = matched_f / matched_v * Decimal(10000) if matched_v else None
    expected = (end - start).days
    return ResearchPeriodSummary(
        start=start, end=end, expected_days=expected, volume_days=len(v), fee_days=len(f),
        matched_days=len(common), zero_fee_days=sum(value == 0 for value in f.values()),
        volume_usd=decimal_string(sum(v.values(), Decimal(0))) if v else None,
        gross_fees_usd=decimal_string(sum(f.values(), Decimal(0))) if f else None,
        matched_volume_usd=decimal_string(matched_v) if matched_v is not None else None,
        matched_gross_fees_usd=decimal_string(matched_f) if matched_f is not None else None,
        effective_gross_fee_bps=observation_value(rate) if rate is not None else None,
        complete=len(v) == len(f) == expected)


def calendar_summaries(volume: dict[date, Decimal], fees: dict[date, Decimal],
                       start: date, end: date, *, months: int) -> tuple[ResearchPeriodSummary, ...]:
    """Calendar buckets keep full bounds, so clipped edge buckets stay partial."""
    month = ((start.month - 1) // months) * months + 1
    cursor = date(start.year, month, 1)
    results = []
    while cursor < end:
        month_index = cursor.year * 12 + cursor.month - 1 + months
        following = date(month_index // 12, month_index % 12 + 1, 1)
        # Input dictionaries are already selection-clipped: no accidental
        # inclusion of data outside the user's requested selection.
        selected_v = {d: v for d, v in volume.items() if start <= d < end}
        selected_f = {d: v for d, v in fees.items() if start <= d < end}
        results.append(summarize(selected_v, selected_f, cursor, following))
        cursor = following
    return tuple(results)


def build_history(connection: Connection, *, source: str = "SRC-LLAMA",
                  start: date | None = None, end: date | None = None,
                  dataset_version: UUID | None = None) -> ResearchHistoryResponse:
    if source not in {"SRC-LLAMA", "SRC-DASHBOARD"}:
        raise delivery.DeliveryInvalidFilter("Unsupported research source")
    if (start is None) != (end is None):
        raise delivery.DeliveryInvalidFilter("Supply both start and end")
    volume_def = delivery.load_chart_definition(connection, "intents-volume", 2)
    fee_def = delivery.load_chart_definition(connection, "gross-fees", 2)
    required = (*volume_def.metric_definition_ids, *fee_def.metric_definition_ids)
    version = dataset_version or delivery.resolve_latest_version(connection, required)
    row, content = delivery.load_approved_dataset(connection, version)
    dataset = delivery.dataset_response(row, content)
    selection_start, selection_end = start or dataset.start, end or dataset.end
    if not 0 < (selection_end - selection_start).days <= 730:
        raise delivery.DeliveryInvalidFilter("Research range must contain 1–730 days")
    kwargs = dict(start=selection_start, end=selection_end, dataset_version=version,
                  filters={"source": source})
    volume = delivery.build_chart_view(connection, chart_id="intents-volume", version=2, **kwargs)
    fees = delivery.build_chart_view(connection, chart_id="gross-fees", version=2, **kwargs)
    v, f = _point_values(volume), _point_values(fees)
    purchases = None
    try:
        purchase_def = delivery.load_chart_definition(connection, "observed-conversions", 1)
        purchase_version = delivery.resolve_latest_version(connection, purchase_def.metric_definition_ids)
        purchase_row, purchase_content = delivery.load_approved_dataset(connection, purchase_version)
        purchase_dataset = delivery.dataset_response(purchase_row, purchase_content)
        # A longer provider window never changes the historical cohort's bounds.
        purchases = delivery.build_chart_view(
            connection, chart_id="observed-conversions", version=1,
            start=purchase_dataset.start, end=purchase_dataset.end,
            dataset_version=purchase_version, filters={})
    except (delivery.DeliveryDataNotReady, delivery.DeliveryNotFound):
        pass
    return ResearchHistoryResponse(
        volume=volume, fees=fees, purchases=purchases,
        summary=summarize(v, f, selection_start, selection_end),
        monthly=calendar_summaries(v, f, selection_start, selection_end, months=1),
        quarterly=calendar_summaries(v, f, selection_start, selection_end, months=3),
        limitations=(
            "Gross fees are not attributable protocol revenue or net profit.",
            "Effective fee rate is summed gross fees / summed volume on matched dates, in basis points; not a capture rate.",
            "Partial calendar periods are observed subtotals, not comparable full-month or full-quarter totals.",
            "Source-reported zero fees are retained; absent dates remain missing.",
            "Provider snapshots share Dune lineage; definitions and revisions differ. Do not splice sources.",
            "The observed purchases cohort remains limited to its own coverage; purchases are not burns.",
            "Saved historical observations do not establish causality, durable retention or token valuation.",
        ))
