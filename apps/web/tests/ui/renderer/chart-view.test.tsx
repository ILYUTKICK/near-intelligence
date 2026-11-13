/**
 * ChartView integration tests (NI-033) — the reusable renderer that public
 * and editor contexts share. Uses a recording fake chart factory (the real
 * ECharts mount is exercised in the real-module smoke test) and synthetic
 * fixtures only. Covers: data-table integration with exact values, missing
 * gaps, bound labels, large decimals, honest loading/empty/unavailable/error
 * states, stale-request cancellation, keyboard/touch range controls,
 * metadata/units survival across range changes and lazy-mount/dispose
 * resource cleanup.
 */
import { axe } from "jest-axe";
import { fireEvent, render, screen, waitFor, within, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Button } from "@/components/ui/button";
import { ChartView } from "@/features/charts/renderer/ChartView";
import type { FiltersSelection } from "@/features/charts/filters/filter-values";
import type { ChartFactory, ChartViewLoader } from "@/features/charts/renderer/ChartView";
import type { ChartOption } from "@/features/charts/renderer/option-builder";
import type { ChartViewResponse } from "@/features/charts/renderer/view-types";
import {
  definition,
  lowerBoundQuality,
  metric,
  observation,
  series,
  view,
  HUGE_DECIMAL,
} from "./fixtures";

/** ECharts option fields are `Arrayable<T>`; normalize indexed access. */
function seriesAt(option: ChartOption | null, index: number): Record<string, unknown> | undefined {
  const single = option?.series;
  const list = single === undefined ? [] : Array.isArray(single) ? single : [single];
  return list[index] as Record<string, unknown> | undefined;
}

interface FakeInstance {
  option: ChartOption | null;
  disposed: boolean;
  resized: boolean;
  container: HTMLElement;
  context: { width?: number; height?: number };
  setOption(option: ChartOption): void;
  resize(): void;
  dispose(): void;
}

function recordingFactory() {
  const instances: FakeInstance[] = [];
  const factory: ChartFactory = (container, context) => {
    const instance: FakeInstance = {
      option: null,
      disposed: false,
      resized: false,
      container,
      context,
      setOption(option: ChartOption) {
        this.option = option;
      },
      resize() {
        this.resized = true;
      },
      dispose() {
        this.disposed = true;
      },
    };
    instances.push(instance);
    return instance;
  };
  return { factory, instances };
}

interface LoaderCall {
  chartId: string;
  definitionId: string;
  start: string;
  end: string;
  filters: FiltersSelection;
  signal: AbortSignal;
}

function loaderReturning(resolved: ChartViewResponse, calls: LoaderCall[]): ChartViewLoader {
  return async (args) => {
    calls.push(args);
    return resolved;
  };
}

const baseDefinition = definition();
const volumeMetric = metric("USD", "Synthetic volume (fixture)", "synthetic_volume");

const resolvedView = view(baseDefinition, [
  series(volumeMetric, [
    observation("2026-11-01", "1000"),
    observation("2026-11-02", null), // gap
    observation("2026-11-03", HUGE_DECIMAL),
    observation("2026-11-04", "4000"),
  ]),
]);

/**
 * Exact-text lookup on raw textContent: @testing-library/dom normalizes node
 * text (the narrow no-break grouping space becomes a plain space) but not the
 * needle string, so raw string needles with U+202F never match. The function
 * matcher compares the cell's full textContent verbatim — the strictest form.
 */
function cellWith(scope: HTMLElement, expected: string): HTMLElement {
  return within(scope).getByText((_, element) => element?.textContent === expected) as HTMLElement;
}

function renderChart(props: Partial<Parameters<typeof ChartView>[0]> = {}) {
  const { factory, instances } = recordingFactory();
  const utils = render(
    <ChartView
      definition={baseDefinition}
      selection={{ start: "2026-11-01", end: "2026-11-06" }}
      view={resolvedView}
      mode="live"
      width={600}
      height={320}
      factory={factory}
      {...props}
    />,
  );
  return { ...utils, instances };
}

afterEach(() => {
  delete (globalThis as { IntersectionObserver?: unknown }).IntersectionObserver;
});

