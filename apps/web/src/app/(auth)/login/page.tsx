import type { Metadata } from "next";
import Link from "next/link";

import { LoginForm } from "@/app/(auth)/login/LoginForm";
import { SkipLink } from "@/components/layout/SkipLink";
import { PublicHeader } from "@/components/layout/PublicHeader";
import { PublicFooter } from "@/components/layout/PublicFooter";

export const metadata: Metadata = { title: "Sign in — NEAR Intelligence" };

/** Same-origin sign-in shell; registration/recovery links arrive with their flows. */
export default function LoginPage() {
  return (
    <div className="flex min-h-dvh flex-col">
      <SkipLink />
      <PublicHeader />
      <main id="main-content" className="flex-1">
        <div className="mx-auto w-full max-w-(--width-prose) px-4 py-12">
          <h1>Sign in</h1>
          <p className="text-body leading-body text-text-secondary mt-2">
            Use your research account email. Verification and recovery emails come from the
            authentication provider; links only work for the origin they were issued for.
          </p>
          <LoginForm />
          <p className="text-ui leading-ui text-text-secondary mt-6">
            New here?{" "}
            <Link href="/signup" className="text-accent underline underline-offset-2 hover:text-accent-hover">
              Create an account
            </Link>
          </p>
        </div>
      </main>
      <PublicFooter />
    </div>
  );
}
