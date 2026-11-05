import type { NextConfig } from "next";

// Root .env loading happens explicitly and lazily in src/lib/env.ts at first
// server use, so the variables are read in the process that serves requests.
// Compose mode injects environment itself; nothing else runs on boot.

const nextConfig: NextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