describe("ChartView — plot and accessible table integration", () => {
  it("distinguishes repeated exact table landmarks with human instance context", () => {
    const { factory } = recordingFactory();
    render(<>
      <ChartView definition={baseDefinition} selection={resolvedView.selection} view={resolvedView}
        mode="historical" factory={factory} instanceLabel="research block 2" />
      <ChartView definition={baseDefinition} selection={resolvedView.selection} view={resolvedView}
        mode="historical" factory={factory} instanceLabel="research block 7" />
    </>);
    for (const block of [2, 7]) {
      const table = screen.getByRole("region", {
        name: `${baseDefinition.title} — exact data table — research block ${block}`,
      });
      expect(table).toHaveAttribute("tabindex", "0");
      expect(within(table).getByText(`${baseDefinition.title} — equivalent data with exact values — research block ${block}`))
        .toBeInTheDocument();
    }
  });
  it("mounts the chart via the factory and renders the exact-value table without hover", async () => {
    const { instances } = renderChart();
    await waitFor(() => expect(instances.length).toBe(1));
    expect(instances[0].option).not.toBeNull();
    expect(seriesAt(instances[0].option, 0)).toMatchObject({ type: "line" });

    // Exact values are in the table (no hover needed): raw strings, bounds
    // labels, and gap rows are all visible text.
    const table = screen.getByRole("region", { name: /exact data table/ });
    expect(cellWith(table, "1\u202f000")).toBeInTheDocument();
    expect(cellWith(table, "4\u202f000")).toBeInTheDocument();
    expect(within(table).getByText("not observed")).toBeInTheDocument();
    expect(within(table).getByText(/no observation for the period/)).toBeInTheDocument();
    expect(within(table).queryByText(/^0$/)).not.toBeInTheDocument();
  });

  it("keeps 29+ digit decimals exact in the table while coordinates use floats", async () => {
    const { instances } = renderChart();
    await waitFor(() => expect(instances.length).toBe(1));
    const table = screen.getByRole("region", { name: /exact data table/ });
    const grouped = "123\u202f456\u202f789\u202f012\u202f345\u202f678\u202f901\u202f234\u202f567\u202f890.5";
    expect(cellWith(table, grouped)).toBeInTheDocument();
    const coordinate = (seriesAt(instances[0].option, 0) as { data: (number | null)[] }).data[2];
    expect(coordinate).toBe(Number(HUGE_DECIMAL));
  });

  it("labels bounded values and never presents a bound as exact", async () => {
    const payouts = metric("NEAR", "Synthetic payouts (fixture)", "synthetic_payouts");
    const bounded = view(
      definition({ chart_id: "synthetic-payouts", visualization_type: "bar" }),
      [series(payouts, [observation("2026-11-01", "1234", lowerBoundQuality())])],
    );
    renderChart({ definition: bounded.definition, view: bounded });
    const table = await screen.findByRole("region", { name: /exact data table/ });
    expect(cellWith(table, "\u22651\u202f234")).toBeInTheDocument();
    expect(within(table).getByText(/lower bound/)).toBeInTheDocument();
  });

  it("renders frame metadata: units, period, quality and last observed", () => {
    renderChart();
    expect(screen.getByText(/^Units:/)).toHaveTextContent("USD");
    expect(screen.getByText(/Period: 2026-11-01 … 2026-11-06 UTC\./)).toBeInTheDocument();
    expect(screen.getByText(/Last observed: 2026-11-06T00:00:00Z\./)).toBeInTheDocument();
    expect(screen.getByText("Live — latest approved data")).toBeInTheDocument();
  });

  it("exposes the manual accessible summary", () => {
    renderChart();
    expect(
      screen.getByText(/Synthetic daily volume \(fixture\)\. 4 periods from 2026-11-01/),
    ).toBeInTheDocument();
  });
});

