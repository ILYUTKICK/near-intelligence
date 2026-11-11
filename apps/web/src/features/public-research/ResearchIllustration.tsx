import Image from "next/image";

export function ResearchIllustration({ className, eager }: { className?: string; eager?: boolean }) {
  return (
    <Image
      src="/illustrations/research-notebook.svg"
      alt=""
      width={560}
      height={475}
      loading={eager ? "eager" : "lazy"}
      className={className}
    />
  );
}
