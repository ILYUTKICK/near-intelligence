/**
 * NI-057 — static chart asset renderer for frozen export evidence.
 *
 * Invoked by the Python export boundary (apps/api/src/near_api/exports/charts.py)
 * as a subprocess: one strict JSON request on STDIN, one strict JSON response on
 * STDOUT, non-zero exit with a typed error object on any refusal. There is no
 * shell, no network, no filesystem access beyond the module graph below, no
 * eval and no HTML/remote-URL input anywhere in the schema — a request that does
 * not conform is rejected with a typed error instead of being rendered.
 *
 * The chart is rendered from the FROZEN `ChartViewResponse` payload embedded in
 * the NI-056 export IR: series, units and quality are exactly the pinned view
 * (no refetch, no latest lookup). The ECharts option is built by the NI-033
 * pure builder (`buildChart(view, { interactions: false })`, CHART_SYSTEM.md),
 * imported directly as TypeScript through Node's erasable-syntax type stripping
 * plus a tiny resolution hook — the renderer is reused, not reimplemented.
 *
 * Determinism: same input bytes -> byte-identical SVG and CSV. ECharts' SVG
 * painter allocates global zrender style-class and clip-path counters per
 * process/call (`zr3-cls-7`, `zr1-c0`), so every emitted identifier token is
 * rewritten to a canonical first-appearance alias inside `class="…"`, `id="…"`,
 * `url(#…)`, `href="#…"` and `<style>` selectors; nothing else is touched.
 * The rewritten identifiers keep their document-internal consistency (each
 * distinct source token maps to exactly one alias), so the SVG stays valid.
 *
 * Assets: per chart, the SVG plus a normalized long-format CSV of the pinned
 * series — every point row carries the exact decimal string verbatim (never a
 * float), the unit, the bound kind and the quality status/reasons; missing
 * points export as empty values with their recorded reason (missing is not
 * zero). SHA-256 hashes of the raw request and of every asset are part of the
 * response so the Python boundary can pin the renderer identity and verify the
 * byte-exact contract (REPRODUCIBILITY).
 */
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { createRequire, registerHooks } from "node:module";
import path from "node:path";

import { z } from "zod";

/** Bumped only for a breaking stdin/stdout protocol change. */
export const RENDERER_PROTOCOL_VERSION = 1;
/** Stable identity of this renderer contract, recorded in export manifests. */
export const RENDERER_ID = "near-export-chart-renderer@1";

const MAX_INPUT_BYTES = 4 * 1024 * 1024;
const MAX_ASSET_CHARS = 8 * 1024 * 1024;
const MAX_CHARTS = 200;
const MAX_SERIES = 32;
const MAX_POINTS = 2000;
const MAX_ERROR_DETAILS = 20;
const WIDTH_BOUNDS = [120, 2000];
const HEIGHT_BOUNDS = [80, 2000];

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

/**
 * Resolution hook: the NI-033 renderer sources use the repo's extensionless
 * relative imports, which Node's ESM resolution does not append `.ts` to.
 * The hook only affects relative specifiers without an extension and only
 * when the `.ts` sibling exists — package specifiers are untouched.
 */
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith(".") && !path.extname(specifier)) {
      try {
        return nextResolve(`${specifier}.ts`, context);
      } catch {
        // No .ts sibling — fall through to default resolution.
      }
    }
    return nextResolve(specifier, context);
  },
});

// Registered hooks apply to these dynamic imports; the option builder stays
// the single rendering implementation (NI-033), the ECharts runtime imports
// are modular per ADR-019 and touch no browser global.
const { buildChart } = await import("../src/features/charts/renderer/option-builder.ts");
const { utcDateLabel } = await import("../src/features/charts/renderer/format.ts");
const { init, use: registerComponents } = await import("echarts/core");
const charts = await import("echarts/charts");
const components = await import("echarts/components");
const renderers = await import("echarts/renderers");
const features = await import("echarts/features");

