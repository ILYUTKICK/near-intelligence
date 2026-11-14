/**
 * Chart frame tests (NI-010; chrome redesign NI-095/NI-096). All
 * source/quality fixtures are synthetic and labeled — they exercise
 * component behavior, not production data.
 */
import { axe } from "jest-axe";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Button } from "@/components/ui/button";
import type { DataQuality } from "@/components/data-state/quality";
import { ChartFrame } from "@/features/charts/ChartFrame";
import { sanitizeSourceUrl } from "@/features/charts/SourceDrawer";
import type { DataSource } from "@/features/charts/chart-frame-types";
import { DataTable } from "@/features/charts/DataTable";

// Synthetic test fixture — partial lower-bound quality, not production data.
const partialLowerQuality: DataQuality = {
  status: "partial",
  bound_kind: "lower",
  reasons: ["Attribution covers a sample of the market."],
  coverage: { observed: 34, expected: 366 },
  freshness_target_seconds: 3600,
};

// Synthetic test fixture — fake provider shape, not production data.
// license/access are the generated contract's enums (NI-032 alignment);
// the fixture labels live in the name/lineage strings.
const syntheticSource: DataSource = {
  id: "00000000-0000-0000-0000-000000000001",
  name: "Synthetic chain explorer (test fixture)",
  docs_url: "https://docs.example.com/near-feeds",
  verified_at: "2026-11-05T12:00:00Z",
  license_status: "verified",
  access_status: "approved",
  lineage: ["fixture step 1: node export", "fixture step 2: daily aggregation"],
  expected_update_frequency: "daily (fixture)",
  last_success_at: "2026-11-05T06:00:00Z",
};

const syntheticRows = [
  { period: "2026-11-01", value: "≥ 1 234", note: "lower bound (fixture)" },
  { period: "2026-11-02", value: "no observation", note: "gap — not zero" },
];

function renderFrame(overrides?: Partial<Parameters<typeof ChartFrame>[0]>) {
  return render(
    <ChartFrame
      title="Daily fees (synthetic test fixture)"
      units="NEAR / day"
      mode="historical"
      quality={partialLowerQuality}
      metadata={{
        units: "NEAR / day",
        period: "2026-11-01 … 2026-11-02 UTC",
        asOf: "2026-11-02 23:59 UTC",
        limitation: "Lower bounds only — fixture.",
      }}
      summary="Two synthetic days of fees; the second day has no observation, which is a gap, not zero."
      sources={[syntheticSource]}
      sourceDrawer={false}
      definition="Sum of burned fees per UTC day (fixture definition)."
      tableRows={syntheticRows}
      rangeSlot={<Button variant="secondary">Last 7 days</Button>}
      actions={<Button variant="quiet">Save chart</Button>}
      {...overrides}
    >
      <div data-testid="plot-area">plot slot</div>
    </ChartFrame>,
  );
}

describe("ChartFrame", () => {
  it("shows the title, units and the compact status badge (NI-095 chrome)", () => {
    renderFrame();
    expect(screen.getByText("Daily fees (synthetic test fixture)")).toBeInTheDocument();
    expect(screen.getByText("NEAR / day")).toBeInTheDocument();
    // The long mode pill, the quality badge and the visible freshness
    // metadata line are gone from the minimalist chrome.
    expect(screen.queryByText("Historical — pinned version")).not.toBeInTheDocument();
    expect(screen.queryByText(/^Partial:/)).not.toBeInTheDocument();
    // The period/last-observed metadata moved into the sr-only nonvisual
    // block: announced, never visually rendered (NI-095 chrome).
    const metadataText = screen.getByText(/Period: 2026-11-01/);
    expect(metadataText.closest(".sr-only")).not.toBeNull();
  });

  it("keeps the summary and the exact-value table in the DOM as nonvisual semantics", () => {
    // The acceptance rule is preserved through sr-only semantics instead of
    // the visible metadata line: the information stays announced.
    const { container } = renderFrame();
    expect(container.textContent).toContain("Last observed: 2026-11-02 23:59 UTC");
    expect(container.textContent).toContain("≥ 1 234");
    const region = screen.getByRole("region", { name: /data table/ });
    const table = within(region).getByRole("table");
    expect(table).toHaveAccessibleName(/equivalent data/);
    expect(within(table).getByText("no observation")).toBeInTheDocument();
    expect(within(table).getByText(/gap — not zero/)).toBeInTheDocument();
    expect(
      screen.getByText(
        /the second day has no observation, which is a gap, not zero/i,
      ),
    ).toBeInTheDocument();
  });

  it("keeps toolbar controls keyboard reachable", async () => {
    const user = userEvent.setup();
    renderFrame();
    await user.tab();
    expect(screen.getByRole("button", { name: "Last 7 days" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Save chart" })).toHaveFocus();
    expect(await axe(document.body, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  it("renders the source provenance as nonvisual semantics (no visible drawer)", () => {
    const { container } = renderFrame();
    // The visible drawer is gone; the source stays announced in the DOM.
    expect(container.textContent).toContain("Synthetic chain explorer (test fixture)");
    expect(screen.queryByText("Sources & definitions")).not.toBeInTheDocument();
  });

  it("shows the stale notice while retaining last-good values", () => {
    renderFrame({ stale: true, mode: "live" });
    expect(screen.getByText(/Showing the last verified values/)).toBeInTheDocument();
    expect(screen.getByText("Last good values")).toBeInTheDocument();
    expect(screen.queryByText("Live — latest approved data")).not.toBeInTheDocument();
  });
});

describe("Source link sanitization", () => {
  it("renders only http(s) targets as links and withholds the rest", () => {
    expect(sanitizeSourceUrl("https://docs.example.com/a")).toBe("https://docs.example.com/a");
    expect(sanitizeSourceUrl("http://docs.example.com/a")).toBe("http://docs.example.com/a");
    expect(sanitizeSourceUrl("javascript:alert(1)")).toBeNull();
    expect(sanitizeSourceUrl("data:text/html,x")).toBeNull();
    expect(sanitizeSourceUrl("//evil.example.com")).toBeNull();
    expect(sanitizeSourceUrl("not a url")).toBeNull();
    expect(sanitizeSourceUrl("")).toBeNull();
  });

  it("never renders a withheld target as an anchor anywhere in the frame", () => {
    render(
      <ChartFrame
        title="Withheld link fixture"
        mode="historical"
        summary="Fixture."
        sources={[{ ...syntheticSource, docs_url: "javascript:alert(1)" }]}
      >
        <div />
      </ChartFrame>,
    );
    // The malicious target must not become a link anywhere in the document.
    expect(document.querySelector('a[href^="javascript:"]')).toBeNull();
  });
});

describe("DataTable empty rows", () => {
  it("states that emptiness is not zero instead of rendering zero rows", () => {
    render(<DataTable caption="Empty fixture" rows={[]} />);
    expect(screen.getByText(/this is not zero/i)).toBeInTheDocument();
    expect(screen.queryByText(/^0$/)).not.toBeInTheDocument();
  });
});
