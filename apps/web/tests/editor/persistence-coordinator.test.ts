/**
 * NI-040 save-coordinator unit tests (synthetic fixtures, visibly labeled).
 * The state machine is deterministic through the injected timer harness: the
 * tests advance virtual time and assert exactly what the EDITOR_SPECIFICATION
 * persistence paragraph and the card acceptance criteria require —
 * 1s-idle/5s-max scheduling, one in-flight request with coalescing,
 * "acknowledging older payload never clears newer dirty edits", key-stable
 * retries (timeout-after-commit), no silent last-write-wins on 409, and an
 * honest queued state on transport failures.
 *
 * The harness models an editor faithfully: `markChanged()` is only a signal —
 * the content a save would persist is whatever `capture()` returns at fire
 * time, so "typing" is `type(body)` (new capture + signal) and "undoing back"
 * is capturing the baseline body again.
 */
import { describe, expect, it, vi } from "vitest";

import {
  SaveCoordinator,
  hasUnsavedWork,
  type SaveStatus,
  type TimerHarness,
} from "@/features/editor/persistence/save-coordinator";
import { DocumentApiError } from "@/features/documents/list/documents-api";
import type { SaveAck, SaveAttempt, SaveRequestBody } from "@/features/editor/persistence/save-transport";

const DOC_ID = "22222222-2222-4222-8222-222222222222";

/** Visible synthetic bodies: A is the baseline, B/C are later edits. */
const BODY_A: SaveRequestBody = {
  schema_version: 1,
  content: { schema_version: 1, type: "doc", content: [{ label: "baseline (fixture)" }] },
  observed_contexts: [],
};
const BODY_B: SaveRequestBody = {
  schema_version: 1,
  content: { schema_version: 1, type: "doc", content: [{ label: "edit B (fixture)" }] },
  observed_contexts: [],
};
const BODY_C: SaveRequestBody = {
  schema_version: 1,
  content: { schema_version: 1, type: "doc", content: [{ label: "edit C (fixture)" }] },
  observed_contexts: [],
};

interface Harness {
  coordinator: SaveCoordinator;
  requests: SaveAttempt[];
  /** Settles the oldest in-flight transport promise (microtasks flushed). */
  respond: (ackOrError: SaveAck | Error) => Promise<void>;
  statuses: SaveStatus[];
  advance: (ms: number) => void;
  /** An editor update: the capture now returns `body`, and the signal fires. */
  type: (body: SaveRequestBody) => void;
}

function makeHarness(initialRevision = 7, baseline: SaveRequestBody = BODY_A): Harness {
  let now = 0;
  let handleSeq = 0;
  let pending: Array<{ at: number; handle: number; fn: () => void }> = [];
  const timers: TimerHarness = {
    set(delayMs, fn) {
      const handle = ++handleSeq;
      pending.push({ at: now + delayMs, handle, fn });
      return handle;
    },
    clear(handle) {
      pending = pending.filter((entry) => entry.handle !== handle);
    },
    now: () => now,
  };
  const advance = (ms: number) => {
    const target = now + ms;
    for (;;) {
      const due = pending.filter((entry) => entry.at <= target).sort((a, b) => a.at - b.at)[0];
      if (!due) {
        break;
      }
      pending = pending.filter((entry) => entry.handle !== due.handle);
      now = Math.max(now, due.at);
      due.fn();
    }
    now = target;
  };

  const requests: SaveAttempt[] = [];
  const resolvers: Array<(ack: SaveAck) => void> = [];
  const rejecters: Array<(error: unknown) => void> = [];
  const transport = (attempt: SaveAttempt) =>
    new Promise<SaveAck>((resolve, reject) => {
      requests.push(attempt);
      resolvers.push(resolve);
      rejecters.push(reject);
    });

  let currentCapture = baseline;
  const statuses: SaveStatus[] = [];
  const coordinator = new SaveCoordinator(DOC_ID, initialRevision, {
    transport,
    capture: () => currentCapture,
    timers,
    newKey: () => `key-${requests.length + 1}-${Math.random()}`,
    onCapture: vi.fn(),
  });
  coordinator.onStatus((status) => statuses.push(status));

  return {
    coordinator,
    requests,
    statuses,
    advance,
    type: (body) => {
      currentCapture = body;
      coordinator.markChanged();
    },
    respond: async (ackOrError) => {
      const resolve = resolvers.shift();
      const reject = rejecters.shift();
      if (ackOrError instanceof Error) {
        reject?.(ackOrError);
      } else {
        resolve?.(ackOrError);
      }
      // The coordinator reacts in promise callbacks — flush the microtask
      // queue so assertions observe the settled state.
      await Promise.resolve();
      await Promise.resolve();
    },
  };
}

const ACK = (revision: number): SaveAck => ({ revision, savedAt: "2026-11-08T10:00:00Z" });

