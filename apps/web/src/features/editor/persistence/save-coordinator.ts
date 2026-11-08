import {
  isTransportFailure,
  newIdempotencyKey,
  type SaveAck,
  type SaveAttempt,
  type SaveRequestBody,
} from "./save-transport";

/**
 * Save scheduling state machine (NI-040), framework-free and deterministic
 * through injected timers. It implements the EDITOR_SPECIFICATION
 * "Persistence and revisions" paragraph exactly:
 *
 * - "Autosave after 1s idle, max 5s while typing; manual Save immediate."
 *   The first unsaved change starts a 1s idle timer (reset by every further
 *   change) and a hard 5s max timer; whichever fires first captures the
 *   editor state and saves. Manual save skips the wait.
 * - "Retain dirty buffer during pending save; only mark revision content
 *   clean if its captured editor state matches acknowledged payload. Changes
 *   typed while request runs remain dirty." At most one request is ever in
 *   flight; later content is coalesced and re-evaluated against the
 *   acknowledged payload at completion.
 * - "Use If-Match with last revision and an idempotency key per payload."
 *   Every attempt carries the last known revision as CAS and a fresh
 *   client-generated UUID key; a RETRY of an unknown-outcome (transport)
 *   failure reuses that attempt's key so a committed save replays instead of
 *   duplicating a revision (timeout-after-commit guarantee).
 * - "Do not enqueue unlimited writes." No queue grows: one in-flight attempt
 *   plus one retained retry attempt — the newest state is always coalesced
 *   into the next scheduled save, never duplicated per keystroke.
 * - "On 409 stop autosaving, preserve local version, show conflict options;
 *   never silently overwrite." A 409 stops all scheduling and surfaces the
 *   server's current revision; only an explicit user decision resumes.
 * - Card acceptance criteria: "Acknowledging older payload never clears
 *   newer dirty edits; network timeout retry cannot duplicate revisions; no
 *   silent last-write-wins; unsaved content recoverable".
 *
 * The coordinator never fabricates success: statuses are `clean` only after
 * a server acknowledgement (or the loaded baseline), `queued` after an
 * unknown-outcome transport failure (content held in the client), `conflict`
 * after a 409, and `error` for typed failures — local content is retained in
 * every non-clean state.
 */

export type SaveStatus =
  /** Everything acknowledged by the server (or the freshly loaded state). */
  | { kind: "clean"; revision: number; savedAt: string | null }
  /** Unsaved changes exist; autosave is scheduled. */
  | { kind: "dirty"; revision: number }
  /** One save request is in flight. */
  | { kind: "saving"; revision: number }
  /** Unknown-outcome transport failure: content held, retry pending. */
  | { kind: "queued"; revision: number; failedAt: string }
  /** 409 REVISION_CONFLICT: autosave stopped, server state surfaced. */
  | { kind: "conflict"; revision: number; serverRevision: number | null; at: string }
  /** Typed failure (401/404/413/422/428/local serialization) — content kept. */
  | {
      kind: "error";
      revision: number;
      /** HTTP status of the typed failure (0 for local serialization). */
      httpStatus: number;
      code: string;
      message: string;
      retryable: boolean;
    };

export interface SaveCoordinatorOptions {
  /** POSTs one attempt; resolves with the server acknowledgement. */
  transport: (attempt: SaveAttempt) => Promise<SaveAck>;
  /** Captures the current editor state as a save request body. May throw. */
  capture: () => SaveRequestBody;
  /** Idle window after the last change before autosave fires (spec: 1s). */
  idleDelayMs?: number;
  /** Hard ceiling while typing continues (spec: max 5s). */
  maxDelayMs?: number;
  /** Injectable timer/clock harness for deterministic tests. */
  timers?: TimerHarness;
  /** Injectable UUID source (defaults to the client's crypto fallback). */
  newKey?: () => string;
  /** Extra captures are reported (the hook persists the recovery draft). */
  onCapture?: (body: SaveRequestBody, revision: number) => void;
}

export interface TimerHarness {
  set(delayMs: number, handler: () => void): unknown;
  clear(handle: unknown): void;
  now(): number;
}

const defaultTimers: TimerHarness = {
  set: (delayMs, handler) => setTimeout(handler, delayMs),
  clear: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
  now: () => Date.now(),
};

/** Dirty states that must trigger the unload warning (nothing lost silently). */
export function hasUnsavedWork(status: SaveStatus): boolean {
  return status.kind !== "clean";
}

export class SaveCoordinator {
  private readonly documentId: string;
  private readonly transport: (attempt: SaveAttempt) => Promise<SaveAck>;
  private capture: () => SaveRequestBody;
  private readonly idleDelayMs: number;
  private readonly maxDelayMs: number;
  private readonly timers: TimerHarness;
  private readonly newKey: () => string;
  private readonly onCapture: ((body: SaveRequestBody, revision: number) => void) | null;

