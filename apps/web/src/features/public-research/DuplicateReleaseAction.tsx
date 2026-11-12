"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AUTH_CHANGE, AUTH_CHANGE_STORAGE } from "@/lib/auth/change";

interface ReleaseFacts {
  version: number;
  title: string;
}

type SessionState = {
  status: "checking" | "anonymous" | "authenticated" | "unknown";
  subject: string | null;
};

/**
 * Public-to-private duplication continuation for the public research release
 * (NI-045). The public thesis page offers the duplication CTA only when the
 * server actually has a published release for the configured slug: the
 * availability check is a real public read of `/api/publications/{slug}` —
 * when no release is seeded the component renders NOTHING (the honest
 * absent state; the page never fakes availability). When a release exists,
 * anonymous visitors get the safe sign-in continuation (`next` preserves the
 * internal /research path only — the login gateway re-validates it), and
 * signed-in users get the duplicate dialog.
 *
 * The dialog pins the release version it READ (the duplicate request carries
 * `publication_version`, never an implicit "latest"), sends a client-
 * generated UUID Idempotency-Key (a lost response replays the same private
 * copy instead of a second one), and never sends ownership or content — the
 * API clones the release server-side with retained attribution.
 */
export function DuplicateReleaseAction({ slug, nextPath }: { slug: string; nextPath: string }) {
  const router = useRouter();
  const id = useId();
  // Release facts from the public read; null means "not available" (absent,
  // unreachable) and the CTA renders nothing instead of pretending.
  const [release, setRelease] = useState<ReleaseFacts | null>(null);
  const [session, setSession] = useState<SessionState>({ status: "checking", subject: null });
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [pending, setPending] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const attempt = useRef<{ key: string } | null>(null);
  const busy = useRef(false);

  const checkSession = useCallback(() => {
    // State changes only when an answer arrives (no synchronous setState in
    // the effect body); a stale identity is replaced atomically by the next
    // answer, exactly like the other public-to-private continuations.
    fetch("/api/auth/session", { credentials: "same-origin", cache: "no-store" })
      .then(async (response) => {
        if (response.status === 401) {
          setSession({ status: "anonymous", subject: null });
          return;
        }
        if (!response.ok) throw new Error("Session unavailable");
        const value: unknown = await response.json();
        if (!value || typeof value !== "object" || !("subject" in value)
          || typeof value.subject !== "string" || !value.subject || value.subject === "unknown") {
          throw new Error("Session identity unavailable");
        }
        setSession({ status: "authenticated", subject: value.subject });
      })
      .catch(() => { setSession((previous) => ({ ...previous, status: "unknown" })); });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    // Availability is a real public read; 404 keeps the page exactly as it
    // was before duplication shipped (no seeded release yet).
    fetch(`/api/publications/${slug}`, { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (response.status === 404) {
          setRelease(null);
          return;
        }
        if (!response.ok) throw new Error("Release unavailable");
        const value: unknown = await response.json();
        if (!value || typeof value !== "object" || !("version" in value) || !("title" in value)
          || typeof value.version !== "number" || typeof value.title !== "string") {
          throw new Error("Release response invalid");
        }
        const { version, title: releaseTitle } = value;
        setRelease({ version, title: releaseTitle });
        // The pre-filled private title is the release title, once, unless the
        // field already holds an edited value (it starts empty per mount).
        setTitle((previous) => previous || releaseTitle);
      })
      .catch(() => { if (!controller.signal.aborted) setRelease(null); });
    const onAuthChange = () => checkSession();
    const onStorage = (event: StorageEvent) => { if (event.key === AUTH_CHANGE_STORAGE) checkSession(); };
    const onFocus = () => checkSession();
    checkSession();
    window.addEventListener(AUTH_CHANGE, onAuthChange);
    window.addEventListener("focus", onFocus);
    window.addEventListener("storage", onStorage);
    return () => {
      controller.abort();
      window.removeEventListener(AUTH_CHANGE, onAuthChange);
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("storage", onStorage);
    };
  }, [slug, checkSession]);

  function changeOpen(next: boolean) {
    if (busy.current) return;
    if (!next) { attempt.current = null; setConfirmed(false); setError(null); }
    setOpen(next);
  }

  async function confirm() {
    if (busy.current || !release || session.status !== "authenticated") return;
    const trimmed = title.trim();
    if (!trimmed) {
      setError("Give the private copy a title before saving it.");
      return;
    }
    busy.current = true;
    setPending(true);
    setConfirmed(true);
    setError(null);
    attempt.current ??= { key: crypto.randomUUID() };
    const current = attempt.current;
    try {
      const response = await fetch(`/api/publications/${slug}/duplicate`, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "content-type": "application/json",
          accept: "application/json",
          "idempotency-key": current.key,
        },
        body: JSON.stringify({ publication_version: release.version, title: trimmed }),
        signal: AbortSignal.timeout(15_000),
      });
      if (!response.ok) {
        throw new Error(await readErrorMessage(response));
      }
      const value: unknown = await response.json();
      if (!value || typeof value !== "object" || !("id" in value)
        || typeof value.id !== "string") {
        throw new Error("The saved copy could not be opened.");
      }
      setOpen(false);
      router.push(`/workspace/research/${value.id}`);
    } catch (submitError) {
      setError(submitError instanceof Error && submitError.message
        ? submitError.message
        : "The copy could not be saved. Try again.");
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  if (!release) {
    // Honest absence: no published release for this slug (or the public API
    // is unreachable) — the public page renders no duplication affordance.
    return null;
  }

  if (session.status === "checking") {
    return null;
  }

  if (session.status === "anonymous" || session.status === "unknown") {
    return (
      <div className="mt-6 max-w-(--width-prose)">
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            // Constructed internally; never an arbitrary redirect target.
            if (nextPath.startsWith("/research")) {
              router.push(`/login?next=${encodeURIComponent(nextPath)}`);
            }
          }}
        >
          Sign in to save a private copy
        </Button>
        {session.status === "unknown" ? (
          <p role="status" className="text-ui leading-ui text-text-secondary mt-2">
            The sign-in state could not be checked. Try returning to this window again.
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="mt-6 max-w-(--width-prose)">
      <Dialog open={open} onOpenChange={changeOpen}>
        <Button type="button" variant="secondary" onClick={() => changeOpen(true)}>
          Save a private copy
        </Button>
        <DialogContent>
          <DialogTitle>Save a private copy of this research</DialogTitle>
          <DialogDescription>
            Creates a new private document in your workspace cloned from the public release
            “{release.title}” (version {release.version}). The copy keeps the release&rsquo;s
            data and model pins and a source attribution; the public release itself is never
            changed by your later edits.
          </DialogDescription>
          <form
            onSubmit={(event) => { event.preventDefault(); void confirm(); }}
            className="mt-4 flex flex-col gap-4"
            noValidate
          >
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${id}-duplicate-title`}>Title of your private copy</Label>
              <Input
                id={`${id}-duplicate-title`}
                value={title}
                maxLength={200}
                required
                disabled={pending}
                autoComplete="off"
                onChange={(event) => setTitle(event.target.value)}
              />
            </div>
            {error ? (
              <p role="alert" className="text-ui leading-ui text-danger font-medium">
                {error}
              </p>
            ) : null}
            <div className="flex flex-wrap justify-end gap-2">
              <Button type="button" variant="secondary" disabled={pending} onClick={() => changeOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" pending={pending}>
                {confirmed ? "Retry saving the copy" : "Save private copy"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "error" in body) {
      const error = (body as { error?: { message?: unknown } }).error;
      if (error && typeof error.message === "string" && error.message) {
        return error.message;
      }
    }
  } catch {
    // A non-JSON body keeps the generic message.
  }
  if (response.status === 401) return "Your session has expired. Sign in again and retry.";
  if (response.status === 403) return "The request was refused. Sign in again and retry.";
  if (response.status === 404) return "The public release is no longer available to duplicate.";
  if (response.status === 409) return "This saving attempt conflicts with an earlier one. Use a new attempt.";
  return "The copy could not be saved. Try again.";
}
