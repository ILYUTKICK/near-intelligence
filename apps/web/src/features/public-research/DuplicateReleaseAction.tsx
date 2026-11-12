"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { z } from "zod";
import type { components } from "@near-intelligence/shared-types";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  apiErrorResponseSchema,
  DOCUMENT_TITLE_MAX_LENGTH,
  documentResponseSchema,
} from "@/features/documents/list/documents-schema";
import { privateFetch } from "@/lib/auth/private-fetch";
import { usePublicSession } from "@/lib/auth/use-public-session";

type ReleaseFacts = Pick<components["schemas"]["PublicationResponse"], "slug" | "version" | "title">;
type DuplicateInput = components["schemas"]["PublicationDuplicateRequest"];

const releaseFactsSchema: z.ZodType<ReleaseFacts> = z.object({
  slug: z.string(),
  version: z.number().int().positive(),
  title: z.string().min(1).max(DOCUMENT_TITLE_MAX_LENGTH),
});

export function DuplicateReleaseAction({ slug, nextPath }: { slug: string; nextPath: string }) {
  const [release, setRelease] = useState<ReleaseFacts | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    const signal = controller.signal;
    fetch("/api/publications/" + encodeURIComponent(slug), { cache: "no-store", signal })
      .then(async response => {
        const parsed = response.ok ? releaseFactsSchema.safeParse(await response.json()) : null;
        if (!signal.aborted) setRelease(parsed?.success && parsed.data.slug === slug ? parsed.data : null);
      })
      .catch(() => { if (!signal.aborted) setRelease(null); });
    return () => controller.abort();
  }, [slug]);

  return release?.slug === slug ? <ReleaseActions key={slug + ":" + release.version} release={release} nextPath={nextPath} /> : null;
}

function ReleaseActions({ release, nextPath }: { release: ReleaseFacts; nextPath: string }) {
  const router = useRouter();
  const { session, recheck } = usePublicSession();
  return (
    <div className="mt-6 max-w-(--width-prose)">
      {session.subject ? <DuplicateDialog key={session.subject} release={release} subject={session.subject}
        accountSignal={session.status === "authenticated" ? session.signal : null} /> : null}
      {session.status === "anonymous" ? <Button type="button" variant="secondary" onClick={() => {
        if (nextPath === "/research") router.push("/login?next=" + encodeURIComponent(nextPath));
      }}>Sign in to save a private copy</Button> : null}
      {session.status === "unknown" ? <div className="flex items-center gap-2">
        <p role="status" className="text-ui text-text-secondary">The sign-in state could not be checked.</p>
        <Button variant="quiet" onClick={recheck}>Retry sign-in check</Button>
      </div> : null}
    </div>
  );
}

function DuplicateDialog({ release, subject, accountSignal }: {
  release: ReleaseFacts; subject: string; accountSignal: AbortSignal | null;
}) {
  const router = useRouter();
  const id = useId();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(release.title);
  const [pending, setPending] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const attempt = useRef<{ key: string; input: DuplicateInput } | null>(null);
  const busy = useRef(false);

  function changeOpen(next: boolean) {
    if (!busy.current) setOpen(next);
  }

  async function confirm() {
    if (busy.current || !accountSignal || accountSignal.aborted) return;
    const trimmed = title.trim();
    if (!trimmed) {
      setError("Give the private copy a title before saving it.");
      return;
    }
    const signal = AbortSignal.any([accountSignal, AbortSignal.timeout(15_000)]);
    attempt.current ??= { key: crypto.randomUUID(), input: { publication_version: release.version, title: trimmed } };
    const current = attempt.current;
    busy.current = true;
    setPending(true);
    setConfirmed(true);
    setError(null);
    try {
      const response = await privateFetch("/api/publications/" + encodeURIComponent(release.slug) + "/duplicate", {
        method: "POST", signal,
        headers: { "content-type": "application/json", accept: "application/json", "idempotency-key": current.key,
          "x-session-subject": subject },
        body: JSON.stringify(current.input),
      });
      const body: unknown = await response.json().catch(() => null);
      signal.throwIfAborted();
      if (!response.ok) {
        const refusal = apiErrorResponseSchema.safeParse(body);
        if (response.status === 422 && refusal.success) {
          attempt.current = null;
          setConfirmed(false);
        }
        throw new Error(refusal.success ? refusal.data.error.message : duplicateError(response.status));
      }
      const copy = documentResponseSchema.safeParse(body);
      if (!copy.success) throw new Error("The saved copy could not be opened. Retry the same copy.");
      setOpen(false);
      router.push("/workspace/research/" + copy.data.id);
    } catch (cause) {
      setError(signal.aborted ? "The request was interrupted. Retry the same copy."
        : cause instanceof Error ? cause.message : "The copy could not be saved. Try again.");
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  if (!accountSignal) return null;
  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild><Button type="button" variant="secondary">Save a private copy</Button></DialogTrigger>
      <DialogContent>
        <DialogTitle>Save a private copy of this research</DialogTitle>
        <DialogDescription>
          Copy “{release.title}” (version {release.version}) into your workspace with its source attribution,
          data pins and model pins.
        </DialogDescription>
        <form onSubmit={event => { event.preventDefault(); void confirm(); }} className="mt-4 flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={id}>Title of your private copy</Label>
            <Input id={id} value={title} maxLength={DOCUMENT_TITLE_MAX_LENGTH} required
              disabled={pending || confirmed} autoComplete="off" onChange={event => setTitle(event.target.value)} />
          </div>
          {error ? <p role="alert" className="text-ui leading-ui text-danger font-medium">{error}</p> : null}
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="secondary" disabled={pending} onClick={() => changeOpen(false)}>Cancel</Button>
            <Button type="submit" pending={pending}>{confirmed ? "Retry saving the copy" : "Save private copy"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function duplicateError(status: number): string {
  if (status === 401 || status === 403) return "Your session could not be verified. Sign in again and retry.";
  if (status === 404) return "The pinned public release is unavailable.";
  if (status === 409) return "The signed-in account changed. Reopen the form to continue.";
  return "The copy could not be saved. Try again.";
}
