/**
 * NI-057 tests: the static chart asset renderer (apps/web/scripts/render-charts.mjs).
 *
 * The renderer is exercised as a real subprocess exactly the way the Python
 * export boundary invokes it: strict JSON on stdin, strict JSON on stdout,
 * non-zero exit with a typed error object on any refusal. Everything here is
 * synthetic fixture data (tests/ui/renderer/fixtures.ts — visibly labeled);
 * no network, no research data.
 *
 * Covered guarantees: byte-identical deterministic output across runs and
 * within one request, CSV equality with the pinned series (exact decimal
 * strings, units, bounds, gaps-with-reasons), static-safety of the emitted
 * SVG, the sha256 record, schema enforcement (strict envelope, corrupt and
 * oversized input, foreign renderer pin) and the no-network source contract.
 */
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  HUGE_DECIMAL,
  definition,
  lowerBoundQuality,
  metric,
  missingQuality,
  observation,
  series,
  view,
} from "../ui/renderer/fixtures";

// jsdom rewrites import.meta.url to an http base, so resolve through the file
// scheme when available and fall back to the vitest working directory (the
// web package root).
const testDir = import.meta.url.startsWith("file:")
  ? path.dirname(fileURLToPath(import.meta.url))
  : process.cwd();
const scriptPath = path.resolve(testDir, "../../scripts/render-charts.mjs");

const CHART_ID = "0f0e0d0c-0b0a-4000-8000-000000000001";

/** Spawn the renderer exactly like the Python boundary does (argv list, stdin). */
function runRenderer(request: unknown | string) {
  const input = typeof request === "string" ? request : JSON.stringify(request);
  return spawnSync(process.execPath, ["--no-warnings", scriptPath], {
    input,
    encoding: "utf8",
    timeout: 60_000,
  });
}

function frozenView() {
  const fixtureMetric = metric("NEAR", "Synthetic export metric (fixture)", "synthetic.metric");
  return view(definition(), [
    series(fixtureMetric, [
      observation("2026-11-01", HUGE_DECIMAL),
      observation("2026-11-02", null, missingQuality("no observation for the period (fixture)")),
      observation("2026-11-03", "2.5", lowerBoundQuality()),
    ]),
  ]);
}

function request(overrides: Record<string, unknown> = {}) {
  return {
    protocol_version: 1,
    width: 640,
    height: 360,
    charts: [{ chart_id: CHART_ID, view: frozenView() }],
    ...overrides,
  };
}

function parseStdout(stdout: string): Record<string, unknown> {
  return JSON.parse(stdout) as Record<string, unknown>;
}

