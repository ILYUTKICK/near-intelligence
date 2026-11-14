import { axe } from "jest-axe";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import ResearchPage from "@/app/(public)/research/page";
import { SupplyScaleFigure } from "@/features/public-research/ResearchFigures";
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

describe("Recorded acquisition windows", () => {
  it("switches units and exposes the registered values and valuation basis", async () => {
    const user = userEvent.setup();
    render(<ResearchPage />);
    const comparison = within(figure("thesis-usd-windows"));
    const near = comparison.getByRole("button", { name: "NEAR" });
    const usd = comparison.getByRole("button", { name: "USD estimate" });
    expect(near).toHaveAttribute("aria-pressed", "true");
    expect(comparison.getByRole("img")).toHaveAccessibleName(/NEAR acquired.*244,845.70/);

    await user.click(usd);
    expect(usd).toHaveAttribute("aria-pressed", "true");
    expect(near).toHaveAttribute("aria-pressed", "false");
    expect(comparison.getByText(/Daily start-of-day prices/)).toBeVisible();
    expect(comparison.getByRole("img")).toHaveAccessibleName(/Estimated USD.*\$547,026/);

    await user.click(comparison.getByText("Values and valuation method"));
    const table = within(comparison.getByRole("table"));
    for (const value of claim("CL-004").quantities.slice(0, 3)) {
      expect(table.getByText("$" + value.value)).toBeVisible();
    }
    for (const value of claim("CL-002").quantities.slice(0, 3)) {
      expect(table.getByText(value.value)).toBeVisible();
    }
    expect(comparison.getByText(/5.45% decline/)).toBeVisible();
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
  it("links the opening comparison and the supply figure to the recorded claims", () => {
    render(<ResearchPage />);
    expect(document.getElementById("purchase-windows")?.querySelector("#thesis-usd-windows")).not.toBeNull();
    expect(screen.getByRole("link", { name: /Compare NEAR and estimated USD/ }))
      .toHaveAttribute("href", "#thesis-usd-windows");
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
