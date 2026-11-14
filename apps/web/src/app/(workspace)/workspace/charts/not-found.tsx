import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return <section className="paper-panel p-6">
    <h1 className="text-title">Chart not found</h1>
    <p className="mt-3 text-ui text-text-secondary">This address does not match a registered published resource. Nothing is shown in its place.</p>
    <Button asChild className="mt-4"><Link href="/workspace/charts">Open the chart library</Link></Button>
  </section>;
}
