"use client";

import { createContext, useContext } from "react";

/**
 * Pluggable workspace auth hook (NI-008 contract). The layout shells render
 * through this hook only; the real Supabase session provider replaces the
 * anonymous default when NI-016/NI-017/NI-021 land — without touching the
 * shell components. No component may derive ownership from anything here;
 * server verification stays the sole authorization boundary.
 */
export type WorkspaceAuthState =
  | { status: "anonymous" }
  | { status: "authenticated"; userId: string };

const WorkspaceAuthContext = createContext<WorkspaceAuthState>({ status: "anonymous" });

export function WorkspaceAuthProvider({
  state,
  children,
}: {
  state: WorkspaceAuthState;
  children: React.ReactNode;
}) {
  return <WorkspaceAuthContext.Provider value={state}>{children}</WorkspaceAuthContext.Provider>;
}

export function useWorkspaceAuth(): WorkspaceAuthState {
  return useContext(WorkspaceAuthContext);
}
