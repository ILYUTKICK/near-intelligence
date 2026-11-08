/** Browser-only transport for existing same-origin private mutations. */
export async function privateFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const method = init.method ?? "GET";
  if (method === "GET") return fetch(input, { ...init, credentials: "same-origin", cache: "no-store" });
  const response = await fetch("/api/auth/csrf", { credentials: "same-origin", cache: "no-store" });
  if (!response.ok) throw new Error("Your session could not be checked. Try again.");
  const value: unknown = await response.json();
  if (!value || typeof value !== "object" || !("token" in value) || typeof value.token !== "string") {
    throw new Error("The session response was invalid.");
  }
  // Preserve the caller's headers as an object for the existing transports.
  const headers = Object.fromEntries(new Headers(init.headers).entries());
  headers["x-csrf-token"] = value.token;
  return fetch(input, { ...init, headers, credentials: "same-origin", cache: "no-store" });
}
