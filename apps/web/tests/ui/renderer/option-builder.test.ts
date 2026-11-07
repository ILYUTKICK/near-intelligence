/**
 * Option builder tests for the NI-033 chart renderer (pure, no mounting).
 *
 * Covers every visualization type the NI-031 registry uses (line, area, bar,
 * panels-style unit grouping, scatter), missing-gap honesty, bound labeling,
 * large decimals, JSON-safety of the static-export mode and the renderer
 * version alignment with apps/api registry.
 *
 * All fixtures are synthetic (see fixtures.ts) — no production data.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import type { TooltipComponentOption } from "echarts/components";
import { describe, expect, it } from "vitest";

import { buildChart, CHART_SERIES_COLORS, displayUnits } from "@/features/charts/renderer/option-builder";
import { RENDERER_VERSION } from "@/features/charts/renderer/view-types";
import type { SeriesResponse } from "@/features/charts/renderer/view-types";
import {
  definition,
  lowerBoundQuality,
  metric,
  observation,
  series,
  view,
  HUGE_DECIMAL,
} from "./fixtures";

const REPO_ROOT = path.resolve(__dirname, "../../../../..");
const WINDOW = { start: "2026-11-01", end: "2026-11-06" };

describe("buildChart — cartesian charts", () => {
  it("builds a gap-preserving line series: missing points stay null, connectNulls false", () => {
    const volume = metric("USD", "Synthetic volume (fixture)", "synthetic_volume");
    const seriesList: SeriesResponse[] = [
      series(volume, [
        observation("2026-11-01", "1000"),
        observation("2026-11-02", "2000"),
        observation("2026-11-03", null), // gap — never interpolated, never zero
        observation("2026-11-04", "4000"),
      ]),
    ];
    const built = buildChart(view(definition(), seriesList));
    expect(built.kind).toBe("ok");
    if (built.kind !== "ok") return;
    const line = built.option.series?.[0] as { type: string; connectNulls: boolean; data: (number | null)[] };
    expect(line.type).toBe("line");
    expect(line.connectNulls).toBe(false);
    expect(line.data[0]).toBe(1000);
    expect(line.data[2]).toBeNull();
    expect(built.hasPlottableData).toBe(true);
    expect(built.panelCount).toBe(1);
  });

  it("adds an area style only for area charts and keeps zero-anchored bars", () => {
    const volume = metric("USD", "Synthetic volume (fixture)", "synthetic_volume");
    const areaBuilt = buildChart(
      view(definition({ visualization_type: "area" }), [series(volume, [observation("2026-11-01", "5")])]),
    );
    expect(areaBuilt.kind).toBe("ok");
    if (areaBuilt.kind === "ok") {
      expect((areaBuilt.option.series?.[0] as { areaStyle?: unknown }).areaStyle).toBeDefined();
    }
    const fees = metric("USD", "Synthetic fees (fixture)", "synthetic_fees");
    const barBuilt = buildChart(
      view(definition({ visualization_type: "bar", chart_id: "synthetic-fees" }), [
        series(fees, [observation("2026-11-01", "7")]),
      ]),
    );
    expect(barBuilt.kind).toBe("ok");
    if (barBuilt.kind === "ok") {
      const bar = barBuilt.option.series?.[0] as { type: string; barMaxWidth: number };
      expect(bar.type).toBe("bar");
      expect(bar.barMaxWidth).toBe(32);
      // Bars are zero-anchored: no hidden truncation.
      expect((barBuilt.option.yAxis as { min: number }[])[0].min).toBe(0);
    }
  });

  it("lays out different-unit series as aligned panels — no dual-axis implication", () => {
    const near = metric("NEAR", "Synthetic purchases (fixture)", "synthetic_purchases");
    const usd = metric("USD", "Synthetic estimate (fixture)", "synthetic_estimate");
    const built = buildChart(
      view(
        definition({ chart_id: "synthetic-sensitivity" }),
        [
          series(near, [observation("2026-11-01", "500")]),
          series(usd, [observation("2026-11-01", "2500")]),
        ],
      ),
    );
    expect(built.kind).toBe("ok");
    if (built.kind !== "ok") return;
    expect(built.panelCount).toBe(2);
    expect((built.option.grid as unknown[]).length).toBe(2);
    expect((built.option.series?.[0] as { xAxisIndex: number }).xAxisIndex).toBe(0);
    expect((built.option.series?.[1] as { xAxisIndex: number }).xAxisIndex).toBe(1);
    const yAxis = built.option.yAxis as { name: string; type: string }[];
    expect(yAxis.map((axis) => axis.name)).toEqual(["NEAR", "USD"]);
    // Multi-series charts carry a legend for the panel titles.
    expect(built.option.legend?.data).toEqual(["Synthetic purchases (fixture)", "Synthetic estimate (fixture)"]);
  });

  it("keeps same-unit series on one axis with grouped bars", () => {
    const supply = metric("NEAR", "Synthetic net supply change (fixture)", "synthetic_supply");
    const purchases = metric("NEAR", "Synthetic purchases (fixture)", "synthetic_purchases");
    const built = buildChart(
      view(definition({ chart_id: "synthetic-supply-context", visualization_type: "bar" }), [
        series(supply, [observation("2026-11-01", "100000")]),
        series(purchases, [observation("2026-11-01", "1500")]),
      ]),
    );
    expect(built.kind).toBe("ok");
    if (built.kind !== "ok") return;
    expect(built.panelCount).toBe(1);
    expect(built.option.legend?.data).toHaveLength(2);
  });
});

describe("buildChart — scatter", () => {
  it("pairs X/Y series and plots only complete pairs", () => {
    const volume = metric("USD", "Synthetic volume (fixture)", "synthetic_volume");
    const fees = metric("USD", "Synthetic fees (fixture)", "synthetic_fees");
    const built = buildChart(
      view(definition({ chart_id: "synthetic-association", visualization_type: "scatter" }), [
        series(volume, [
          observation("2026-11-01", "100"),
          observation("2026-11-02", "200"),
          observation("2026-11-03", "300"),
        ]),
        series(fees, [
          observation("2026-11-01", "10"),
          observation("2026-11-02", null), // incomplete pair — excluded from plot, kept in table
          observation("2026-11-03", "30"),
        ]),
      ]),
    );
    expect(built.kind).toBe("ok");
    if (built.kind !== "ok") return;
    const scatter = built.option.series?.[0] as { type: string; data: [number, number][] };
    expect(scatter.type).toBe("scatter");
    expect(scatter.data).toEqual([
      [100, 10],
      [300, 30],
    ]);
    expect(built.hasPlottableData).toBe(true);
    // The incomplete pair remains visible in the exact-value table.
    const gapRow = built.table.rows.find((row) => row.date === "2026-11-02");
    expect(gapRow?.cells[1]).toEqual({ kind: "missing", reason: "no observation for the period" });
  });

  it("reports no plottable data when no complete pair exists", () => {
    const volume = metric("USD", "Synthetic volume (fixture)", "synthetic_volume");
    const fees = metric("USD", "Synthetic fees (fixture)", "synthetic_fees");
    const built = buildChart(
      view(definition({ chart_id: "synthetic-association", visualization_type: "scatter" }), [
        series(volume, [observation("2026-11-01", "100")]),
        series(fees, [observation("2026-11-01", null)]),
      ]),
    );
    expect(built.kind).toBe("ok");
    if (built.kind !== "ok") return;
    expect(built.hasPlottableData).toBe(false);
  });
});

describe("buildChart — exact values, bounds and honesty", () => {
  it("keeps exact decimal strings in the table and float only in coordinates", () => {
    const near = metric("NEAR", "Synthetic purchases (fixture)", "synthetic_purchases");
    const built = buildChart(
      view(definition(), [series(near, [observation("2026-11-01", HUGE_DECIMAL)])]),
    );
    expect(built.kind).toBe("ok");
    if (built.kind !== "ok") return;
    const cell = built.table.rows[0].cells[0];
    expect(cell.kind === "value" && cell.exact).toBe(HUGE_DECIMAL);
    expect(cell.kind === "value" && cell.display).toBe(
      "123\u202f456\u202f789\u202f012\u202f345\u202f678\u202f901\u202f234\u202f567\u202f890.5",
    );
    const line = built.option.series?.[0] as { data: (number | null)[] };
    // The documented coordinate boundary: Number() for plot position only.
    expect(line.data[0]).toBe(Number(HUGE_DECIMAL));
  });

  it("labels bounded values in the table, summary and tooltip lookup", () => {
    const payouts = metric("NEAR", "Synthetic payouts (fixture)", "synthetic_payouts");
    const built = buildChart(
      view(
        definition({ chart_id: "synthetic-payouts", visualization_type: "bar" }),
        [series(payouts, [observation("2026-11-01", "1234", lowerBoundQuality())])],
      ),
    );
    expect(built.kind).toBe("ok");
    if (built.kind !== "ok") return;
    const cell = built.table.rows[0].cells[0];
    expect(cell.kind === "value" && cell.display).toBe("\u22651\u202f234");
    expect(cell.kind === "value" && cell.bound).toBe("lower bound");
    expect(built.summary).toContain("a bound or estimate");
    // The tooltip formatter renders the exact string with the bound label.
    const formatter = (built.option.tooltip as TooltipComponentOption).formatter;
    expect(typeof formatter).toBe("function");
    const text = (formatter as unknown as (params: unknown) => string)([
      { seriesIndex: 0, dataIndex: 0 },
    ]);
    expect(text).toContain("2026-11-01 (UTC)");
    expect(text).toContain("\u22651\u202f234");
    expect(text).toContain("lower bound");
  });

  it("renders gap rows with reasons and never as zero", () => {
    const volume = metric("USD", "Synthetic volume (fixture)", "synthetic_volume");
    const built = buildChart(
      view(definition(), [series(volume, [observation("2026-11-01", null)])]),
    );
    expect(built.kind).toBe("ok");
    if (built.kind !== "ok") return;
    expect(built.hasPlottableData).toBe(false);
    expect(built.table.rows[0].cells[0]).toEqual({
      kind: "missing",
      reason: "no observation for the period",
    });
    expect(built.summary).toContain("not zero");
  });

  it("mentions ambiguous-variant reasons verbatim in the table", () => {
    const volume = metric("USD", "Synthetic volume (fixture)", "synthetic_volume");
    const reason = "the period holds multiple dimension variants for this metric; an approved filter value must disambiguate them";
    const built = buildChart(
      view(definition(), [
        series(volume, [observation("2026-11-01", null, {
          status: "unavailable",
          bound_kind: null,
          reasons: [reason],
          coverage: { observed: 0, expected: 1 },
          freshness_target_seconds: null,
        })]),
      ]),
    );
    expect(built.kind).toBe("ok");
    if (built.kind !== "ok") return;
    expect(built.table.rows[0].cells[0]).toEqual({ kind: "missing", reason });
  });
});

describe("buildChart — renderer contract guards", () => {
  it("refuses definitions pinned to another renderer capability set", () => {
    const volume = metric("USD", "Synthetic volume (fixture)", "synthetic_volume");
    const built = buildChart(
      view(definition({ renderer_version: "other-renderer@9" }), [
        series(volume, [observation("2026-11-01", "1")]),
      ]),
    );
    expect(built).toEqual({
      kind: "unsupported-renderer",
      rendererVersion: "other-renderer@9",
      expected: "echarts-modular-svg@1",
    });
  });

  it("produces a JSON-safe option for the static-export mode", () => {
    const volume = metric("USD", "Synthetic volume (fixture)", "synthetic_volume");
    const usd = metric("NEAR", "Synthetic purchases (fixture)", "synthetic_purchases");
    const resolved = view(definition(), [
      series(volume, [observation("2026-11-01", "1000"), observation("2026-11-02", null)]),
      series(usd, [observation("2026-11-01", "500")]),
    ]);
    const pure = buildChart(resolved, { interactions: false, animation: false });
    expect(pure.kind).toBe("ok");
    if (pure.kind !== "ok") return;
    const roundTripped = JSON.parse(JSON.stringify(pure.option)) as unknown;
    expect(roundTripped).toEqual(pure.option);
  });

  it("carries interaction closures only in the browser mode", () => {
    const volume = metric("USD", "Synthetic volume (fixture)", "synthetic_volume");
    const resolved = view(definition(), [series(volume, [observation("2026-11-01", "1000")])]);
    const browserBuilt = buildChart(resolved, { interactions: true });
    expect(browserBuilt.kind).toBe("ok");
    if (browserBuilt.kind === "ok") {
      expect(typeof (browserBuilt.option.tooltip as TooltipComponentOption).formatter).toBe("function");
    }
  });

  it("exposes the display units line in series order without duplication", () => {
    const near = metric("NEAR", "Synthetic purchases (fixture)", "synthetic_purchases");
    const usd = metric("USD", "Synthetic estimate (fixture)", "synthetic_estimate");
    const resolved = view(definition(), [
      series(near, [observation("2026-11-01", "1")]),
      series(usd, [observation("2026-11-01", "2")]),
    ]);
    expect(displayUnits(resolved)).toBe("NEAR · USD");
  });
});

describe("renderer/registry alignment", () => {
  it("RENDERER_VERSION equals the apps/api chart registry constant", () => {
    const registrySource = readFileSync(
      path.join(REPO_ROOT, "apps/api/src/near_api/charts/registry.py"),
      "utf8",
    );
    const match = registrySource.match(/RENDERER_VERSION = "([^"]+)"/);
    expect(match?.[1]).toBe(RENDERER_VERSION);
  });

  it("covers every visualization type the registry uses", () => {
    const registrySource = readFileSync(
      path.join(REPO_ROOT, "apps/api/src/near_api/charts/registry.py"),
      "utf8",
    );
    expect(registrySource).toContain('VISUALIZATION_TYPES = ("line", "area", "bar", "scatter", "panels")');
    // Each of these is exercised above: line, area, bar, scatter, panels
    // (unit-grouped aligned panels) — the builder's panel rule covers the
    // registry "panels" visualization and any mixed-unit chart generically.
    const volume = metric("USD", "Synthetic volume (fixture)", "synthetic_volume");
    const built = buildChart(view(definition({ visualization_type: "panels" }), [
      series(volume, [observation("2026-11-01", "10")]),
    ]));
    expect(built.kind).toBe("ok");
  });

  it("chart palette values still exist in the design tokens (no silent drift)", () => {
    const tokens = readFileSync(
      path.join(REPO_ROOT, "apps/web/src/styles/tokens.css"),
      "utf8",
    ).toLowerCase();
    for (const color of CHART_SERIES_COLORS) {
      expect(tokens).toContain(color.toLowerCase());
    }
    expect(tokens).toContain("#4b5c54"); // color.text-secondary (axis text)
    expect(tokens).toContain("#d8ddd2"); // color.border (axis lines)
  });
});
