import Link from "next/link";

import { ProductIcon } from "@/components/layout/ProductIcon";
import { cn } from "@/lib/utils";
import type { ChartDefinitionResponse } from "@/features/charts/renderer/view-types";
import { categoryWordings, updateFrequencyWordings, visualizationWordings } from "./wording";

export function ChartCatalogEntry({ chart, href, row = false }: {
  chart: ChartDefinitionResponse;
  href: string;
  row?: boolean;
}) {
  const available = chart.data_status === "available";
  return (
    <li className={cn(
      "relative min-w-0 px-6 py-4 hover:bg-surface-muted/55",
      row ? "flex flex-wrap items-center justify-between gap-x-5 gap-y-3" : "paper-panel",
    )}>
      <div className="min-w-0 flex-1 basis-72">
        <h2 aria-label={chart.title} className={row ? "font-sans text-ui font-semibold" : "text-heading"}>
          <Link
            href={href}
            aria-label={`Open chart: ${chart.title}`}
            className="text-text after:absolute after:inset-0 after:rounded-surface focus-visible:after:outline-2 focus-visible:after:outline-focus"
          >
            {chart.title}
          </Link>
        </h2>
        <p className="mt-1 text-ui text-text-secondary">{chart.description}</p>
        <p className="mt-2 text-metadata text-text-secondary">
          {categoryWordings[chart.category]} · {visualizationWordings[chart.visualization_type]} ·{" "}
          {updateFrequencyWordings[chart.update_frequency]} · Units:{" "}
          {[...new Set(Object.values(chart.units))].join(", ")}
        </p>
        {!available && chart.unavailable_reason ? (
          <p className="mt-2 text-ui text-text-secondary">Reason: {chart.unavailable_reason}</p>
        ) : null}
      </div>
      <div className={cn("flex items-center gap-4", !row && "mt-4")}>
        <span className={cn("rounded-full px-2.5 py-1 text-metadata font-medium", available ? "bg-sage text-accent" : "bg-surface-muted text-text-secondary")}>
          {available ? "Available" : "Unavailable — this is not zero"}
        </span>
        <ProductIcon name="arrow" className="ml-auto size-4 shrink-0 text-accent" />
      </div>
    </li>
  );
}
