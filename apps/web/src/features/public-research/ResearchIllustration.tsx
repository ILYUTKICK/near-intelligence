import Image from "next/image";

/** The owner's approved TRACE mascot. Decorative beside the native page copy. */
export function ResearchIllustration({ className, eager }: { className?: string; eager?: boolean }) {
  return <Image src="/brand/trace-approved.png" alt="" width={1312} height={1199}
    loading={eager ? "eager" : "lazy"} fetchPriority={eager ? "high" : undefined} className={className} />;
}