registerComponents([
  charts.LineChart,
  charts.BarChart,
  charts.ScatterChart,
  components.GridComponent,
  components.TooltipComponent,
  components.AriaComponent,
  components.LegendComponent,
  components.AxisPointerComponent,
  features.LegacyGridContainLabel,
  renderers.SVGRenderer,
]);

const echartsPackage = createRequire(import.meta.url)("echarts/package.json");

// ---------------------------------------------------------------------------
// Typed stdin schema (render boundary over the generated NI-032 contracts, the
// established catalog-schema.ts pattern). Only fields the render consumes are
// declared; unknown envelope keys are rejected outright, unknown view fields
// are stripped and can never reach the SVG. No URL, HTML or code field exists.
// ---------------------------------------------------------------------------

const dataQualitySchema = z.object({
  status: z.enum(["ok", "partial", "missing", "stale", "unavailable", "revised"]),
  bound_kind: z.enum(["exact", "estimate", "lower", "upper"]).nullable(),
  reasons: z.array(z.string().min(1)).max(20),
});

const observationSchema = z.object({
  start: z.string().min(1),
  end: z.string().min(1),
  // Exact decimal string exactly as pinned (never a number, never reformatted).
  value: z.string().min(1).nullable(),
  quality: dataQualitySchema,
});

const seriesSchema = z.object({
  metric: z.object({
    id: z.string().min(1),
    title: z.string().min(1),
    unit: z.string().min(1),
  }),
  points: z.array(observationSchema).max(MAX_POINTS),
});

const definitionSchema = z.object({
  title: z.string().min(1).max(200),
  visualization_type: z.enum(["line", "area", "bar", "scatter", "panels"]),
  renderer_version: z.string().min(1),
});

const chartViewSchema = z.object({
  definition: definitionSchema,
  series: z.array(seriesSchema).max(MAX_SERIES),
});

const requestSchema = z.strictObject({
  protocol_version: z.literal(RENDERER_PROTOCOL_VERSION),
  width: z.number().int().min(WIDTH_BOUNDS[0]).max(WIDTH_BOUNDS[1]),
  height: z.number().int().min(HEIGHT_BOUNDS[0]).max(HEIGHT_BOUNDS[1]),
  charts: z
    .array(
      z.object({
        chart_id: z.string().regex(UUID_PATTERN),
        view: chartViewSchema,
      }),
    )
    .min(1)
    .max(MAX_CHARTS),
});

// ---------------------------------------------------------------------------
// Typed failure protocol
// ---------------------------------------------------------------------------

class RenderError extends Error {
  constructor(code, message, details = []) {
    super(message);
    this.code = code;
    this.details = details;
  }
}

/** Strict JSON error object on stdout, short line on stderr, non-zero exit. */
function fail(error, exitCode) {
  const payload = {
    error: {
      protocol_version: RENDERER_PROTOCOL_VERSION,
      code: error.code,
      message: error.message,
      details: error.details.slice(0, MAX_ERROR_DETAILS),
    },
  };
  process.stdout.write(`${JSON.stringify(payload)}\n`);
  process.stderr.write(`render-charts: ${error.code}: ${error.message}\n`);
  process.exit(exitCode);
}

const INPUT_EXIT_CODE = 2;
const RENDER_EXIT_CODE = 3;
const INTERNAL_EXIT_CODE = 4;

function invalidInput(code, message, details = []) {
  return () => fail(new RenderError(code, message, details), INPUT_EXIT_CODE);
}

// ---------------------------------------------------------------------------
// SVG post-processing: canonical identifiers + static-safety assertions
// ---------------------------------------------------------------------------

