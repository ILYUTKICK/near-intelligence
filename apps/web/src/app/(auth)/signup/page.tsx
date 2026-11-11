import type { Metadata } from "next";
import Link from "next/link";

import { SignupForm } from "@/app/(auth)/signup/SignupForm";

export const metadata: Metadata = { title: "Sign up — NEAR Intelligence" };

export default function SignupPage() {
  return (
    <>
      <header className="text-center">
        <p className="eyebrow">Create account</p>
        <h1 className="mt-2 text-title">Start your research.</h1>
        <p className="mt-2 text-ui text-text-secondary">Create a workspace for evidence you can return to.</p>
      </header>
      <SignupForm />
      <p className="mt-5 text-center text-ui text-text-secondary">
        Already have an account?{" "}
        <Link href="/login" className="font-medium underline underline-offset-2">Sign in</Link>
      </p>
    </>
  );
}
