/**
 * NI-013 methodology page: provider/definition/cleaning/readiness sections on
 * the stable anchors, exact verified periods, explicit attribution/supply
 * bounds, no raw-download guarantees — and every command label verified
 * against the tooling the repository actually ships.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { axe } from "jest-axe";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MethodologyPage from "@/app/(public)/methodology/page";

const repoRoot = join(process.cwd(), "..", "..");

function readRepo(relative: string): string {
  return readFileSync(join(repoRoot, relative), "utf8");
}

const rootPackageJson = JSON.parse(readRepo("package.json")) as { scripts: Record<string, string> };
const webPackageJson = JSON.parse(readRepo("apps/web/package.json")) as {
  name: string;
  scripts: Record<string, string>;
};

/** External documentation links verified live in docs/SOURCE_VERIFICATION.md. */
const verifiedExternalHrefs = [
  "https://docs.near.org/api/rpc/providers",
  "https://docs.near.org/api/rpc/block-chunk",
  "https://docs.near-intents.org/llms.txt",
  "https://docs.llama.fi/pro-api",
  "https://github.com/DefiLlama/dimension-adapters/blob/master/fees/near-intents/index.ts",
  "https://docs.dune.com/api-reference/overview/authentication",
  "https://docs.dune.com/api-reference/overview/rate-limits",
  "https://docs.coingecko.com/reference/coins-id-market-chart-range",
  "https://docs.cloud.google.com/bigquery/public-data",
  "https://www.near.org/blog/evolving-near-tokenomics",
];

function renderedPage() {
  return render(<MethodologyPage />);
}