  private status: SaveStatus;
  private listeners = new Set<(status: SaveStatus) => void>();
  private stopped = false;

  /** Stable string of the content the server already holds (clean reference). */
  private baselineBody: string | null = null;
  private idleHandle: unknown = null;
  private maxHandle: unknown = null;
  /** Clock anchor of the first unsaved change (max-delay ceiling). */
  private dirtyAnchor: number | null = null;

  private inFlight: SaveAttempt | null = null;
  /** Retained attempt after a transport failure; retried with the same key. */
  private retainedAttempt: SaveAttempt | null = null;
  /** A manual save arrived while a request was in flight: follow up at once. */
  private followUpManual = false;
  /** Throttle anchor for the recovery-draft capture. */
  private lastDraftCapture = Number.NEGATIVE_INFINITY;

  constructor(
    documentId: string,
    initialRevision: number,
    options: SaveCoordinatorOptions,
  ) {
    this.documentId = documentId;
    this.transport = options.transport;
    this.capture = options.capture;
    this.idleDelayMs = options.idleDelayMs ?? 1000;
    this.maxDelayMs = options.maxDelayMs ?? 5000;
    this.timers = options.timers ?? defaultTimers;
    this.newKey = options.newKey ?? newIdempotencyKey;
    this.onCapture = options.onCapture ?? null;
    this.status = { kind: "clean", revision: initialRevision, savedAt: null };
  }

  // -- observation ---------------------------------------------------------- //

  /**
   * Replaces the content capture (the React binding keeps it current without
   * recreating the coordinator). Tests inject their capture via the
   * constructor.
   */
  setCapture(capture: () => SaveRequestBody): void {
    this.capture = capture;
  }

  getStatus(): SaveStatus {
    return this.status;
  }

