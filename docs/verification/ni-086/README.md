# NI-086 — Approved editorial Overview

Implemented and verified locally on 14 November 2026 (Europe/Moscow), following
the owner's approved [full-page concept](approved-overview-concept.png).
The homepage introduces the research product and provides working paths into
Blog, full research, data, methodology and private work. Original quantitative
evidence and model status remain in their owning pages and services.

## Delivered page

Native React/HTML hero “Understand NEAR. Build your own thesis.”; project-local
decorative paper/branch/pen artwork; one actual featured publication through the
shared Blog registry/card; three real data-category links; Read→Inspect→Build
workflow; short methodology band; green workspace CTA. The page has no data API
dependency, fake KPI, live badge, invented article or duplicated financial table.

The legacy `findings`, `evidence`, `mechanism` and `release-status` anchors remain
meaningful entry points, with links into the full economic mechanism/status.
This is the explicit owner-approved replacement of NI-012's on-home presentation,
not a change to financial definitions, published article claims or model gates.

The [asset record](ASSETS.md) contains the final project asset path, dimensions,
built-in image-generation mode and verbatim prompt. The artwork has SHA-256
`8dd081e0209c3c0447789a9c17c1e634eefb1c9d731dd0de37c18e2f41c437f1`.
It contains no actual financial observations and is excluded from accessibility
content through empty alt text. A real Next Image request at width 640 returned
**image/webp, 15,682 bytes**, from the 2,046,996-byte source PNG; no remote asset
host or new image dependency is required.

## Checks

- Six focused frontend suites: **62/62 passed**, including Overview, Blog,
  public routes, existing thesis/figures and ten retained financial-loader cases.
  The final run used `--maxWorkers=1 --testTimeout=15000` for heavy jsdom/axe
  cases. Initial runs exposed a CTA focus-class mismatch and one invalid test
  option; these were fixed. Unchanged research axe cases exceeded the earlier
  5-second deadline; assertions were retained in the successful serial run.
- Web TypeScript and clean lint passed; final production build passed after
  the browser contrast correction. Build ID: `E0KUqyBTBvduaTs0Foq_o`.
- Updated real loopback landing integration: **1/1 synthetic pass** and
  **1/1 saved-archive pass**. The API correctly had no approved series before
  publication; exact string values and approval/version/coverage/source-ambiguity
  rules remained tested after publication. The visible editorial page and links
  were unchanged before/after publication and after the API stopped. Two real
  input hashes remained unchanged; synthetic mode exposed 3/3 series, archive
  mode 2/3 because the unqualified fee source stays honestly ambiguous.
- Python integration-test syntax compiled; no application/backend dependency or
  financial contract was changed. Documentation links, whitespace and unique,
  topologically ordered task references passed (84 execution rows).

Local logs: `/private/tmp/ni086-web-verified.log`, `ni086-typecheck-final.log`,
`ni086-lint-final.log`, `ni086-build-final.log`, `ni086-landing-synthetic.log`
and `ni086-landing-archive.log` in the same directory. They are local operator
evidence, not repository data artifacts.

## Actual desktop/browser acceptance

Final preview: `http://127.0.0.1:51528/`, isolated real saved-archive API at
`http://127.0.0.1:51527`. Final handoff is
`.local/ni086-preview-final/handoff.json`; the stack remains running.
Authentication transport is synthetic; public research/data delivery uses the
real application/API/database and explicitly supplied historical inputs.

At 1440×900, the approved hierarchy, hero artwork, one publication, data cards,
workflow, methodology and CTA rendered. A real CSS inheritance defect made the
CTA heading navy despite a light parent; an explicit light heading color fixed
it. Final computed colors were `rgb(255,253,250)` on `rgb(28,91,65)` — **7.89:1**
contrast. Keyboard focus had a clearly visible light outline. Page-width overflow
was **0px**. Screenshots were rechecked after that correction.

Keyboard/click paths reached Blog and its full research article; the original
interactive history still resolved **694 volume / 543 fee / 543 matched days**
and retained the separate 90-day purchase window. The workspace action navigated
to the protected workspace route without submitting any sign-in form. Independent
HTTP checks returned **200** for Overview, Blog, all three data directions and
methodology. Sanitized results are in local `.local/ni086/http-checks.json`.

Proof: [first screen](overview-desktop.jpg), [full desktop page](overview-full-desktop.jpg).
The full-page screenshot is 1440×2782. No new mobile verification was performed.

## Source identity and boundaries

Combined source SHA-256:
`ee12b936214b3e0ce9082b2c7efe411a4b5f3299ce6f509cb8ca46ddc8120f53`
over 378 source files under web/API/shared-types source roots, using sorted
relative path, uint64 big-endian path byte length, path bytes, uint64 big-endian
content byte length and content bytes; extensions `.ts/.tsx/.py/.json/.css`,
excluding Python bytecode. Artwork hash is recorded separately above.

No source archive rewrite, external data request, collector restart, dependency
addition, Git staging/commit/push or remote deployment occurred. This local UI
task does not close NI-079 or outstanding real model/attribution/refresh gates.
