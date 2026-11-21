import type { ReactNode } from "react";

import { Brand } from "@/components/layout/Brand";
import { SkipLink } from "@/components/layout/SkipLink";
import { ResearchIllustration } from "@/features/public-research/ResearchIllustration";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto grid min-h-dvh w-full max-w-[1140px] content-center gap-x-20 gap-y-8 px-(--page-gutter) py-10 md:grid-cols-[1fr_minmax(0,27rem)]">
      <SkipLink />
      <header className="self-center">
        <Brand />
        <div className="mt-9 hidden md:block">
          <p className="eyebrow">Your research workspace</p>
          <p className="mt-3 font-serif text-page font-medium tracking-tight">
            Your evidence.<br />Your research.<br /><span className="text-accent">Your thesis.</span>
          </p>
          <p className="mt-4 max-w-[33ch] text-ui text-text-secondary">
            Bring charts, sources and observations together in a private research workspace.
          </p>
          <ResearchIllustration eager className="paper-panel mt-6 h-auto w-full max-w-[20rem] bg-surface p-4 object-contain" />
        </div>
      </header>
      <main id="main-content" className="paper-panel w-full self-center p-6 sm:p-9">
        {children}
      </main>
    </div>
  );
}
