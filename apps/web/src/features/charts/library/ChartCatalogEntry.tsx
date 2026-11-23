import Link from "next/link";

import { cn } from "@/lib/utils";
import type { ChartDefinitionResponse } from "@/features/charts/renderer/view-types";
import { categoryWordings, updateFrequencyWordings, visualizationWordings } from "./wording";

export function ChartCatalogEntry({ chart, href, row = false }: {
  chart: ChartDefinitionResponse;
  href: string;
  row?: boolean;
}) {
  const available = chart.data_status === "available";
  if (row) {
    return (
      <li className="border-b border-border">
        <Link
          href={href}
          aria-label={`Open chart: ${chart.title}`}
          aria-describedby={available ? undefined : `chart-status-${chart.chart_id}`}
          className="grid items-center gap-x-5 gap-y-1 px-2 py-3 hover:bg-surface-muted/55 sm:px-4"
        >
          <h2 className="text-left font-sans text-base font-medium leading-snug">{chart.title}</h2>
          <p className="text-metadata text-text-secondary">
            {categoryWordings[chart.category]}
            {!available ? <> · <span id={`chart-status-${chart.chart_id}`}>Unavailable</span></> : null}
          </p>
        </Link>
      </li>
    );
  }
  return (
    <li className="paper-panel relative min-w-0 px-6 py-4 hover:bg-surface-muted/55">
      <div className="min-w-0">
        <h2 aria-label={chart.title} className="text-heading">
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
      <div className="mt-4 flex items-center gap-4">
        <span className={cn("rounded-full px-2.5 py-1 text-metadata font-medium", available ? "bg-sage text-accent" : "bg-surface-muted text-text-secondary")}>
          {available ? "Available" : "Unavailable — this is not zero"}
        </span>
      </div>
    </li>
  );
}
