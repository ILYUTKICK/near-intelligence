/**
 * In-memory sliding-window rate guard (NI-020), calibrated to the
 * conservative AUTHENTICATION_SECURITY.md targets: 5 login attempts/minute
 * per IP to start. Single-instance by design for the MVP; a distributed
 * limiter is a deployment concern (NI-067) and must replace this before
 * multi-instance hosting.
 */

interface Bucket {
  timestamps: number[];
}

const buckets = new Map<string, Bucket>();

export interface RateLimitResult {
  allowed: boolean;
  retryAfterSeconds: number;
}

export function checkRateLimit(
  key: string,
  limit: number,
  windowMs: number,
  now: number = Date.now(),
): RateLimitResult {
  const bucket = buckets.get(key) ?? { timestamps: [] };
  bucket.timestamps = bucket.timestamps.filter((ts) => now - ts < windowMs);
  if (bucket.timestamps.length >= limit) {
    const oldest = bucket.timestamps[0] ?? now;
    buckets.set(key, bucket);
    return { allowed: false, retryAfterSeconds: Math.max(1, Math.ceil((windowMs - (now - oldest)) / 1000)) };
  }
  bucket.timestamps.push(now);
  buckets.set(key, bucket);
  // Opportunistic cleanup so abandoned keys cannot grow the map unbounded.
  if (buckets.size > 10_000) {
    for (const [k, b] of buckets) {
      if (b.timestamps.every((ts) => now - ts >= windowMs)) {
        buckets.delete(k);
      }
    }
  }
  return { allowed: true, retryAfterSeconds: 0 };
}

/** Best-effort client identity: proxy chain first, then the socket peer. */
export function clientKey(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for");
  if (forwarded) {
    return forwarded.split(",")[0].trim();
  }
  return request.headers.get("x-real-ip") ?? "unknown";
}

/** Test isolation only: clears every bucket (never call from production code). */
export function resetRateLimitForTests(): void {
  buckets.clear();
}
