/**
 * NI-016 verification: the built frontend must not contain server auth
 * secrets. Reads the local .env (never committed), takes every server-only
 * auth value, and scans the production client bundle for them. Exit 1 on
 * any leak. NEXT_PUBLIC_* values are public by design and are ignored.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(webRoot, "..", "..");
const buildDir = path.join(webRoot, ".next");

function parseEnvFile(filePath) {
  try {
    const values = {};
    for (const line of readFileSync(filePath, "utf8").split("\n")) {
      const match = line.match(/^([A-Z0-9_]+)=(.*)$/);
      if (match) {
        values[match[1]] = match[2].trim();
      }
    }
    return values;
  } catch {
    return null;
  }
}

const env = parseEnvFile(path.join(repoRoot, ".env"));
if (!env) {
  console.error("No root .env found — run `cp .env.example .env` and configure it first.");
  process.exit(1);
}

const SERVER_SECRET_VARS = [
  "SUPABASE_JWT_ISSUER",
  "SUPABASE_JWKS_URL",
  "SUPABASE_JWT_AUDIENCE",
  "AUTH_ALLOWED_REDIRECT_ORIGINS",
  "AUTH_COOKIE_SIGNING_SECRET",
  "CSRF_SIGNING_SECRET",
];

const secrets = SERVER_SECRET_VARS.map((name) => ({ name, value: env[name] }))
  .filter(({ value }) => value && !/^REPLACE/i.test(value))
  .filter(({ value }) => value.length >= 8); // tiny placeholders can't leak meaningfully

if (secrets.length === 0) {
  console.log("No real server secrets configured in .env — nothing to scan for.");
  process.exit(0);
}

function* walkFiles(dir) {
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      yield* walkFiles(full);
    } else {
      yield full;
    }
  }
}

let scanned = 0;
const leaks = [];
for (const file of walkFiles(path.join(buildDir, "static"))) {
  scanned += 1;
  const content = readFileSync(file, "utf8");
  for (const { name, value } of secrets) {
    if (content.includes(value)) {
      leaks.push(`${name} leaked into ${path.relative(webRoot, file)}`);
    }
  }
}

if (leaks.length > 0) {
  console.error(`FAIL — ${leaks.length} server secret(s) found in the client bundle:`);
  for (const leak of leaks) {
    console.error(`  ${leak}`);
  }
  process.exit(1);
}
console.log(`OK — ${scanned} client files scanned; no server auth secrets present.`);
