"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ProductIcon } from "@/components/layout/ProductIcon";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/**
 * Catalog search (NI-034). The query is URL state: submitting pushes
 * `/charts?q=…` so the server-rendered catalog request reflects the URL and
 * back/forward navigate search history. Works without client JavaScript as
 * a plain GET form (progressive enhancement); the active category is kept
 * as a hidden field so search and category compose.
 */
export function CatalogSearch({ initialQuery, category, basePath = "/charts" }: { initialQuery: string; category: string | null; basePath?: string }) {
  const router = useRouter();
  const [value, setValue] = useState(initialQuery);

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const params = new URLSearchParams();
    const query = value.trim();
    if (query !== "") {
      params.set("q", query);
    }
    if (category !== null) {
      params.set("category", category);
    }
    router.push(params.size > 0 ? `${basePath}?${params.toString()}` : basePath);
  }

  return (
    <form role="search" action={basePath} method="get" onSubmit={submit} className="flex flex-col gap-1.5">
      <Label htmlFor="chart-catalog-search">Search charts</Label>
      <div className="flex gap-2">
        <div className="relative min-w-0">
          <ProductIcon name="search" className="pointer-events-none absolute top-3.5 left-3.5 size-4 text-text-secondary" />
          <Input
            id="chart-catalog-search"
            name="q"
            type="search"
            maxLength={200}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="Title, description or chart id"
            className="rounded-full pl-10 text-ui"
          />
        </div>
        {category !== null ? <input type="hidden" name="category" value={category} /> : null}
        <Button type="submit" variant="secondary">Search</Button>
      </div>
    </form>
  );
}
