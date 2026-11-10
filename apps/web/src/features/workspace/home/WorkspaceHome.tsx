"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ErrorPanel, LoadingPanel } from "@/components/data-state/DataState";
import { Button, buttonVariants } from "@/components/ui/button";
import { createDocument } from "@/features/documents/list/documents-api";
import { formatUpdated } from "@/features/documents/list/format";
import { AUTH_CHANGE, AUTH_CHANGE_STORAGE } from "@/lib/auth/change";
import { getHome, type Home } from "./api";
import { HomeIndicators } from "./HomeIndicators";

/** Revalidate identity on focus/auth signals before displaying retained private state. */
export function WorkspaceHome() {
  const [session, setSession] = useState<{ subject: string | null; status: "checking" | "ready" | "error" }>({ subject: null, status: "checking" });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let controller = new AbortController();
    function check(reset = false) {
      controller.abort(); controller = new AbortController();
      const signal = controller.signal;
      setSession((previous) => ({ subject: reset ? null : previous.subject, status: "checking" }));
      fetch("/api/auth/session", { credentials: "same-origin", cache: "no-store", signal })
        .then(async (response) => {
          if (!response.ok) throw new Error("Session unavailable");
          const value: unknown = await response.json();
          if (!value || typeof value !== "object" || !("subject" in value) || typeof value.subject !== "string" || !value.subject || value.subject === "unknown") throw new Error("Session unavailable");
          if (!signal.aborted) setSession({ subject: value.subject, status: "ready" });
        }).catch(() => { if (!signal.aborted) setSession((previous) => ({ ...previous, status: "error" })); });
    }
    const auth = () => check(true);
    const focus = () => check();
    const storage = (event: StorageEvent) => { if (event.key === AUTH_CHANGE_STORAGE) check(true); };
    check();
    window.addEventListener(AUTH_CHANGE, auth); window.addEventListener("focus", focus); window.addEventListener("storage", storage);
    return () => { controller.abort(); window.removeEventListener(AUTH_CHANGE, auth); window.removeEventListener("focus", focus); window.removeEventListener("storage", storage); };
  }, [retry]);
  return <>
    {session.status === "checking" ? <LoadingPanel label="Checking your workspace session" /> : null}
    {session.status === "error" ? <ErrorPanel message="Your session could not be checked. Private research is hidden until it can be checked." onRetry={() => setRetry((value) => value + 1)} /> : null}
    {session.subject ? <HomeContent key={session.subject} suspended={session.status !== "ready"} /> : null}
  </>;
}

