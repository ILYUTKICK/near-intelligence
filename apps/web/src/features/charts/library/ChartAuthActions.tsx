"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { SaveChartButton } from "../saved/SaveChartButton";
import { AddChartToResearch } from "../add-to-research/AddChartToResearch";
import type { SaveInput } from "../saved/api";
import { AUTH_CHANGE, AUTH_CHANGE_STORAGE } from "@/lib/auth/change";

/**
 * Public-to-private action continuation (NI-034; reused by the public data
 * explorer NI-015 through the `basePath` prop).
 *
 * For anonymous visitors the private actions (Save chart / Add to Research)
 * are offered as safe auth continuations: clicking starts the sign-in flow
 * with an internal `next` payload that preserves the chart context — the
 * pinned definition version, range, dataset version and validated filters —
 * exactly as INFORMATION_ARCHITECTURE.md requires: "Public-to-private
 * actions preserve a short-lived internal pending action with chart
 * ID/version/range/filter context, never serialized private document
 * content or arbitrary redirect URLs."
 *
 * The payload is built only from the mounted detail route's own href output
 * and re-verified to be an internal path under `basePath` before navigation
 * (no open-redirect injection; the login gateway validates it again
 * server-side through safeInternalReturnTo). Pending UI announces the
 * continuation honestly.
 *
 * NI-035/NI-041 connect resolved, signed-in actions to owned persistence.
 * Their payload comes from the mounted view, including its inspected dataset;
 * account changes unmount action state before another identity can use it.
 */
export function ChartAuthActions({
  nextPath,
  chartTitle,
  basePath = "/charts/",
  saveInput,
}: {
  nextPath: string;
  chartTitle: string;
  /** Internal-path base the continuation may target (with trailing slash). */
  basePath?: string;
  saveInput?: SaveInput;
}) {
  const router = useRouter();
  const [session, setSession] = useState<{
    status: "checking" | "anonymous" | "authenticated" | "unknown";
    subject: string | null;
  }>({ status: "checking", subject: null });
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let controller = new AbortController();
    function check(resetIdentity = false) {
      controller.abort(); controller = new AbortController();
      const signal = controller.signal;
      setSession((previous) => ({ status: "checking", subject: resetIdentity ? null : previous.subject }));
      fetch("/api/auth/session", { credentials: "same-origin", cache: "no-store", signal })
        .then(async (response) => {
          if (response.status === 401) {
            if (!signal.aborted) setSession({ status: "anonymous", subject: null });
            return;
          }
          if (!response.ok) throw new Error("Session unavailable");
          const value: unknown = await response.json();
          if (!value || typeof value !== "object" || !("subject" in value)
            || typeof value.subject !== "string" || !value.subject || value.subject === "unknown") {
            throw new Error("Session identity unavailable");
          }
          if (!signal.aborted) setSession({ status: "authenticated", subject: value.subject });
        })
        .catch(() => { if (!signal.aborted) setSession((previous) => ({ ...previous, status: "unknown" })); });
    }
    const authChange = () => check(true);
    const focus = () => check();
    const storage = (event: StorageEvent) => { if (event.key === AUTH_CHANGE_STORAGE) check(true); };
    check();
    window.addEventListener(AUTH_CHANGE, authChange);
    window.addEventListener("focus", focus);
    window.addEventListener("storage", storage);
    return () => { controller.abort(); window.removeEventListener(AUTH_CHANGE, authChange);
      window.removeEventListener("focus", focus); window.removeEventListener("storage", storage); };
  }, []);

  function continueToSignIn(): void {
    // Defense in depth: the payload is constructed internally, but never
    // navigate unless it is an internal path under this route's base (no
    // arbitrary URLs).
    if (!isInternalPath(nextPath, basePath)) {
      setPending(false);
      return;
    }
    setPending(true);
    router.push(`/login?next=${encodeURIComponent(nextPath)}`);
  }

  // Retain the mounted attempt for a known subject while hiding all its UI.
  // A verified different subject (or an explicit auth-change signal) resets it.
  if (session.subject && saveInput) {
    return <div key={`${session.subject}:${JSON.stringify(saveInput)}`} className="flex flex-wrap gap-2">
      <SaveChartButton input={saveInput} suspended={session.status !== "authenticated"} />
      <AddChartToResearch input={saveInput} suspended={session.status !== "authenticated"} />
      {session.status === "unknown" ? <p role="status">The sign-in state could not be checked. Try returning to this window again.</p> : null}
    </div>;
  }

  if (session.status === "checking") {
    return null;
  }

  if (session.status === "anonymous") {
    return (
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={continueToSignIn} pending={pending}>
            Sign in to save this chart
          </Button>
          <Button variant="secondary" onClick={continueToSignIn} pending={pending}>
            Sign in to add it to research
          </Button>
        </div>
        {pending ? (
          <p role="status" className="text-ui leading-ui text-text-secondary">
            Signing in to continue — this chart and its selection are preserved in the sign-in link.
          </p>
        ) : (
          <p className="text-ui leading-ui text-text-secondary">
            Saving and adding to research need your account. Signing in returns you to
            &ldquo;{chartTitle}&rdquo; with the current selection preserved.
          </p>
        )}
      </div>
    );
  }

  if (session.status === "authenticated") {
    return (
      <p className="text-ui leading-ui text-text-secondary">A resolved chart is required before saving.</p>
    );
  }

  return (
    <p className="text-ui leading-ui text-text-secondary">
      The sign-in state could not be checked, so private actions are not offered right now.
      The chart itself stays fully available.
    </p>
  );
}

/** Only an internal path under `base` (never "//", never absolute URLs) qualifies. */
export function isInternalPath(value: string, base: string): boolean {
  return value.startsWith(base) && !value.startsWith("//") && !value.includes("\\");
}

/** Only an internal /charts path (never "//", never absolute URLs) qualifies. */
export function isInternalChartPath(value: string): boolean {
  return isInternalPath(value, "/charts/");
}
