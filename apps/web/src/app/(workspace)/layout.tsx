import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { WorkspaceHeader } from "@/components/layout/WorkspaceHeader";
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
      <div className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col md:flex-row">
        <WorkspaceSidebar />
        <div className="min-w-0 flex-1">
          <WorkspaceHeader />
          <main id="main-content" className="workspace-main px-(--page-gutter) py-8">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
