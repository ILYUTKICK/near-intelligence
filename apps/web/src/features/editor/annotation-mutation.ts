import { createApiClient, type components } from "@near-intelligence/shared-types";
import { DocumentApiError } from "@/features/documents/list/documents-api";
import { apiErrorResponseSchema } from "@/features/documents/list/documents-schema";
import { privateFetch } from "@/lib/auth/private-fetch";

export type AnnotationSave = components["schemas"]["DocumentSaveResponse"];

export const annotationClient = () => createApiClient(window.location.origin, privateFetch);
export const annotationHeaders = (revision: number, key: string) => ({ "if-match": `"${revision}"`, "idempotency-key": key });

export function acknowledgeAnnotation<T extends AnnotationSave>(
  result: { data?: T; response: Response; error?: unknown }, documentId: string, label: "insight" | "hypothesis" | "evidence link",
): T {
  const { data, response } = result;
  if (!response.ok) {
    const parsed = apiErrorResponseSchema.safeParse(result.error);
    const error = parsed.success ? parsed.data.error : null;
    const message = error?.code === "REVISION_CONFLICT" ? `The research changed. Your ${label} draft is still here.`
      : response.status === 404 ? `This research or ${label} is unavailable to your account.`
        : response.status === 401 || response.status === 403 ? "Your session changed. Sign in again to continue."
          : error?.message ?? `The ${label} could not be saved. Retry the same action.`;
    throw new DocumentApiError(response.status, error?.code ?? "UNKNOWN_ERROR", message);
  }
  if (!data || data.document.id !== documentId || data.version.document_id !== documentId
    || data.document.current_version_id !== data.version.id || data.document.revision !== data.version.revision) {
    throw new Error("The saved revision could not be verified. Retry the same action.");
  }
  return data;
}
