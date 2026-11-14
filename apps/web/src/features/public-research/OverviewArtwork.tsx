import Image from "next/image";

/** Decorative approved-style artwork. Lines on the paper are not observations. */
export function OverviewArtwork() {
  return <div className="overflow-hidden rounded-surface bg-sage/40">
    <Image src="/illustrations/overview-research-desk.png" alt="" width={1254} height={1254}
      loading="eager" fetchPriority="high" sizes="(min-width: 1280px) 560px, (min-width: 1024px) 45vw, 100vw"
      className="h-auto w-full object-cover" />
  </div>;
}
