import Link from "next/link";

export function Brand() {
  return (
    <Link href="/" className="flex w-fit items-center gap-2.5 rounded-control">
      <span className="grid size-9 shrink-0 place-items-center rounded-[12px] bg-sage text-accent">
        <svg aria-hidden="true" viewBox="0 0 25 25" className="size-6">
          <path
            d="M5 19V6l14 13V6M5 6l4-2m10 15-4 2"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.1"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <span className="text-sm leading-none font-bold text-text">
        NEAR{" "}
        <span className="mt-1 block text-[0.6rem] leading-none font-medium tracking-[0.15em] text-text-secondary uppercase">
          Intelligence
        </span>
      </span>
    </Link>
  );
}
