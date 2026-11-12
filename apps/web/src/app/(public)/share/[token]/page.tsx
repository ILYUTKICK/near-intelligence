import type { Metadata } from "next";

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
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const result = await fetchSharedProjection(token);
  if (!result.ok) {
    return (
      <div className="page-container">
        <div className="paper-panel p-8" role="alert" data-testid="share-denied">
          <h1 className="font-serif text-page leading-page">This share link is not available</h1>
          <p className="text-body leading-body text-text-secondary mt-3">
            The link may be wrong, or the owner may have revoked it or let it
            expire. Revoked and expired links stop working immediately for
            everyone — nothing is shown rather than partial or stale content.
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="page-container">
      <ShareViewer projection={result.projection} />
    </div>
  );
}
