"use client";

import { useEffect, useState } from "react";
import { AUTH_CHANGE, AUTH_CHANGE_STORAGE } from "./change";

type PublicSession =
  | { status: "checking" | "unknown"; subject: string | null }
  | { status: "anonymous"; subject: null }
  | { status: "authenticated"; subject: string; signal: AbortSignal };

/** A public page can suspend private actions while the account is verified again. */
export function usePublicSession() {
  const [session, setSession] = useState<PublicSession>({ status: "checking", subject: null });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let controller = new AbortController();

    function check(resetIdentity = false) {
      controller.abort();
      controller = new AbortController();
      const signal = controller.signal;
      setSession(previous => ({ status: "checking", subject: resetIdentity ? null : previous.subject }));
      fetch("/api/auth/session", { credentials: "same-origin", cache: "no-store", signal })
        .then(async response => {
          if (response.status === 401) {
            if (!signal.aborted) setSession({ status: "anonymous", subject: null });
            return;
          }
          if (!response.ok) throw new Error("Session unavailable");
          const value: unknown = await response.json();
          if (!value || typeof value !== "object" || !("subject" in value)
            || typeof value.subject !== "string" || !value.subject || value.subject === "unknown") {
            throw new Error("Session identity unavailable");
          }
          if (!signal.aborted) setSession({ status: "authenticated", subject: value.subject, signal });
        })
        .catch(() => {
          if (!signal.aborted) setSession(previous => ({ status: "unknown", subject: previous.subject }));
        });
    }

    const authChange = () => check(true);
    const focus = () => check();
    const storage = (event: StorageEvent) => { if (event.key === AUTH_CHANGE_STORAGE) check(true); };
    check();
    window.addEventListener(AUTH_CHANGE, authChange);
    window.addEventListener("focus", focus);
    window.addEventListener("storage", storage);
    return () => {
      controller.abort();
      window.removeEventListener(AUTH_CHANGE, authChange);
      window.removeEventListener("focus", focus);
      window.removeEventListener("storage", storage);
    };
  }, [attempt]);

  return { session, recheck: () => setAttempt(value => value + 1) };
}
