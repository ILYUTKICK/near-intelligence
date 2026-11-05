import { PublicFooter } from "@/components/layout/PublicFooter";
import { PublicHeader } from "@/components/layout/PublicHeader";
import { SkipLink } from "@/components/layout/SkipLink";

export default function HomePage() {
  return (
    <div className="flex min-h-dvh flex-col">
      <SkipLink />
      <PublicHeader />
      <main id="main-content" className="flex-1">
        <div className="mx-auto w-full max-w-(--width-content-max) px-4 py-12">
          <h1>NEAR Intelligence</h1>
          <p className="text-body leading-body text-text-secondary max-w-(--width-prose) mt-4">
            Evidence-first NEAR investment research. This page is the NI-002 runtime skeleton
            wearing the NI-008 public shell; the reading surfaces, data explorer and workspace
            are implemented by their own NI-tasks and intentionally contain no metrics, controls
            or sample values yet.
          </p>
        </div>
      </main>
      <PublicFooter />
    </div>
  );
}
