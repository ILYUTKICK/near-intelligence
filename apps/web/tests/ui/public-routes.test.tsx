/**
 * NI-011 public routes: server-side shells render without login, mechanism
 * separates purchases from burns, stable anchors exist, no fake metrics.
 */
import { axe } from "jest-axe";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "@/app/(public)/page";
import MethodologyPage from "@/app/(public)/methodology/page";
import ResearchPage from "@/app/(public)/research/page";
import { publicNav } from "@/lib/navigation";

describe("Landing", () => {
  it("renders the standfirst and registry links with no metric digits", async () => {
    const { container } = render(<HomePage />);
    expect(screen.getByRole("heading", { level: 1, name: "NEAR Intelligence" })).toBeInTheDocument();
    expect(screen.getByText(/missing value is never shown as zero/i)).toBeInTheDocument();
    for (const link of ["Read the research", "How the numbers are made"]) {
      const anchor = screen.getByRole("link", { name: link });
      expect(publicNav.map((item) => item.href).concat(["/research", "/methodology"])).toContain(
        anchor.getAttribute("href"),
      );
    }
    // No fabricated quantitative claims: no percent signs in the content.
    expect(container.textContent).not.toMatch(/%/);
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
    expect(screen.getByText(/intentionally does not contain them/i)).toBeInTheDocument();
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});
