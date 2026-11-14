import Link from "next/link";

import { ProductIcon } from "@/components/layout/ProductIcon";
import { claimRegistry, type ClaimQuantity, type ThesisClaim } from "./content";
import { RecordedQuantityPlot } from "./RecordedQuantityPlot";

// Values come from the claim registry. Only plot geometry crosses the Number boundary.
const dayMonth = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", timeZone: "UTC" });

/** "First 30-day window, 2026-08-06 through 2026-09-04 …" → "06 Aug–04 Sep". */
export function scopePeriodLabel(scope: string): string {
  const dates = scope.match(/\d{4}-\d{2}-\d{2}/g);
  if (!dates || dates.length !== 2) return scope;
  return dates.map((date) => dayMonth.format(new Date(date))).join("–");
}

function claimById(id: string): ThesisClaim {
  const claim = claimRegistry.find((entry) => entry.id === id);
  if (!claim) {
    throw new Error(`Research figures reference an unknown claim id: ${id}`);
  }
  return claim;
}

/** Resolves a recorded quantity by index and asserts the recorded unit. */
function quantityAt(claim: ThesisClaim, index: number, unitPart: string): ClaimQuantity {
  const quantity = claim.quantities[index];
  if (!quantity || !quantity.unit.includes(unitPart)) {
    throw new Error(`Claim ${claim.id} quantity ${index} does not carry the expected ${unitPart} unit`);
  }
  return quantity;
}

/** Zero-based relative width; exact strings never pass through Number. */
interface FigureBar {
  readonly label: string;
  readonly srLabel: string;
  readonly value: ClaimQuantity;
}

const badgeClasses =
  "inline-flex items-center gap-1.5 rounded-full bg-sage px-2.5 py-1 text-metadata font-medium text-accent";
const claimLinkClasses =
  "flex items-center gap-1.5 font-medium hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

function QuantityBars({ bars, unit }: { readonly bars: readonly FigureBar[]; readonly unit: string }) {
  return (
    <>
    <RecordedQuantityPlot labels={bars.map((bar) => bar.label)} values={bars.map((bar) => bar.value.value)} unit={unit} title="Recorded evidence comparison" />
    <ul className="mt-3 space-y-4">
      {bars.map((bar) => (
        <li key={bar.label} className="grid items-center gap-x-4 sm:grid-cols-[11rem_minmax(0,1fr)]">
          <span className="text-ui text-text-secondary sm:row-span-2">
            <span aria-hidden="true">{bar.label}</span>
            <span className="sr-only">{bar.srLabel}</span>
          </span>
          <span className="text-ui tabular-nums font-semibold text-text">
            {bar.value.unit.startsWith("USD") ? <span aria-hidden="true">≈ </span> : null}
            {bar.value.unit.startsWith("USD") ? <span className="sr-only">approximately </span> : null}
            {bar.value.value} <span className="font-medium text-text-secondary">{unit}</span>
          </span>
        </li>
      ))}
    </ul>
    </>
  );
}

function FigureShell({
  idPrefix,
  kind,
  claimIds,
  badge,
  title,
  subtitle,
  bars,
  unit,
  takeaway,
  note,
}: {
  readonly idPrefix: string;
  readonly kind: string;
  readonly claimIds: readonly string[];
  readonly badge: string;
  readonly title: string;
  readonly subtitle: string;
  readonly bars: readonly FigureBar[];
  readonly unit: string;
  readonly takeaway: string;
  readonly note: string;
}) {
  const id = `${idPrefix}-${kind}`;
  return (
    <figure id={id} aria-labelledby={`${id}-title`} className="paper-panel min-w-0 p-6 sm:p-8">
      <figcaption className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="eyebrow">Recorded evidence · {claimIds.join(" / ")}</p>
          <h3 id={`${id}-title`} className="mt-2 text-heading leading-heading">
            {title}
          </h3>
        </div>
        <span className={badgeClasses}>
          <span aria-hidden="true" className="size-1.5 rounded-full bg-accent" /> {badge}
        </span>
      </figcaption>
      <p className="mt-2 text-metadata text-text-secondary">{subtitle}</p>
      <QuantityBars bars={bars} unit={unit} />
      <p className="mt-4 border-t border-border pt-3 text-body leading-body font-medium text-text">{takeaway}</p>
      <p className="mt-2 text-ui leading-ui text-text-secondary">{note}</p>
      <p className="mt-2 text-metadata leading-metadata text-text-secondary">
        Historical · Aug–Nov 2026 UTC · verified 4 November 2026 · exact quantities, scopes and
        sources in the claim cards below
      </p>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3 text-metadata text-text-secondary">
        {claimIds.map((id) => (
          <Link key={id} href={`#${id}-heading`} className={claimLinkClasses}>
            Recorded claim {id} <ProductIcon name="arrow" className="size-3.5" />
          </Link>
        ))}
      </div>
    </figure>
  );
}

/**
 * CL-007 with the recorded CL-001 cohort total — the scale of observed
 * purchases against positive net supply growth. Both bars are NEAR on one
 * zero-based scale; purchases are not subtracted from supply and the figure
 * is not a capture rate or a deflation claim.
 */
export function SupplyScaleFigure({ idPrefix = "thesis" }: { readonly idPrefix?: string }) {
  const supply = claimById("CL-007");
  const cohort = claimById("CL-001");
  const purchases = quantityAt(cohort, 1, "NEAR acquired");
  const netIncrease = quantityAt(supply, 0, "NEAR exact boundary total-supply increase");
  const shareOfIncrease = quantityAt(supply, 2, "percent of the net supply increase");
  const shareOfOpening = quantityAt(supply, 1, "percent of the opening supply");
  const directionWord = (direction: ClaimQuantity["direction"]) =>
    direction === "decrease" ? "decrease" : direction === "increase" ? "increase" : "change";
  return (
    <FigureShell
      idPrefix={idPrefix}
      kind="supply-scale"
      claimIds={["CL-007", "CL-001"]}
      badge="Observed — scale comparison"
      title="Purchases stay small beside net supply growth"
      subtitle="Same recorded 90-day cohort · NEAR · two independent recorded totals, one scale"
      bars={[
        {
          label: "Observed purchases",
          srLabel: `Observed purchases: ${purchases.scope}`,
          value: purchases,
        },
        {
          label: "Net supply increase",
          srLabel: `Net supply increase: ${netIncrease.scope}`,
          value: netIncrease,
        },
      ]}
      unit="NEAR"
      takeaway={
        `Observed purchases are ${shareOfIncrease.value} ${shareOfIncrease.unit}; the net increase itself `
        + `is an ${directionWord(shareOfOpening.direction)} of ${shareOfOpening.value} ${shareOfOpening.unit}. `
        + `A scale comparison — not deflation, not a capture rate.`
      }
      note={
        `Purchases are never subtracted from total supply. Emission does not equal market selling `
        + `pressure; recipients may hold or stake their rewards.`
      }
    />
  );
}