describe("save scheduling (1s idle / 5s max)", () => {
  it("autosaves once after the 1s idle window, not before", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    h.type(BODY_B);
    h.advance(999);
    expect(h.requests).toHaveLength(0);
    h.advance(1);
    expect(h.requests).toHaveLength(1);
    expect(h.requests[0]).toMatchObject({ documentId: DOC_ID, revision: 7 });
    expect(JSON.stringify(h.requests[0].body)).toBe(JSON.stringify(BODY_B));
    expect(h.coordinator.getStatus().kind).toBe("saving");
  });

  it("keeps resetting the idle timer while typing and fires at the 5s ceiling", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    // Typing continuously: every 600ms, below the 1s idle window.
    for (let step = 0; step < 8; step += 1) {
      h.type(step % 2 === 0 ? BODY_B : BODY_C);
      h.advance(600);
      expect(h.requests).toHaveLength(0);
    }
    // 8 × 600ms = 4.8s — still inside the ceiling; the max timer fires at 5s.
    h.advance(200);
    expect(h.requests).toHaveLength(1);
  });

  it("a manual save is immediate and cancels the pending idle timer", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    h.type(BODY_B);
    h.coordinator.saveNow();
    expect(h.requests).toHaveLength(1);
    h.advance(5000);
    expect(h.requests).toHaveLength(1);
  });
});

describe("one in-flight request; coalescing; truthful dirty state", () => {
  it("does not start a second request while one is in flight", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    h.type(BODY_B);
    h.advance(1000); // attempt with BODY_B in flight
    h.type(BODY_C);
    h.type(BODY_B);
    h.advance(5000);
    expect(h.requests).toHaveLength(1);
  });

  it("acknowledging the older payload never clears newer dirty edits", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    h.type(BODY_B);
    h.advance(1000); // attempt with BODY_B in flight
    h.type(BODY_C); // user typed while the request ran
    await h.respond(ACK(8));
    expect(h.coordinator.getStatus()).toMatchObject({ kind: "dirty", revision: 8 });
    // The coalesced follow-up carries the NEWER content, not the acked one.
    h.advance(1000);
    expect(h.requests).toHaveLength(2);
    expect(JSON.stringify(h.requests[1].body)).toBe(JSON.stringify(BODY_C));
  });

  it("marks clean only when the captured state matches the acknowledged payload", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    h.type(BODY_B);
    h.advance(1000);
    await h.respond(ACK(8));
    expect(h.coordinator.getStatus()).toEqual({
      kind: "clean",
      revision: 8,
      savedAt: "2026-11-08T10:00:00Z",
    });
    expect(hasUnsavedWork(h.coordinator.getStatus())).toBe(false);
  });

  it("follows up a manual save immediately after the in-flight request settles", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    h.type(BODY_B);
    h.advance(1000); // attempt B in flight
    h.type(BODY_C);
    h.coordinator.saveNow(); // manual intent while in flight → coalesce
    await h.respond(ACK(8));
    expect(h.requests).toHaveLength(2);
    expect(JSON.stringify(h.requests[1].body)).toBe(JSON.stringify(BODY_C));
    expect(h.coordinator.getStatus().kind).toBe("saving");
  });

  it("content identical to the baseline never saves a phantom revision", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    h.type(BODY_B); // user typed…
    h.type(BODY_A); // …and undid back to the baseline
    h.advance(1000);
    expect(h.requests).toHaveLength(0);
    expect(h.coordinator.getStatus()).toMatchObject({ kind: "clean", revision: 7 });
  });
});

describe("idempotency (timeout-after-commit)", () => {
  it("retries a transport failure with the SAME idempotency key", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    h.type(BODY_B);
    h.advance(1000); // attempt 1, key K1
    const firstKey = h.requests[0].idempotencyKey;
    await h.respond(new TypeError("network down")); // unknown outcome
    expect(h.coordinator.getStatus().kind).toBe("queued");
    h.coordinator.retry();
    expect(h.requests).toHaveLength(2);
    expect(h.requests[1].idempotencyKey).toBe(firstKey);
    await h.respond(ACK(8));
    expect(h.coordinator.getStatus()).toMatchObject({ kind: "clean", revision: 8 });
  });

  it("retains content while queued and flushes newer edits after the retry ack", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    h.type(BODY_B);
    h.advance(1000); // attempt 1 (BODY_B) fails
    await h.respond(new TypeError("network down"));
    h.type(BODY_C); // user keeps typing while queued
    h.coordinator.retry();
    expect(h.requests).toHaveLength(2);
    expect(JSON.stringify(h.requests[1].body)).toBe(JSON.stringify(BODY_B)); // retained first
    expect(h.coordinator.getStatus().kind).toBe("saving");
    await h.respond(ACK(8));
    // Newer content stays dirty and is scheduled with a FRESH key.
    expect(h.coordinator.getStatus()).toMatchObject({ kind: "dirty", revision: 8 });
    h.advance(1000);
    expect(h.requests).toHaveLength(3);
    expect(JSON.stringify(h.requests[2].body)).toBe(JSON.stringify(BODY_C));
    expect(h.requests[2].idempotencyKey).not.toBe(h.requests[1].idempotencyKey);
  });

  it("a queued attempt is exposed for an honest queue display", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    h.type(BODY_B);
    h.advance(1000);
    await h.respond(new TypeError("offline"));
    expect(h.coordinator.getRetainedAttempt()).not.toBeNull();
    expect(h.coordinator.hasUnsavedWork()).toBe(true);
  });
});

