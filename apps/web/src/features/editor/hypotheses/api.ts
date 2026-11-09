import type { components } from "@near-intelligence/shared-types";
import { acknowledgeAnnotation, annotationClient, annotationHeaders } from "../annotation-mutation";

type HypothesisCreateRequest = components["schemas"]["HypothesisCreateRequest"];
type HypothesisPatchRequest = components["schemas"]["HypothesisPatchRequest"];
type HypothesisDeleteRequest = components["schemas"]["HypothesisDeleteRequest"];

export async function createHypothesis(documentId: string, revision: number, body: HypothesisCreateRequest, key: string, signal: AbortSignal) {
  return acknowledgeAnnotation(await annotationClient().POST("/api/documents/{document_id}/hypotheses", {
    params: { path: { document_id: documentId } }, headers: annotationHeaders(revision, key), body, signal,
  }), documentId, "hypothesis");
}

export async function editHypothesis(documentId: string, hypothesisId: string, revision: number, body: HypothesisPatchRequest, key: string, signal: AbortSignal) {
  return acknowledgeAnnotation(await annotationClient().PATCH("/api/documents/{document_id}/hypotheses/{hypothesis_id}", {
    params: { path: { document_id: documentId, hypothesis_id: hypothesisId } }, headers: annotationHeaders(revision, key), body, signal,
  }), documentId, "hypothesis");
}

export async function deleteHypothesis(documentId: string, hypothesisId: string, revision: number, body: HypothesisDeleteRequest, key: string, signal: AbortSignal) {
  return acknowledgeAnnotation(await annotationClient().DELETE("/api/documents/{document_id}/hypotheses/{hypothesis_id}", {
    params: { path: { document_id: documentId, hypothesis_id: hypothesisId } }, headers: annotationHeaders(revision, key), body, signal,
  }), documentId, "hypothesis");
}