  onStatus(listener: (status: SaveStatus) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /** True while there is anything unacknowledged (drives the unload warning). */
  hasUnsavedWork(): boolean {
    return hasUnsavedWork(this.status);
  }

  /** The retained retry attempt, if any (exposed for an honest queue display). */
  getRetainedAttempt(): SaveAttempt | null {
    return this.retainedAttempt;
  }

  /** Captures the current editor content (download / new-copy actions). */
  captureLocal(): SaveRequestBody {
    return this.capture();
  }

  // -- state transitions ---------------------------------------------------- //

  /**
   * Adopts the current captured content as the acknowledged server state
   * (initial load and post-reload adoption). Everything the editor holds
   * after this call counts as clean until changed.
   */
  adoptBaseline(revision: number): void {
    if (this.stopped || this.inFlight) {
      return;
    }
    const body = this.capture();
    this.baselineBody = stableBody(body);
    this.cancelTimers();
    this.retainedAttempt = null;
    this.followUpManual = false;
    this.setStatus({ kind: "clean", revision, savedAt: null });
  }

  /**
   * The editor content changed. Cheap on purpose — the save itself captures
   * content only when a save actually fires, and the recovery draft is
   * re-captured at most once per idle window. Scheduling stops during
   * conflict/error/auth states (explicit resolution required) and while a
   * request is in flight (coalesced: the completion re-evaluates the latest
   * state), but edits in those states still update the recovery draft.
   */
  markChanged(): void {
    if (this.stopped || this.inFlight) {
      return;
    }
    const kind = this.status.kind;
    if (kind === "dirty" || kind === "clean") {
      if (this.dirtyAnchor === null) {
        this.dirtyAnchor = this.timers.now();
        this.maxHandle = this.timers.set(this.maxDelayMs, () => this.fireAutosave());
      }
      if (this.idleHandle !== null) {
        this.timers.clear(this.idleHandle);
      }
      this.idleHandle = this.timers.set(this.idleDelayMs, () => this.fireAutosave());
      if (kind !== "dirty") {
        this.setStatus({ kind: "dirty", revision: this.revisionOf() });
      }
      this.maybeCaptureForDraft();
      return;
    }
    // queued/conflict/error: autosave stays stopped, but the user is still
    // producing real content — keep the recovery draft current.
    this.maybeCaptureForDraft();
  }

  /** Manual Save: immediate, cancels pending autosave timers. */
  saveNow(): void {
    if (this.inFlight) {
      // One request in flight: coalesce — follow up immediately on
      // completion instead of waiting for the idle window again.
      this.followUpManual = true;
      return;
    }
    if (this.stopped) {
      return;
    }
    if (this.status.kind === "conflict") {
      // Saving against a stale revision would just 409 again; the shell
      // reopens the conflict dialog instead (explicit resolution only).
      return;
    }
    if (this.retainedAttempt) {
      // The retained attempt goes first (same idempotency key); the newest
      // content follows immediately after its acknowledgement.
      this.followUpManual = true;
      this.start(this.retainedAttempt);
      return;
    }
    this.fireAutosave();
  }

  /** Retry after a transport failure or a typed error (explicit or `online`). */
  retry(): void {
    if (this.stopped || this.inFlight) {
      return;
    }
    if (this.retainedAttempt) {
      this.start(this.retainedAttempt);
      return;
    }
    if (this.status.kind === "error" && this.status.retryable) {
      this.fireAutosave();
    }
  }

  /**
   * Explicit conflict resolution: overwrite the server with the local
   * content, compare-and-set against `revision` (the server's current
   * revision learned from the 409). Never called automatically.
   */
  overwriteConflict(revision: number): void {
    if (this.stopped || this.inFlight) {
      return;
    }
    this.cancelTimers();
    let body: SaveRequestBody;
    try {
      body = this.capture();
    } catch (error) {
      this.setLocalSerializeError();
      throw error;
    }
    // A fresh decision gets a fresh idempotency key (a new overwrite attempt
    // is not a retry of the conflicted one).
    const attempt: SaveAttempt = {
      documentId: this.documentId,
      revision,
      idempotencyKey: this.newKey(),
      body,
    };
    this.start(attempt);
  }

  /**
   * Adopts a server state after an explicit reload: the editor now holds the
   * server content, which becomes the acknowledged baseline.
   */
  adoptServerState(revision: number): void {
    if (this.stopped || this.inFlight) {
      return;
    }
    const body = this.capture();
    this.baselineBody = stableBody(body);
    this.cancelTimers();
    this.retainedAttempt = null;
    this.followUpManual = false;
    this.setStatus({ kind: "clean", revision, savedAt: null });
  }

  /** Cancels timers and ignores all future work (component unmount). */
  stop(): void {
    this.stopped = true;
    this.cancelTimers();
    this.listeners.clear();
  }

  /** True after stop(); the React binding re-arms with a fresh instance. */
  isStopped(): boolean {
    return this.stopped;
  }

  // -- internals ------------------------------------------------------------ //

  private revisionOf(): number {
    return this.status.revision;
  }

  /**
   * Throttled recovery-draft capture (once per idle window). Content equal to
   * the acknowledged baseline writes nothing; a capture failure (defensive)
   * keeps the previous draft.
   */
  private maybeCaptureForDraft(): void {
    const now = this.timers.now();
    if (now - this.lastDraftCapture < this.idleDelayMs) {
      return;
    }
    this.lastDraftCapture = now;
    let body: SaveRequestBody;
    try {
      body = this.capture();
    } catch {
      return;
    }
    if (this.baselineBody !== null && stableBody(body) === this.baselineBody) {
      return;
    }
    this.onCapture?.(body, this.revisionOf());
  }

  private fireAutosave(): void {
    if (this.stopped || this.inFlight) {
      return;
    }
    if (this.listeners.size === 0) {
      // Nothing is subscribed: the editor is gone (final unmount). A pending
      // autosave timer must not fire a stray request into whatever comes
      // next — the component's own unmount cancelled nothing, so go inert.
      this.cancelTimers();
      this.retainedAttempt = null;
      return;
    }
    this.cancelTimers();
    let body: SaveRequestBody;
    try {
      body = this.capture();
    } catch {
      // The editor cannot produce content the canonical schema rejects; this
      // is defensive. Nothing is sent, content stays in the editor.
      this.setLocalSerializeError();
      return;
    }
    // Content identical to the acknowledged baseline needs no revision
    // (e.g. the user typed and undid back): stay clean, no phantom save.
    if (this.baselineBody !== null && stableBody(body) === this.baselineBody) {
      this.dirtyAnchor = null;
      this.setStatus({ kind: "clean", revision: this.revisionOf(), savedAt: null });
      return;
    }
    const attempt: SaveAttempt = {
      documentId: this.documentId,
      revision: this.revisionOf(),
      idempotencyKey: this.newKey(),
      body,
    };
    this.onCapture?.(body, attempt.revision);
    this.start(attempt);
  }

  private start(attempt: SaveAttempt): void {
    this.cancelTimers();
    this.retainedAttempt = null;
    this.inFlight = attempt;
    this.onCapture?.(attempt.body, attempt.revision);
    this.setStatus({ kind: "saving", revision: this.revisionOf() });
    void this.transport(attempt).then(
      (ack) => this.handleAck(attempt, ack),
      (error: unknown) => this.handleFailure(attempt, error),
    );
  }

  private handleAck(attempt: SaveAttempt, ack: SaveAck): void {
    this.inFlight = null;
    if (this.stopped) {
      return;
    }
    // Only the captured editor state that MATCHES the acknowledged payload
    // becomes clean; anything typed while the request ran stays dirty
    // (card acceptance: "Acknowledging older payload never clears newer
    // dirty edits").
    let current: string | null = null;
    try {
      current = stableBody(this.capture());
    } catch {
      current = null;
    }
    const acknowledged = stableBody(attempt.body);
    const matches = current !== null && current === acknowledged;
    this.dirtyAnchor = null;
    if (matches) {
      this.baselineBody = acknowledged;
      this.followUpManual = false;
      this.setStatus({ kind: "clean", revision: ack.revision, savedAt: ack.savedAt });
      return;
    }
    // Newer edits exist (or could not be read): remain dirty at the new
    // revision and schedule the coalesced follow-up.
    if (this.followUpManual) {
      this.followUpManual = false;
      this.fireAutosave();
      return;
    }
    this.setStatus({ kind: "dirty", revision: ack.revision });
    this.markChanged();
  }

  private handleFailure(attempt: SaveAttempt, error: unknown): void {
    this.inFlight = null;
    if (this.stopped) {
      return;
    }
    if (isTransportFailure(error)) {
      // Unknown outcome: the server may have committed. Retain the attempt
      // (with its idempotency key) and surface an honest held state — never
      // a fabricated success, never a silent drop.
      this.retainedAttempt = attempt;
      this.setStatus({
        kind: "queued",
        revision: this.revisionOf(),
        failedAt: new Date(this.timers.now()).toISOString(),
      });
      return;
    }
    const apiError = error as {
      status?: number;
      code?: string;
      message?: string;
      currentRevision?: number | null;
    };
    if (apiError.status === 409) {
      // No silent last-write-wins: autosave stops, the server's current
      // revision is surfaced for the explicit reload/overwrite decision.
      this.cancelTimers();
      this.setStatus({
        kind: "conflict",
        revision: this.revisionOf(),
        serverRevision: apiError.currentRevision ?? null,
        at: new Date(this.timers.now()).toISOString(),
      });
      return;
    }
    this.cancelTimers();
    const status = apiError.status ?? 0;
    this.setStatus({
      kind: "error",
      revision: this.revisionOf(),
      httpStatus: status,
      code: apiError.code ?? "UNKNOWN_ERROR",
      message: describeSaveError(status, apiError.message),
      retryable: status !== 404,
    });
  }

  private setLocalSerializeError(): void {
    this.cancelTimers();
    this.setStatus({
      kind: "error",
      revision: this.revisionOf(),
      httpStatus: 0,
      code: "LOCAL_SERIALIZE",
      message: "The current content could not be serialized for saving — nothing was sent.",
      retryable: false,
    });
  }

  private cancelTimers(): void {
    if (this.idleHandle !== null) {
      this.timers.clear(this.idleHandle);
      this.idleHandle = null;
    }
    if (this.maxHandle !== null) {
      this.timers.clear(this.maxHandle);
      this.maxHandle = null;
    }
  }

  private setStatus(status: SaveStatus): void {
    // Re-notifying an unchanged status would re-render the shell for nothing
    // (and re-run baseline effects in a loop): skip equal statuses and keep
    // the current object identity.
    if (statusEquals(this.status, status)) {
      return;
    }
    this.status = status;
    for (const listener of this.listeners) {
      listener(status);
    }
  }
}

function statusEquals(a: SaveStatus, b: SaveStatus): boolean {
  if (a.kind !== b.kind) {
    return false;
  }
  return JSON.stringify(a) === JSON.stringify(b);
}

function describeSaveError(status: number, serverMessage?: string): string {
  if (status === 401) {
    return "Your session has expired. Your edits are kept in this tab — sign in again, then retry the save.";
  }
  if (status === 404) {
    return "This document no longer exists (it may have been deleted in another session). Your edits are kept in this tab — download a local copy to preserve them.";
  }
  if (status === 413) {
    return "The document exceeds the server's size limit. Your edits are kept in this tab — reduce the content size, then retry.";
  }
  return serverMessage || "The save was rejected by the server. Your edits are kept in this tab.";
}

/**
 * Deterministic string form of a request body for equality checks. The
 * canonical transform produces a stable key order for the same logical
 * content, so plain JSON.stringify is injective on the values produced here.
 * A false "different" (key-order change only) merely schedules one extra
 * save — the safe direction; a false "equal" is impossible for distinct
 * JSON values without cycles.
 */
export function stableBody(body: SaveRequestBody): string {
  return JSON.stringify(body);
}
