/**
 * Playwright global setup/teardown for the NI-063 research-workflow e2e
 * (harness-only code, never part of the application).
 *
 * setup(): boots the real product stack through apps/web/e2e/harness/stack.py
 * (`uv run --project apps/api`): disposable loopback PostgreSQL 18, real
 * FastAPI gateway (synthetic ES256 provider transport only), the production
 * `next start` build, and the real NI-058 export worker. It then copies the
 * stack's JSON handoff to the agreed state path for the spec and records the
 * stack PID for teardown.
 *
 * teardown(): stops the stack (SIGTERM to the recorded PID); stack.py then
 * stops uvicorn/Next and the disposable PostgreSQL and deletes its temp
 * directory.
 *
 * No provider, collector or non-loopback network access happens anywhere.
 */
import { spawn } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";

import { pgBin, repoRoot, statePath } from "./state";

const pidFile = `${statePath()}.pid`;

export default async function setup(): Promise<void> {
  const webDir = path.join(repoRoot, "apps", "web");
  if (!existsSync(path.join(webDir, ".next", "BUILD_ID"))) {
    throw new Error(
      "The production web build is missing (apps/web/.next/BUILD_ID). "
      + "Run `pnpm --filter web build` before the e2e journey — the harness boots `next start`.");
  }
  const handoff = `${statePath()}.handoff.json`;
  rmSync(handoff, { force: true });
  rmSync(statePath(), { force: true });
  rmSync(pidFile, { force: true });
  mkdirSync(path.dirname(statePath()), { recursive: true });

  const environment = { ...process.env };
  // The export worker renderer and `next start` need this Node on PATH.
  environment.PATH = `${path.dirname(process.execPath)}:${environment.PATH ?? ""}`;

  console.log("[ni063-e2e] booting the disposable real stack (PostgreSQL 18 + FastAPI + next start)…");
  const stackProcess = spawn("uv", [
    "run", "--project", path.join(repoRoot, "apps", "api"),
    "python", path.join(repoRoot, "apps", "web", "e2e", "harness", "stack.py"),
    "--pg-bin", pgBin(),
    "--handoff", handoff,
  ], { cwd: repoRoot, env: environment, stdio: ["ignore", "pipe", "pipe"] });
  writeFileSync(pidFile, String(stackProcess.pid), "utf-8");

  const output = { out: "", err: "" };
  stackProcess.stdout!.on("data", (chunk: Buffer) => {
    output.out = (output.out + chunk.toString()).slice(-12000);
    process.stdout.write(chunk);
  });
  stackProcess.stderr!.on("data", (chunk: Buffer) => {
    output.err = (output.err + chunk.toString()).slice(-12000);
    process.stderr.write(`[ni063-stack] ${chunk}`);
  });
  const exited = new Promise((resolve) => {
    stackProcess.once("exit", (code, signal) => resolve({ code, signal }));
  });

  try {
    const deadline = Date.now() + 180_000;
    while (Date.now() < deadline) {
      if (existsSync(handoff)) {
        copyFileSync(handoff, statePath());
        console.log("[ni063-e2e] stack handoff received; the journey can start");
        return;
      }
      if (stackProcess.exitCode !== null || stackProcess.signalCode !== null) {
        throw new Error("the NI-063 stack exited before the handoff was written");
      }
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
    throw new Error("the NI-063 stack did not produce its handoff within 180 s");
  } catch (error) {
    stackProcess.kill("SIGKILL");
    await exited;
    const tail = `${output.out}\n${output.err}`.trim();
    throw new Error(`${String(error)}\n--- stack output tail ---\n${tail || "(no output)"}`);
  }
}
