"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ChartView } from "@/features/charts/renderer/ChartView";
import type { ChartDefinitionResponse, ChartViewResponse } from "@/features/charts/renderer/view-types";

import { filterEnumOptions, filterLabel } from "./filter-controls";
import { ChartAuthActions } from "./ChartAuthActions";
import {
  detailHrefFor,
  isIsoCalendarDate,
  windowDays,
} from "./selection-url";
import type { DroppedParam, SerializedSelection } from "./selection-url";

/**
 * Chart detail selection island (NI-034; reused by the public data explorer
 * NI-015 through the `basePath` prop).
 *
 * The URL is the selection's persistence: range, dataset version and filter
 * changes are written back with replace-state (INFORMATION_ARCHITECTURE.md
 * "Filter changes use replace-state; navigation to a new chart pushes
 * history"), so the chart version/range survive navigation and back/forward.
 * The page re-resolves the view from the new URL; this component never
 * fetches on its own and never adds a URL field beyond the approved
 * selection parameters serialized by selection-url.ts.
 *
 * `basePath` decides where the chart detail is mounted (default "/charts",
 * the NI-034 chart library detail). Both the replace-state URLs and the
 * sign-in continuation payload are derived from it, so they can never
 * disagree, and the serialized selection is identical for every base.
 *
 * The custom date-range control lives here (CHART_SYSTEM.md assigns the
 * custom picker to the chart detail page): native date inputs, validated
 * against the definition's bounded ranges, with inline honest errors — an
 * unsupported range is never clamped silently.
 */
export function ChartDetailClient({
  chartId,
  definition,
  view,
  selection,
  dropped,
  basePath = "/charts",
}: {
  chartId: string;
  definition: ChartDefinitionResponse;
  view: ChartViewResponse | null;
  selection: SerializedSelection;
  dropped: DroppedParam[];
  /** Route base this detail page is mounted at (e.g. "/charts", "/data/intents"). */
  basePath?: string;
}) {
  const router = useRouter();
  /** The one href builder for this mounted detail route. */
  const detailHref = (sel: SerializedSelection): string => detailHrefFor(basePath, chartId, sel);
  // The custom-range inputs hold a local draft while being edited; without a
  // draft they mirror the URL selection (the single source of truth). The
  // draft resets when a selection is applied or a preset is used — no
  // syncing effects.
  const [draft, setDraft] = useState<{ start: string; end: string } | null>(null);
  const [rangeError, setRangeError] = useState<string | null>(null);
  const customStart = draft?.start ?? selection.start;
  const customEnd = draft?.end ?? selection.end;

  /** Range/filter changes: replace-state with the full pinned selection. */
  function applySelection(next: Partial<Pick<SerializedSelection, "start" | "end" | "filters">>): void {
    setDraft(null);
    setRangeError(null);
    router.replace(detailHref({ ...selection, ...next }), { scroll: false });
  }

  function handleSelectionChange(next: { start: string; end: string }): void {
    // RangeSelect presets carry no filters; the current validated filters stay.
    applySelection({ start: next.start, end: next.end });
  }

  function applyCustomRange(): void {
    const startValue = customStart;
    const endValue = customEnd;
    if (!isIsoCalendarDate(startValue) || !isIsoCalendarDate(endValue)) {
      setRangeError("Enter both dates as calendar dates (YYYY-MM-DD).");
      return;
    }
    const days = windowDays(startValue, endValue);
    const maxDays = definition.available_ranges.max_days;
    if (days < 1) {
      setRangeError("The range must be non-empty: end must be after start.");
      return;
    }
    if (days > maxDays) {
      setRangeError(`This chart version allows at most ${maxDays} days per view; the requested range covers ${days}.`);
      return;
    }
    applySelection({ start: startValue, end: endValue });
  }

  function setFilter(key: string, value: string): void {
    const filters = { ...selection.filters };
    if (value === "") {
      delete filters[key];
    } else {
      filters[key] = value;
    }
    applySelection({ filters });
  }

  const properties = definition.filter_schema["properties"];
  const filterKeys = properties !== null && typeof properties === "object" && !Array.isArray(properties)
    ? Object.keys(properties as Record<string, unknown>).sort()
    : [];
  const live = selection.datasetVersion === "latest";

  return (
    <div className="flex flex-col gap-6">
      {dropped.length > 0 ? (
        <div role="status" className="rounded-surface border border-border bg-surface-muted p-4">
          <p className="font-ui text-ui leading-ui font-medium">
            Some URL parameters were not used — the chart request carries only supported fields.
          </p>
          <ul className="mt-2 list-disc pl-5 text-ui leading-ui text-text-secondary">
            {dropped.map((item, index) => (
              <li key={`${item.param}-${index}`}>
                <span className="font-medium">{item.param}</span>: {item.reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {filterKeys.length === 0 ? (
        <p className="text-ui leading-ui text-text-secondary">
          No filters are registered for this chart version; every observation is shown unfiltered.
        </p>
      ) : (
        <div role="group" aria-label="Chart filters" className="flex flex-wrap gap-4">
          {filterKeys.map((key) => {
            const options = filterEnumOptions(properties, key);
            return (
              <div key={key} className="flex flex-col gap-1">
                <Label htmlFor={`chart-filter-${key}`}>{filterLabel(key)}</Label>
                <select
                  id={`chart-filter-${key}`}
                  value={selection.filters[key] ?? ""}
                  onChange={(event) => setFilter(key, event.target.value)}
                  className="h-11 rounded-control border border-control-border bg-surface px-3 font-ui text-ui leading-ui text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                >
                  <option value="">All — no filter</option>
                  {options.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
              </div>
            );
          })}
        </div>
      )}

      <ChartView
        definition={definition}
        view={view}
        selection={{ start: selection.start, end: selection.end, filters: selection.filters }}
        mode={live ? "live" : "historical"}
        onSelectionChange={handleSelectionChange}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {live ? (
              <Button variant="quiet" onClick={() => router.refresh()}>
                Refresh to latest
              </Button>
            ) : null}
            <ChartAuthActions
              nextPath={detailHref({ ...selection, datasetVersion: view?.dataset.id ?? selection.datasetVersion })}
              chartTitle={definition.title}
              saveInput={view ? { chart_definition_version_id: definition.id, label: definition.title,
                selection: { ...view.selection, filters: selection.filters }, dataset_version_id: view.dataset.id, mode: "live" } : undefined}
              basePath={`${basePath}/`}
            />
          </div>
        }
      />

      <div className="flex flex-col gap-2 max-w-prose">
        <p className="font-ui text-ui leading-ui font-medium">Custom range (UTC, end exclusive)</p>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="chart-range-start">Start date</Label>
            <input
              id="chart-range-start"
              type="date"
              value={customStart}
              onChange={(event) => setDraft({ start: event.target.value, end: customEnd })}
              className="h-11 rounded-control border border-control-border bg-surface px-3 font-ui text-ui leading-ui text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="chart-range-end">End date</Label>
            <input
              id="chart-range-end"
              type="date"
              value={customEnd}
              onChange={(event) => setDraft({ start: customStart, end: event.target.value })}
              className="h-11 rounded-control border border-control-border bg-surface px-3 font-ui text-ui leading-ui text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            />
          </div>
          <Button variant="secondary" onClick={applyCustomRange}>Apply range</Button>
        </div>
        {rangeError ? (
          <p role="alert" className="text-ui leading-ui text-danger font-medium">{rangeError}</p>
        ) : (
          <p className="text-ui leading-ui text-text-secondary">
            The range is limited to {definition.available_ranges.max_days} days for this chart version.
          </p>
        )}
      </div>
    </div>
  );
}