describe("render-charts.mjs (NI-057 static renderer)", () => {
  it("renders the frozen view into SVG plus a CSV equal to the pinned series", () => {
    const result = runRenderer(request());
    expect(result.status).toBe(0);
    expect(result.error).toBeUndefined();
    const output = parseStdout(result.stdout ?? "");
    const chart = (output.charts as Record<string, unknown>[])[0];
    expect(chart.chart_id).toBe(CHART_ID);
    expect(chart.svg as string).toMatch(/^<svg width="640" height="360"/);
    expect(chart.series_count).toBe(1);
    expect(chart.point_count).toBe(3);
    // The CSV rows are the pinned series, byte-exact — no float anywhere.
    expect(chart.csv).toBe(
      [
        "date,series_index,series,unit,value,value_kind,quality,quality_reasons",
        `2026-11-01,0,Synthetic export metric (fixture),NEAR,${HUGE_DECIMAL},,ok,`,
        "2026-11-02,0,Synthetic export metric (fixture),NEAR,,,missing,no observation for the period (fixture)",
        "2026-11-03,0,Synthetic export metric (fixture),NEAR,2.5,lower,ok,",
        "",
      ].join("\n"),
    );
  });

  it("is byte-identical across separate runs", () => {
    // The shared fixtures mint fresh UUIDs per call, so freeze ONE request
    // string and prove: same input bytes -> byte-identical response.
    const input = JSON.stringify(request());
    const first = runRenderer(input);
    const second = runRenderer(input);
    expect(first.status).toBe(0);
    expect(second.status).toBe(0);
    expect(second.stdout).toBe(first.stdout);
  });

  it("is byte-identical when the same chart repeats inside one request", () => {
    const result = runRenderer(
      request({
        charts: [
          { chart_id: CHART_ID, view: frozenView() },
          { chart_id: "0f0e0d0c-0b0a-4000-8000-000000000002", view: frozenView() },
        ],
      }),
    );
    expect(result.status).toBe(0);
    const output = parseStdout(result.stdout ?? "");
    const charts = output.charts as Record<string, unknown>[];
    expect(charts.map((chart) => chart.chart_id)).toEqual([
      CHART_ID,
      "0f0e0d0c-0b0a-4000-8000-000000000002",
    ]);
    expect(charts[0].svg).toBe(charts[1].svg);
    expect(charts[0].csv).toBe(charts[1].csv);
  });

  it("records the sha256 of the request and of every asset", () => {
    const input = JSON.stringify(request());
    const result = runRenderer(input);
    expect(result.status).toBe(0);
    const output = parseStdout(result.stdout ?? "");
    expect(output.protocol_version).toBe(1);
    const renderer = output.renderer as Record<string, unknown>;
    expect(renderer.id).toBe("near-export-chart-renderer@1");
    expect(renderer.echarts_version).toBe("6.1.0");
    expect(typeof renderer.node_version).toBe("string");
    expect(output.input_sha256).toBe(createHash("sha256").update(input, "utf8").digest("hex"));
    const chart = (output.charts as Record<string, unknown>[])[0];
    expect(chart.svg_sha256).toBe(
      createHash("sha256").update(chart.svg as string, "utf8").digest("hex"),
    );
    expect(chart.csv_sha256).toBe(
      createHash("sha256").update(chart.csv as string, "utf8").digest("hex"),
    );
  });

  it("emits a static-safe SVG: no scripts, no remote references, no HTML hosts", () => {
    const result = runRenderer(request());
    expect(result.status).toBe(0);
    const chart = (parseStdout(result.stdout ?? "").charts as Record<string, unknown>[])[0];
    const svg = chart.svg as string;
    expect(svg).toContain('xmlns="http://www.w3.org/2000/svg"'); // namespace, not a fetch
    expect(svg).not.toMatch(/<script/i);
    expect(svg).not.toMatch(/<foreignObject/i);
    expect(svg).not.toMatch(/<image/i);
    expect(svg).not.toMatch(/javascript:/i);
    expect(svg).not.toMatch(/(xlink:)?href\s*=\s*["']?\s*(https?:)?\/\//i);
    expect(svg).not.toMatch(/url\(\s*["']?\s*(https?:)?\/\//i);
    expect(svg).not.toMatch(/data:text\/html/i);
  });

  it("fails with a typed error on corrupt stdin", () => {
    for (const corrupt of ["", "not json", '{"protocol_version": 1', "[1, 2, 3]"]) {
      const result = runRenderer(corrupt);
      expect(result.status).not.toBe(0);
      const output = parseStdout(result.stdout ?? "");
      const error = output.error as Record<string, unknown>;
      expect(["invalid_json", "invalid_payload"]).toContain(error.code);
      expect(error.protocol_version).toBe(1);
      expect(typeof error.message).toBe("string");
    }
  });

  it("rejects schema violations with bounded typed details", () => {
    const cases: [unknown, string][] = [
      [{ ...request(), unexpected_key: true }, "Unrecognized key"], // strict envelope
      [{ ...request(), charts: [{ chart_id: "../../etc/passwd", view: frozenView() }] }, "chart_id"],
      [
        { ...request(), charts: [{ chart_id: CHART_ID, view: { definition: {}, series: [] } }] },
        "definition",
      ],
      [{ ...request(), width: 100_000 }, "width"],
      [{ ...request(), charts: [] }, "charts"],
      [
        {
          ...request(),
          charts: [
            ...Array.from({ length: 201 }, (_, index) => ({
              chart_id: `0f0e0d0c-0b0a-4000-8000-${index.toString(16).padStart(12, "0")}`,
              view: frozenView(),
            })),
          ],
        },
        "charts",
      ],
    ];
    for (const [payload, pathFragment] of cases) {
      const result = runRenderer(payload);
      expect(result.status).toBe(2);
      const error = parseStdout(result.stdout ?? "").error as Record<string, unknown>;
      expect(error.code).toBe("invalid_payload");
      const details = error.details as string[];
      expect(details.length).toBeGreaterThan(0);
      expect(details.length).toBeLessThanOrEqual(20);
      expect(details.join(" ")).toContain(pathFragment);
    }
  });

  it("rejects oversized input before parsing", () => {
    const oversized = `{"pad":"${"x".repeat(5 * 1024 * 1024)}"}`;
    const result = runRenderer(oversized);
    expect(result.status).toBe(2);
    const error = parseStdout(result.stdout ?? "").error as Record<string, unknown>;
    expect(error.code).toBe("invalid_input_size");
    expect(error.message).toContain("4194304"); // the recorded cap
  });

  it("refuses a chart pinned to a foreign renderer instead of redrawing", () => {
    const payload = request();
    const chart = (payload.charts as { view: { definition: Record<string, unknown> } }[])[0];
    chart.view.definition.renderer_version = "other-renderer@9";
    const result = runRenderer(payload);
    expect(result.status).toBe(3);
    const error = parseStdout(result.stdout ?? "").error as Record<string, unknown>;
    expect(error.code).toBe("unsupported_renderer");
  });

  it("stays offline: the script imports no network, process-spawn or eval surface", () => {
    const source = readFileSync(scriptPath, "utf8");
    expect(source).not.toMatch(/\bfetch\s*\(/);
    expect(source).not.toMatch(/XMLHttpRequest/);
    expect(source).not.toMatch(/node:(http|https|net|dns|tls|dgram)\b/);
    expect(source).not.toMatch(/child_process/);
    expect(source).not.toMatch(/\beval\s*\(/);
    expect(source).not.toMatch(/new\s+Function\b/);
    // The only child-process usage in the whole pipeline is the Python side.
    expect(source).not.toMatch(/spawn|execFile|execSync/);
  });
});