describe("ChartView — honest states", () => {
  it("shows a loading state until the loader resolves", async () => {
    const calls: LoaderCall[] = [];
    const pending: ChartViewLoader = (args) => {
      calls.push(args);
      return new Promise(() => {});
    };
    render(
      <ChartView
        definition={baseDefinition}
        selection={{ start: "2026-11-01", end: "2026-11-06" }}
        loader={pending}
        mode="live"
        width={600}
        height={320}
        factory={recordingFactory().factory}
      />,
    );
    expect(screen.getByRole("status", { name: "Loading chart data" })).toBeInTheDocument();
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0].filters).toEqual({});
  });

  it("renders an unavailable definition honestly and never mounts a chart", () => {
    const gated = definition({
      chart_id: "synthetic-gated",
      data_status: "unavailable",
      unavailable_reason: "Synthetic gate reason (fixture): the metric is gated.",
    });
    const { instances } = renderChart({ definition: gated, view: null });
    expect(screen.getByText(/Unavailable — this is not zero/)).toBeInTheDocument();
    expect(screen.getByText(/Synthetic gate reason \(fixture\)/)).toBeInTheDocument();
    expect(instances).toHaveLength(0);
  });

  it("renders an all-missing view as unavailable with reasons, not zeros", async () => {
    const empty = view(
      baseDefinition,
      [series(volumeMetric, [observation("2026-11-01", null)])],
      {
        quality: {
          status: "missing",
          bound_kind: null,
          reasons: ["no observation for the period"],
          coverage: { observed: 0, expected: 5 },
          freshness_target_seconds: null,
        },
      },
    );
    renderChart({ view: empty });
    expect(await screen.findByText(/No data — this is not zero/)).toBeInTheDocument();
    expect(screen.getByText("no observation for the period")).toBeInTheDocument();
  });

  it("shows an error with retry, then recovers", async () => {
    const calls: LoaderCall[] = [];
    let fail = true;
    const flaky: ChartViewLoader = async (args) => {
      calls.push(args);
      if (fail) {
        throw new Error("Synthetic resolution failure (fixture)");
      }
      return resolvedView;
    };
    render(
      <ChartView
        definition={baseDefinition}
        selection={{ start: "2026-11-01", end: "2026-11-06" }}
        loader={flaky}
        mode="live"
        width={600}
        height={320}
        factory={recordingFactory().factory}
      />,
    );
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/Synthetic resolution failure/)).toBeInTheDocument();
    fail = false;
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(calls.length).toBeGreaterThanOrEqual(2));
    expect(await screen.findByRole("region", { name: /exact data table/ })).toBeInTheDocument();
  });

  it("keeps the last good plot visible when a refresh fails", async () => {
    const calls: LoaderCall[] = [];
    let fail = false;
    const flaky: ChartViewLoader = async (args) => {
      calls.push(args);
      if (fail) {
        throw new Error("Refresh failed (fixture)");
      }
      return resolvedView;
    };
    const props = {
      definition: baseDefinition,
      selection: { start: "2026-11-01", end: "2026-11-06" as string },
      loader: flaky,
      mode: "live" as const,
      width: 600,
      height: 320,
    };
    const first = render(<ChartView {...props} factory={recordingFactory().factory} />);
    await screen.findByRole("region", { name: /exact data table/ });

    fail = true;
    first.rerender(
      <ChartView
        {...props}
        selection={{ start: "2026-10-08", end: "2026-11-06" }}
        factory={recordingFactory().factory}
      />,
    );
    await screen.findByRole("alert");
    // Last good values stay on screen next to the failure.
    expect(screen.getByRole("region", { name: /exact data table/ })).toBeInTheDocument();
    expect(cellWith(screen.getByRole("region", { name: /exact data table/ }), "1\u202f000")).toBeInTheDocument();
  });

  it("marks a stale view with the stale notice while retaining values", () => {
    const stale = view(baseDefinition, [series(volumeMetric, [observation("2026-11-01", "1000")])], {
      quality: {
        status: "stale",
        bound_kind: null,
        reasons: [],
        coverage: { observed: 1, expected: 5 },
        freshness_target_seconds: 3600,
      },
    });
    renderChart({ view: stale, mode: "historical" });
    expect(screen.getByText(/Showing the last verified values/)).toBeInTheDocument();
    expect(screen.getByText("Historical — pinned version")).toBeInTheDocument();
  });
});

