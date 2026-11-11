"""Registered metric definitions for NI-029 (immutable, versioned).

One :class:`MetricDefinition` per catalog concept (docs/METRIC_CATALOG.md).
The definition UUID is ``uuid5`` over ``"<metric_id>:v<version>"`` in a fixed
registry namespace, so the same definition always carries the same identity
across code, manifests and database rows. Definitions are immutable: a
changed meaning appends ``version 2`` and never rewrites version 1.

``register_definitions`` persists the current registry into
``app.metric_definitions`` (migration 0005) as the unprivileged
``near_operator``. It is idempotent and verifies stored content: an existing
``(metric_id, version)`` row whose payload diverges from the code registry is
a registry error — the row may only be superseded by a new version, never
edited. A definition whose ``formula_key`` does not resolve to a registered
computation in :mod:`near_api.metrics.compute` fails ``validate_registry``,
because emitting observations for an unimplemented formula would be a
fabrication.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Callable, Mapping
from uuid import UUID

from sqlalchemy import text

# Deterministic identity namespace for the NI-029 metric registry
# (uuid5 over the name string below; do not regenerate).
REGISTRY_NAMESPACE = uuid.UUID("2f6d1f0e-3f2a-5c4b-9a1d-4c7e8b0d2a31")

METRIC_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,79}$")

# Availability codes follow docs/METRIC_CATALOG.md:
# A saved observed data; P provider-reported, source-qualified and revisable;
# B bound/estimate only; G gated/unavailable until source/definition verified.
AVAILABILITY_CODES = ("A", "P", "B", "G")


class MetricRegistryError(RuntimeError):
    """The registry is internally inconsistent or diverges from stored rows."""


@dataclass(frozen=True)
class MetricDefinition:
    """One immutable metric definition version."""

    metric_id: str
    version: int
    name: str
    unit: str
    frequency: str
    economic_scope: str
    formula_key: str
    source_id: str | None
    definition: dict = field(default_factory=dict)
    quality_rules: dict = field(default_factory=dict)

    @property
    def id(self) -> UUID:
        payload = f"{self.metric_id}:v{self.version}"
        return uuid.uuid5(REGISTRY_NAMESPACE, payload)

    def row(self) -> dict:
        """Column payload for app.metric_definitions (canonical JSON values)."""
        return {
            "id": self.id,
            "metric_id": self.metric_id,
            "version": self.version,
            "name": self.name,
            "unit": self.unit,
            "frequency": self.frequency,
            "economic_scope": self.economic_scope,
            "formula_key": self.formula_key,
            "source_id": self.source_id,
            "definition": self.definition,
            "quality_rules": self.quality_rules,
        }


def _definition(metric_id: str, *, version: int, name: str, unit: str, frequency: str,
                economic_scope: str, formula_key: str, source_id: str | None,
                availability: str, description: str, limitations: tuple[str, ...],
                quality_rules: dict) -> MetricDefinition:
    return MetricDefinition(
        metric_id=metric_id, version=version, name=name, unit=unit, frequency=frequency,
        economic_scope=economic_scope, formula_key=formula_key, source_id=source_id,
        definition={
            "availability": availability,
            "description": description,
            "limitations": list(limitations),
        },
        quality_rules=quality_rules,
    )


TreasuryAccounts = ("buybacks.multisignature.near", "fefundsadmin.sputnik-dao.near",
                    "1csfundsadmin.sputnik-dao.near")

DEFINITIONS: tuple[MetricDefinition, ...] = (
    _definition(
        "observed_near_purchases", version=1,
        name="Observed NEAR purchases (treasury-linked cohort)",
        unit="NEAR", frequency="daily", source_id="SRC-BQ",
        economic_scope="Successful wrap.near token_diff conversions of other assets into "
                       "NEAR by collector accounts observed paying the three named "
                       "intents treasuries in the saved 90-day cohort",
        formula_key="observed_near_purchases_v1", availability="A",
        description="Sum of positive wrap.near differences in successful token_diff events "
                    "with at least one negative other asset, aggregated from canonical "
                    "per-account daily records by exact yoctoNEAR Decimal sums.",
        limitations=(
            "Acquisitions within the observed pool, not all-market NEAR demand.",
            "Not proven fee-funded buybacks; purchases and payouts may be stages of the "
            "same funds and are never added together.",
            "Cohort is limited to accounts paying the three treasuries; buyers without "
            "such payouts are outside the measured population.",
        ),
        quality_rules={
            "duplicate_identity": "identical canonical records collapse once; conflicting "
                                  "payloads are a quarantine error",
            "invalid_wrap_amounts": "any record with invalid wrap amounts fails computation",
            "non_success_execution": "only successful execution can establish a conversion",
        },
    ),
    _definition(
        "conversion_count", version=1,
        name="Observed conversion event count (treasury-linked cohort)",
        unit="events", frequency="daily", source_id="SRC-BQ",
        economic_scope="Canonical events satisfying the observed_near_purchases definition",
        formula_key="conversion_count_v1", availability="A",
        description="Count of canonical buy events under the documented source key "
                    "(account + day + deduplicated intent hashes); not user swaps.",
        limitations=(
            "Event count is not a user or customer count; collector accounts aggregate "
            "many participants.",
        ),
        quality_rules={
            "duplicate_identity": "identical canonical records collapse once",
            "dedup_key": "account + intent/event identity deduplicated before counting",
        },
    ),
    _definition(
        "treasury_payouts_near", version=1,
        name="Treasury payouts from intents.near (three named wallets)",
        unit="NEAR", frequency="daily", source_id="SRC-BQ",
        economic_scope="Successful native TRANSFER receipts from intents.near to "
                       "buybacks.multisignature.near, fefundsadmin.sputnik-dao.near and "
                       "1csfundsadmin.sputnik-dao.near matched to DIP4 native_withdraw "
                       "events",
        formula_key="treasury_payouts_near_v1", availability="A",
        description="Sum of matched successful native transfer amounts (exact yoctoNEAR); "
                    "each withdrawal matches the unique candidate transfer with equal "
                    "receiver and amount within the documented 300 s tolerance and every "
                    "receipt action is used at most once.",
        limitations=(
            "Cash transfers out of the intents contract, not accrual revenue or profit.",
            "Internal treasury hops and inflows from other senders are excluded and "
            "reported separately in observation quality metadata.",
            "Amount-and-receiver matching within 300 s is not a full receipt-parent "
            "proof; the matcher version and tolerance are recorded.",
        ),
        quality_rules={
            "matcher": "amount + receiver + unique candidate within 300 s; single use",
            "internal_hops": "transfers between treasury accounts are excluded from payouts",
            "other_senders": "inflows from senders other than intents.near are excluded",
            "failed_transfers": "only SUCCESS_VALUE execution establishes a transfer",
            "unmatched": "an in-window withdrawal without exactly one candidate is an error",
        },
    ),
    _definition(
        "treasury_payout_count", version=1,
        name="Treasury payout count (matched receipt actions)",
        unit="payouts", frequency="daily", source_id="SRC-BQ",
        economic_scope="Distinct matched native transfer actions under the "
                       "treasury_payouts_near definition",
        formula_key="treasury_payout_count_v1", availability="A",
        description="Count of matched receipt actions, not transactions; each payout is "
                    "one matched (withdrawal, transfer) pair.",
        limitations=(
            "Receipt-action identity, not tx count or user count.",
        ),
        quality_rules={
            "single_use": "every matched receipt action is used at most once",
        },
    ),
    _definition(
        "treasury_payouts_near", version=2,
        name="Treasury payouts from intents.near per recipient",
        unit="NEAR", frequency="daily", source_id="SRC-BQ",
        economic_scope="Successful native TRANSFER receipts from intents.near to "
                       "buybacks.multisignature.near, fefundsadmin.sputnik-dao.near and "
                       "1csfundsadmin.sputnik-dao.near matched to DIP4 native_withdraw "
                       "events, one observation per recipient; "
                       "dimensions.recipient carries the verified receiver",
        formula_key="treasury_payouts_near_v2", availability="A",
        description="Per-recipient variant of the v1 aggregate definition: the same "
                    "matcher run, split by the verified transfer receiver into one "
                    "series per named treasury. The three named wallets are the "
                    "complete declared universe, so the per-recipient values must sum "
                    "to the v1 aggregate value for the same period; delivery enforces "
                    "the identity when the full universe is selected.",
        limitations=(
            "Cash transfers out of the intents contract, not accrual revenue or profit.",
            "Internal treasury hops and inflows from other senders are excluded and "
            "reported separately in observation quality metadata.",
            "The recipient dimension is the verified transfer receiver only; no "
            "integrator, customer or user classification exists in the source.",
        ),
        quality_rules={
            "matcher": "amount + receiver + unique candidate within 300 s; single use",
            "internal_hops": "transfers between treasury accounts are excluded from payouts",
            "other_senders": "inflows from senders other than intents.near are excluded",
            "failed_transfers": "only SUCCESS_VALUE execution establishes a transfer",
            "unmatched": "an in-window withdrawal without exactly one candidate is an error",
            "recipient_universe": "dimensions.recipient is exactly one of the three "
                                  "named treasuries; the per-recipient values sum to "
                                  "the v1 aggregate for the same period",
        },
    ),
    _definition(
        "near_price_usd", version=1,
        name="Saved NEAR/USD provider price point",
        unit="USD/NEAR", frequency="daily", source_id="SRC-PRICE",
        economic_scope="Saved provider NEAR/USD market data points at explicit UTC "
                       "timestamps; dimensions.price_basis selects the start-of-day "
                       "(00:00 UTC) baseline and the end-of-day (next 00:00 UTC) "
                       "alternative",
        formula_key="near_price_usd_v1", availability="P",
        description="The saved provider price exactly at the documented UTC instant; a "
                    "stock, not additive across periods.",
        limitations=(
            "No inferred fill and no intraday interpolation; a missing point stays "
            "missing and is never forward-filled or zeroed.",
            "Provider market data is revisable; the saved snapshot timestamp is retained.",
        ),
        quality_rules={
            "no_forward_fill": "a missing price point is a missing observation",
            "explicit_timestamp": "each point carries its exact UTC timestamp",
        },
    ),
    _definition(
        "estimated_purchase_usd", version=1,
        name="Estimated purchase value in USD (daily price basis)",
        unit="USD", frequency="daily", source_id="SRC-PRICE",
        economic_scope="Observed treasury-linked purchases valued at the saved daily "
                       "provider price; dimensions.price_basis selects the start-of-day "
                       "baseline or the end-of-day alternative",
        formula_key="estimated_purchase_usd_v1", availability="B",
        description="Daily purchases in NEAR multiplied by the saved price point of the "
                    "selected basis; period sums are sums of these daily estimates.",
        limitations=(
            "Valuation estimate, not execution consideration and not realized proceeds.",
            "A missing price makes that day's USD value missing (never zero) and makes "
            "the period aggregate unavailable.",
            "Values are stored at the NUMERIC(78,30) scale; the exact daily product "
            "string is preserved in the observation quality metadata and the hash-pinned "
            "manifest artifact.",
        ),
        quality_rules={
            "missing_price": "missing price -> missing USD value with a reason",
            "window_completeness": "a period sum requires a price for every day",
            "rounding": "explicit ROUND_HALF_EVEN to the 30-decimal storage scale; the "
                        "exact value is retained in quality metadata",
        },
    ),
    _definition(
        "provider_intents_volume_usd", version=1,
        name="Provider-reported Intents gross volume (source-qualified)",
        unit="USD", frequency="daily", source_id="SRC-LLAMA",
        economic_scope="Provider's reported daily gross cross-chain Intents turnover; "
                       "dimensions.source qualifies SRC-LLAMA and SRC-DASHBOARD variants",
        formula_key="provider_intents_volume_usd_v1", availability="P",
        description="The provider-reported daily gross turnover series retained exactly "
                    "as reported per qualified source.",
        limitations=(
            "Definitions and revisions differ between providers; there is no automatic "
            "dedup or reconciliation across sources.",
            "Never sum across sources; source disagreement is kept as parallel "
            "qualified observations.",
            "Both public adapters share Dune lineage, so agreement is not independent "
            "confirmation.",
        ),
        quality_rules={
            "source_qualified": "every observation carries its source dimension",
            "cross_source_sum": "forbidden",
        },
    ),
    _definition(
        "provider_gross_fees_usd", version=1,
        name="Provider-reported Intents gross fees (source-qualified)",
        unit="USD", frequency="daily", source_id="SRC-LLAMA",
        economic_scope="Provider's reported Intents protocol plus distribution gross fee "
                       "definition; dimensions.source qualifies SRC-LLAMA and "
                       "SRC-DASHBOARD variants",
        formula_key="provider_gross_fees_usd_v1", availability="P",
        description="The provider-reported daily gross fee series retained exactly as "
                    "reported per qualified source.",
        limitations=(
            "Not revenue retained by NEAR and not attributable protocol revenue "
            "(OQ-01/OQ-11 remain open).",
            "Recent completed days can be revised by the provider; saved snapshots are "
            "not declared final.",
            "Never sum across sources.",
        ),
        quality_rules={
            "source_qualified": "every observation carries its source dimension",
            "cross_source_sum": "forbidden",
            "revision_policy": "a source revision is a new dataset version, never an "
                               "overwrite",
        },
    ),
    _definition(
        "effective_gross_fee_bps", version=1,
        name="Effective gross fee rate (basis points, source-qualified)",
        unit="bps", frequency="daily", source_id="SRC-LLAMA",
        economic_scope="10000 x compatible provider gross fees / provider volume with both "
                       "sides from the same qualified source; dimensions.source selects "
                       "the source",
        formula_key="effective_gross_fee_bps_v1", availability="P",
        description="Ratio of sums over the period (sum fees / sum volume x 10000), never "
                    "an average of daily ratios.",
        limitations=(
            "A descriptive relation of two provider series, not a contracted fee rate "
            "and not a proven share of any fee stream.",
            "Zero, negative or missing denominator makes the ratio unavailable (null), "
            "not zero.",
            "Both series share Dune lineage; the ratio is not an independent "
            "reconstruction.",
        ),
        quality_rules={
            "ratio_of_sums": "sum before division; daily ratios are never averaged",
            "zero_denominator": "unavailable with a reason, never zero",
            "source_qualified": "numerator and denominator must use the same source",
        },
    ),
    _definition(
        "total_supply_near", version=1,
        name="Total NEAR supply at pinned boundary block",
        unit="NEAR", frequency="snapshot", source_id="SRC-FASTNEAR",
        economic_scope="Exact total_supply from indexed block headers at the selected UTC "
                       "window boundaries",
        formula_key="total_supply_near_v1", availability="A",
        description="Stock value at a pinned block height/hash; observation quality "
                    "metadata records the exact block identity and timestamp.",
        limitations=(
            "A stock, never additive across periods.",
            "Boundary coverage only; a daily future series requires fresh verified "
            "headers.",
        ),
        quality_rules={
            "pinned_block": "block height, hash and timestamp recorded per observation",
        },
    ),
    _definition(
        "net_supply_change_near", version=1,
        name="Net total supply change over a boundary window",
        unit="NEAR", frequency="snapshot", source_id="SRC-FASTNEAR",
        economic_scope="Closing total_supply minus opening total_supply over identical "
                       "boundary windows",
        formula_key="net_supply_change_near_v1", availability="A",
        description="Exact boundary difference of the pinned stock values.",
        limitations=(
            "Observed net change, not a forecast and not an annualized rate.",
            "Observed purchases are never deducted from supply: purchases are not burns "
            "and do not enter this identity.",
        ),
        quality_rules={
            "no_purchase_deduction": "purchases never reduce the measured supply change",
        },
    ),
    _definition(
        "issuance_lower_bound_near", version=1,
        name="Gross issuance lower bound",
        unit="NEAR", frequency="snapshot", source_id="SRC-BQ",
        economic_scope="Documented positive supply changes plus verified simultaneous "
                       "burn, less the documented numeric tolerance",
        formula_key="issuance_lower_bound_near_v1", availability="B",
        description="Conservative lower bound: sum of positive block supply changes plus "
                    "balance_burnt verified in audited mint headers, minus the 0.01 NEAR "
                    "FLOAT64 numeric tolerance.",
        limitations=(
            "6 of 297 positive-change headers audited; the unverified simultaneous "
            "offset is unknown and never assumed zero.",
            "Do not insert bounds into exact accounting identities.",
        ),
        quality_rules={
            "bound_kind": "always lower",
            "incomplete_audit": "mint_headers_verified/target recorded per observation",
        },
    ),
    _definition(
        "burns_lower_bound_near", version=1,
        name="Gross burn lower bound",
        unit="NEAR", frequency="snapshot", source_id="SRC-BQ",
        economic_scope="Documented negative supply changes plus verified simultaneous "
                       "burn, less the documented numeric tolerance",
        formula_key="burns_lower_bound_near_v1", availability="B",
        description="Conservative lower bound: sum of absolute negative block supply "
                    "changes plus verified simultaneous burn, minus the 0.01 NEAR "
                    "numeric tolerance.",
        limitations=(
            "Not the exact gas burn total; purchases, staking and treasury movements "
            "are not burns.",
        ),
        quality_rules={
            "bound_kind": "always lower",
            "incomplete_audit": "mint_headers_verified/target recorded per observation",
        },
    ),
    _definition(
        "purchases_to_net_supply_pct", version=1,
        name="Observed purchases as percent of positive net supply increase",
        unit="percent", frequency="snapshot", source_id="SRC-BQ",
        economic_scope="100 x observed purchases / positive net supply increase over the "
                       "matched boundary window",
        formula_key="purchases_to_net_supply_pct_v1", availability="A",
        description="Exact ratio of the two observed window quantities; a scale context "
                    "between buyback flow and net issuance.",
        limitations=(
            "Not a deflation or capture-rate claim; purchases can return to the market.",
            "A non-positive net increase makes the ratio unavailable (null), never zero "
            "or negative.",
        ),
        quality_rules={
            "non_positive_denominator": "unavailable with a reason",
            "matched_window": "numerator and denominator must cover the same window",
        },
    ),
    _definition(
        "purchases_to_issuance_upper_pct", version=1,
        name="Observed purchases as percent of issuance (upper bound)",
        unit="percent", frequency="snapshot", source_id="SRC-BQ",
        economic_scope="100 x observed purchases / strictly positive issuance lower bound "
                       "over the matched window",
        formula_key="purchases_to_issuance_upper_pct_v1", availability="B",
        description="Because the denominator is a lower bound of gross issuance, the "
                    "ratio is an upper bound of the true share; bound_kind is upper and "
                    "the direction is documented on every observation.",
        limitations=(
            "Rounding is outward-safe only in the upper direction; this is not an exact "
            "share.",
            "A non-positive issuance lower bound makes the ratio unavailable.",
        ),
        quality_rules={
            "bound_kind": "always upper when present",
            "non_positive_denominator": "unavailable with a reason",
            "direction": "purchases / issuance_lower_bound >= true share",
        },
    ),
    _definition(
        "treasury_balance_near", version=1,
        name="Treasury native balance at pinned block",
        unit="NEAR", frequency="snapshot", source_id="SRC-NEAR-RPC",
        economic_scope="Native account balance of the three named treasury wallets at the "
                       "pinned RPC block",
        formula_key="treasury_balance_near_v1", availability="A",
        description="Point-in-time stock from the pinned block header; per-account "
                    "snapshots and locked amounts are recorded in quality metadata.",
        limitations=(
            "A balance snapshot, not cumulative revenue and not permanently removed "
            "supply.",
        ),
        quality_rules={
            "pinned_block": "block height, hash and time recorded per observation",
        },
    ),
    _definition(
        "protocol_revenue_usd", version=1,
        name="Economically attributable protocol revenue (gated)",
        unit="USD", frequency="daily", source_id=None,
        economic_scope="Gross revenue retained by the defined protocol entity after "
                       "distribution and rebates under a chosen recognition basis",
        formula_key="protocol_revenue_usd_v1", availability="G",
        description="Explicitly unavailable: no verified daily economically attributable "
                    "revenue/allocation ledger exists (OQ-01), so every observation is "
                    "null with that reason. Gross provider fees and cash payouts are not "
                    "substitutes.",
        limitations=(
            "Missing allocation ledger, fee policy history and redistribution permission "
            "gate this metric (OQ-01).",
            "Do not substitute gross fees, volume or treasury payouts.",
        ),
        quality_rules={
            "null_semantics": "every observation is null with reason; missing is not zero",
            "gate": "requires a reconciled fee/allocation ledger before any value exists",
        },
    ),
    _definition(
        "protocol_capture_rate", version=1,
        name="Protocol capture rate (gated)",
        unit="percent", frequency="daily", source_id=None,
        economic_scope="100 x attributable protocol revenue / compatible gross generated "
                       "fees",
        formula_key="protocol_capture_rate_v1", availability="G",
        description="Explicitly unavailable: the revenue numerator is gated (OQ-01) and "
                    "the compatible-denominator reconciliation is unresolved (OQ-11), so "
                    "every observation is null with that reason.",
        limitations=(
            "Matching units, time and universe are unresolved; cash sweeps may lag.",
            "No hard daily 0-100 clip hiding mismatch; the metric stays null instead.",
        ),
        quality_rules={
            "null_semantics": "every observation is null with reason",
            "gate": "requires protocol_revenue_usd and a compatible fee denominator",
        },
    ),
    _definition(
        "fee_funded_buybacks_near", version=1,
        name="Fee-funded buybacks (gated)",
        unit="NEAR", frequency="snapshot", source_id=None,
        economic_scope="Executed conversion attributable to earned fees under documented "
                       "mixed-pool accounting",
        formula_key="fee_funded_buybacks_near_v1", availability="G",
        description="Explicitly unavailable for the full window: pooled funds cannot be "
                    "traced into specific payouts (OQ-08), so every observation is null "
                    "with that reason. The separately named narrow provenance equivalent "
                    "is out of NI-029 scope.",
        limitations=(
            "Pooled funds are not physically tagged; no full-window attribution exists.",
            "The 27 Oct-2 Nov strict inventory equivalent is a NI-051 research artifact, "
            "not this metric.",
        ),
        quality_rules={
            "null_semantics": "every observation is null with reason",
            "gate": "requires documented mixed-pool accounting attribution",
        },
    ),
)

_DEFINITIONS_BY_METRIC_ID: dict[str, MetricDefinition] = {}
for _definition_item in DEFINITIONS:
    _previous = _DEFINITIONS_BY_METRIC_ID.get(_definition_item.metric_id)
    if _previous is not None:
        # Superseding versions of one metric id coexist in the registry; the
        # map holds the latest registered version. An exact (metric_id,
        # version) repeat is a registry authoring error.
        if _previous.version >= _definition_item.version:
            raise MetricRegistryError(
                f"metric versions must ascend in the registry: "
                f"{_definition_item.metric_id} v{_definition_item.version} after "
                f"v{_previous.version}")
    _DEFINITIONS_BY_METRIC_ID[_definition_item.metric_id] = _definition_item


def definition_by_metric_id(metric_id: str) -> MetricDefinition:
    """The latest registered definition version of one metric id."""
    return _DEFINITIONS_BY_METRIC_ID[metric_id]


def definition_by_metric_id_version(metric_id: str, version: int) -> MetricDefinition:
    """The exact registered definition version (registry lookups that must
    never silently move to a newer version pin the version explicitly)."""
    for definition in DEFINITIONS:
        if definition.metric_id == metric_id and definition.version == version:
            return definition
    raise KeyError(f"{metric_id}:v{version}")


def definition_by_id(definition_id: UUID) -> MetricDefinition:
    for definition in DEFINITIONS:
        if definition.id == definition_id:
            return definition
    raise KeyError(definition_id)


def validate_registry(formulas: Mapping[str, Callable]) -> None:
    """Fail closed on an internally inconsistent or unimplementable registry."""
    seen_ids: set[UUID] = set()
    for definition in DEFINITIONS:
        if not METRIC_ID_PATTERN.match(definition.metric_id):
            raise MetricRegistryError(f"invalid metric_id {definition.metric_id!r}")
        if definition.version < 1:
            raise MetricRegistryError(f"{definition.metric_id}: version must be positive")
        if definition.id in seen_ids:
            raise MetricRegistryError(f"uuid collision for {definition.metric_id}")
        seen_ids.add(definition.id)
        if definition.formula_key not in formulas:
            raise MetricRegistryError(
                f"{definition.metric_id}: formula_key {definition.formula_key!r} has no "
                "registered computation; emitting observations for it would fabricate data")
        if definition.frequency not in ("daily", "weekly", "monthly", "snapshot"):
            raise MetricRegistryError(f"{definition.metric_id}: invalid frequency")
        if definition.definition.get("availability") not in AVAILABILITY_CODES:
            raise MetricRegistryError(f"{definition.metric_id}: invalid availability code")
        if definition.source_id is None and \
                definition.definition["availability"] != "G":
            raise MetricRegistryError(
                f"{definition.metric_id}: only gated definitions may lack a source")
        if definition.source_id is not None and not definition.source_id.startswith("SRC-"):
            raise MetricRegistryError(f"{definition.metric_id}: invalid source id")
        if definition.definition["availability"] == "G" and \
                "null_semantics" not in definition.quality_rules:
            raise MetricRegistryError(
                f"{definition.metric_id}: gated definitions must declare null semantics")


def _canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def register_definitions(connection) -> dict:
    """Idempotently insert the registry as near_operator; verify stored content.

    The caller must already be inside an operator transaction (the same
    boundary as dataset staging). Existing rows with identical content are
    kept; existing rows with diverging content are a registry error, because
    a registered definition is immutable and can only be superseded by a new
    version.
    """
    from near_api.metrics.compute import FORMULA_REGISTRY

    validate_registry(FORMULA_REGISTRY)
    registered, existing = 0, 0
    for definition in DEFINITIONS:
        row = definition.row()
        stored = connection.execute(text("""
            SELECT id, metric_id, version, name, unit, frequency, economic_scope,
                   formula_key, source_id, definition, quality_rules
            FROM app.metric_definitions WHERE metric_id = :metric_id AND version = :version
        """), {"metric_id": row["metric_id"], "version": row["version"]}).mappings().first()
        if stored is not None:
            existing += 1
            expected = {key: (_canonical_json(value) if isinstance(value, dict) else value)
                        for key, value in row.items()}
            actual = {key: (_canonical_json(stored[key]) if isinstance(stored[key], dict)
                            else stored[key])
                      for key in expected}
            if actual != expected:
                diverging = sorted(key for key in expected if actual[key] != expected[key])
                raise MetricRegistryError(
                    f"Stored definition {row['metric_id']} v{row['version']} diverges from "
                    f"the code registry in {diverging}; a registered definition is "
                    "immutable - supersede it with a new version instead of editing it")
            if stored["id"] != row["id"]:
                raise MetricRegistryError(
                    f"Stored definition {row['metric_id']} v{row['version']} has identity "
                    f"{stored['id']} instead of the deterministic {row['id']}")
            continue
        connection.execute(text("""
            INSERT INTO app.metric_definitions(id, metric_id, version, name, unit, frequency,
                economic_scope, formula_key, source_id, definition, quality_rules)
            VALUES (:id, :metric_id, :version, :name, :unit, :frequency, :economic_scope,
                    :formula_key, :source_id, CAST(:definition AS jsonb),
                    CAST(:quality_rules AS jsonb))
        """), {key: (_canonical_json(value) if isinstance(value, dict) else value)
                for key, value in row.items()})
        registered += 1
    return {"registered": registered, "existing": existing, "total": len(DEFINITIONS)}
