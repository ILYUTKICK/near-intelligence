/**
 * NI-060 read-only share viewer tests (synthetic fixtures, visibly labeled):
 * the frozen projection renders statically (never the editor), charts render
 * from the controlled frozen view with their exact-value tables and sources,
 * the denied state is one honest shape for every failure reason, and the
 * payload validation boundary refuses private or malformed content instead
 * of rendering it.
 */
import { axe } from "jest-axe";
import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ShareViewer } from "@/features/shares/ShareViewer";
import { shareProjectionSchema, type ShareProjectionPayload } from "@/features/shares/share-schema";
import { definition, metric, observation, series, okQuality } from "./renderer/fixtures";

const CHART_BLOCK_ID = "44444444-4444-4444-8444-444444444444";

function viewerProjection(): ShareProjectionPayload {
  const chartMetric = metric("NEAR", "Fixture metric (synthetic)", "fixture.metric");
  const chartSeries = series(chartMetric, [
    observation("2026-11-01", "12.5"),
    observation("2026-11-02", null),
  ], { start: "2026-11-01", end: "2026-11-06" });
  const view = {
    // The generated contract marks `unavailable_reason` optional (the API
    // defaults it); the render-boundary schema requires the resolved shape.
    definition: { ...definition(), unavailable_reason: null },
    selection: chartSeries.selection,
    dataset: chartSeries.dataset,
    series: [chartSeries],
    resolved_at: "2026-11-06T12:00:00Z",
    context_hash: "b".repeat(64),
    quality: okQuality(),
  };
  return {
    share_projection_version: 1,
    document: {
      title: "Fixture shared research (synthetic)",
      revision: 7,
      schema_version: 1,
      content_sha256: "a".repeat(64),
      created_at: "2026-11-01T09:00:00Z",
      limitations: "Frozen read-only publication of one research revision (fixture).",
    },
    blocks: [
      { block_type: "paragraph", block_id: "11111111-1111-4111-8111-111111111111",
        runs: [{ type: "text", text: "Fixture intro ", marks: [] },
               { type: "text", text: "with emphasis", marks: [{ type: "bold" }] }] },
      { block_type: "heading", block_id: "22222222-2222-4222-8222-222222222222", level: 1,
        runs: [{ type: "text", text: "Findings", marks: [] }] },
      { block_type: "hypothesis", block_id: "33333333-3333-4333-8333-333333333333",
        statement: "Fixture hypothesis statement", assessment: "untested" },
      { block_type: "liveChart", block_id: CHART_BLOCK_ID,
        chart_definition_version_id: "55555555-5555-4555-8555-555555555555",
        mode: "live",
        selection: { start: "2026-11-01", end: "2026-11-06", frequency: "day", filters: {} },
        observed_dataset_version_id: "66666666-6666-4666-8666-666666666666",
        view },
    ],
    sources: [{ source_id: "SRC-FIXTURE", name: "Fixture source (synthetic)" }],
    model_runs: [{ run_id: "77777777-7777-4777-8777-777777777777", spec_id: "fixture.spec", spec_version: 1 }],
    citations: [],
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ShareViewer (read-only rendering)", () => {
  it("renders the frozen content statically with provenance and limitations", async () => {
    render(<ShareViewer projection={viewerProjection()} />);
    const viewer = screen.getByTestId("share-viewer");
    expect(within(viewer).getByRole("heading", { level: 1 })).toHaveTextContent("Fixture shared research");
    expect(viewer).toHaveTextContent(/Revision 7/);
    expect(screen.getByTestId("share-hypothesis")).toHaveTextContent("Fixture hypothesis statement");
    // The chart renders as a frozen figure (no loader/refresh affordances)
    // and its exact-value table carries the exact decimal strings.
    const chart = screen.getByTestId("share-chart");
    expect(chart).toHaveTextContent(/Frozen chart/);
    expect(chart).toHaveTextContent("12.5");
    expect(chart).toHaveTextContent(/never refreshes/);
    // No chart data loading indicator: the view is controlled.
    expect(screen.queryByText("Loading chart data")).not.toBeInTheDocument();
    // The registries section lists the sanitized source and the run reference.
    expect(screen.getByTestId("share-registries")).toHaveTextContent("SRC-FIXTURE");
    expect(screen.getByTestId("share-registries")).toHaveTextContent("fixture.spec");
    // The limitations line closes the page.
    expect(screen.getByTestId("share-viewer")).toHaveTextContent(
      "Frozen read-only publication of one research revision (fixture).");
    // The token never exists inside the viewer state: the projection carries
    // no owner or private identifiers at all.
    expect(viewer.textContent).not.toMatch(/owner_id|author|document_id/);
    // The exact-value table renders synchronously with the controlled view;
    // wait for it so the async chart mount has settled before the axe pass.
    await screen.findByText("12.5");
    const results = await axe(screen.getByTestId("share-viewer"));
    expect(results).toHaveNoViolations();
  });

  it("renders a list block and evidence reference without any editor surface", () => {
    const projection = viewerProjection();
    projection.blocks.push(
      { block_type: "bullet_list", block_id: "12121212-1212-4212-8212-121212121212",
        items: [{ type: "list_item", content: [
          { type: "paragraph", content: [{ type: "text", text: "Fixture bullet", marks: [] }] }] }] },
      { block_type: "evidence", block_id: "13131313-1313-4313-8313-131313131313",
        classification: "supporting", target_kind: "model_run",
        target_ref: "77777777-7777-4777-8777-777777777777" },
    );
    render(<ShareViewer projection={projection} />);
    expect(screen.getAllByRole("list").some((list) => list.textContent?.includes("Fixture bullet"))).toBe(true);
    expect(screen.getByTestId("share-evidence")).toHaveTextContent(/published model run/);
    // No editable region of any kind: contenteditable/textbox must not exist.
    expect(document.querySelector("[contenteditable='true']")).toBeNull();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    // No refresh or latest-data affordances.
    expect(screen.queryByRole("button", { name: /refresh/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /latest/i })).not.toBeInTheDocument();
  });
});

describe("Share projection validation boundary", () => {
  it("accepts the exact fixture shape", () => {
    expect(shareProjectionSchema.safeParse(viewerProjection()).success).toBe(true);
  });

  it("rejects a payload carrying a private identifier key", () => {
    const leaking = viewerProjection() as Record<string, unknown>;
    leaking.document = { ...(leaking.document as object), owner_id: "99999999-9999-4999-8999-999999999999" };
    expect(shareProjectionSchema.safeParse(leaking).success).toBe(false);
  });

  it("rejects a payload with a wrong projection version", () => {
    const drifted = viewerProjection() as Record<string, unknown>;
    drifted.share_projection_version = 2;
    expect(shareProjectionSchema.safeParse(drifted).success).toBe(false);
  });
});
