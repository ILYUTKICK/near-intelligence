import type { Metadata } from "next";
import { safeInternalReturnTo } from "@/lib/auth/session";
import Link from "next/link";

import { DemoSignIn } from "@/app/(auth)/login/DemoSignIn";
import { LoginForm } from "@/app/(auth)/login/LoginForm";

export const metadata: Metadata = { title: "Sign in — NEAR Intelligence" };

/** Same-origin sign-in shell; registration/recovery links arrive with their flows. */
export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string | string[] }> }) {
  const { next } = await searchParams;
  const returnTo = safeInternalReturnTo(typeof next === "string" && next.length <= 4096 ? next : null);
  return (
    <>
      <header className="text-center">
        <p className="eyebrow">Sign in</p>
        <h1 className="mt-2 text-title">Open your research workspace</h1>
        <p className="mt-2 text-ui text-text-secondary">Start with a research template for charts and notes</p>
      </header>
      <DemoSignIn returnTo={returnTo} />
      <details className="mt-6 border-t border-border pt-4">
        <summary className="cursor-pointer text-ui font-medium text-link">Sign in to an existing account</summary>
        <LoginForm returnTo={returnTo} />
        <p className="mt-5 text-center text-ui text-text-secondary">
          <Link href="/signup" className="font-medium underline underline-offset-2">Create a permanent account</Link>
        </p>
      </details>
    </>
  );
}
