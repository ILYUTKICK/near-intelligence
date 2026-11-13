import type { NextConfig } from "next";

// Root .env loading happens explicitly and lazily in src/lib/env.ts at first
// server use, so the variables are read in the process that serves requests.
// Compose mode injects environment itself; nothing else runs on boot.

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The generated shared-types package exports TypeScript source directly;
  // Next must compile it like first-party app code (NI-033 renderer contract).
  transpilePackages: ["@near-intelligence/shared-types"],
  logging: {
    incomingRequests: { ignore: [/^\/share(?:\/|\?|$)/] },
  },
  async headers() {
    return [
      {
        // NI-060 share viewer (ADR-021): the capability token lives only in
        // the path segment — referrer suppression keeps it out of any
        // target site's logs, and the tag double-locks the robots noindex.
        source: "/share/:token",
        headers: [
          { key: "Cache-Control", value: "no-store, max-age=0" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Robots-Tag", value: "noindex, nofollow" },
        ],
      },
    ];
  },
};

export default nextConfig;
