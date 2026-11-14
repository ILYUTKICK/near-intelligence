/** Public methodology keeps the reader article, not the removed operator appendices. */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { axe } from "jest-axe";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MethodologyPage from "@/app/(public)/methodology/page";
import { methodology } from "@/features/public-research/content";

const repoRoot = join(process.cwd(), "..", "..");
function readRepo(relative: string): string {
  return readFileSync(join(repoRoot, relative), "utf8");
}
const rootPackageJson = JSON.parse(readRepo("package.json")) as { scripts: Record<string, string> };
const webPackageJson = JSON.parse(readRepo("apps/web/package.json")) as {
  name: string; scripts: Record<string, string>;
};
function renderedPage() { return render(<MethodologyPage />); }

describe("Reader-facing methodology", () => {
  it("retains all six chapters, canonical anchors and an accessible article", async () => {
    const { container } = renderedPage();
    const links = within(screen.getByRole("navigation", { name: "On this page" })).getAllByRole("link");
    expect(links).toHaveLength(6);
    for (const id of ["sources", "definitions", "collection", "verify", "readiness", "reproduce"]) {
      expect(container.querySelector(`#${id}`)?.tagName).toBe("SECTION");
    }
    for (const link of links) expect(container.querySelector(link.getAttribute("href")!)).not.toBeNull();
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  it("removes every disclosure and its technical content from page markup", () => {
    const { container } = renderedPage();
    expect(container.querySelectorAll("details, summary")).toHaveLength(0);
    expect(screen.getAllByRole("table")).toHaveLength(1);
    expect(screen.getByRole("table").getAttribute("aria-label")).not.toBe("Source register table");
    for (const title of [
      "Full source register & access notes", "Definition versions & availability labels",
      "Validation rules & recorded calculation path", "Model readiness policy & recorded verdicts",
      "Reproduction commands & environment",
    ]) expect(screen.queryByText(title)).toBeNull();
    expect(container.textContent).not.toMatch(/SRC-BQ|SRC-NEAR-RPC|PROXY_ONLY_READY|NOT_READY|near_api|--database-url|NI-\d+/);
    expect(container.textContent).not.toContain("GATED_METRIC_NO_OBSERVATIONS");
    expect(container.textContent).not.toContain("At least 60 complete daily observations");
    expect(container.textContent).not.toContain("flows_90d_raw.json");
    expect(container.textContent).not.toContain("18,496 bytes");
  });

  it("keeps source names, shared lineage and historical scope visible", () => {
    const { container } = renderedPage();
    expect(screen.getByText(/NEAR public BigQuery tables · NEAR RPC/)).toBeVisible();
    expect(screen.getByText(/DefiLlama · NEAR Revenue Dashboard · Dune/)).toBeVisible();
    expect(screen.getByText(/CoinGecko · NEAR materials/)).toBeVisible();
    expect(screen.getByText(/These sources share Dune lineage/)).toBeVisible();
    expect(container.textContent).toContain("6 August–3 November 2026 UTC");
    expect(container.textContent).toContain("2026-08-06");
    expect(container.textContent).toContain("2026-11-04");
    expect(container.textContent).toMatch(/Coverage, access and reuse rights vary by source/);
  });

  it("keeps economic distinctions, missing data and the scientific limits explicit", () => {
    const { container } = renderedPage();
    const text = container.textContent;
    expect(screen.getByText(/Cash flows, not revenue/)).toBeVisible();
    expect(text).toContain("Treasury purchases do not reduce total supply — burns do");
    expect(text).toMatch(/Not whole-market demand/);
    expect(text).toMatch(/Missing observations remain gaps, never zeros/);
    expect(text).toMatch(/conservative lower bounds/);
    expect(text).toContain("6 of 297");
    expect(text).toMatch(/cannot establish a long-term stable mechanism/);
    expect(screen.getByRole("heading", { name: "Correlation is not causation." })).toBeVisible();
    expect(screen.getByText(/No reviewed fitted result is published here/)).toBeVisible();
    expect(text).not.toMatch(/β\s*=|p\s*[=<]\s*0\.|\bR2?\s*=/);
  });

  it("keeps the actual chart verification and versioned reproduction guidance", () => {
    const { container } = renderedPage();
    const verify = container.querySelector("#verify")!;
    expect(verify.textContent).toMatch(/Sources & definitions/);
    expect(verify.textContent).toMatch(/dates, filters and dataset version/);
    expect(verify.textContent).toMatch(/equivalent data table/);
    expect(verify.textContent).toMatch(/acknowledged revision/);
    const reproduce = container.querySelector("#reproduce")!;
    expect(reproduce.textContent).toMatch(/content hashes/);
    expect(reproduce.textContent).toMatch(/approved immutable dataset/);
    expect(reproduce.textContent).toMatch(/No raw-data downloads are offered/);
    expect(reproduce.querySelectorAll("pre, code, details")).toHaveLength(0);
  });

  it("offers only chapter and actual product links, with no raw download affordance", () => {
    const { container } = renderedPage();
    for (const link of container.querySelectorAll("a")) {
      const href = link.getAttribute("href")!;
      expect(href.startsWith("#") || ["/charts", "/models", "/research"].includes(href)).toBe(true);
      expect(link.getAttribute("download")).toBeNull();
    }
  });
});

describe("Canonical methodology tooling stays available internally", () => {
  it("retains canonical command documentation that matches available tooling", () => {
    const commands = methodology.reproduce.implemented.map(item => item.command);
    const joined = commands.join("\n");

    // Root package.json really ships the API test scripts.
    expect(rootPackageJson.scripts["test:api:unit"]).toBeDefined();
    expect(rootPackageJson.scripts["test:api:db"]).toBeDefined();
    expect(joined).toContain("corepack pnpm test:api:unit");
    expect(joined).toContain("corepack pnpm test:api:db");

    // The web filter name and test script really exist.
    expect(webPackageJson.name).toBe("web");
    expect(webPackageJson.scripts.test).toBeDefined();
    expect(joined).toContain("corepack pnpm --filter web test");

    // NI-027 archive importer: every flag shown exists in the CLI.
    const archiveCli = readRepo("apps/api/src/near_api/ingestion/archive.py");
    const archiveCommand = commands.find((command) => command.includes("near_api.ingestion.archive"));
    expect(archiveCommand).toBeDefined();
    for (const flag of ["--archive-root", "--manifest", "--cohorts", "--database-url", "--dry-run"]) {
      expect(archiveCli).toContain(flag);
      expect(archiveCommand).toContain(flag);
    }

    // NI-028 datasets CLI: every verb shown is a real subparser.
    const datasetsCli = readRepo("apps/api/src/near_api/datasets/cli.py");
    const datasetsCommand = commands.find((command) => command.includes("near_api.datasets"));
    expect(datasetsCommand).toBeDefined();
    for (const verb of ["stage", "stage-from-import", "validate", "publish", "show"]) {
      expect(datasetsCli).toMatch(new RegExp(`add_parser\\(\\s*"${verb}"`));
      expect(datasetsCommand).toContain(verb);
    }

    // NI-029 metrics CLI: --spec/--out-dir exist.
    const metricsCli = readRepo("apps/api/src/near_api/metrics/__main__.py");
    const metricsCommand = commands.find((command) => command.includes("near_api.metrics"));
    expect(metricsCommand).toBeDefined();
    for (const flag of ["--spec", "--out-dir"]) {
      expect(metricsCli).toContain(flag);
      expect(metricsCommand).toContain(flag);
    }

    // NI-051 readiness gate: flags exist in the tracked gate script.
    const readinessCli = readRepo("research/models/readiness.py");
    const readinessCommand = commands.find((command) =>
      command.includes("research/models/readiness.py"),
    );
    expect(readinessCommand).toBeDefined();
    for (const flag of ["--archive-root", "--configs-dir", "--out-dir"]) {
      expect(readinessCli).toContain(flag);
      expect(readinessCommand).toContain(flag);
    }

    // NI-052/NI-053/NI-054 research CLI: the verbs exist in the dispatcher and
    // every flag shown exists in the owning module.
    const researchCli = readRepo("apps/api/src/near_api/research/__main__.py");
    const fitCli = readRepo("research/models/fit.py");
    const diagnosticsCli = readRepo("research/models/diagnostics.py");
    const publicationCli = readRepo("apps/api/src/near_api/research/publication.py");
    for (const verb of ["fit", "diagnostics", "verify", "publish"]) {
      expect(researchCli).toMatch(new RegExp(`"${verb}"`));
    }
    const fitCommand = commands.find((command) => command.includes("near_api.research fit"));
    expect(fitCommand).toBeDefined();
    for (const flag of ["--archive-root", "--out-dir", "--code-commit"]) {
      expect(fitCli).toContain(flag);
      expect(fitCommand).toContain(flag);
    }
    const diagnosticsCommand = commands.find((command) =>
      command.includes("near_api.research diagnostics"),
    );
    expect(diagnosticsCommand).toBeDefined();
    for (const flag of ["--archive-root", "--out-dir", "--code-commit"]) {
      expect(diagnosticsCli).toContain(flag);
      expect(diagnosticsCommand).toContain(flag);
    }
    const verifyCommand = commands.find((command) => command.includes("near_api.research verify"));
    expect(verifyCommand).toBeDefined();
    for (const flag of ["--bundle", "--offline"]) {
      expect(researchCli).toContain(flag);
      expect(verifyCommand).toContain(flag);
    }
    const publishCommand = commands.find((command) => command.includes("near_api.research publish"));
    expect(publishCommand).toBeDefined();
    for (const flag of ["--bundle", "--database-url"]) {
      expect(researchCli).toContain(flag);
      expect(publishCommand).toContain(flag);
    }
    // The bundle files the verify command points at are the tracked gate
    // artifacts (fit manifest, diagnostics report, readiness report names).
    expect(publicationCli).toContain("fit_manifest.json");
    expect(publicationCli).toContain("diagnostics_report.json");
    expect(publicationCli).toContain("readiness_report.json");

    // NI-030 refresh adapter: the single-shot flags exist in the CLI.
    const refreshCli = readRepo("apps/api/src/near_api/ingestion/refresh.py");
    const refreshCommand = commands.find((command) =>
      command.includes("near_api.ingestion.refresh"),
    );
    expect(refreshCommand).toBeDefined();
    for (const flag of ["--once", "--database-url", "--storage-root", "--repo-root", "--source"]) {
      expect(refreshCli).toContain(flag);
      expect(refreshCommand).toContain(flag);
    }
  });

  it("preserves source and readiness records without publishing their appendices", () => {
    expect(methodology.sources.providers).toHaveLength(10);
    expect(methodology.readiness.specs.map(spec => spec.spec)).toContain("true_revenue_daily_v1");
    expect(methodology.readiness.gateNumbers).toContain("At least 60 complete daily observations, and at least 10 per estimated parameter including the intercept.");
    expect(methodology.reproduce.implemented.some(item => item.command.includes("near_api.cli"))).toBe(false);
  });
});
