/**
 * Layout shell tests (NI-008): route-registry assertions against the IA,
 * mobile drawer keyboard/focus behavior, breadcrumbs, skip navigation.
 */
import { axe } from "jest-axe";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { usePathname } from "next/navigation";

import { Breadcrumbs } from "@/components/layout/Breadcrumbs";
import { MobileNavDrawer } from "@/components/layout/MobileNavDrawer";
import { PublicHeader } from "@/components/layout/PublicHeader";
import { SkipLink } from "@/components/layout/SkipLink";
import { WorkspaceSidebar } from "@/components/layout/WorkspaceSidebar";
import { authNav, publicNav, workspaceNav, workspaceNavByGroup } from "@/lib/navigation";

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/workspace/research"),
}));

beforeEach(() => {
  vi.mocked(usePathname).mockReturnValue("/workspace/research");
});

describe("Route registry", () => {
  it("matches the canonical IA exactly", () => {
    expect(publicNav.map((item) => [item.label, item.href])).toEqual([
      ["Overview", "/"],
      ["Blog", "/blog"],
      ["Data", "/data"],
      ["Methodology", "/methodology"],
      ["Models", "/models"],
    ]);
    expect(workspaceNavByGroup().map(({ group }) => group)).toEqual([
      "Workspace",
      "Data Explorer",
      "Analytics",
      "Account",
    ]);
    const labels = workspaceNav.map((item) => item.label);
    expect(labels).toEqual([
      "Home",
      "My Research",
      "Saved Charts",
      "Chart library",
      "Network Activity",
      "Intents & Adoption",
      "Revenue & Fees",
      "Token Economics",
      "Ecosystem",
      "Econometric Models",
      "Profile",
      "Settings",
    ]);
  });

  it("has unique hrefs, enabled scope priorities and no excluded routes", () => {
    const all = [...publicNav, ...workspaceNav, ...authNav];
    for (const navigation of [publicNav, workspaceNav, authNav]) {
      const hrefs = navigation.map((item) => item.href);
      expect(new Set(hrefs).size).toBe(hrefs.length);
    }
    for (const item of all) {
      expect(item.enabled).toBe(true);
      expect(item.priority).toBe(item.href === "/blog" ? "P1" : "P0");
      // Strategy/Portfolio screens from the legacy plan stay excluded.
      expect(item.href).not.toMatch(/strategy|portfolio/i);
      expect(item.label).not.toMatch(/strategy|portfolio/i);
    }
  });

  it("keeps explorer and analytics links inside implemented workspace routes", () => {
    for (const item of workspaceNav) {
      expect(item.href, `${item.label} href`).toMatch(/^\/workspace(?:\/|$)/);
    }
    expect(workspaceNav.filter((item) => item.group === "Data Explorer").map((item) => item.href)).toEqual([
      "/workspace/data/network", "/workspace/data/intents", "/workspace/data/revenue",
      "/workspace/data/token-economics", "/workspace/data/ecosystem",
    ]);
    expect(workspaceNav.find((item) => item.label === "Chart library")?.href).toBe("/workspace/charts");
    expect(workspaceNav.find((item) => item.label === "Econometric Models")?.href).toBe("/workspace/models");
  });
});

describe("Skip link", () => {
  it("is the first tabbable element and targets the main landmark", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <div>
        <SkipLink />
        <PublicHeader />
        <main id="main-content" />
      </div>,
    );
    await user.tab();
    expect(screen.getByText("Skip to main content")).toHaveFocus();
    expect(screen.getByText("Skip to main content")).toHaveAttribute("href", "#main-content");
    expect(container.querySelector("#main-content")).toBeInTheDocument();
  });
});

describe("Public header", () => {
  it("renders registry navigation and exposes the active route", async () => {
    vi.mocked(usePathname).mockReturnValue("/");
    render(<PublicHeader />);
    const nav = screen.getByRole("navigation", { name: "Primary" });
    expect(within(nav).getByRole("link", { name: "Blog" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Sign in" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open site menu" })).toBeInTheDocument();
    expect(await axe(document.body, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});

describe("Mobile navigation drawer", () => {
  it("opens from the keyboard, traps items, closes with Escape and restores focus", async () => {
    const user = userEvent.setup();
    render(<MobileNavDrawer items={publicNav} triggerLabel="Open site menu" />);
    const trigger = screen.getByRole("button", { name: "Open site menu" });
    await user.tab();
    expect(trigger).toHaveFocus();
    await user.keyboard("{Enter}");
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("link", { name: "Blog" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    expect(await axe(document.body, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  it("renders workspace groups with availability notes", async () => {
    const user = userEvent.setup();
    const items = workspaceNavByGroup().flatMap(({ items: groupItems }) => groupItems);
    render(
      <MobileNavDrawer
        items={items}
        groups={["Workspace", "Data Explorer", "Analytics", "Account"]}
        triggerLabel="Open workspace menu"
      />,
    );
    await user.click(screen.getByRole("button", { name: "Open workspace menu" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Data Explorer")).toBeInTheDocument();
    expect(within(dialog).getByText("availability varies by source")).toBeInTheDocument();
    expect(within(dialog).getByRole("link", { name: /Econometric Models/ })).toBeInTheDocument();
  });
});

describe("Workspace sidebar", () => {
  it("groups navigation and marks the active route", () => {
    render(<WorkspaceSidebar />);
    const nav = screen.getByRole("navigation", { name: "Workspace" });
    const active = within(nav).getByRole("link", { name: /My Research/ });
    expect(active).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: /Saved Charts/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open workspace menu" })).toBeInTheDocument();
  });
});

describe("Breadcrumbs", () => {
  it("links ancestors, marks the current page and is labeled", () => {
    render(
      <Breadcrumbs
        items={[
          { label: "Workspace", href: "/workspace" },
          { label: "My Research", href: "/workspace/research" },
          { label: "Fees memo" },
        ]}
      />,
    );
    const nav = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(within(nav).getByRole("link", { name: "Workspace" })).toHaveAttribute("href", "/workspace");
    expect(within(nav).getByText("Fees memo")).toHaveAttribute("aria-current", "page");
  });
});
