import type { components } from "@near-intelligence/shared-types";
import { acknowledgeAnnotation, annotationClient, annotationHeaders } from "../annotation-mutation";

export type InsightCreateRequest = components["schemas"]["InsightCreateRequest"];
export type InsightPatchRequest = components["schemas"]["InsightPatchRequest"];
export type InsightDeleteRequest = components["schemas"]["InsightDeleteRequest"];

export async function createInsight(documentId: string, revision: number, body: InsightCreateRequest, key: string, signal: AbortSignal) {
  return acknowledgeAnnotation(await annotationClient().POST("/api/documents/{document_id}/insights", {
    params: { path: { document_id: documentId } }, headers: annotationHeaders(revision, key), body, signal,
  }), documentId, "insight");
}

export async function editInsight(documentId: string, insightId: string, revision: number, body: InsightPatchRequest, key: string, signal: AbortSignal) {
  return acknowledgeAnnotation(await annotationClient().PATCH("/api/documents/{document_id}/insights/{insight_id}", {
    params: { path: { document_id: documentId, insight_id: insightId } }, headers: annotationHeaders(revision, key), body, signal,
  }), documentId, "insight");
}

export async function deleteInsight(documentId: string, insightId: string, revision: number, body: InsightDeleteRequest, key: string, signal: AbortSignal) {
  return acknowledgeAnnotation(await annotationClient().DELETE("/api/documents/{document_id}/insights/{insight_id}", {
    params: { path: { document_id: documentId, insight_id: insightId } }, headers: annotationHeaders(revision, key), body, signal,
  }), documentId, "insight");
}
