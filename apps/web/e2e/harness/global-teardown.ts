/**
 * Playwright global teardown for the NI-063 research-workflow e2e
 * (harness-only code): stops the stack booted by global-setup.ts (SIGTERM to
 * the recorded PID); stack.py then stops uvicorn/Next and the disposable
 * PostgreSQL and deletes its temp directory.
 */
import { existsSync, readFileSync, rmSync } from "node:fs";

import { statePath } from "./state";

const pidFile = `${statePath()}.pid`;

export default async function teardown(): Promise<void> {
  if (!existsSync(pidFile)) {
    console.log("[ni063-e2e] no stack pid recorded — nothing to stop");
    return;
  }
  const pid = Number(readFileSync(pidFile, "utf-8").trim());
  rmSync(pidFile, { force: true });
  if (!Number.isInteger(pid) || pid <= 0) {
    console.log("[ni063-e2e] recorded stack pid is unusable — nothing to stop");
    return;
  }
  let alive = true;
  try {
    process.kill(pid, 0);
  } catch {
    alive = false;
  }
  if (!alive) {
    console.log("[ni063-e2e] stack already stopped");
    return;
  }
  console.log("[ni063-e2e] stopping the stack…");
  process.kill(pid, "SIGTERM");
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    try {
      process.kill(pid, 0);
    } catch {
      console.log("[ni063-e2e] stack stopped; disposable cluster removed");
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  console.error("[ni063-e2e] the stack did not stop within 60 s — killing hard");
  try {
    process.kill(pid, "SIGKILL");
  } catch {
    // already gone
  }
}