const ZR_TOKEN = /^zr\d+(?:-[\w]+)*$/;
const IDENTIFIER_CONTEXT =
  /(class|id)="([^"]*)"|url\(#([^)]+)\)|(?:xlink:)?href="(#[^"]*)"/g;
const STYLE_BLOCK = /(<style[^>]*>)([\s\S]*?)(<\/style>)/g;
const CSS_SELECTOR_TOKEN = /([.#])zr\d+(?:-[\w]+)*/g;

/**
 * Rewrite zrender's globally counter-derived identifiers (`zr3-cls-7`,
 * `zr1-c0`) to canonical first-appearance aliases so repeated renders are
 * byte-identical. Each distinct source token maps to exactly one alias, so
 * the class/style/clip-path/use references stay internally consistent.
 */
function normalizeSvgIdentifiers(svg) {
  const aliases = new Map();
  const aliasOf = (token) => {
    if (!ZR_TOKEN.test(token)) {
      return token;
    }
    if (!aliases.has(token)) {
      aliases.set(token, `zr${aliases.size}-x${aliases.size}`);
    }
    return aliases.get(token);
  };
  const mapAttributeValue = (value) =>
    value.split(/\s+/).map(aliasOf).join(" ");
  return svg
    .replace(IDENTIFIER_CONTEXT, (_match, attribute, value, urlId, hrefId) => {
      if (attribute) {
        return `${attribute}="${mapAttributeValue(value)}"`;
      }
      if (urlId !== undefined) {
        return `url(#${aliasOf(urlId)})`;
      }
      return `href="${aliasOf(hrefId.slice(1))}"`;
    })
    .replace(STYLE_BLOCK, (_match, open, body, close) => {
      const selectors = body.replace(
        CSS_SELECTOR_TOKEN,
        (_m, prefix) => `${prefix}${aliasOf(_m.slice(1))}`,
      );
      return `${open}${selectors}${close}`;
    });
}

/** The rendered SVG must stay static: no scripts, no remote references, no HTML hosts. */
const UNSAFE_SVG_PATTERNS = [
  [/<script/i, "script element"],
  [/<foreignobject/i, "foreignObject element"],
  [/<image/i, "image element"],
  [/javascript:/i, "javascript URL"],
  [/href\s*=\s*["']?\s*(?:https?:)?\/\//i, "remote reference"],
  [/url\(\s*["']?\s*(?:https?:)?\/\//i, "remote reference"],
  [/data:text\/html/i, "HTML data URL"],
];

function assertSvgStaticSafety(svg, chartId) {
  for (const [pattern, label] of UNSAFE_SVG_PATTERNS) {
    if (pattern.test(svg)) {
      throw new RenderError(
        "unsafe_svg_output",
        `The rendered SVG for chart ${chartId} contains a forbidden ${label}`,
        [`charts.${chartId}.svg`],
      );
    }
  }
}

// ---------------------------------------------------------------------------
// Rendering (frozen view in, deterministic assets out)
// ---------------------------------------------------------------------------

function renderSvg(view, width, height, chartId) {
  const built = buildChart(view, { interactions: false, animation: false });
  if (built.kind !== "ok") {
    throw new RenderError(
      "unsupported_renderer",
      `Chart ${chartId} is pinned to renderer ${built.rendererVersion}; this renderer provides ${built.expected}`,
      [`charts.${chartId}.view.definition.renderer_version`],
    );
  }
  const chart = init(null, null, { renderer: "svg", ssr: true, width, height });
  try {
    chart.setOption(built.option);
    const svg = normalizeSvgIdentifiers(chart.renderToSVGString());
    assertSvgStaticSafety(svg, chartId);
    if (svg.length > MAX_ASSET_CHARS) {
      throw new RenderError(
        "asset_size_exceeded",
        `The rendered SVG for chart ${chartId} exceeds the ${MAX_ASSET_CHARS} character bound`,
        [`charts.${chartId}.svg`],
      );
    }
    return svg;
  } finally {
    chart.dispose();
  }
}

function csvField(value) {
  return /[\r\n,"]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value;
}

/**
 * Normalized long-format CSV of the pinned series: one row per point, the
 * exact decimal string verbatim, unit, bound kind, quality status and
 * reasons. Rows are ordered by (UTC date, series response order, point
 * order) — deterministic and lossless; nothing is deduplicated or filled.
 */
function chartCsv(view) {
  const rows = [];
  view.series.forEach((series, seriesIndex) => {
    series.points.forEach((point, pointIndex) => {
      rows.push({
        date: utcDateLabel(point.start),
        seriesIndex,
        pointIndex,
        series: series.metric.title,
        unit: series.metric.unit,
        value: point.value === null ? "" : point.value,
        valueKind: point.quality.bound_kind ?? "",
        quality: point.quality.status,
        reasons: point.quality.reasons.join("; "),
      });
    });
  });
  rows.sort((left, right) =>
    left.date.localeCompare(right.date) ||
    left.seriesIndex - right.seriesIndex ||
    left.pointIndex - right.pointIndex);
  const header = "date,series_index,series,unit,value,value_kind,quality,quality_reasons";
  const lines = rows.map((row) =>
    [row.date, String(row.seriesIndex), row.series, row.unit, row.value, row.valueKind, row.quality, row.reasons]
      .map(csvField)
      .join(","));
  const csv = `${[header, ...lines].join("\n")}\n`;
  if (csv.length > MAX_ASSET_CHARS) {
    throw new RenderError(
      "asset_size_exceeded",
      `The normalized CSV exceeds the ${MAX_ASSET_CHARS} character bound`,
      ["csv"],
    );
  }
  return csv;
}

function sha256(text) {
  return createHash("sha256").update(text, "utf8").digest("hex");
}

function render() {
  const raw = readFileSync(0);
  if (raw.length > MAX_INPUT_BYTES) {
    fail(
      new RenderError(
        "invalid_input_size",
        `The request is ${raw.length} bytes; the renderer accepts at most ${MAX_INPUT_BYTES}`,
      ),
      INPUT_EXIT_CODE,
    );
  }
  let parsedJson;
  try {
    parsedJson = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(raw));
  } catch {
    fail(
      new RenderError("invalid_json", "The request is not valid UTF-8 JSON"),
      INPUT_EXIT_CODE,
    );
  }
  const parsed = requestSchema.safeParse(parsedJson);
  if (!parsed.success) {
    fail(
      new RenderError(
        "invalid_payload",
        "The request does not match the renderer schema",
        parsed.error.issues.slice(0, MAX_ERROR_DETAILS).map(
          (issue) => issue.path.length === 0
            ? issue.message
            : `${issue.path.join(".")}: ${issue.message}`,
        ),
      ),
      INPUT_EXIT_CODE,
    );
  }

  const renderedCharts = [];
  try {
    for (const item of parsed.data.charts) {
      const svg = renderSvg(item.view, parsed.data.width, parsed.data.height, item.chart_id);
      const csv = chartCsv(item.view);
      renderedCharts.push({
        chart_id: item.chart_id,
        svg,
        svg_sha256: sha256(svg),
        csv,
        csv_sha256: sha256(csv),
        series_count: item.view.series.length,
        point_count: item.view.series.reduce((sum, series) => sum + series.points.length, 0),
      });
    }
  } catch (error) {
    if (error instanceof RenderError) {
      fail(error, RENDER_EXIT_CODE);
    }
    fail(
      new RenderError(
        "render_failure",
        error instanceof Error ? error.message : "The chart could not be rendered",
      ),
      RENDER_EXIT_CODE,
    );
  }

  const response = {
    protocol_version: RENDERER_PROTOCOL_VERSION,
    renderer: {
      id: RENDERER_ID,
      echarts_version: echartsPackage.version,
      node_version: process.versions.node,
    },
    input_sha256: createHash("sha256").update(raw).digest("hex"),
    charts: renderedCharts,
  };
  process.stdout.write(`${JSON.stringify(response)}\n`);
}

try {
  render();
} catch (error) {
  fail(
    new RenderError(
      "internal_error",
      error instanceof Error ? error.message : "Unexpected renderer failure",
    ),
    INTERNAL_EXIT_CODE,
  );
}
