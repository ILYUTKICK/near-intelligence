import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { z } from "zod";
import { ResearchRevisions } from "@/features/editor/revisions";

export const metadata: Metadata = { title: "Research revisions — NEAR Intelligence" };

export default async function RevisionsPage({ params, searchParams }: {
  params: Promise<{ documentId: string }>;
  searchParams: Promise<{ version?: string | string[]; cursor?: string | string[] }>;
}) {
  const [{ documentId }, query] = await Promise.all([params, searchParams]);
  const parsed = z.object({ version: z.uuid().optional(), cursor: z.string().max(64).optional() }).safeParse(query);
  if (!z.uuid().safeParse(documentId).success || !parsed.success) notFound();
  const { version, cursor } = parsed.data;
  return <ResearchRevisions key={JSON.stringify([documentId, version, cursor])} documentId={documentId.toLowerCase()}
    versionId={version?.toLowerCase()} cursor={cursor} />;
}
