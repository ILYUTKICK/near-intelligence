import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { afterEach, describe, expect, it, vi } from "vitest";

import HomePage from "@/app/(public)/page";
import { publications } from "@/features/blog/publications";

afterEach(() => vi.unstubAllGlobals());

describe("Approved editorial Overview", () => {
  it("renders the approved section hierarchy and preserves meaningful legacy anchors", () => {
    const { container } = render(<HomePage />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Understand NEAR.Build your own thesis.");
    expect(screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent)).toEqual([
      "The research, in focus.", "Explore the evidence.", "How it works",
      "Sources first. Assumptions visible.", "Make the research your own.",
    ]);
    for (const id of ["findings", "evidence", "mechanism", "release-status"]) expect(container.querySelector(`#${id}`)).not.toBeNull();
    expect(screen.getByRole("link", { name: "How it works" })).toHaveAttribute("href", "#how-it-works");
    const workflow = screen.getByRole("region", { name: "How it works" });
    expect(within(workflow).getByRole("link", { name: "Read the hypotheses" })).toHaveAttribute("href", "/research#question");
    expect(within(workflow).getByRole("link", { name: "Browse charts" })).toHaveAttribute("href", "/charts");
    expect(within(workflow).getByRole("link", { name: "Start a research document" })).toHaveAttribute("href", "/workspace");
    expect(screen.getByRole("link", { name: "full research" })).toHaveAttribute("href", "/research#mechanism");
    expect(screen.getByRole("link", { name: "Research status" })).toHaveAttribute("href", "/research#econometrics");
  });

  it("features one actual curated publication, without fabricated metadata or additional articles", () => {
    render(<HomePage />);
    const article = screen.getByRole("article");
    expect(publications).toHaveLength(1);
    expect(within(article).getByRole("heading", { name: publications[0].title })).toBeInTheDocument();
    expect(within(article).getByRole("link", { name: "Read the research" })).toHaveAttribute("href", "/research");
    expect(article).toHaveTextContent("November 2026 research release");
    expect(article.querySelector("time")).toBeNull();
    expect(article).not.toHaveTextContent(/Coming soon|Synthetic|Published 14 November/);
  });

  it("routes three data directions to their actual explorer categories", () => {
    render(<HomePage />);
    const directions = screen.getByRole("list", { name: "Data exploration directions" });
    expect(within(directions).getAllByRole("listitem")).toHaveLength(3);
    expect(within(directions).getByRole("link", { name: "Explore data: Intents activity" })).toHaveAttribute("href", "/data/intents");
    expect(within(directions).getByRole("link", { name: "Explore data: Revenue & fees" })).toHaveAttribute("href", "/data/revenue");
    expect(within(directions).getByRole("link", { name: "Explore data: Token economics" })).toHaveAttribute("href", "/data/token-economics");
    expect(screen.getByText("Historical datasets · coverage varies by source")).toBeInTheDocument();
  });

  it("is independent of API availability and presents no raw financial result or editor metadata", () => {
    const fetcher = vi.fn(() => { throw new Error("Synthetic unavailable backend"); });
    vi.stubGlobal("fetch", fetcher);
    const { container } = render(<HomePage />);
    expect(fetcher).not.toHaveBeenCalled();
    expect(container.textContent).not.toMatch(/Selected approved metrics|Latest approved observation|\bDATA_NOT_READY\b|observed_near_purchases|treasury_payouts_near|provider_gross_fees_usd|document_id|owner_id|Bearer|\d+%/);
    expect(screen.queryByText(/^Live$/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open workspace" })).toHaveAttribute("href", "/workspace");
    expect(screen.getByRole("link", { name: "Open workspace" })).toHaveClass("focus-visible:outline-focus");
  });

  it("uses decorative prioritized artwork rather than a baked-in screenshot or financial chart", () => {
    const { container } = render(<HomePage />);
    const image = container.querySelector("img");
    expect(image).toHaveAttribute("alt", "");
    expect(image).toHaveAttribute("loading", "eager");
    expect(image).toHaveAttribute("fetchpriority", "high");
    expect(image?.getAttribute("src")).toContain("trace-approved.png");
    expect(image).toHaveAttribute("width", "1312");
    expect(image).toHaveAttribute("height", "1199");
  });

  it("supports keyboard action order and passes the accessibility tree check", async () => {
    const { container } = render(<HomePage />);
    const [discovery, firstArticle] = screen.getAllByRole("link", { name: "Read the research" });
    discovery.focus();
    expect(discovery).toHaveFocus();
    await userEvent.tab();
    expect(screen.getByRole("link", { name: "Explore data" })).toHaveFocus();
    expect(firstArticle).toHaveAttribute("href", "/research");
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});