describe("ChartView — range selection (keyboard/touch)", () => {
  it("offers keyboard-reachable 44px presets anchored to the selection end", async () => {
    const user = userEvent.setup();
    const changes: { start: string; end: string }[] = [];
    renderChart({
      onSelectionChange: (selection) => changes.push(selection),
    });
    await screen.findByRole("region", { name: /exact data table/ });
    const group = screen.getByRole("group", { name: "Time range" });
    const seven = within(group).getByRole("button", { name: "Last 7 days" });
    expect(seven).toHaveClass("h-11"); // 44px touch target
    await user.tab();
    expect(seven).toHaveFocus();
    await user.click(within(group).getByRole("button", { name: "Last 30 days" }));
    expect(changes).toEqual([{ start: "2026-10-07", end: "2026-11-06" }]);
  });

  it("marks the active preset with aria-pressed and describes custom ranges", async () => {
    const { rerender } = renderChart({ onSelectionChange: () => {} });
    await screen.findByRole("region", { name: /exact data table/ });
    // No preset matches the initial window, so none is pressed yet.
    const group = screen.getByRole("group", { name: "Time range" });
    expect(within(group).getByRole("button", { name: "Last 7 days" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.getByText(/Custom range: 2026-11-01 – 2026-11-06/)).toBeInTheDocument();

    // Parent applies the change; rerender with the preset's selection.
    rerender(
      <ChartView
        definition={baseDefinition}
        selection={{ start: "2026-10-30", end: "2026-11-06" }}
        view={resolvedView}
        mode="live"
        width={600}
        height={320}
        factory={recordingFactory().factory}
        onSelectionChange={() => {}}
      />,
    );
    expect(within(screen.getByRole("group", { name: "Time range" })).getByRole("button", { name: "Last 7 days" })).toHaveAttribute("aria-pressed", "true");
  });
});

describe("ChartView — data flow and stale requests", () => {
  it("aborts the superseded request when the selection changes and on unmount", async () => {
    const calls: LoaderCall[] = [];
    const loader = loaderReturning(resolvedView, calls);
    const props = {
      definition: baseDefinition,
      selection: { start: "2026-11-01", end: "2026-11-06" as string },
      loader,
      mode: "live" as const,
      width: 600,
      height: 320,
    };
    const { rerender, unmount } = render(<ChartView {...props} factory={recordingFactory().factory} />);
    await waitFor(() => expect(calls).toHaveLength(1));

    rerender(
      <ChartView
        {...props}
        selection={{ start: "2026-10-08", end: "2026-11-06" }}
        factory={recordingFactory().factory}
      />,
    );
    await waitFor(() => expect(calls).toHaveLength(2));
    // The first request was cancelled the moment the new one superseded it.
    expect(calls[0].signal.aborted).toBe(true);
    expect(calls[1].signal.aborted).toBe(false);

    unmount();
    expect(calls[1].signal.aborted).toBe(true);
  });

  it("re-resolves through the loader when the range changes; units/metadata survive", async () => {
    const calls: LoaderCall[] = [];
    const loader = loaderReturning(resolvedView, calls);
    const props = {
      definition: baseDefinition,
      selection: { start: "2026-11-01", end: "2026-11-06" as string },
      loader,
      mode: "live" as const,
      width: 600,
      height: 320,
    };
    const { rerender } = render(<ChartView {...props} factory={recordingFactory().factory} />);
    await screen.findByRole("region", { name: /exact data table/ });
    expect(screen.getByText(/Period: 2026-11-01 … 2026-11-06 UTC\./)).toBeInTheDocument();
    expect(screen.getByText(/^Units:/)).toHaveTextContent("USD");

    const nextWindow = view(
      baseDefinition,
      [series(volumeMetric, [observation("2026-10-20", "77")])],
      { selection: { start: "2026-10-08", end: "2026-11-06", frequency: "day", filters: {} } },
    );
    const { factory, instances } = recordingFactory();
    rerender(
      <ChartView
        {...props}
        selection={{ start: "2026-10-08", end: "2026-11-06" }}
        view={undefined}
        loader={loaderReturning(nextWindow, calls)}
        factory={factory}
      />,
    );
    await waitFor(() => expect(calls.length).toBeGreaterThanOrEqual(2));
    expect(calls.at(-1)?.start).toBe("2026-10-08");
    expect(calls.at(-1)?.end).toBe("2026-11-06");

    // The new view resolves; metadata updates while units survive unchanged.
    await waitFor(() =>
      expect(screen.getByText(/Period: 2026-10-08 … 2026-11-06 UTC\./)).toBeInTheDocument(),
    );
    expect(screen.getByText(/^Units:/)).toHaveTextContent("USD");
    const table = screen.getByRole("region", { name: /exact data table/ });
    expect(within(table).getByText("77")).toBeInTheDocument();
    await waitFor(() => expect(instances.length).toBeGreaterThanOrEqual(1));
  });
});

describe("ChartView — lazy mount and resource cleanup", () => {
  class IntersectionObserverStub {
    static instances: IntersectionObserverStub[] = [];
    callback: IntersectionObserverCallback;
    observed: Element[] = [];
    disconnected = false;
    constructor(callback: IntersectionObserverCallback) {
      this.callback = callback;
      IntersectionObserverStub.instances.push(this);
    }
    observe(element: Element): void {
      this.observed.push(element);
    }
    disconnect(): void {
      this.disconnected = true;
    }
    unobserve(): void {}
    trigger(isIntersecting: boolean): void {
      this.callback(
        [{ isIntersecting } as IntersectionObserverEntry],
        this as unknown as IntersectionObserver,
      );
    }
  }

  it("defers the chart mount until the host intersects the viewport", async () => {
    (globalThis as { IntersectionObserver?: unknown }).IntersectionObserver = IntersectionObserverStub;
    IntersectionObserverStub.instances = [];
    const { factory, instances } = recordingFactory();
    render(
      <ChartView
        definition={baseDefinition}
        selection={{ start: "2026-11-01", end: "2026-11-06" }}
        view={resolvedView}
        mode="live"
        width={600}
        height={320}
        factory={factory}
      />,
    );
    // Off-screen: observed but not mounted.
    await waitFor(() => expect(IntersectionObserverStub.instances).toHaveLength(1));
    expect(instances).toHaveLength(0);
    // Scrolls into view -> mounts exactly once.
    act(() => {
      IntersectionObserverStub.instances[0].trigger(true);
    });
    await waitFor(() => expect(instances).toHaveLength(1));
  });

  it("disposes the instance on unmount and on view rebuild", async () => {
    const { factory, instances } = recordingFactory();
    const props = {
      definition: baseDefinition,
      selection: { start: "2026-11-01", end: "2026-11-06" },
      mode: "live" as const,
      width: 600,
      height: 320,
    };
    const first = render(<ChartView {...props} view={resolvedView} factory={factory} />);
    await waitFor(() => expect(instances.length).toBe(1));

    const updated = view(baseDefinition, [
      series(volumeMetric, [observation("2026-11-01", "2000")]),
    ]);
    first.rerender(<ChartView {...props} view={updated} factory={factory} />);
    await waitFor(() => expect(instances.length).toBe(2));
    expect(instances[0].disposed).toBe(true);
    expect(instances[1].disposed).toBe(false);

    first.unmount();
    expect(instances[1].disposed).toBe(true);
  });
});

describe("ChartView — one renderer for public and editor contexts", () => {
  it("renders identical accessible tables for public and editor configurations", async () => {
    const publicRender = renderChart({
      mode: "live",
      actions: <Button variant="secondary">Save chart</Button>,
    });
    await publicRender.findByRole("region", { name: /exact data table/ });
    const publicTable = screen.getByRole("region", { name: /exact data table/ }).textContent;

    const editorDefinition = definition({ chart_id: "synthetic-volume-editor" });
    const editorView = { ...resolvedView, definition: editorDefinition };
    const { factory } = recordingFactory();
    render(
      <ChartView
        definition={editorDefinition}
        selection={{ start: "2026-11-01", end: "2026-11-06" }}
        view={editorView}
        mode="historical"
        actions={<Button variant="quiet">Add to Research</Button>}
        width={600}
        height={320}
        factory={factory}
      />,
    );
    const editorTable = screen.getAllByRole("region", { name: /exact data table/ }).at(-1);
    expect(editorTable?.textContent).toBe(publicTable);
    expect(screen.getByRole("button", { name: "Add to Research" })).toBeInTheDocument();
  });
});

describe("ChartView — accessibility", () => {
  it("passes axe on the ready chart with table and summary", async () => {
    const { factory } = recordingFactory();
    render(
      <ChartView
        definition={baseDefinition}
        selection={{ start: "2026-11-01", end: "2026-11-06" }}
        view={resolvedView}
        mode="live"
        width={600}
        height={320}
        factory={factory}
      />,
    );
    await screen.findByRole("region", { name: /exact data table/ });
    // The `region` page-landmark rule stays disabled with the recorded
    // NI-007 rationale (component tests render fragments, not full pages).
    const results = await axe(document.body, { rules: { region: { enabled: false } } });
    expect(results).toHaveNoViolations();
  });
});


describe("ChartView — localized rendering failures", () => {
  it("catches a synchronous factory error, retains exact data, and retries without crashing", async () => {
    const instance = { setOption: vi.fn(), dispose: vi.fn(), resize: vi.fn() };
    const factory = vi.fn().mockImplementationOnce(() => { throw new Error("Synthetic factory failure"); }).mockReturnValue(instance);
    render(<ChartView definition={baseDefinition} view={resolvedView} selection={{ start: "2026-11-01", end: "2026-11-06" }} mode="historical" factory={factory} />);
    expect(await screen.findByText(/The plot could not render/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /exact data table/ })).toBeInTheDocument();
    const button = screen.getByRole("button", { name: /retry/i });
    fireEvent.click(button);
    await waitFor(() => expect(instance.setOption).toHaveBeenCalled());
    expect(screen.queryByText(/The plot could not render/)).not.toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveStyle({ height: "320px" });
  });
  it("disposes an instance whose setOption fails while keeping the table", async () => {
    const instance = { setOption: vi.fn(() => { throw new Error("Synthetic option failure"); }), dispose: vi.fn(), resize: vi.fn() };
    render(<ChartView definition={baseDefinition} view={resolvedView} selection={{ start: "2026-11-01", end: "2026-11-06" }} mode="historical" factory={() => instance} />);
    expect(await screen.findByText(/The plot could not render/)).toBeInTheDocument();
    expect(instance.dispose).toHaveBeenCalledOnce(); expect(screen.getByRole("region", { name: /exact data table/ })).toBeInTheDocument();
  });
});

describe("ChartView — compact presentation (NI-078, NI-076 D3/D4)", () => {
  it("hides the repeated frame title in compact contexts while the exact table stays visible", () => {
    render(<ChartView definition={definition()} view={resolvedView} selection={{ start: "2026-11-01", end: "2026-11-06" }} mode="historical" presentation="compact" />);
    // The frame does not repeat the title in compact contexts.
    const figure = screen.getByRole("img").closest("figure");
    expect(figure).not.toBeNull();
    expect(within(figure as HTMLElement).queryByText(definition().title, { exact: true })).toBeNull();
    // Units, mode badge and freshness metadata stay visible.
    expect(within(figure as HTMLElement).getByText(/Units:/)).toBeInTheDocument();
    expect(within(figure as HTMLElement).getByText("Historical — pinned version")).toBeInTheDocument();
    expect(within(figure as HTMLElement).getByText(/Period:/)).toBeInTheDocument();
    // The public-detail contract holds: exact values stay open (no hover).
    expect(screen.getByRole("region", { name: /exact data table/ })).toBeInTheDocument();
    expect(screen.queryByText("Exact values and summary")).toBeNull();
  });

  it("keeps one exact-value disclosure and preserves provenance in saved previews", () => {
    render(<ChartView definition={definition()} view={resolvedView} selection={{ start: "2026-11-01", end: "2026-11-06" }} mode="historical" presentation="saved-preview" />);
    const disclosure = screen.getByText("Exact values and summary").closest("details");
    expect(disclosure).not.toBeNull();
    const region = within(disclosure as HTMLElement).getByRole("region", { name: /exact data table/ });
    expect(region).toBeInTheDocument();
    expect(region.closest("details")).toBe(disclosure);
    expect(screen.queryByText("Accessible summary")).toBeNull();
    expect(screen.queryByText("Historical — pinned version")).toBeNull();
    expect(screen.queryByText(/Period:/)).toBeNull();
    expect(screen.getByText(/Last observed:/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sources & definitions" })).toBeInTheDocument();
  });

  it("keeps the table always open outside compact contexts", () => {
    render(<ChartView definition={definition()} view={resolvedView} selection={{ start: "2026-11-01", end: "2026-11-06" }} mode="historical" />);
    expect(screen.getByRole("region", { name: /exact data table/ })).toBeInTheDocument();
    expect(screen.queryByText("Exact values and summary")).toBeNull();
  });
});
