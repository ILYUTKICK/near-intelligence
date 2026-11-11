import { notFound } from "next/navigation";
import { z } from "zod";
import { SnapshotDetail } from "@/features/charts/snapshots/SnapshotDetail";
export default async function SnapshotPage({ params }: { params: Promise<{ snapshotId: string }> }) {
  const { snapshotId } = await params;
  if (!z.uuid().safeParse(snapshotId).success) notFound();
  return <SnapshotDetail snapshotId={snapshotId} />;
}