describe("Methodology anchors and honesty", () => {
  it("carries the stable anchors including the readiness section", async () => {
    const { container } = renderedPage();
    for (const anchor of ["sources", "definitions", "collection", "readiness", "reproduce"]) {
      const element = document.getElementById(anchor);
      expect(element, `missing #${anchor}`).not.toBeNull();
      expect(element!.tagName).toBe("SECTION");
    }
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  it("states the exact verified periods", () => {
    const { container } = renderedPage();
    const text = container.textContent as string;
    // 90-day conversion/payout cohort (gate window, end exclusive).
    expect(text).toContain("2026-08-06");
    expect(text).toContain("2026-11-04");
    // Intents creation cohort.
    expect(text).toContain("2026-11-01");
    expect(text).toContain("2026-11-03");
    // The single OQ-03 probe timestamp.
    expect(text).toContain("2026-11-06T19:13:45Z");
  });

  it("keeps attribution and supply bounds explicit", () => {
    const { container } = renderedPage();
    const text = container.textContent as string;
    expect(text).toContain("Treasury purchases do not reduce total supply — burns do");
    expect(text).toMatch(/conservative lower bounds/i);
    expect(text).toContain("6 of 297");
    // Short attribution cohorts stay descriptive; the 90-day window is short.
    expect(text).toMatch(/Short attribution cohorts/i);
    expect(text).toMatch(/cannot establish a long-term stable mechanism/i);
    // Purchases cohort is not market demand; payouts are not revenue.
    expect(text).toMatch(/not whole-market demand/i);
    expect(text).toMatch(/cash flows, not revenue/i);
  });

  it("never offers raw-data downloads or unsupported public access guarantees", () => {
    const { container } = renderedPage();
    const text = container.textContent as string;
    expect(text).toMatch(/No raw-data downloads are offered/i);
    expect(text).toMatch(/intentionally does not contain them/i);
    expect(text).toMatch(/fresh retrieval does not make an old observation fresh/i);
    // No download affordances of any kind.
    for (const anchor of Array.from(container.querySelectorAll("a"))) {
      expect(anchor.getAttribute("download")).toBeNull();
    }
  });

  it("links only verified provider documentation (no repository or file links)", () => {
    const { container } = renderedPage();
    const hrefs = Array.from(container.querySelectorAll("a")).map((a) => a.getAttribute("href"));
    const external = hrefs.filter((href) => !href?.startsWith("#"));
    // External links are HTTPS and come from the verified provider register.
    expect(new Set(hrefs.filter((href) => href?.startsWith("#")))).toEqual(new Set(["#collection", "#sources"]));
    for (const href of external) {
      expect(href).toMatch(/^https:\/\//);
      expect(verifiedExternalHrefs).toContain(href);
    }
    expect(external).toHaveLength(verifiedExternalHrefs.length);
    expect(external).toHaveLength(new Set(external).size);
  });
});

describe("Methodology command labels vs available tooling", () => {
  function listByName(name: string): HTMLElement {
    return screen.getByRole("list", { name });
  }

  function commandsOf(list: HTMLElement): string[] {
    return Array.from(list.querySelectorAll("code")).map((code) => code.textContent ?? "");
  }

  it("lists implemented commands that exist in the repository tooling", () => {
    render(<MethodologyPage />);
    const commands = commandsOf(listByName("Implemented commands"));
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

  it("keeps unimplemented CLI verbs out of the implemented list", () => {
    render(<MethodologyPage />);
    const implementedText = listByName("Implemented commands").textContent as string;
    // The unified near_api.cli module does not exist; the refresh and research
    // commands run through their own modules (listed above as implemented).
    expect(implementedText).not.toContain("near_api.cli");
    expect(implementedText).not.toContain("research run");
    expect(implementedText).not.toContain("download");
    const unavailableText = listByName("Commands not implemented yet").textContent as string;
    expect(unavailableText).toContain("python -m near_api.cli …");
    expect(unavailableText).toContain("near_api.cli module does not exist");
    expect(unavailableText).toContain("dataset download endpoints");
  });

  it("states the honest NI-070 estimator status with no fitted values", () => {
    const { container } = renderedPage();
    const text = container.textContent as string;
    expect(text).toMatch(/no real-archive fit has been executed, so no fitted results exist anywhere/);
    expect(text).toMatch(/real-archive fit run is pending operator execution/);
    expect(text).toMatch(/public model catalog stays honestly empty/);
    // The synthetic verification is recorded, never a real-data claim.
    expect(text).toMatch(/synthetic-verified/);
    expect(text).toMatch(/intercept 0, slope 1/);
    expect(text).toMatch(/atol 1e-10/);
    // No fitted statistic can exist on the page.
    expect(text).not.toMatch(/β\s*=|p\s*[=<]\s*0\.|\bR2?\s*=/);
  });

  it("renders gate thresholds exactly as the preregistered policy config declares", () => {
    const gatePolicy = JSON.parse(
      readRepo("research/models/configs/readiness_gate_policy_v1.json"),
    ) as {
      min_complete_daily_observations: number;
      min_observations_per_parameter: number;
      max_substantive_slopes: number;
      long_run_min_days: number;
      window: { start: string; end_exclusive: string };
    };
    const { container } = renderedPage();
    const text = container.textContent as string;
    expect(text).toContain(`At least ${gatePolicy.min_complete_daily_observations} complete daily observations`);
    expect(text).toContain(`at least ${gatePolicy.min_observations_per_parameter} per estimated parameter`);
    expect(text).toContain(`At most ${gatePolicy.max_substantive_slopes} substantive slopes`);
    expect(text).toContain(`A minimum of ${gatePolicy.long_run_min_days} days`);
    expect(text).toContain(gatePolicy.window.start);
    expect(text).toContain(gatePolicy.window.end_exclusive);
  });
});

describe("Methodology source→transform→metric path", () => {
  it("traces SRC-BQ through import/staging to a registered metric in order", () => {
    const { container } = renderedPage();
    const text = container.textContent as string;
    const indexSource = text.indexOf("SRC-BQ saved export flows_90d_raw.json");
    const indexImport = text.indexOf("NI-027 archive import verifies the file hashes");
    const indexStage = text.indexOf("NI-028 stage-from-import");
    const indexMetric = text.indexOf("observed_near_purchases v1 (availability A)");
    expect(indexSource).toBeGreaterThan(-1);
    expect(indexImport).toBeGreaterThan(indexSource);
    expect(indexStage).toBeGreaterThan(indexImport);
    expect(indexMetric).toBeGreaterThan(indexStage);
  });

  it("renders the provider register as a table with provider rows", () => {
    renderedPage();
    const table = screen.getByRole("table", { name: /Provider register/i });
    const rows = within(table).getAllByRole("row");
    // 10 provider rows + header row.
    expect(rows).toHaveLength(11);
    for (const id of [
      "SRC-NEAR-RPC",
      "SRC-BQ",
      "SRC-INTENTS",
      "SRC-LLAMA",
      "SRC-DASHBOARD",
      "SRC-DUNE",
      "SRC-PRICE",
      "SRC-FASTNEAR",
      "SRC-NEARBLOCKS",
      "SRC-GOV",
    ]) {
      expect(within(table).getByRole("rowheader", { name: id })).toBeInTheDocument();
    }
  });

  it("renders readiness verdicts with the recorded reason codes", () => {
    renderedPage();
    expect(screen.getByText(/PROXY_ONLY_READY_WITH_LIMITS/)).toBeInTheDocument();
    for (const spec of ["true_revenue_daily_v1", "gross_fee_activity_v1", "purchases_activity_v1", "supply_bounds_activity_v1"]) {
      expect(screen.getByText(spec)).toBeInTheDocument();
    }
    for (const verdict of ["NOT_READY", "READY_WITH_LIMITS", "REJECTED"]) {
      expect(screen.getAllByText(verdict).length).toBeGreaterThan(0);
    }
    for (const code of [
      "GATED_METRIC_NO_OBSERVATIONS",
      "PROTOCOL_REVENUE_NOT_ESTABLISHED_OQ01",
      "LOWER_BOUND_SERIES_NOT_EXACT_OUTCOME",
      "WINDOW_AGGREGATE_NOT_DAILY",
      "MINT_HEADER_AUDIT_INCOMPLETE",
    ]) {
      expect(screen.getByText(code)).toBeInTheDocument();
    }
  });
});
