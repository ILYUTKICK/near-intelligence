/**
 * NI-078 recorded-evidence figures (NI-076 D2): the CL-004 approximate USD
 * windows and the CL-007 purchases-versus-net-supply-scale comparison.
 *
 * The figures consume ONLY the typed claim registry in content.ts, so the
 * assertions below compare the rendered values against the registry objects
 * EXACTLY — a retyped or rounded value fails here. Also asserted: the
 * estimate labeling (CL-004), the single measurement unit per figure (no
 * dual axis), the "purchases are never subtracted from supply" caution, and
 * the accessible names/summaries.
 *
 * All content comes from the saved NI-014 claim registry (historical
 * observations verified 4 November 2026); no fixtures, no live data.
 */
import { axe } from "jest-axe";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ResearchPage from "@/app/(public)/research/page";
import { SupplyScaleFigure, UsdWindowsFigure } from "@/features/public-research/ResearchFigures";
import { claimRegistry } from "@/features/public-research/content";

function claim(id: string) {
  const found = claimRegistry.find((entry) => entry.id === id);
  if (!found) throw new Error(`missing registry claim ${id}`);
  return found;
}

function figure(id: string) {
  const element = document.getElementById(id);
  expect(element, `missing figure #${id}`).not.toBeNull();
  return element as HTMLElement;
}

describe("CL-004 approximate USD windows figure", () => {
  it("renders the three recorded USD window values exactly as registered", () => {
    const claim004 = claim("CL-004");
    const windows = claim004.quantities.slice(0, 3);
    expect(windows.map((quantity) => quantity.value)).toEqual(["437,374", "557,914", "547,026"]);
    render(<UsdWindowsFigure />);
    const figureNode = figure("thesis-usd-windows");
    for (const quantity of windows) {
      // Exact string match: no rounding, no reformatting of recorded values.
      expect(within(figureNode).getByText(quantity.value)).toBeInTheDocument();
      expect(within(figureNode).getByText(quantity.scope)).toBeInTheDocument();
    }
  });

  it("labels the estimate and its recorded price-mark basis", () => {
    render(<UsdWindowsFigure />);
    const figureNode = figure("thesis-usd-windows");
    expect(within(figureNode).getByText("Estimate — valuation, not execution")).toBeInTheDocument();
    expect(figureNode.textContent).toMatch(/daily start-of-day price marks/);
    expect(figureNode.textContent).toMatch(/approximate acquisition value/i);
    // The recorded window-over-window decomposition comes from the registry.
    const startMarks = claim("CL-004").quantities[3];
    const endMarks = claim("CL-004").quantities[4];
    expect(figureNode.textContent).toContain(startMarks.value);
    expect(figureNode.textContent).toContain(endMarks.value);
    expect(figureNode.textContent).toMatch(new RegExp(startMarks.basis!.replace(/[()*]/g, "\\$&")));
    expect(figureNode.textContent).toMatch(new RegExp(endMarks.basis!.replace(/[()*]/g, "\\$&")));
  });

  it("carries no USD quantity from another claim and no NEAR unit", () => {
    render(<UsdWindowsFigure />);
    const figureNode = figure("thesis-usd-windows");
    // Single unit: NEAR quantities from other claims must not appear here.
    expect(figureNode.textContent).not.toContain("524,480.127692882832410490617319");
    expect(figureNode.textContent).not.toContain("7,936,181.547057263680300503519861");
  });
});

describe("CL-007 purchases versus net supply scale figure", () => {
  it("renders both recorded NEAR totals exactly and never subtracts purchases from supply", () => {
    const purchases = claim("CL-001").quantities[1];
    const netIncrease = claim("CL-007").quantities[0];
    const shareOfIncrease = claim("CL-007").quantities[2];
    const shareOfOpening = claim("CL-007").quantities[1];
    expect(purchases.unit).toBe("NEAR acquired");
    expect(netIncrease.unit).toBe("NEAR exact boundary total-supply increase");
    render(<SupplyScaleFigure />);
    const figureNode = figure("thesis-supply-scale");
    expect(within(figureNode).getByText(purchases.value)).toBeInTheDocument();
    expect(within(figureNode).getByText(netIncrease.value)).toBeInTheDocument();
    // The scale reading uses the recorded percentages verbatim.
    expect(figureNode.textContent).toContain(shareOfIncrease.value);
    expect(figureNode.textContent).toContain(shareOfOpening.value);
    // The standing caution is visible: purchases are not subtracted from supply.
    expect(figureNode.textContent).toMatch(/Purchases are never subtracted from total supply/);
    expect(figureNode.textContent).toMatch(/not deflation, not a capture rate/);
  });

  it("plots one unit (NEAR) on one scale with an accessible summary", () => {
    render(<SupplyScaleFigure />);
    const figureNode = figure("thesis-supply-scale");
    expect(within(figureNode).getByText("Observed — scale comparison")).toBeInTheDocument();
    // No USD quantity appears in the NEAR scale comparison.
    expect(figureNode.textContent).not.toContain("437,374");
    expect(figureNode.textContent).not.toContain("557,914");
    expect(figureNode.textContent).not.toContain("547,026");
  });
});

describe("Figures on the thesis page", () => {
  it("renders both figures in their owning sections beside the claim cards", () => {
    render(<ResearchPage />);
    // CL-004 figure inside the revenue capture section, before its claim card.
    const revenueCapture = document.getElementById("revenue-capture");
    expect(revenueCapture).not.toBeNull();
    expect(revenueCapture!.querySelector("#thesis-usd-windows")).not.toBeNull();
    // CL-007 figure inside the token economics section, before its claim card.
    const tokenEconomics = document.getElementById("token-economics");
    expect(tokenEconomics).not.toBeNull();
    expect(tokenEconomics!.querySelector("#thesis-supply-scale")).not.toBeNull();
    // All plotted quantities link to their recorded claim cards.
    const claimLinks = screen.getAllByRole("link", { name: /Recorded claim/ });
    expect(claimLinks.map((link) => link.getAttribute("href")).sort())
      .toEqual(["#CL-001-heading", "#CL-002-heading", "#CL-004-heading", "#CL-007-heading"]);
  });

  it("passes axe on the rendered page", async () => {
    const { container } = render(<ResearchPage />);
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});
