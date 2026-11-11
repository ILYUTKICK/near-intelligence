import type { NextRequest } from "next/server";

import { forwardPrivate } from "@/lib/auth/private-gateway";

export function GET(request: NextRequest) {
  return forwardPrivate(request, "/api/me");
}

export function PATCH(request: NextRequest) {
  return forwardPrivate(request, "/api/me");
}
