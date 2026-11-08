import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { AccountMenu } from "@/components/layout/AccountMenu";
import { WorkspaceSidebar } from "@/components/layout/WorkspaceSidebar";
import { SkipLink } from "@/components/layout/SkipLink";
import { SESSION_COOKIE, decodeSessionCookie } from "@/lib/auth/session";

/**
 * Workspace shell gate (NI-021). Server-side check of the HMAC-signed
 * session cookie on every request through this group: anonymous or expired
 * visitors reach /login safely with no workspace content rendered. The gate
 * never replaces backend ownership — every private API request re-verifies
 * the bearer server-side (NI-018/019).
 *
 * force-dynamic: authenticated pages must never be cached (private no-store
 * semantics).
 */
export const dynamic = "force-dynamic";

export default async function WorkspaceLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  const session = decodeSessionCookie(cookieStore.get(SESSION_COOKIE)?.value);
  if (!session) {
    redirect("/login");
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <SkipLink />
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex w-full max-w-(--width-content-max) items-center justify-between gap-2 px-4 py-2">
          <p className="font-serif text-title leading-title text-text">NEAR Intelligence</p>
          <p className="text-metadata leading-metadata text-text-secondary">
            Signed in · private workspace
          </p>
          <AccountMenu />
        </div>
      </header>
      <div className="mx-auto flex w-full max-w-(--width-content-max) flex-1 gap-0 px-0 md:px-4">
        <WorkspaceSidebar />
        <main id="main-content" className="min-w-0 flex-1 p-4">
          {children}
        </main>
      </div>
      <p className="sr-only">Private workspace. All content is owner-scoped.</p>
    </div>
  );
}
