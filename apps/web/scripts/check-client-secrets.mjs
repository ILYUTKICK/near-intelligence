/**
 * NI-016 verification, corrected by NI-062: the built frontend must not
 * contain server auth secrets. Reads the local .env (never committed), takes
 * every server-only auth value, and scans the production client bundle for
 * them. Exit 1 on any leak. NEXT_PUBLIC_* values are public by design and
 * are ignored.
 *
 * NI-062 correction (recorded NI-041 regression input): the original scanner
 * treated low-entropy JWT audience/issuer/JWKS/origin metadata as secrets.
 * The local audience `authenticated` is an ordinary word that legitimately
 * appears in UI state literals, so the honest scan never treats THAT ONE
 * variable's bare generic-word value as a leak; every other server value
 * (issuer/JWKS/origin URLs and both signing secrets) stays scanned exactly
 * as configured. An always-on self-test proves both directions on every run
 * before the real scan: a positive leak (signing secret in a fixture bundle)
 * must FAIL, and the public-metadata false positive (the audience literal in
 * a fixture bundle) must PASS.
 */
import { mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import os from "node:os";
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

const SERVER_AUTH_VARS = [
  "SUPABASE_JWT_ISSUER",
  "SUPABASE_JWKS_URL",
  "SUPABASE_JWT_AUDIENCE",
  "AUTH_ALLOWED_REDIRECT_ORIGINS",
  "AUTH_COOKIE_SIGNING_SECRET",
  "CSRF_SIGNING_SECRET",
];

/**
 * A bare generic word (letters/digits/dashes, no URL structure) is public
 * application vocabulary for the JWT AUDIENCE slot ONLY: the recorded
 * NI-041 false positive is the local audience `authenticated`, an ordinary
 * word that legitimately appears in UI state literals, so scanning that one
 * variable can only produce false positives. Every other server value —
 * issuer/JWKS/origin URLs AND BOTH SIGNING SECRETS — is always scanned
 * exactly as configured: a low-entropy signing secret is a configuration
 * error (the auth config guards reject it) and must never also lose its
 * leak scan here.
 */
const GENERIC_WORD_VARS = new Set(["SUPABASE_JWT_AUDIENCE"]);

function isGenericWord(value) {
  return /^[a-z][a-z0-9_-]{2,31}$/i.test(value) && !value.includes(".")
    && !value.includes("/") && !value.includes(":");
}

function serverSecrets(env) {
  return SERVER_AUTH_VARS.map((name) => ({ name, value: env[name] }))
    .filter(({ value }) => value && !/^REPLACE/i.test(value))
    .filter(({ value }) => value.length >= 8) // tiny placeholders can't leak meaningfully
    .map(({ name, value }) => ({ name, value,
      generic: GENERIC_WORD_VARS.has(name) && isGenericWord(value) }));
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

/**
 * Scan one directory: returns the leak list (variable name + file) for any
 * scanned value contained in any file. Generic-word values are skipped as
 * public metadata and reported separately.
 */
export function scanBundle(dir, secrets) {
  const leaks = [];
  let scanned = 0;
  const skipped = [];
  for (const file of walkFiles(dir)) {
    scanned += 1;
    const content = readFileSync(file, "utf8");
    for (const { name, value, generic } of secrets) {
      if (generic) {
        skipped.push(`${name} (public metadata word, not scanned)`);
        continue;
      }
      if (content.includes(value)) {
        leaks.push(`${name} leaked into ${path.relative(dir, file)}`);
      }
    }
  }
  return { scanned, leaks, skippedPublicMetadata: [...new Set(skipped)] };
}

function report(leaks) {
  if (leaks.length > 0) {
    console.error(`FAIL — ${leaks.length} server secret(s) found in the client bundle:`);
    for (const leak of leaks) {
      console.error(`  ${leak}`);
    }
    return false;
  }
  return true;
}

/** Always-on regressions: a real leak fails, public metadata never does. */
export function runSelfTest() {
  const directory = mkdtempSync(path.join(os.tmpdir(), "ni062-secret-scan-"));
  const secrets = [
    { name: "CSRF_SIGNING_SECRET", value: "self-test-signing-secret-0123456789", generic: false },
    { name: "SUPABASE_JWT_AUDIENCE", value: "authenticated", generic: true },
    { name: "SUPABASE_JWT_ISSUER", value: "https://self-test.supabase.co/auth/v1", generic: false },
  ];
  try {
    // Positive control: a signing secret in the bundle MUST fail.
    writeFileSync(path.join(directory, "leak.js"),
      "const leaked = 'self-test-signing-secret-0123456789';\n");
    const positive = scanBundle(directory, secrets);
    if (report(positive.leaks)) {
      console.error("SELF-TEST FAILURE: the positive leak control was not detected");
      return false;
    }
    console.log("self-test positive control: leak detection verified");

    // False-positive regression: the audience literal (ordinary UI state
    // word) MUST pass even when an issuer URL leak still fails.
    rmSync(path.join(directory, "leak.js"));
    writeFileSync(path.join(directory, "ui-state.js"),
      "const state = { status: 'authenticated' };\n"
      + "const issuer = 'https://self-test.supabase.co/auth/v1';\n");
    const mixed = scanBundle(directory, secrets);
    const audienceLeak = mixed.leaks.find((leak) => leak.startsWith("SUPABASE_JWT_AUDIENCE"));
    if (audienceLeak) {
      console.error("SELF-TEST FAILURE: public-metadata word flagged as a leak");
      return false;
    }
    if (mixed.leaks.length !== 1 || !mixed.leaks[0].startsWith("SUPABASE_JWT_ISSUER")) {
      console.error("SELF-TEST FAILURE: the issuer URL leak was not detected");
      return false;
    }
    console.log("self-test: public-metadata tolerance verified");
    return true;
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

function main() {
  const env = parseEnvFile(path.join(repoRoot, ".env"));
  if (!env) {
    // No .env means no configured secrets — nothing can leak into the bundle.
    console.log("No root .env configured — nothing to scan for.");
    return;
  }
  const secrets = serverSecrets(env);
  if (secrets.length === 0) {
    console.log("No real server secrets configured in .env — nothing to scan for.");
    return;
  }

  if (!runSelfTest()) {
    process.exit(1);
  }

  const generic = secrets.filter(({ generic }) => generic).map(({ name }) => name);
  if (generic.length > 0) {
    console.log(`Public metadata words not scanned as secrets: ${generic.join(", ")}`);
  }
  const bundleDir = path.join(buildDir, "static");
  if (!statSync(buildDir, { throwIfNoEntry: false })) {
    console.error("FAIL — no production build found (.next missing); "
      + "run `pnpm --filter web build` before scanning.");
    process.exit(1);
  }
  const { scanned, leaks } = scanBundle(bundleDir, secrets);
  if (report(leaks)) {
    console.log(`OK — ${scanned} client files scanned; no server auth secrets present.`);
  } else {
    process.exit(1);
  }
}

main();