function HomeContent({ suspended }: { suspended: boolean }) {
  const router = useRouter();
  const [home, setHome] = useState<Home | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generation, setGeneration] = useState(0);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [acknowledgedId, setAcknowledgedId] = useState<string | null>(null);
  const createKey = useRef<string | null>(null);
  const active = useRef(true);
  const navigatedId = useRef<string | null>(null);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  useEffect(() => {
    if (!suspended && acknowledgedId && navigatedId.current !== acknowledgedId) {
      navigatedId.current = acknowledgedId;
      router.push(`/workspace/research/${acknowledgedId}`);
    }
  }, [suspended, acknowledgedId, router]);
  useEffect(() => {
    if (suspended) return;
    const controller = new AbortController();
    getHome(controller.signal).then((value) => { if (!controller.signal.aborted) { setHome(value); setError(null); } })
      .catch((failure: unknown) => { if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : "Your research could not be loaded."); });
    return () => controller.abort();
  }, [suspended, generation]);

  async function create() {
    if (creating || suspended) return;
    setCreating(true); setCreateError(null);
    // Retain the same intent across uncertain network failures and same-user revalidation.
    createKey.current ??= crypto.randomUUID();
    try {
      const document = await createDocument({ title: "Untitled research", idempotencyKey: createKey.current });
      if (active.current) {
        createKey.current = null;
        setAcknowledgedId(document.id);
      }
    } catch {
      if (active.current) setCreateError("The document could not be confirmed. Retry uses the same creation request.");
    } finally { if (active.current) setCreating(false); }
  }
  if (suspended) return null;
  const latest = home?.recent_documents[0];
  return <div className="min-w-0 max-w-(--width-content-max) space-y-8">
    <header>
      <p className="text-metadata text-text-secondary">Private workspace</p>
      <h1>{home && !home.counts.documents ? "Your research starts here" : "Welcome back"}</h1>
      <p className="mt-3 text-body leading-body text-text-secondary">Keep the question, evidence and limitations together. Pick up your work or start a new research document.</p>
      <div className="mt-4 flex flex-wrap gap-2" aria-label="Research actions">
        {/* The primary-variant utility color applies directly since the global
            anchor rule moved into the base cascade layer (NI-064). */}
        {latest ? <Link className={buttonVariants()} href={`/workspace/research/${latest.id}`}>Continue research<span className="sr-only">: {latest.title}</span></Link> : null}
        <Button variant={latest ? "secondary" : "primary"} pending={creating} onClick={create}>Create document</Button>
        <Link className={buttonVariants({ variant: "quiet" })} href="/workspace/research">My Research</Link>
      </div>
      {createError ? <p role="alert" className="mt-3 text-danger">{createError}</p> : null}
      <p className="mt-2 text-metadata text-text-secondary">Create saves an empty private document immediately, then opens its editor.</p>
    </header>
    {error ? <ErrorPanel message={home ? `${error} Showing the last loaded research for this account; it may have changed.` : error} onRetry={() => setGeneration((value) => value + 1)} /> : null}
    {!home && !error ? <LoadingPanel label="Loading your recent research" /> : null}
    {home ? <>
      <section aria-labelledby="recent-documents-heading">
        <h2 id="recent-documents-heading">Recent documents</h2>
        <p className="mt-2 text-metadata text-text-secondary">{home.counts.documents} owned document{home.counts.documents === 1 ? "" : "s"} · Up to five most recently updated</p>
        {home.recent_documents.length ? <ul className="mt-3 divide-y divide-border">
          {home.recent_documents.map((document) => <li key={document.id} className="min-w-0 py-3">
            <Link className="inline-flex min-h-11 items-center break-words text-link underline underline-offset-4 [overflow-wrap:anywhere]" href={`/workspace/research/${document.id}`}>{document.title}</Link>
            <p className="text-metadata text-text-secondary">Revision {document.revision} · Updated {formatUpdated(document.updated_at)} UTC</p>
          </li>)}
        </ul> : <p role="status" className="mt-3 rounded-surface border border-border p-4">No documents yet. Create your first document above, then explore data and save the evidence relevant to your question.</p>}
      </section>
      <section aria-labelledby="workflow-heading" className="rounded-surface border border-border bg-surface-muted p-4">
        <h2 id="workflow-heading">Research checklist</h2>
        <p className="mt-2 text-ui text-text-secondary [overflow-wrap:anywhere]">{latest ? `For your latest document: ${latest.title}` : "Start a document to begin this workflow."} These steps record work completed; they do not assess whether a claim is true.</p>
        <ul className="mt-3 space-y-2">
          {[["Create a document", Boolean(latest)], ["Organize it with a heading", Boolean(latest?.progress.headings)], ["Add a chart", Boolean(latest?.progress.charts)], ["Record an insight", Boolean(latest?.progress.insights)]].map(([label, done]) => <li key={String(label)} className="flex gap-2"><span aria-hidden="true">{done ? "✓" : "○"}</span><span>{label} — {done ? "Complete" : "To do"}</span></li>)}
        </ul>
      </section>
      <div className="grid min-w-0 gap-8 lg:grid-cols-2">
        <section aria-labelledby="recent-charts-heading">
          <h2 id="recent-charts-heading">Recent saved charts</h2>
          {home.recent_charts.length ? <ul className="mt-3 divide-y divide-border">{home.recent_charts.map((chart) => <li key={chart.id} className="min-w-0 py-3"><Link className="inline-flex min-h-11 items-center text-link underline [overflow-wrap:anywhere]" href={`/workspace/saved-charts/${chart.id}`}>{chart.label ?? "Saved chart"}</Link><p className="text-metadata text-text-secondary">{chart.mode === "live" ? "Live selection — resolves latest approved data" : "Pinned snapshot"} · Updated {formatUpdated(chart.updated_at)} UTC</p></li>)}</ul> : <p role="status" className="mt-3 text-text-secondary">No saved charts yet. Save a chart from the explorer to keep its selection.</p>}
          <Link className="mt-3 inline-flex min-h-11 items-center text-link underline" href="/workspace/saved-charts">All saved charts</Link>
        </section>
        <section aria-labelledby="recent-notes-heading">
          <h2 id="recent-notes-heading">Recent insight notes</h2>
          {home.recent_insights.length ? <ul className="mt-3 divide-y divide-border">{home.recent_insights.map((note) => <li key={`${note.document_id}:${note.block_id}`} className="min-w-0 py-3"><p className="whitespace-pre-wrap [overflow-wrap:anywhere]">{note.excerpt || "Insight note"}</p><p className="mt-1 text-metadata text-text-secondary">{note.type} · {note.classification} · Updated {formatUpdated(note.modified_at)} UTC</p><Link className="inline-flex min-h-11 items-center text-link underline [overflow-wrap:anywhere]" href={`/workspace/research/${note.document_id}`}>Open document: {note.document_title}</Link></li>)}</ul> : <p role="status" className="mt-3 text-text-secondary">No insight notes in your current document revisions. Notes appear here after they have been saved in a document.</p>}
        </section>
      </div>
      <HomeIndicators indicators={home.indicators} />
    </> : null}
  </div>;
}
