"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

/**
 * Public-to-private action continuation (NI-034).
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
 * The payload is built only from `chartDetailHref` output and re-verified to
 * be an internal /charts path before navigation (no open-redirect
 * injection; the login gateway validates it again server-side through
 * safeInternalReturnTo). Pending UI announces the continuation honestly.
 *
 * The persistence half of the flow (destination picker, actual save) is the
 * saved-charts/research-insertion scope (NI-035/NI-041): a signed-in visitor
 * sees an honest pending note instead of a dead button.
 */
export function ChartAuthActions({ nextPath, chartTitle }: { nextPath: string; chartTitle: string }) {
  const router = useRouter();
  const [session, setSession] = useState<"checking" | "anonymous" | "authenticated" | "unknown">("checking");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/auth/session", { credentials: "same-origin", signal: controller.signal })
      .then((response) => {
        if (response.ok) {
          setSession("authenticated");
        } else if (response.status === 401) {
          setSession("anonymous");
        } else {
          setSession("unknown");
        }
      })
      .catch(() => setSession("unknown"));
    return () => controller.abort();
  }, []);

  function continueToSignIn(): void {
    // Defense in depth: the payload is constructed internally, but never
    // navigate unless it is an internal /charts path (no arbitrary URLs).
    if (!isInternalChartPath(nextPath)) {
      setPending(false);
      return;
    }
    setPending(true);
    router.push(`/login?next=${encodeURIComponent(nextPath)}`);
  }

  if (session === "checking") {
    return null;
  }

  if (session === "anonymous") {
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

  if (session === "authenticated") {
    return (
      <p className="text-ui leading-ui text-text-secondary">
        You are signed in. Saving charts to your workspace and adding them to research are
        delivered by the saved-charts persistence, which is not implemented yet — nothing is
        saved from this page rather than pretending otherwise.
      </p>
    );
  }

  return (
    <p className="text-ui leading-ui text-text-secondary">
      The sign-in state could not be checked, so private actions are not offered right now.
      The chart itself stays fully available.
    </p>
  );
}

/** Only an internal /charts path (never "//", never absolute URLs) qualifies. */
export function isInternalChartPath(value: string): boolean {
  return value.startsWith("/charts/") && !value.startsWith("//") && !value.includes("\\");
}
