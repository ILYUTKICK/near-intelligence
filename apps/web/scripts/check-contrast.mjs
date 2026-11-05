/**
 * WCAG 2.1 contrast audit for the NI-006 design tokens (DESIGN_SYSTEM.md).
 *
 * Parses the hex token values from src/styles/tokens.css (no duplicated color
 * constants) and checks every documented role pairing against its WCAG target:
 * body-size text >= 4.5:1, large text / control boundaries / focus indicators
 * >= 3:1. Exit code 1 if any target fails, so CI can gate on it later (NI-005).
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const tokensPath = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "src",
  "styles",
  "tokens.css",
);
const css = readFileSync(tokensPath, "utf8");

const tokens = {};
for (const match of css.matchAll(/--color-([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})/g)) {
  tokens[match[1]] = match[2];
}

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const lin = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function ratio(fg, bg) {
  const [l1, l2] = [luminance(fg), luminance(bg)].sort((a, b) => b - a);
  return (l1 + 0.05) / (l2 + 0.05);
}

const TEXT = 4.5;
const LARGE_OR_BOUNDARY = 3.0;

/** [foreground, background, target, role description] */
const pairs = [
  ["text", "canvas", TEXT, "primary text on ivory canvas"],
  ["text", "surface", TEXT, "primary text on reading paper"],
  ["text", "surface-muted", TEXT, "primary text on quiet surface"],
  ["text", "sage", TEXT, "primary text on sage highlight fill"],
  ["text-secondary", "surface", TEXT, "secondary text on surface"],
  ["text-secondary", "canvas", TEXT, "secondary text on canvas"],
  ["accent", "surface", TEXT, "links/primary actions on surface"],
  ["accent", "canvas", TEXT, "links/primary actions on canvas"],
  ["accent-hover", "surface", TEXT, "hover action on surface"],
  ["warning", "surface", TEXT, "warning text on surface"],
  ["warning", "surface-muted", TEXT, "warning text on pale background"],
  ["danger", "surface", TEXT, "danger text on surface"],
  ["danger", "canvas", TEXT, "danger text on canvas"],
  ["on-accent", "accent", TEXT, "label on primary button fill"],
  ["on-accent", "accent-hover", TEXT, "label on hover button fill"],
  ["focus", "surface", LARGE_OR_BOUNDARY, "focus ring against surface"],
  ["focus", "canvas", LARGE_OR_BOUNDARY, "focus ring against canvas"],
  ["control-border", "surface", LARGE_OR_BOUNDARY, "input boundary on surface"],
  ["control-border", "canvas", LARGE_OR_BOUNDARY, "input boundary on canvas"],
  ["chart-2", "surface", LARGE_OR_BOUNDARY, "chart series 2 on paper"],
  ["chart-3", "surface", LARGE_OR_BOUNDARY, "chart series 3 on paper"],
  ["chart-4", "surface", LARGE_OR_BOUNDARY, "chart series 4 on paper"],
];

let failures = 0;
for (const [fg, bg, target, role] of pairs) {
  if (!tokens[fg] || !tokens[bg]) {
    console.error(`MISSING TOKEN: ${fg} or ${bg} not found in tokens.css`);
    failures += 1;
    continue;
  }
  const r = ratio(tokens[fg], tokens[bg]);
  const ok = r >= target;
  if (!ok) failures += 1;
  console.log(
    `${ok ? "PASS" : "FAIL"}  ${r.toFixed(2)}:1  (target >= ${target}:1)  ${fg} on ${bg} — ${role}`,
  );
}

console.log(failures === 0 ? "\nAll token contrast checks passed." : `\n${failures} contrast check(s) failed.`);
process.exit(failures === 0 ? 0 : 1);
