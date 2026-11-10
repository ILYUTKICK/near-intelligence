"use client";
import { useCallback, useEffect, useRef, useState } from "react";

import { AUTH_CHANGE, AUTH_CHANGE_STORAGE } from "@/lib/auth/change";

/**
 * NI-062 identity guard for the full editor workbench (the recorded NI-042
 * audit input: "workbench.tsx retains loaded document/recovery content
 * without auth-change, focus or storage identity revalidation"). The chart
 * provider (NI-042) revalidates only chart controls; this hook revalidates
 * the IDENTITY the loaded content belongs to, on the same signals:
 *
 * - a fresh verified `/api/auth/session` answer on mount, the AUTH_CHANGE
 *   event (login/logout/demo announce it), the cross-tab storage signal,
 *   focus and visibility change — the abandoned-tab scenarios;
 * - the first VERIFIED subject becomes the content's owner; any later
 *   verified DIFFERENT subject proves a cross-tab account switch: `onChanged`
 *   fires and the caller must not retain or submit the previous principal's
 *   content any further (the workbench unmounts the editor and clears the
 *   local recovery draft; the server-side RLS 404 remains the write backstop);
 * - a verified 401 (session ended) is deliberately NOT a change: the
 *   session that loaded the content ended (expiry/logout/invalidation) and
 *   the content still belongs to the SAME verified owner. The NI-040
 *   recovery contract keeps the tab's content ("sign in again, then retry
 *   the save") so the same user's re-authentication can acknowledge it; any
 *   later DIFFERENT verified subject still clears everything. This tradeoff
 *   (a signed-out tab retains its own owner's content until a new principal
 *   verifies, with every submission path dead) is recorded in
 *   docs/qa/ni062-security-review.md;
 * - transport failures and 503s verify nothing: the guard stays suspended
 *   instead of destructively clearing on an outage (same rule as the chart
 *   provider).
 *
 * `verify()` runs the same check on demand (the copy-as-new gate) so no
 * content can be carried into a NEW owner's document between the last
 * signal and the click.
 */

export interface SessionOwnerGuard {
  /** Latest verified subject (null until one check verified a session). */
  readonly subject: string | null;
  /** The verified subject the loaded content belongs to (first check). */
  readonly owner: string | null;
  /**
   * Register a listener that fires once, when a verified check proves a
   * DIFFERENT principal than the owner. Returns the unsubscribe function.
   */
  readonly onChanged: (listener: () => void) => () => void;
  /**
   * Fresh re-verification; resolves with the verified subject (null when no
   * session could be verified right now). Updates owner/onChanged like any
   * signal-driven check.
   */
  readonly verify: () => Promise<string | null>;
}

export function useSessionOwnerGuard(): SessionOwnerGuard {
  const [subject, setSubject] = useState<string | null>(null);
  const [owner, setOwner] = useState<string | null>(null);
  const ownerRef = useRef<string | null>(null);
  const changedRef = useRef(false);
  const controllerRef = useRef<AbortController | null>(null);
  const listenersRef = useRef<Set<() => void>>(new Set());

  // One live check at a time: a newer check aborts the previous one, and the
  // final unmount aborts whatever is still in flight. All setState calls run
  // after the awaited fetch resolves (event callbacks, never during render).
  const check = useCallback(async (): Promise<string | null> => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const signal = controller.signal;
    try {
      const response = await fetch("/api/auth/session", {
        credentials: "same-origin",
        cache: "no-store",
        signal,
      });
      if (signal.aborted) {
        return null;
      }
      if (response.status === 401) {
        // Verified session end. The owner (if established) still matches the
        // content: keep it for the same-user recovery path (see module doc).
        setSubject(null);
        return null;
      }
      if (!response.ok) {
        return null; // outage/config error: verify nothing, stay suspended
      }
      const value: unknown = await response.json();
      if (signal.aborted) {
        return null;
      }
      if (!value || typeof value !== "object" || !("subject" in value)
        || typeof value.subject !== "string" || !value.subject
        || value.subject === "unknown") {
        return null;
      }
      const verified = value.subject;
      if (ownerRef.current === null) {
        ownerRef.current = verified;
        setOwner(verified);
      } else if (ownerRef.current !== verified && !changedRef.current) {
        changedRef.current = true;
        for (const listener of [...listenersRef.current]) {
          listener();
        }
      }
      setSubject(verified);
      return verified;
    } catch {
      // Network failure/abort: nothing is verified; the next signal retries.
      return null;
    }
  }, []);

  // On-demand re-verification (copy-as-new gate).
  const verify = useCallback((): Promise<string | null> => {
    return check();
  }, [check]);

  const onChanged = useCallback((listener: () => void) => {
    listenersRef.current.add(listener);
    return () => {
      listenersRef.current.delete(listener);
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const onSignal = () => { void check(); };
    const onStorage = (event: StorageEvent) => {
      if (event.key === AUTH_CHANGE_STORAGE) {
        void check();
      }
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        void check();
      }
    };
    // The mount check runs outside the effect body (a verified answer is an
    // event callback, not a synchronous effect state update).
    const mountHandle = setTimeout(onSignal, 0);
    window.addEventListener(AUTH_CHANGE, onSignal);
    window.addEventListener("focus", onSignal);
    window.addEventListener("storage", onStorage);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      clearTimeout(mountHandle);
      controllerRef.current?.abort();
      window.removeEventListener(AUTH_CHANGE, onSignal);
      window.removeEventListener("focus", onSignal);
      window.removeEventListener("storage", onStorage);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [check]);

  return { subject, owner, onChanged, verify };
}
