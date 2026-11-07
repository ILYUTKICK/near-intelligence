/**
 * Real-module smoke test (NI-033): the default chart factory must initialize
 * a real modular ECharts SVG instance in a DOM (jsdom), render plotted
 * geometry, and dispose cleanly on unmount. Complements the recording-fake
 * behavior tests with proof that the actual echarts/core entry, the modular
 * registration and the SVG renderer work end to end.
 *
 * Fixtures are synthetic (fixtures.ts) — no production data.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChartView } from "@/features/charts/renderer/ChartView";
import { definition, metric, observation, series, view } from "./fixtures";

const baseDefinition = definition();
const volumeMetric = metric("USD", "Synthetic volume (fixture)", "synthetic_volume");
const resolvedView = view(baseDefinition, [
  series(volumeMetric, [
    observation("2026-11-01", "1000"),
    observation("2026-11-02", "2000"),
    observation("2026-11-03", null), // gap renders as a break, not a zero bar
    observation("2026-11-04", "4000"),
  ]),
]);

describe("default chart factory with real echarts/core", () => {
  it("initializes an SVG instance, renders geometry and disposes on unmount", async () => {
    const { container, unmount } = render(
      <ChartView
        definition={baseDefinition}
        selection={{ start: "2026-11-01", end: "2026-11-06" }}
        view={resolvedView}
        mode="live"
        width={600}
        height={320}
      />,
    );

    // The default factory (dynamic modular imports) mounted an SVG chart.
    const svg = await waitFor(() => {
      const element = container.querySelector("svg");
      expect(element).not.toBeNull();
      return element as SVGSVGElement;
    });
    // SVG renderer: plotted geometry exists as vector shapes.
    await waitFor(() => expect(svg.querySelectorAll("path, circle, polyline").length).toBeGreaterThan(0));
    // The ARIA component description is present on the instance output.
    await waitFor(() => expect(screen.getByRole("img", { name: /Synthetic daily volume/ })).toBeInTheDocument());

    // Unmount disposes without errors (ECharts cleans its DOM/hooks).
    expect(() => unmount()).not.toThrow();
    await waitFor(() => expect(container.querySelector("svg")).toBeNull());
  });
});
