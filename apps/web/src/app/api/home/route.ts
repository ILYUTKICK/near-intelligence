import type { NextRequest } from "next/server";

import { forwardPrivate } from "@/lib/auth/private-gateway";

/** NI-024: reuse the signed-cookie private gateway; identity is verified by the API. */
export function GET(request: NextRequest) {
  return forwardPrivate(request, "/api/home");
}
