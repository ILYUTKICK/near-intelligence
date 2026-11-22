"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import { isWithinRoute, workspaceNav } from "@/lib/navigation";
import { AccountMenu } from "./AccountMenu";
import { Breadcrumbs } from "./Breadcrumbs";
import { ProductIcon } from "./ProductIcon";

export function WorkspaceHeader() {
  const pathname = usePathname();
  const current = workspaceNav.find((item) => item.href !== "/workspace" && isWithinRoute(pathname, item.href));
  let label = current?.label ?? "Home";
  if (pathname?.startsWith("/workspace/research/")) {
    label = pathname.endsWith("/versions") ? "Revision history" : "Research editor";
  } else if (pathname?.startsWith("/workspace/charts")) {
    label = "Chart library";
  } else if (pathname?.startsWith("/workspace/data") && !current) {
    label = "Data explorer";
  } else if (pathname?.startsWith("/workspace/saved-charts/")) {
    label = "Saved chart";
  }

  return (
    <header className="px-(--page-gutter) flex min-h-20 flex-wrap items-center justify-between gap-2 border-b-2 border-panel-border bg-surface py-3 md:min-h-16 md:py-2">
      <Breadcrumbs label="Workspace breadcrumb" items={[{ label: "Workspace", href: "/workspace" }, { label }]} />
      <div className="flex flex-wrap items-center gap-2">
        <span className="hidden px-2 text-metadata text-text-secondary lg:inline">Private workspace</span>
        <Button asChild variant="secondary" className="px-0">
          <Link href="/methodology#sources" aria-label="Source documentation">
            <ProductIcon name="book" className="size-[18px]" />
          </Link>
        </Button>
        <AccountMenu />
      </div>
    </header>
  );
}
