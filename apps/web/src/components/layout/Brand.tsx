import Image from "next/image";
import Link from "next/link";

/** Canonical owner-approved graph wordmark, shared by every application shell. */
export function Brand() {
  return <Link href="/" className="inline-flex w-fit shrink-0 items-center rounded-control" aria-label="NEAR Intelligence">
    <Image src="/brand/near-intelligence-logo.svg" alt="NEAR Intelligence" width={164} height={64} priority className="h-auto w-[164px]" />
  </Link>;
}
