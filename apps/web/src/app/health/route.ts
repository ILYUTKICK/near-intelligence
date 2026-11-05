import { loadServerEnv } from "@/lib/env";

export const dynamic = "force-dynamic";

/**
 * Process liveness for the web service (NI-002 skeleton).
 *
 * Validates the required server configuration on every cold request so that
 * missing or malformed settings fail with a readable error instead of a
 * silently misconfigured service. No collector, model or ingestion job starts
 * here or anywhere else on boot.
 */
export async function GET() {
  try {
    const env = loadServerEnv();
    return Response.json({
      status: "ok",
      service: "web",
      appEnv: env.APP_ENV,
      checkedAt: new Date().toISOString(),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown configuration error";
    return Response.json({ status: "error", error: message }, { status: 503 });
  }
}
