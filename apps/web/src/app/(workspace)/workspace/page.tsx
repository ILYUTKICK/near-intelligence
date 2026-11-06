import type { Metadata } from "next";
import { cookies } from "next/headers";

import { SESSION_COOKIE, decodeSessionCookie } from "@/lib/auth/session";

export const metadata: Metadata = { title: "Workspace — NEAR Intelligence" };

/**
 * Authenticated workspace entry (NI-021 gate demonstration). The research-
 * focused Home with greeting/continue flows is NI-024; until then this page
 * shows honest structure with no metrics, no fake documents and no dead
 * controls. Route protection here never replaces backend ownership.
 */
export default async function WorkspaceHomePage() {
  const cookieStore = await cookies();
  const session = decodeSessionCookie(cookieStore.get(SESSION_COOKIE)?.value);

  return (
    <div className="max-w-(--width-prose)">
      <h1>Workspace</h1>
      <p className="text-body leading-body text-text-secondary mt-4">
        This is the protected workspace shell (NI-021). The research-focused Home — greeting,
        recent documents, saved charts and continuation flows — is implemented by NI-024. Your
        session is active; every private API request re-verifies ownership server-side.
      </p>
      <p className="text-body leading-body text-text-secondary mt-2">
        Navigation in the sidebar mirrors the canonical registry; the entries resolve as their
        own tasks land.
      </p>
    </div>
  );
}
