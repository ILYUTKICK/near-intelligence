"use client";
import { useCallback, useEffect, useState } from "react";
import { AUTH_CHANGE, AUTH_CHANGE_STORAGE } from "@/lib/auth/change";

/** No persistent private cache. Auth/focus changes clear before revalidation. */
export function useOwnedData<T>(loader: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({ data: null, error: null, loading: true });
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    let controller = new AbortController();
    let generation = 0;
    async function load() {
      controller.abort();
      controller = new AbortController();
      const signal = controller.signal;
      const current = ++generation;
      setState({ data: null, error: null, loading: true });
      if (document.visibilityState === "hidden") return;
      try {
        const session = await fetch("/api/auth/session", { signal, credentials: "same-origin", cache: "no-store" });
        if (!session.ok) throw new Error("Sign in again to see your saved charts.");
        const data = await loader(signal);
        if (!signal.aborted && generation === current) setState({ data, error: null, loading: false });
      } catch (error) {
        if (!signal.aborted && generation === current) setState({ data: null, loading: false,
          error: error instanceof Error ? error.message : "Saved charts could not be loaded." });
      }
    }
    const storage = (event: StorageEvent) => { if (event.key === AUTH_CHANGE_STORAGE) void load(); };
    void load();
    window.addEventListener(AUTH_CHANGE, load);
    window.addEventListener("storage", storage);
    window.addEventListener("focus", load);
    document.addEventListener("visibilitychange", load);
    return () => {
      controller.abort(); generation++;
      window.removeEventListener(AUTH_CHANGE, load);
      window.removeEventListener("storage", storage);
      window.removeEventListener("focus", load);
      document.removeEventListener("visibilitychange", load);
    };
  }, [loader, revision]);
  return { ...state, reload };
}
