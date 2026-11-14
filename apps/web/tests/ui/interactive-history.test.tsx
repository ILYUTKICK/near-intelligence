import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InteractiveHistory } from "@/features/public-research/InteractiveHistory";
import type { ResearchHistory, PeriodSummary } from "@/features/public-research/history-schema";
import { definition, metric, observation, series, view } from "./renderer/fixtures";

vi.mock("@/features/charts/renderer/ChartView", () => ({ ChartView: ({ definition: def }: { definition: { title: string } }) => <figure>{def.title}</figure> }));
const summary: PeriodSummary = {
  start: "2026-11-01", end: "2026-11-06", expected_days: 5,
  volume_days: 5, fee_days: 3, matched_days: 3, zero_fee_days: 1,
  volume_usd: "10000.123456789", gross_fees_usd: "3.5", matched_volume_usd: "3500",
  matched_gross_fees_usd: "3.5", effective_gross_fee_bps: "10", complete: false,
};
function history(): ResearchHistory {
  const volume = view(definition({ title: "Synthetic volume history (fixture)" }), [series(metric("USD", "Synthetic volume", "synthetic_volume"), [observation("2026-11-01", "1000")])]);
  const fees = view(definition({ title: "Synthetic fee history (fixture)" }), [series(metric("USD", "Synthetic fees", "synthetic_fees"), [observation("2026-11-01", "1")])]);
  return { volume, fees, purchases: null, summary, monthly: [summary], quarterly: [summary], limitations: ["Synthetic fixture — no production data."] };
}
afterEach(() => vi.unstubAllGlobals());

describe("interactive research history", () => {
  it("shows exact server calculations, coverage and partial periods without treating absent purchases as zero", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json(history())));
    render(<InteractiveHistory />);
    await screen.findByText("Synthetic volume history (fixture)");
    expect(screen.getByText(/Volume: 5 days · fees: 3 days · matched: 3 days/)).toBeInTheDocument();
    expect(screen.getByText(/Daily purchase history is unavailable/)).toBeInTheDocument();
    const table = screen.getByRole("region", { name: "Monthly history calculations" });
    expect(table.textContent).toContain("10 000.123456789");
    expect(table).toHaveTextContent("Partial");
    await userEvent.click(screen.getByRole("button", { name: "Quarterly" }));
    expect(screen.getByRole("region", { name: "Quarterly history calculations" })).toBeInTheDocument();
  });

  it("pins period changes to the resolved immutable dataset and validates custom dates", async () => {
    const payload = history();
    const fetcher = vi.fn(async () => Response.json(payload));
    vi.stubGlobal("fetch", fetcher);
    render(<InteractiveHistory />);
    await screen.findByText("Synthetic volume history (fixture)");
    await userEvent.click(screen.getByRole("button", { name: "Last 90 days" }));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    const request = fetcher.mock.calls[1] as unknown as [Request];
    const url = new URL(request[0].url);
    expect(url.searchParams.get("dataset_version")).toBe(payload.volume.dataset.id);
    expect(url.searchParams.get("end")).toBe(payload.volume.dataset.end);
    const form = screen.getByRole("button", { name: "Apply period" }).closest("form")!;
    await userEvent.clear(within(form).getByLabelText("Start date (UTC)"));
    await userEvent.type(within(form).getByLabelText("Start date (UTC)"), "2026-11-08");
    await userEvent.click(within(form).getByRole("button", { name: "Apply period" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Choose an end after the start");
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("keeps failure explicit and retries without fabricated history", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(Response.json({}, { status: 503 })).mockResolvedValue(Response.json(history()));
    vi.stubGlobal("fetch", fetcher);
    render(<InteractiveHistory />);
    expect(await screen.findByRole("alert")).toHaveTextContent("History is unavailable");
    expect(screen.queryByText("Synthetic volume history (fixture)")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry history" }));
    await screen.findByText("Synthetic volume history (fixture)");
  });
});
