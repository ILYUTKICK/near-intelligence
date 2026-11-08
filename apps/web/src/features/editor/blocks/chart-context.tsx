"use client";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import type { components } from "@near-intelligence/shared-types";
import { AUTH_CHANGE, AUTH_CHANGE_STORAGE } from "@/lib/auth/change";

export type ChartObservation = components["schemas"]["ResolvedContext"];
interface ChartEditorContextValue {
  documentId: string;
  saved: boolean;
  subject: string | null;
  ready: boolean;
  revision?: number;
  onObserve?: (blockId: string, observation: ChartObservation) => void;
}
const ChartEditorContext = createContext<ChartEditorContextValue | null>(null);
export const useChartEditorContext = () => useContext(ChartEditorContext);
export const HistoricalRevisionContext = createContext<{ documentId: string; versionId: string; sessionSignal: AbortSignal } | null>(null);

/** One identity guard per editor, shared by every chart; no private cache. */
export function ChartEditorProvider({ documentId, saved, enabled, revision, onObserve, children }: {
  documentId: string; saved: boolean; enabled: boolean; revision?: number;
  onObserve?: ChartEditorContextValue["onObserve"]; children: ReactNode;
}) {
  const [session, setSession] = useState<{ subject: string | null; ready: boolean }>({ subject: null, ready: false });
  const owner = useRef<string | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let controller = new AbortController();
    async function check() {
      controller.abort(); controller = new AbortController();
      const signal = controller.signal;
      setSession({ subject: owner.current, ready: false });
      if (document.visibilityState === "hidden") return;
      try {
        const response = await fetch("/api/auth/session", { credentials: "same-origin", cache: "no-store", signal });
        const value: unknown = response.ok ? await response.json() : null;
        if (signal.aborted) return;
        if (!value || typeof value !== "object" || !("subject" in value) || typeof value.subject !== "string" || !value.subject || value.subject === "unknown") return;
        owner.current ??= value.subject;
        // A different identity must reopen the owner-checked document first.
        setSession({ subject: owner.current, ready: owner.current === value.subject });
      } catch { /* Keep controls suspended until session revalidation succeeds. */ }
    }
    const storage = (event: StorageEvent) => { if (event.key === AUTH_CHANGE_STORAGE) void check(); };
    void check();
    window.addEventListener(AUTH_CHANGE, check); window.addEventListener("focus", check);
    window.addEventListener("storage", storage); document.addEventListener("visibilitychange", check);
    return () => { controller.abort(); window.removeEventListener(AUTH_CHANGE, check); window.removeEventListener("focus", check);
      window.removeEventListener("storage", storage); document.removeEventListener("visibilitychange", check); };
  }, [documentId, enabled]);
  return <ChartEditorContext value={{ documentId, saved, revision, onObserve, ...session }}>{children}</ChartEditorContext>;
}
