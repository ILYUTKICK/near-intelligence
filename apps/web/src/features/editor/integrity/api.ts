import type { components } from "@near-intelligence/shared-types";
import { annotationClient } from "../annotation-mutation";

export type IntegrityReport = components["schemas"]["IntegrityReport"];
export type IntegrityFinding = components["schemas"]["IntegrityFinding"];

/**
 * Owner-checked advisory integrity report of the acknowledged revision
 * (NI-065). Read-only: a rerun is simply a new GET.
 */
export async function fetchIntegrityReport(documentId: string, revision: number, signal: AbortSignal) {
  const { data, response } = await annotationClient().GET("/api/documents/{document_id}/integrity", {
    params: { path: { document_id: documentId } }, signal,
  });
  if (!response.ok || !data || data.document_id !== documentId || data.revision !== revision
    || !data.is_acknowledged) throw new Error("Integrity findings could not be loaded. Nothing was changed — try again.");
  return data;
}
