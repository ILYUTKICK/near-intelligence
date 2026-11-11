/**
 * NI-005: verify that relative links inside Markdown documentation resolve.
 * Scans repository Markdown files (root, docs/, app READMEs,
 * packages READMEs), extracts [text](target) links, and checks that
 * relative file targets exist (anchors are stripped). Absolute http(s),
 * mailto and bare-anchor links are skipped. Exit 1 on any broken link.
 */
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function* markdownFiles(dir) {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === ".next" || entry.startsWith(".")) {
      continue;
    }
    const full = path.join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      yield* markdownFiles(full);
    } else if (entry.endsWith(".md")) {
      yield full;
    }
  }
}

const scanRoots = [
  repoRoot,
  path.join(repoRoot, "docs"),
  path.join(repoRoot, "apps"),
  path.join(repoRoot, "packages"),
];

const linkPattern = /\[[^\]]*\]\(([^)\s]+)\)/g;
let checked = 0;
const broken = [];

for (const root of scanRoots) {
  if (!existsSync(root)) {
    continue;
  }
  for (const file of markdownFiles(root)) {
    const content = readFileSync(file, "utf8");
    for (const match of content.matchAll(linkPattern)) {
      const target = match[1];
      if (/^(https?:|mailto:|#)/i.test(target)) {
        continue;
      }
      const withoutAnchor = target.split("#")[0];
      if (withoutAnchor.length === 0) {
        continue; // pure in-page anchor
      }
      const resolved = path.resolve(path.dirname(file), decodeURIComponent(withoutAnchor));
      const relativeTarget = path.relative(repoRoot, resolved).split(path.sep).join("/");
      // The raw research archive and local state are intentionally unshared
      // (README/COLLABORATION: "a fresh clone may lack linked evidence
      // artifacts") — links into them are documented gaps, not breakage.
      const knownUnshared =
        relativeTarget.startsWith("research/") && !relativeTarget.endsWith(".md");
      if (knownUnshared) {
        continue;
      }
      checked += 1;
      if (!existsSync(resolved)) {
        broken.push(`${path.relative(repoRoot, file)} -> ${target}`);
      }
    }
  }
}

if (broken.length > 0) {
  console.error(`FAIL — ${broken.length} broken relative documentation link(s):`);
  for (const item of broken) {
    console.error(`  ${item}`);
  }
  process.exit(1);
}
console.log(`OK — ${checked} relative documentation links resolve.`);
