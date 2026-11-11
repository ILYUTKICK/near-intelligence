import type { Metadata } from "next";

import { DocumentList } from "@/features/documents/list/DocumentList";

export const metadata: Metadata = { title: "My Research — NEAR Intelligence" };

/**
 * My Research (NI-023): the entry point to persisted documents. The page
 * itself is a server shell inside the NI-021 session gate; every row is
 * fetched client-side from the owner-scoped document API through the verified
 * session — no user identifier travels in any request, and no sample
 * documents exist in production rendering.
 */
export default function MyResearchPage() {
  return <DocumentList />;
}
