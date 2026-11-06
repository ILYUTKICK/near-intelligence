import type { Metadata } from "next";
import Link from "next/link";

import { SignupForm } from "@/app/(auth)/signup/SignupForm";
import { PublicFooter } from "@/components/layout/PublicFooter";
import { PublicHeader } from "@/components/layout/PublicHeader";
import { SkipLink } from "@/components/layout/SkipLink";

export const metadata: Metadata = { title: "Sign up — NEAR Intelligence" };

export default function SignupPage() {
  return (
    <div className="flex min-h-dvh flex-col">
      <SkipLink />
      <PublicHeader />
      <main id="main-content" className="flex-1">
        <div className="mx-auto w-full max-w-(--width-prose) px-4 py-12">
          <h1>Sign up</h1>
          <p className="text-body leading-body text-text-secondary mt-2 max-w-(--width-prose)">
            Create your research account. A confirmation email is sent to your address — follow
            its link from this browser to activate the session.
          </p>
          <SignupForm />
          <p className="text-ui leading-ui text-text-secondary mt-6">
            Already have an account?{" "}
            <Link href="/login" className="text-accent underline underline-offset-2 hover:text-accent-hover">
              Sign in
            </Link>
          </p>
        </div>
      </main>
      <PublicFooter />
    </div>
  );
}
