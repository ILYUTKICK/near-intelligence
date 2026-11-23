"use client";

import { useRouter } from "next/navigation";
import { Fragment, useState } from "react";

import { Button } from "@/components/ui/button";
import { AddChartToResearch } from "../add-to-research/AddChartToResearch";
import { SaveChartButton } from "../saved/SaveChartButton";
import type { SaveInput } from "../saved/api";
import { usePublicSession } from "@/lib/auth/use-public-session";

import { isInternalPath } from "./ChartAuthActions";

/**
 * Explorer chart actions. Workspace visitors can save their inspected chart
 * or add it to research. Signed-in visitors get real owned persistence;
 * anonymous visitors get the safe sign-in continuation that preserves the
 * chart context in the internal `next` payload (same contract as
 * ChartAuthActions, reduced to the single card action).
 */
export function CategoryChartActions({
  nextPath,
  basePath,
  saveInput,
  variant = "secondary",
  allowSave = false,
}: {
  nextPath: string;
  basePath: string;
  saveInput?: SaveInput;
  /** NI-101 restores saving on the private explorer and chart details. */
  allowSave?: boolean;
  /** The detail page renders anonymous continuation as the primary button. */
  variant?: "secondary" | "primary";
}) {
  const router = useRouter();
  const { session } = usePublicSession();
  const [pending, setPending] = useState(false);

  if (session.subject && saveInput) {
    return <div key={session.subject} className="flex flex-wrap gap-2">
      <Fragment key={JSON.stringify(saveInput)}>
        {allowSave ? <SaveChartButton input={saveInput} suspended={session.status !== "authenticated"} /> : null}
        <AddChartToResearch input={saveInput} suspended={session.status !== "authenticated"} />
      </Fragment>
    </div>;
  }
  if (session.status === "checking") {
    return null;
  }
  if (session.status === "anonymous") {
    return (
      <>
        <Button
          variant={variant}
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
