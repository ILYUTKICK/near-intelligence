import { notFound } from "next/navigation";
import { z } from "zod";
import { SavedChartDetail } from "@/features/charts/saved/SavedChartDetail";
export default async function SavedChartPage({ params }: { params: Promise<{ instanceId: string }> }) {
  const { instanceId } = await params;
  if (!z.uuid().safeParse(instanceId).success) notFound();
  return <SavedChartDetail instanceId={instanceId} />;
}
