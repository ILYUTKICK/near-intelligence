/**
 * NI-070 release-manifest integrity (content-vs-manifest, NI-013-style).
 *
 * The original research release publishes its report set under
 * research/reports/ with an immutable content/evidence manifest. This test
 * verifies, offline:
 * - every SHA-256 recorded in the manifest matches the exact bytes of the
 *   document it names (and the recorded byte size matches);
 * - every Markdown document under research/reports/ is manifest-pinned — the
 *   manifest itself is the only exception (a manifest cannot contain its own
 *   hash; its integrity is anchored by repository history and this test);
 * - the published operator recipe and estimator facts stay bound to the
 *   tracked tooling and preregistered configs;
 * - the release docs keep the honest pending status and contrary evidence,
 *   and carry no private metadata, no credentials, no absolute local
 *   filesystem paths and no fitted-value claims.
 */
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const repoRoot = join(process.cwd(), "..", "..");
const reportsDir = join(repoRoot, "research", "reports");

function readRepo(relative: string): string {
  return readFileSync(join(repoRoot, relative), "utf8");
}

const manifestRel = "research/reports/original-research-release-2026-11.manifest.md";
const reportRel = "research/reports/original-research-release-2026-11.md";

const manifest = readRepo(manifestRel);
const report = readRepo(reportRel);

interface ManifestRow {
  filename: string;
  recordedBytes: number;
  recordedSha256: string;
}

/** Rows of the "Published release documents" table (linked, hashed entries). */
function manifestRows(): ManifestRow[] {
  const rows: ManifestRow[] = [];
  for (const match of manifest.matchAll(
    /^\| \[([^\]]+)\]\(([^)]+)\) \| (\d+) \| `([0-9a-f]{64})` \|$/gm,
  )) {
    rows.push({ filename: match[2], recordedBytes: Number(match[3]), recordedSha256: match[4] });
  }
  return rows;
}

describe("Release manifest pins the published documents", () => {
  it("records a hash row for every Markdown document except the manifest itself", () => {
    const files = readdirSync(reportsDir).filter((name) => name.endsWith(".md"));
    expect(files).toContain("original-research-release-2026-11.md");
    expect(files).toContain("original-research-release-2026-11.manifest.md");
    const pinned = new Set(manifestRows().map((row) => row.filename));
    for (const file of files) {
      if (file === "original-research-release-2026-11.manifest.md") continue;
      expect(pinned.has(file), `${file} must be pinned by the manifest`).toBe(true);
    }
  });

  it("recomputes every recorded SHA-256 and byte size over the exact file bytes", () => {
    const rows = manifestRows();
    expect(rows.length).toBeGreaterThanOrEqual(1);
    for (const row of rows) {
      const bytes = readFileSync(join(reportsDir, row.filename));
      const sha256 = createHash("sha256").update(bytes).digest("hex");
      expect(sha256, `${row.filename} SHA-256 must match the manifest`).toBe(row.recordedSha256);
      expect(bytes.byteLength, `${row.filename} byte size must match the manifest`).toBe(
        row.recordedBytes,
      );
    }
  });

  it("points the definition versions at the tracked metric registry", () => {
    expect(manifest).toContain("apps/api/src/near_api/metrics/registry.py");
    // The gated definitions are recorded as gated, never as available values.
    expect(manifest).toMatch(/`protocol_revenue_usd`.*G/);
    expect(manifest).toMatch(/always null with recorded reasons/);
  });
});

describe("Release report stays bound to the tracked tooling", () => {
  const fitCli = readRepo("research/models/fit.py");
  const diagnosticsCli = readRepo("research/models/diagnostics.py");
  const researchMain = readRepo("apps/api/src/near_api/research/__main__.py");
  const gatePolicy = JSON.parse(
    readRepo("research/models/configs/readiness_gate_policy_v1.json"),
  ) as { window: { start: string; end_exclusive: string }; min_complete_daily_observations: number };

  it("publishes the operator recipe with flags that exist in the tooling", () => {
    expect(report).toContain("python -m near_api.research fit");
    expect(report).toContain("python -m near_api.research diagnostics");
    expect(report).toContain("python -m near_api.research verify");
    expect(report).toContain("python -m near_api.research publish");
    expect(report).toContain("--code-commit <git sha>");
    for (const flag of ["--archive-root", "--out-dir", "--code-commit"]) {
      expect(fitCli).toContain(flag);
      expect(diagnosticsCli).toContain(flag);
    }
    for (const verb of ["fit", "diagnostics", "verify", "publish"]) {
      expect(researchMain).toMatch(new RegExp(`"${verb}"`));
    }
  });

  it("records the gate window and thresholds from the preregistered policy", () => {
    expect(report).toContain(gatePolicy.window.start);
    expect(report).toContain(gatePolicy.window.end_exclusive);
    expect(report).toContain(`at least ${gatePolicy.min_complete_daily_observations} complete daily observations`);
  });

  it("states the honest pending status and preserves the contrary evidence", () => {
    expect(report).toMatch(/real-archive fit run (is )?pending operator execution/i);
    expect(report).toMatch(/No\s+fitted coefficient,\s+standard error,\s+confidence interval,\s+p-value or diagnostic/i);
    expect(report).toMatch(/from the real archive exists anywhere in this release/);
    expect(report).toMatch(/PROXY_ONLY_READY_WITH_LIMITS/);
    expect(report).toMatch(/REJECTED/);
    expect(report).toMatch(/6 of 297/);
    expect(report).toMatch(/OQ02_JUDGING_ACCEPTANCE_RISK/);
    expect(report).toMatch(/declined/);
    // The H1-H4 statuses are recorded, with the no-remapping rule preserved.
    expect(report).toMatch(/No\s+numeric remapping is valid/);
  });

  it("carries no private metadata, credentials or local filesystem paths", () => {
    const published = manifest + "\n" + report;
    const patterns: RegExp[] = [
      /\/Users\//,
      /\/home\//,
      /document[_-]?id/i,
      /revision[_-]?id/i,
      /user[_-]?id/i,
      /\bsupabase\b/i,
      /\bBearer\b/,
      /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i,
      /(api[_-]?key|token)\s*[:=]/i,
    ];
    for (const pattern of patterns) {
      expect(published).not.toMatch(pattern);
    }
    // The recorded evidence hashes are the only long hex strings allowed, and
    // they are the documented 64-hex SHA-256 values, not secrets.
    const longHex = published.match(/\b[0-9a-f]{40,}\b/g) ?? [];
    for (const hex of longHex) {
      expect(hex).toMatch(/^[0-9a-f]{64}$/);
    }
  });
});
