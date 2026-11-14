"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { AddChartToResearch } from "../add-to-research/AddChartToResearch";
import type { SaveInput } from "../saved/api";
import { usePublicSession } from "@/lib/auth/use-public-session";

import { isInternalPath } from "./ChartAuthActions";

/**
 * NI-095 dashboard-card action: exactly ONE visible action per chart card —
 * "+ Add to research". Signed-in visitors get the real owned persistence;
 * anonymous visitors get the safe sign-in continuation that preserves the
 * chart context in the internal `next` payload (same contract as
 * ChartAuthActions, reduced to the single card action).
 */
export function CategoryChartActions({
  nextPath,
  basePath,
  saveInput,
}: {
  nextPath: string;
  basePath: string;
  saveInput: SaveInput;
}) {
  const router = useRouter();
  const { session } = usePublicSession();
  const [pending, setPending] = useState(false);

  if (session.subject) {
    return <div key={session.subject} className="flex flex-wrap gap-2">
      <AddChartToResearch input={saveInput} suspended={session.status !== "authenticated"} />
    </div>;
  }
  if (session.status === "checking") {
    return null;
  }
  if (session.status === "anonymous") {
    return (
      <>
        <Button
          variant="secondary"
          pending={pending}
          onClick={() => {
            if (!isInternalPath(nextPath, basePath)) {
              setPending(false);
              return;
            }
            setPending(true);
            router.push(`/login?next=${encodeURIComponent(nextPath)}`);
          }}
        >
          + Add to research
        </Button>
        {pending ? (
          <p role="status" className="text-ui leading-ui text-text-secondary">
            Signing in to continue — this chart and its selection are preserved in the sign-in link.
          </p>
        ) : null}
      </>
    );
  }
  return (
    <p className="text-ui leading-ui text-text-secondary">
      The sign-in state could not be checked, so private actions are not offered right now.
    </p>
  );
}
