import type { components, operations } from "@near-intelligence/shared-types";
import { acknowledgeAnnotation, annotationClient, annotationHeaders } from "../annotation-mutation";

export type EvidenceTargetPage = components["schemas"]["EvidenceTargetListResponse"];
export type EvidenceLink = components["schemas"]["Evidence"];
export type PublicEvidenceKind = operations["listDocumentEvidenceTargets"]["parameters"]["query"]["target_kind"];
type EvidenceCreateRequest = components["schemas"]["EvidenceCreateRequest"];
type EvidencePatchRequest = components["schemas"]["EvidencePatchRequest"];

/** Owner-checked evidence list of the document's current revision (NI-050 panel). */
export async function listDocumentEvidence(documentId: string, signal: AbortSignal) {
  const { data, response } = await annotationClient().GET("/api/documents/{document_id}/evidence", {
    params: { path: { document_id: documentId } }, signal,
  });
  if (!response.ok || !data) throw new Error("Linked evidence could not be loaded. Try again.");
  // The generated contract is `Evidence[]`; any other payload is a failed
  // load, never a partial render — the panel keeps the paper untouched and
  // offers an explicit retry instead of rendering a malformed list.
  if (!Array.isArray(data)) throw new Error("Linked evidence could not be loaded. Try again.");
  return data;
}

export async function createEvidence(documentId: string, revision: number, body: EvidenceCreateRequest, key: string, signal: AbortSignal) {
  return acknowledgeAnnotation(await annotationClient().POST("/api/documents/{document_id}/evidence", {
    params: { path: { document_id: documentId } }, headers: annotationHeaders(revision, key), body, signal,
  }), documentId, "evidence link");
}

export async function editEvidence(documentId: string, evidenceId: string, revision: number, body: EvidencePatchRequest, key: string, signal: AbortSignal) {
  return acknowledgeAnnotation(await annotationClient().PATCH("/api/documents/{document_id}/evidence/{evidence_id}", {
    params: { path: { document_id: documentId, evidence_id: evidenceId } }, headers: annotationHeaders(revision, key), body, signal,
  }), documentId, "evidence link");
}

export async function deleteEvidence(documentId: string, evidenceId: string, revision: number, key: string, signal: AbortSignal) {
  return acknowledgeAnnotation(await annotationClient().DELETE("/api/documents/{document_id}/evidence/{evidence_id}", {
    params: { path: { document_id: documentId, evidence_id: evidenceId } }, headers: annotationHeaders(revision, key), signal,
  }), documentId, "evidence link");
}

export async function listEvidenceTargets(documentId: string, kind: PublicEvidenceKind, cursor: string | undefined, signal: AbortSignal) {
  const { data, response } = await annotationClient().GET("/api/documents/{document_id}/evidence-targets", {
    params: { path: { document_id: documentId }, query: { target_kind: kind, cursor } }, signal,
  });
  if (!response.ok || !data) throw new Error("Public evidence targets could not be loaded. Try again.");
  return data;
}
