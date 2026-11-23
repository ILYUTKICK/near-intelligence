import { ResearchIllustration } from "./ResearchIllustration";

/** Approved TRACE, with a clear silhouette and no data invented by the artwork. */
export function OverviewArtwork() {
  return <div className="paper-panel mx-auto w-full max-w-[29rem] overflow-hidden bg-surface p-5 lg:p-7">
    <ResearchIllustration eager className="h-auto w-full object-contain" />
  </div>;
}
