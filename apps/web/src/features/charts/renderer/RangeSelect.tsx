"use client";

import { Button } from "@/components/ui/button";

import type { ChartDefinitionResponse } from "./view-types";

/**
 * Keyboard/touch range presets (NI-033).
 *
 * Presets come from the definition's bounded `available_ranges`
 * (`presets_days`, `max_days` — the registry contract), so no preset can
 * exceed the chart's allowed maximum. The selected range is anchored to the
 * current selection's end (the caller's latest complete observation), not
 * wall-clock time, per CHART_SYSTEM.md. Real buttons: reachable by
 * keyboard, 44px touch targets, active preset announced via aria-pressed.
 * A custom date-range picker belongs to the chart detail page (NI-034) and
 * is deliberately not faked here.
 */
export function RangeSelect({
  definition,
  selection,
  onChange,
}: {
  definition: ChartDefinitionResponse;
  /** Current resolved selection ("YYYY-MM-DD" half-open window). */
  selection: { start: string; end: string };
  onChange: (selection: { start: string; end: string }) => void;
}) {
  const presets = definition.available_ranges.presets_days;
  const maxDays = definition.available_ranges.max_days;
  const activePreset = presets.find(
    (days) => shiftDate(selection.end, -days) === selection.start,
  );
  const windowDays = Math.max(
    1,
    Math.round((Date.parse(selection.end) - Date.parse(selection.start)) / 86_400_000),
  );

  return (
    <div role="group" aria-label="Time range" className="flex flex-wrap items-center gap-2">
      {presets.map((days) => (
        <Button
          key={days}
          variant={activePreset === days ? "primary" : "secondary"}
          aria-pressed={activePreset === days}
          onClick={() =>
            onChange({ start: shiftDate(selection.end, -days), end: selection.end })
          }
        >
          Last {days} days
        </Button>
      ))}
      {activePreset === undefined ? (
        <span className="text-ui leading-ui text-text-secondary">
          Custom range: {selection.start} – {selection.end} ({windowDays} of up to {maxDays} days)
        </span>
      ) : null}
    </div>
  );
}

/** Calendar-safe date shift (UTC days) on a "YYYY-MM-DD" string. */
export function shiftDate(isoDate: string, days: number): string {
  const shifted = new Date(`${isoDate}T00:00:00Z`);
  shifted.setUTCDate(shifted.getUTCDate() + days);
  return shifted.toISOString().slice(0, 10);
}
