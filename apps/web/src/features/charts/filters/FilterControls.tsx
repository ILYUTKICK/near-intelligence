"use client";

import type { ChartDefinitionResponse } from "@/features/charts/renderer/view-types";

import { filterEnumOptions, filterLabel } from "@/features/charts/library/filter-controls";

import {
  canonicalValueOrder,
  isMultiValueProperty,
  type FilterValue,
  type FiltersSelection,
} from "./filter-values";

/**
 * NI-071 shared filter controls for one chart definition version (the chart
 * detail page and the editor live-chart block render the same component).
 *
 * A dimension whose closed-schema property declares `multi_value: true`
 * renders as an accessible checkbox group: every checked option is one
 * selected value, the resolved view fans out into one compared series per
 * selected value (server-side fan-out), and clearing every checkbox selects
 * "all — no filter" again. Dimensions without the marker keep the strict
 * NI-031 single-select. Nothing here invents an option: the choices are the
 * definition version's declared enum, and the stored per-key value order is
 * the schema's declared order (the server's canonical form), never the
 * click order.
 */

const CONTROL_CLASS = "h-11 min-w-0 rounded-control border border-control-border bg-surface px-3 font-ui text-ui leading-ui text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";
const CHECKBOX_CLASS = "h-5 w-5 rounded-control border border-control-border bg-surface text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

export function filterPropertiesOf(
  definition: ChartDefinitionResponse,
): Record<string, unknown> {
  const properties = definition.filter_schema["properties"];
  return properties !== null && typeof properties === "object" && !Array.isArray(properties)
    ? properties as Record<string, unknown>
    : {};
}

function SingleFilterControl({ id, label, options, value, onChange }: {
  id: string;
  label: string;
  options: string[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="font-ui text-ui leading-ui font-medium">{label}</label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}
        className={CONTROL_CLASS}>
        <option value="">All — no filter</option>
        {options.map((option) => (
          <option key={option} value={option}>{option}</option>
        ))}
      </select>
    </div>
  );
}

function MultiFilterControl({ idPrefix, label, options, selected, onChange }: {
  idPrefix: string;
  label: string;
  options: string[];
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  return (
    <fieldset className="flex min-w-0 flex-col gap-1">
      <legend className="font-ui text-ui leading-ui font-medium">{label}</legend>
      <div role="group" aria-label={`${label} — select one or more values to compare`}
        className="flex flex-wrap gap-x-4 gap-y-2">
        {options.map((option) => {
          const id = `${idPrefix}-${option}`;
          return (
            <span key={option} className="flex items-center gap-2">
              <input
                id={id}
                type="checkbox"
                checked={selected.includes(option)}
                onChange={(event) => {
                  const next = event.target.checked
                    ? [...selected, option]
                    : selected.filter((value) => value !== option);
                  // The stored order is the schema's declared order, never
                  // the click order.
                  onChange(canonicalValueOrder(next, options));
                }}
                className={CHECKBOX_CLASS}
              />
              <label htmlFor={id} className="font-ui text-ui leading-ui">{option}</label>
            </span>
          );
        })}
      </div>
      <p className="text-metadata leading-metadata text-text-secondary">
        Select one or more; each selected value resolves its own compared series,
        and clearing every box shows the unfiltered chart.
      </p>
    </fieldset>
  );
}

/** One shared, honest filter control group for the definition's dimensions. */
export function ChartFilterControls({ definition, filters, onChange, idPrefix }: {
  definition: ChartDefinitionResponse;
  /** Current filter document (single strings or multi-value lists). */
  filters: FiltersSelection;
  /** Receives the complete next filter document (unapproved values never enter). */
  onChange: (filters: FiltersSelection) => void;
  /** Unique prefix for control ids (the editor renders several instances). */
  idPrefix: string;
}) {
  const properties = filterPropertiesOf(definition);
  const keys = Object.keys(properties).sort();
  if (keys.length === 0) {
    return <p className="text-metadata text-leading text-text-secondary">No filters are registered for this chart version.</p>;
  }
  function setFilter(key: string, value: FilterValue | null): void {
    const next: FiltersSelection = { ...filters };
    if (value === null || (Array.isArray(value) && value.length === 0) || value === "") {
      delete next[key];
    } else {
      next[key] = value;
    }
    onChange(next);
  }
  return (
    <div role="group" aria-label="Chart filters" className="flex flex-wrap gap-4">
      {keys.map((key) => {
        const options = filterEnumOptions(properties, key);
        const label = filterLabel(key);
        const value = filters[key];
        if (isMultiValueProperty(properties[key])) {
          return (
            <MultiFilterControl
              key={key}
              idPrefix={`${idPrefix}-${key}`}
              label={label}
              options={options}
              selected={Array.isArray(value) ? value : value !== undefined ? [value] : []}
              onChange={(values) => setFilter(key, values.length > 0 ? values : null)}
            />
          );
        }
        return (
          <SingleFilterControl
            key={key}
            id={`${idPrefix}-${key}`}
            label={label}
            options={options}
            value={typeof value === "string" ? value : ""}
            onChange={(next) => setFilter(key, next === "" ? null : next)}
          />
        );
      })}
    </div>
  );
}