describe("conflict (no silent last-write-wins)", () => {
  async function conflictedHarness(): Promise<Harness> {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    h.type(BODY_B);
    h.advance(1000);
    await h.respond(new DocumentApiError(409, "REVISION_CONFLICT", "revision moved", 9));
    return h;
  }

  it("stops autosaving on 409 and surfaces the server revision", async () => {
    const h = await conflictedHarness();
    expect(h.coordinator.getStatus()).toEqual({
      kind: "conflict",
      revision: 7,
      serverRevision: 9,
      at: expect.any(String),
    });
    h.type(BODY_C);
    h.advance(10000);
    expect(h.requests).toHaveLength(1); // no silent retry/overwrite
  });

  it("overwrites only through the explicit decision, CAS against the server revision", async () => {
    const h = await conflictedHarness();
    h.type(BODY_C);
    h.coordinator.overwriteConflict(9);
    expect(h.requests).toHaveLength(2);
    expect(h.requests[1]).toMatchObject({ revision: 9 });
    expect(JSON.stringify(h.requests[1].body)).toBe(JSON.stringify(BODY_C));
    // A fresh explicit decision uses a fresh key; the conflicted attempt's
    // key is not reused.
    expect(h.requests[1].idempotencyKey).not.toBe(h.requests[0].idempotencyKey);
    await h.respond(ACK(10));
    expect(h.coordinator.getStatus()).toMatchObject({ kind: "clean", revision: 10 });
  });

  it("a raced overwrite that 409s again re-surfaces the conflict", async () => {
    const h = await conflictedHarness();
    h.coordinator.overwriteConflict(9);
    await h.respond(new DocumentApiError(409, "REVISION_CONFLICT", "moved again", 11));
    expect(h.coordinator.getStatus()).toMatchObject({ kind: "conflict", serverRevision: 11 });
    h.type(BODY_C);
    h.advance(10000);
    expect(h.requests).toHaveLength(2);
  });
});

describe("typed errors keep the content", () => {
  it("401 (expired auth) is retryable but not auto-resumed by typing", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    h.type(BODY_B);
    h.advance(1000);
    await h.respond(new DocumentApiError(401, "AUTHENTICATION_REQUIRED", "Authentication is required"));
    expect(h.coordinator.getStatus()).toMatchObject({ kind: "error", retryable: true });
    h.type(BODY_C);
    h.advance(10000);
    expect(h.requests).toHaveLength(1);
    h.coordinator.retry();
    expect(h.requests).toHaveLength(2);
  });

  it("404 (deleted elsewhere) is not retryable", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    h.type(BODY_B);
    h.advance(1000);
    await h.respond(new DocumentApiError(404, "NOT_FOUND", "Resource was not found"));
    expect(h.coordinator.getStatus()).toMatchObject({ kind: "error", retryable: false });
  });

  it("413 keeps the content and editing resumes scheduling (the fix can save)", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    h.type(BODY_B);
    h.advance(1000);
    await h.respond(new DocumentApiError(413, "PAYLOAD_TOO_LARGE", "Request is too large"));
    expect(h.coordinator.getStatus()).toMatchObject({ kind: "error", retryable: true });
    h.type(BODY_C);
    h.advance(1000);
    expect(h.requests).toHaveLength(2);
    expect(h.coordinator.getStatus().kind).toBe("saving");
  });
});

describe("unload warning and lifecycle", () => {
  it("reports unsaved work for every unacknowledged state", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    expect(h.coordinator.hasUnsavedWork()).toBe(false);
    h.type(BODY_B);
    expect(h.coordinator.hasUnsavedWork()).toBe(true);
  });

  it("a stopped coordinator never fires again", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    h.coordinator.stop();
    h.type(BODY_B);
    h.advance(10000);
    h.coordinator.saveNow();
    expect(h.requests).toHaveLength(0);
  });

  it("adoptServerState re-arms after a reload without scheduling a save", async () => {
    const h = makeHarness();
    h.coordinator.adoptBaseline(7);
    h.type(BODY_B);
    h.advance(1000);
    await h.respond(new DocumentApiError(409, "REVISION_CONFLICT", "revision moved", 9));
    h.coordinator.adoptServerState(9);
    expect(h.coordinator.getStatus()).toMatchObject({ kind: "clean", revision: 9 });
    h.advance(10000);
    expect(h.requests).toHaveLength(1);
  });
});
