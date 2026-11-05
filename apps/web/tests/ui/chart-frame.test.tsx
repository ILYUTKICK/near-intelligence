/**
 * Chart frame tests (NI-010). All source/quality fixtures are synthetic and
 * labeled — they exercise component behavior, not production data.
 */
import { axe } from "jest-axe";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

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
const syntheticSource: DataSource = {
  id: "00000000-0000-0000-0000-000000000001",
  name: "Synthetic chain explorer (test fixture)",
  docs_url: "https://docs.example.com/near-feeds",
  verified_at: "2026-11-05T12:00:00Z",
  license_status: "CC BY 4.0 (fixture)",
  access_status: "public, rate-limited (fixture)",
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
  it("shows title, units, mode, quality badge and freshness metadata", () => {
    renderFrame();
    expect(screen.getByText("Daily fees (synthetic test fixture)")).toBeInTheDocument();
    expect(screen.getByText(/^Units:/)).toHaveTextContent("NEAR / day");
    expect(screen.getByText("Historical — pinned version")).toBeInTheDocument();
    expect(screen.getByTitle(/^Partial:/)).toBeInTheDocument();
    expect(screen.getByText(/Period: 2026-11-01 … 2026-11-02 UTC\./)).toBeInTheDocument();
    expect(screen.getByText(/Last observed: 2026-11-02 23:59 UTC\./)).toBeInTheDocument();
  });

  it("keeps source timestamps and bounds present in the metadata line", () => {
    // The acceptance rule: these never disappear on small screens — they are
    // unconditional (wrapping) elements, so their presence is asserted here.
    const { container } = renderFrame();
    expect(container.textContent).toContain("Last observed: 2026-11-02 23:59 UTC");
    expect(container.textContent).toContain("≥ 1 234");
  });

  it("renders the equivalent data table inside a labeled scroll region", () => {
    renderFrame();
    const region = screen.getByRole("region", { name: /data table/ });
    expect(region).toBeInTheDocument();
    const table = within(region).getByRole("table");
    // The sr-only <caption> becomes the table's accessible name.
    expect(table).toHaveAccessibleName(/equivalent data/);
    expect(within(table).getByText("no observation")).toBeInTheDocument();
    expect(within(table).getByText(/gap — not zero/)).toBeInTheDocument();
  });

  it("announces the accessible summary", () => {
    renderFrame();
    const summary = screen.getByText(
      /the second day has no observation, which is a gap, not zero/i,
    );
    expect(summary).toBeInTheDocument();
  });

  it("keeps toolbar controls keyboard reachable and opens the source drawer", async () => {
    const user = userEvent.setup();
    renderFrame();
    await user.tab();
    expect(screen.getByRole("button", { name: "Last 7 days" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Save chart" })).toHaveFocus();

    // Walk focus forward until the drawer trigger (details/table sit between).
    const trigger = screen.getByText("Sources & definitions");
    for (let i = 0; i < 10 && document.activeElement !== trigger; i += 1) {
      await user.tab();
    }
    expect(trigger).toHaveFocus();

    await user.keyboard("{Enter}");
    const dialog = await screen.findByRole("dialog", { name: "Sources and definitions" });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText("Synthetic chain explorer (test fixture)")).toBeInTheDocument();
    expect(within(dialog).getByText("CC BY 4.0 (fixture)")).toBeInTheDocument();
    expect(within(dialog).getByText("2026-11-05T06:00:00Z")).toBeInTheDocument();
    expect(within(dialog).getByText("fixture step 1: node export")).toBeInTheDocument();
    expect(await axe(document.body, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  it("shows the stale notice while retaining last-good values", () => {
    renderFrame({ stale: true, mode: "live" });
    expect(screen.getByText(/Showing the last verified values/)).toBeInTheDocument();
    expect(screen.getByText("Live — latest approved data")).toBeInTheDocument();
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

  it("renders a withheld link as inert text, not an anchor", async () => {
    const user = userEvent.setup();
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
    await user.click(screen.getByText("Sources & definitions"));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    // The malicious target must not become a link anywhere in the document.
    expect(document.querySelector('a[href^="javascript:"]')).toBeNull();
    expect(screen.getByText(/link withheld/)).toBeInTheDocument();
  });
});

describe("DataTable empty rows", () => {
  it("states that emptiness is not zero instead of rendering zero rows", () => {
    render(<DataTable caption="Empty fixture" rows={[]} />);
    expect(screen.getByText(/this is not zero/i)).toBeInTheDocument();
    expect(screen.queryByText(/^0$/)).not.toBeInTheDocument();
  });
});
