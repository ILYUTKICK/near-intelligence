/**
 * Shared state plumbing for the NI-063 Playwright harness (harness-only code).
 *
 * The Python stack script (stack.py) writes a JSON handoff file; the Node
 * global setup (boot.ts) reads it and copies it to the agreed state path so
 * the spec can consume the bootstrapped real-stack coordinates. The state file
 * lives under the gitignored `.local/` directory and contains only loopback
 * URLs and synthetic fixture identifiers — no secrets.
 */
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

/**
 * Repository root, resolved the same way the app's env loader does: walk up
 * from the process working directory until pnpm-workspace.yaml is found (the
 * transpiled harness must not rely on __dirname).
 */
export const repoRoot = (() => {
  let dir = process.cwd();
  for (let depth = 0; depth < 10; depth += 1) {
    if (existsSync(path.join(dir, "pnpm-workspace.yaml"))) {
      return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) {
      return process.cwd();
    }
    dir = parent;
  }
  return process.cwd();
})();

/** Absolute path of the JSON state file shared between setup and tests. */
export function statePath(): string {
  return process.env.NI063_STATE
    ?? path.join(repoRoot, ".local", "ni063-e2e-state.json");
}

/** PostgreSQL 18 bin directory used for the disposable cluster. */
export function pgBin(): string {
  return process.env.NI063_PG_BIN
    ?? (process.platform === "win32" ? "" : process.platform === "darwin"
      ? "/opt/homebrew/opt/postgresql@18/bin"
      : "/usr/lib/postgresql/18/bin");
}

/** Read the handoff state written by boot.ts. */
export function readState(): unknown {
  const file = statePath();
  if (!existsSync(file)) {
    throw new Error(`NI-063 e2e state is missing at ${file} — the global setup must run first`);
  }
  return JSON.parse(readFileSync(file, "utf-8"));
}
