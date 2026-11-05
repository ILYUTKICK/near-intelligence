/**
 * State matrix tests for the NI-009 data-state components.
 * All fixtures below are synthetic and labeled as such — they exercise
 * component behavior and are never presented as production data.
 */
import { axe } from "jest-axe";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  EmptyState,
  ErrorPanel,
  LoadingPanel,
  StaleNotice,
  UnavailableState,
} from "@/components/data-state/DataState";
import { QualityBadge } from "@/components/data-state/QualityBadge";
import { SaveStatus } from "@/components/data-state/SaveStatus";
import type { DataQuality } from "@/components/data-state/quality";

// Synthetic test fixture — missing-data quality, not production data.
const missingQuality: DataQuality = {
  status: "missing",
  bound_kind: null,
  reasons: ["No observations collected for this period."],
  coverage: { observed: 0, expected: 366 },
  freshness_target_seconds: null,
};

// Synthetic test fixture — partial lower-bound quality, not production data.
const partialQuality: DataQuality = {
  status: "partial",
  bound_kind: "lower",
  reasons: ["Attribution covers a sample of the market."],
  coverage: { observed: 34, expected: 366 },
  freshness_target_seconds: 3600,
};

// Synthetic test fixture — stale quality, not production data.
const staleQuality: DataQuality = {
  status: "stale",
  bound_kind: "exact",
  reasons: ["Source last retrieved 3 hours ago."],
  coverage: { observed: 366, expected: 366 },
  freshness_target_seconds: 900,
};

const metadata = {
  units: "NEAR / day",
  period: "2026-08-06 … 2026-11-03 UTC",
  asOf: "2026-11-03 23:59 UTC",
  limitation: "Sampled attribution, not full-market revenue.",
};

describe("Empty state", () => {
  it("explains emptiness and never renders a zero value", async () => {
    render(<EmptyState metadata={metadata} />);
    expect(screen.getByRole("status")).toHaveTextContent(/no data for this selection/i);
    expect(screen.getByText(/empty result is not zero/i)).toBeInTheDocument();
    // The acceptance rule: an empty array must not surface as the number zero.
    expect(screen.queryByText(/^0$/)).not.toBeInTheDocument();
    // Metadata (units/date/limitation) is retained in the empty state.
    expect(screen.getByText("NEAR / day")).toBeInTheDocument();
    expect(screen.getByText(/Sampled attribution/)).toBeInTheDocument();
    expect(await axe(document.body, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  it("renders a true zero when the data genuinely is zero", () => {
    // Contrast case for the matrix: a real zero value is displayed as zero,
    // which is exactly why the empty state must never collapse into one.
    const value = 0;
    render(<p className="tabular-nums">{value} NEAR</p>);
    expect(screen.getByText("0 NEAR")).toBeInTheDocument();
  });
});

describe("Unavailable state", () => {
  it("shows reasons and metadata and never substitutes a zero", async () => {
    render(<UnavailableState quality={missingQuality} metadata={metadata} />);
    const panel = screen.getByRole("status");
    expect(panel).toHaveTextContent(/is not zero/i);
    expect(panel).toHaveTextContent("No observations collected for this period.");
    expect(screen.getByText("NEAR / day")).toBeInTheDocument();
    expect(screen.queryByText(/^0$/)).not.toBeInTheDocument();
    expect(await axe(document.body, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});

describe("Quality badge", () => {
  it("labels every status and bound kind in text, not color alone", () => {
    const expectedLabels = {
      ok: "Complete",
      partial: "Partial",
      missing: "No data",
      stale: "Stale",
      unavailable: "Unavailable",
      revised: "Revised",
    } as const;
    for (const [status, label] of Object.entries(expectedLabels)) {
      const { unmount } = render(
        <QualityBadge quality={{ ...missingQuality, status: status as DataQuality["status"] }} />,
      );
      // Match the badge root by its title ("Label: description") and assert
      // the visible text — status is text+glyph, never color alone.
      const badge = screen.getByTitle(new RegExp(`^${label}:`));
      expect(badge).toHaveTextContent(label);
      unmount();
    }
    const { unmount } = render(<QualityBadge quality={partialQuality} />);
    const partialBadge = screen.getByTitle(/^Partial:/);
    expect(partialBadge).toHaveTextContent("lower bound");
    expect(partialBadge).toHaveTextContent("34/366");
    unmount();
  });
});

describe("Stale notice", () => {
  it("retains values metadata and states the freshness target in text", async () => {
    render(
      <div>
        <StaleNotice quality={staleQuality} metadata={metadata} />
        <p className="tabular-nums">1 234 567 NEAR</p>
      </div>,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/freshness target 15 min/);
    expect(screen.getByText(/2026-11-03 23:59 UTC/)).toBeInTheDocument();
    expect(screen.getByText("1 234 567 NEAR")).toBeInTheDocument();
    expect(await axe(document.body, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});

describe("Error panel retry", () => {
  it("fires retry once per click even under rapid double clicks", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    function Panel() {
      const [pending, setPending] = useState(false);
      return (
        <ErrorPanel
          message="Source request timed out."
          onRetry={() => {
            onRetry();
            // Real flows flip pending while the request is in flight.
            setPending(true);
          }}
          retryPending={pending}
        />
      );
    }
    render(<Panel />);
    const retry = screen.getByRole("button", { name: "Retry" });
    await user.click(retry);
    await user.dblClick(retry);
    expect(onRetry).toHaveBeenCalledTimes(1);
    expect(retry).toBeDisabled();
    expect(await axe(document.body, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});

describe("Loading panel and save status", () => {
  it("announces loading politely and keeps save status persistent with live updates", async () => {
    const { rerender } = render(
      <div>
        <LoadingPanel label="Loading chart data" />
        <SaveStatus status="idle" />
      </div>,
    );
    expect(screen.getByRole("status", { name: "Loading chart data" })).toBeInTheDocument();
    expect(screen.getByText("All changes saved")).toBeInTheDocument();

    rerender(
      <div>
        <LoadingPanel label="Loading chart data" />
        <SaveStatus status="saving" />
      </div>,
    );
    expect(screen.getByText("Saving…")).toBeInTheDocument();

    rerender(
      <div>
        <LoadingPanel label="Loading chart data" />
        <SaveStatus status="saved" savedAt="23:15:02 UTC" />
      </div>,
    );
    expect(screen.getByText("Saved at 23:15:02 UTC")).toBeInTheDocument();

    rerender(
      <div>
        <LoadingPanel label="Loading chart data" />
        <SaveStatus status="error" />
      </div>,
    );
    expect(screen.getByText(/Save failed/)).toBeInTheDocument();
    expect(screen.getByText(/Save failed/)).toHaveClass("text-danger");
  });
});
