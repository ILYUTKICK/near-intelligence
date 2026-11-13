import Link from "next/link";

import { ProductIcon } from "@/components/layout/ProductIcon";
import { cn } from "@/lib/utils";
import { getLandingClaim } from "./landing-findings";
import { scopePeriodLabel as periodLabel } from "./ResearchFigures";
import { RecordedQuantityPlot } from "./RecordedQuantityPlot";

/** Fixed-window editorial illustration of the recorded NI-014 claim. */
export function RecordedPurchases({ compact = false }: { compact?: boolean }) {
  const claim = getLandingClaim("CL-002");
  const windows = claim.quantities.filter((quantity) => quantity.unit === "NEAR acquired");
  const lengths = windows.map((quantity) => Number(quantity.value.replaceAll(",", "")));
  const maxLength = Math.max(...lengths);

  return (
    <figure className={cn("paper-panel", compact ? "p-4" : "p-6 sm:p-8")}>
      <figcaption className="flex flex-wrap items-start justify-between gap-2">
        <div>
          {compact ? (
            <p className="text-metadata font-semibold">Observed purchases</p>
          ) : (
            <>
              <p className="eyebrow">Recorded evidence</p>
              <h2 className="mt-2 text-heading md:text-title">A recurrent channel, with fewer tokens acquired</h2>
            </>
          )}
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-sage px-2.5 py-1 text-metadata font-medium text-accent">
          <span aria-hidden="true" className="size-1.5 rounded-full bg-accent" /> Historical
        </span>
      </figcaption>
      <p className="mt-2 text-metadata text-text-secondary">NEAR · Three 30-day windows · Aug–Nov 2026 UTC</p>
      {!compact ? <RecordedQuantityPlot labels={windows.map((quantity) => periodLabel(quantity.scope))} values={windows.map((quantity) => quantity.value)} unit="NEAR" title="Observed purchases in three 30-day windows" /> : null}
      <ul className={cn("mt-3", compact ? "space-y-2" : "space-y-4")}>
        {windows.map((quantity, index) => (
          <li key={quantity.scope} className={cn(
            "grid items-center gap-x-4",
            compact ? "gap-y-1" : "sm:grid-cols-[8.5rem_minmax(0,1fr)]",
          )}>
            <span className={cn("text-text-secondary", compact ? "text-metadata" : "text-ui sm:row-span-2")}>
              <span aria-hidden="true">{periodLabel(quantity.scope)}</span>
              <span className="sr-only">{quantity.scope}</span>
            </span>
            <span className={cn("tabular-nums font-semibold", compact ? "col-start-2 row-start-1 text-right text-metadata" : "text-ui")}>
              {quantity.value}
            </span>
            {compact ? <div aria-hidden="true" className="col-span-2 h-1 overflow-hidden rounded-full bg-sage/50">
              <div className="h-full rounded-full bg-accent" style={{ width: `${(lengths[index] / maxLength) * 100}%` }} />
            </div> : null}
          </li>
        ))}
      </ul>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3 text-metadata text-text-secondary">
        <span>{claim.id} · Observed treasury-linked cohort</span>
        <Link href={compact ? "/research#CL-002-heading" : "#CL-002-heading"} className="flex items-center gap-1.5 font-medium hover:underline">
          Recorded claim <ProductIcon name="arrow" className="size-3.5" />
        </Link>
      </div>
    </figure>
  );
}
