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
        <h1 className="mt-2 text-title">Welcome back.</h1>
        <p className="mt-2 text-ui text-text-secondary">Continue where your research left off.</p>
      </header>
      <LoginForm returnTo={returnTo} />
      <p className="mt-5 text-center text-ui text-text-secondary">
        New to NEAR Intelligence?{" "}
        <Link href="/signup" className="font-medium underline underline-offset-2">Create an account</Link>
      </p>
      <DemoSignIn returnTo={returnTo} />
    </>
  );
}
