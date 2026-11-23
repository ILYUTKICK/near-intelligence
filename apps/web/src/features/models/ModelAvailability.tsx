import Link from "next/link";
import type { ReactNode } from "react";

import { ProductIcon } from "@/components/layout/ProductIcon";
import { Button } from "@/components/ui/button";

const recordedReadiness = [
  { title: "True protocol revenue", status: "Not ready", detail: "A comparable daily attributable series is missing." },
  { title: "Gross-fee and volume association", status: "Proxy only", detail: "The source defines a largely mechanical fee–volume relationship. The gate permits a limited association." },
  { title: "Incomplete issuance bounds", status: "Rejected", detail: "The preregistered specification requires exact outcomes." },
];

export function ModelAvailability({ title, description, action }: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="mt-8 grid gap-5 lg:grid-cols-2">
      <section className="paper-panel flex flex-col items-center justify-center px-7 py-12 text-center">
        <span className="mb-4 grid size-12 place-items-center rounded-full bg-info-surface text-chart-2">
          <ProductIcon name="filter" className="size-5" />
        </span>
        <h2 className="text-heading md:text-title">{title}</h2>
        <p className="mt-2 max-w-[45ch] text-ui text-text-secondary">{description}</p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <Button asChild><Link href="/methodology#reproduce">How models are verified and reproduced</Link></Button>
          {action}
        </div>
      </section>
      <section className="paper-panel p-6">
        <p className="eyebrow">Recorded readiness · November 2026</p>
        <h2 className="mt-2 text-heading">What can the evidence support?</h2>
        <ul className="mt-3 divide-y divide-border">
          {recordedReadiness.map((item) => (
            <li key={item.title} className="py-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-ui font-semibold">{item.title}</p>
                <span className="rounded-full bg-surface-muted px-2.5 py-1 text-metadata text-text-secondary">
                  {item.status}
                </span>
              </div>
              <p className="mt-1 text-metadata text-text-secondary">{item.detail}</p>
            </li>
          ))}
        </ul>
        <Link href="/methodology#readiness" className="mt-3 flex items-center gap-2 text-ui font-medium hover:underline">
          Read the readiness criteria
        </Link>
      </section>
    </div>
  );
}
