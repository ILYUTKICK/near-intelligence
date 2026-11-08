/**
 * Local-copy download for recovery flows (NI-040 conflict dialog and the
 * read-only recovery view). The content is handed to the user as a JSON file
 * — the honest recovery path that never depends on the API being reachable.
 */
export function downloadJson(rawContent: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(rawContent, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
