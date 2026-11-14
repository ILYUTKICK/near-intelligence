/**
 * NI-011 public routes: server-side shells render without login, mechanism
 * separates purchases from burns, stable anchors exist, no fake metrics.
 *
 * NI-086 replaces the old metric-heavy landing with an API-independent
 * editorial Overview. The retained source loader still has its independent
 * exact-value/failure matrix in landing-metrics.test.tsx. Full evidence and
 * mechanism assertions here remain on their owning research route.
 */
import { axe } from "jest-axe";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import HomePage from "@/app/(public)/page";
import MethodologyPage from "@/app/(public)/methodology/page";
import ResearchPage from "@/app/(public)/research/page";

// The NI-045 duplication CTA on the research page reads the router for the
// sign-in continuation; these shell tests stub the router (the page renders
// outside the app-router context). CTA behavior: duplicate-release.test.tsx.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

describe("Overview", () => {
  it("introduces the platform with a real article, data destinations and workspace action", async () => {
    const { container } = render(<HomePage />);
    expect(screen.getByRole("heading", { level: 1, name: /Understand NEAR/ })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Read the research" }).map((link) => link.getAttribute("href"))).toEqual(["/blog", "/research"]);
    expect(screen.getByRole("link", { name: "Our methodology" })).toHaveAttribute("href", "/methodology");
    expect(screen.getByRole("link", { name: "Open workspace" })).toHaveAttribute("href", "/workspace");
    expect(screen.getByRole("link", { name: "Explore data: Intents activity" })).toHaveAttribute("href", "/data/intents");
    expect(screen.getByText(/Historical datasets/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/Selected approved metrics|Unavailable — this is not zero/);
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});

describe("Research route", () => {
  it("exposes stable anchors h1–h4 and the mechanism stages", () => {
    render(<ResearchPage />);
    for (const anchor of ["h1", "h2", "h3", "h4", "mechanism"]) {
      expect(document.getElementById(anchor)).not.toBeNull();
    }
    const mechanism = screen.getByRole("region", { name: /economic mechanism/i });
    const orderedList = mechanism.querySelector("ol");
    expect(orderedList).not.toBeNull();
    const stages = within(orderedList as HTMLElement).getAllByRole("listitem");
    const titles = ["Activity", "Fees", "Revenue", "Conversion", "Retention & supply"];
    expect(stages).toHaveLength(titles.length);
    stages.forEach((item, index) => {
      // The stage title span is the only element with the exact title text
      // inside its list item (bodies may repeat the word).
      expect(within(item).getByText(titles[index], { selector: "span" })).toBeInTheDocument();
    });
  });

  it("explicitly separates purchases from burns", () => {
    render(<ResearchPage />);
    expect(screen.getByText(/Treasury purchases do not reduce total supply — burns do/i)).toBeInTheDocument();
    expect(screen.getByText(/never relabels one as another/i)).toBeInTheDocument();
  });

  it("carries explicit per-hypothesis status lines (NI-014 published the thesis)", async () => {
    const { container } = render(<ResearchPage />);
    // h1–h4 each carry an honest current status instead of the old
    // unpublished placeholder; the detailed claim-level assertions live in
    // thesis.test.tsx.
    for (const status of [
      "Unresolved",
      "Partial evidence",
      "Not supported on current evidence",
    ]) {
      expect(screen.getAllByText(status).length).toBeGreaterThan(0);
    }
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});

describe("Methodology route", () => {
  it("carries the stable sources and reproduce anchors", async () => {
    const { container } = render(<MethodologyPage />);
    for (const anchor of ["sources", "definitions", "collection", "reproduce"]) {
      expect(document.getElementById(anchor)).not.toBeNull();
    }
    expect(screen.getByText(/Missing observations remain gaps, never zeros/i)).toBeInTheDocument();
    expect(container.querySelectorAll("details, summary")).toHaveLength(0);
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});
