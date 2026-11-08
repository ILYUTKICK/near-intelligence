import type { SaveRequestBody } from "./save-transport";

/**
 * Session draft recovery (NI-040 card: "memory draft/session recovery";
 * acceptance: "unsaved content recoverable"). While content is unacknowledged
 * the latest captured state is written to `sessionStorage` (survives a reload
 * or crash of the SAME tab; it never leaves the browser, so private content
 * stays client-side). A successful save clears the draft — the server then
 * holds the content. Storage failures (quota, privacy mode) are swallowed:
 * the autosave queue and unload warning do not depend on the draft.
 *
 * Session (not local) storage is deliberate: a persistent cross-session draft
 * would silently resurrect content the user may have discarded elsewhere.
 */

const DRAFT_KEY_PREFIX = "near-intelligence.editor-draft.";

export interface StoredDraft {
  /** The revision the draft content was based on (informational display). */
  baseRevision: number;
  /** ISO time of the capture that wrote the draft. */
  capturedAt: string;
  body: SaveRequestBody;
}

export function draftKey(documentId: string): string {
  return `${DRAFT_KEY_PREFIX}${documentId}`;
}

export function readStoredDraft(documentId: string): StoredDraft | null {
  try {
    const raw = sessionStorage.getItem(draftKey(documentId));
    if (raw === null) {
      return null;
    }
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed !== "object" ||
      parsed === null ||
      !("baseRevision" in parsed) ||
      !("capturedAt" in parsed) ||
      !("body" in parsed) ||
      typeof (parsed as StoredDraft).baseRevision !== "number" ||
      typeof (parsed as StoredDraft).capturedAt !== "string" ||
      typeof (parsed as StoredDraft).body !== "object" ||
      (parsed as StoredDraft).body === null
    ) {
      return null;
    }
    const body = (parsed as StoredDraft).body as SaveRequestBody;
    if (
      typeof body.schema_version !== "number" ||
      typeof body.content !== "object" ||
      body.content === null ||
      !Array.isArray(body.observed_contexts)
    ) {
      return null;
    }
    return parsed as StoredDraft;
  } catch {
    // Corrupt or unavailable storage: an absent draft is the honest state.
    return null;
  }
}

export function writeStoredDraft(documentId: string, draft: StoredDraft): void {
  try {
    sessionStorage.setItem(draftKey(documentId), JSON.stringify(draft));
  } catch {
    // Quota exceeded or storage disabled: autosave and the unload warning
    // remain the primary protection; the recovery offer simply won't exist.
  }
}

export function clearStoredDraft(documentId: string): void {
  try {
    sessionStorage.removeItem(draftKey(documentId));
  } catch {
    // Unavailable storage: nothing to clear.
  }
}
