import type { Metadata } from "next";

import { Brand } from "@/components/layout/Brand";
import { SkipLink } from "@/components/layout/SkipLink";
import { ShareViewer } from "@/features/shares/ShareViewer";
import { fetchSharedProjection } from "@/features/shares/share-viewer-api";

export const metadata: Metadata = {
  title: "Shared research — NEAR Intelligence",
  // The share is a capability URL: it must never be indexed, archived or
  // suggested (ADR-021). Referrer suppression comes from the global
  // Referrer-Policy header for this path (next.config headers).
  robots: { index: false, follow: false, nocache: true },
};

/**
 * The read-only viewer at /share/[token] (NI-060, ADR-021).
 *
 * The projection is fetched server-side (no-store) against the token-gated
 * API; unknown, revoked and expired links are the SAME generic 404 on the
 * API, so this page renders ONE honest denied state for every failure — no
 * existence leak, no oracle, and nothing rendered rather than partial
 * content. The page carries no workspace chrome, no links into private
 * routes and no refresh/latest-data action: it renders exactly the frozen
 * projection the owner consented to publish.
 */
export default async function SharedRevisionPage({
  params,
  searchParams,
}: {
  params: Promise<{ token: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { token } = await params;
  const result = Object.keys(await searchParams).length
    ? { ok: false as const }
    : await fetchSharedProjection(token);
  return (
    <div className="min-h-dvh">
      <SkipLink />
      <header className="border-b border-border bg-canvas">
        <div className="mx-auto w-full max-w-(--width-content-max) px-(--page-gutter) py-4">
          <Brand />
        </div>
      </header>
      <main id="main-content" className="page-container">
        {result.ok ? <ShareViewer projection={result.projection} /> : (
          <div className="paper-panel p-8" role="alert" data-testid="share-denied">
            <h1 className="font-serif text-page leading-page">This share link is not available</h1>
            <p className="text-body leading-body text-text-secondary mt-3">
              Check the link or ask the owner for access.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
