# NI-080 — workspace correction batch

Owner feedback on 13 November 2026: remove Home Data context, keep chart/category
navigation in the cabinet, and let a visitor enter a usable demo with an email
label. [Task and acceptance](../../TASKS.md); [route contract](../../INFORMATION_ARCHITECTURE.md).

## Implementation

- Home removes the indicator section, including its title, values and links.
  The existing Home API contract remains available to other consumers.
- Workspace explorer, chart library/detail and model catalog/detail mount shared
  screens behind the existing signed-session layout. Search/category/pagination,
  chart selection/version/backlinks and saved-chart Explore actions retain the
  workspace prefix. Public routes reuse the same implementation.
- Login leads with an email-label demo form. It creates an independent anonymous
  identity and an owned eight-section `investment-v1` research template through
  the authenticated document API. Password sign-in remains in a separate
  disclosure. A label neither verifies an email nor retrieves an existing account.
- The loopback QA harness now serves anonymous signup, rotating refresh and logout
  transport for the normal gateway. It retains ES256 verification, principal
  bootstrap, HMAC cookies, Origin/CSRF checks and RLS. These endpoints exist only
  in the harness, not in application/deployment code. Remote anonymous sign-in
  still requires a configured provider; no provider call was made here.

## Verification record

Source baseline: main `8eed5d3` (PR #99 merged), branch
`codex/ni-080-workspace-demo`. Production build: `1nm9xI9qFhfh7tn1k1f1r`. Frozen `apps/web` Git tree:
`bf06347f744a37a919d432400da6a2dac7086a5e` (includes source, harness and tests).
The final local acceptance results are recorded below.

The first full unit run overlapped production builds: 671/672 passed, with one
5-second timeout in the unchanged public-thesis section test. The unchanged
thesis file passed 26/26 in isolation. No timeout or assertion was weakened.
Initial Turbopack builds hit the host sandbox's local-port restriction; the
retained error cache also failed on the first retry. A build with a fresh
Turbopack cache and local process permission passed. No source workaround was
introduced for that environment error.

The initial browser probe passed actual email-label entry, starter-template
reload, Home removal, cabinet navigation and explorer axe (zero findings).
It then exposed an implicit-range problem: default latest views used wall-clock
dates even when the available dataset was historical. The default range now follows the resolved dataset coverage, with the second
request pinned to its immutable ID; explicit date selections remain authoritative.
Old-coverage, explicit-selection and featured-pin regressions pass. The first plot assertion also referred to a nonexistent
test ID and has been corrected to the actual figure SVG; no product test hook
was added just to satisfy it.

## Final checks

- Serial no-concurrent-build unit/interaction run: **63 files / 676 tests pass**
  (82.39 s). Focused auth validation/seed failure checks: **8/8 pass**.
- Chart/library/explorer focused regressions: **91/91 pass**.
- Strict TypeScript, ESLint, production build, OpenAPI/generated contracts,
  22 contrast pairs, 870 relative documentation links and whitespace pass.
- New real-stack demo/navigation scenario: **1/1 pass** (9.1 s including boot):
  email form → own starter → reload → Saved Charts → Explore → Network/Intents
  inside cabinet → actual SVG → custom dates → save/reopen → refresh rotation
  → same-label second visitor denied first document → logout/relogin isolation.
  Explorer axe: zero serious/critical or lower-impact findings.
- Full real-stack regression: **25/25 pass** (2.7 m), including accessibility,
  custom range, saved cards, research→outage→export, two-user denial, publication
  copying, revocable sharing and the new email-demo scenario. Every axe surface
  has zero serious/critical and zero lower-impact findings.
- Native in-app-browser verification: normal email form opens the owned starter;
  Home has no Data context; Saved Charts Explore, Network Activity, Intents and
  the default historical plot retain the cabinet. A separate local preview was
  left running for owner review.
- The client-secret checker ran its self-tests, then reported no root
  `.env` configured; no scan against actual provider secrets is claimed.

## Evidence boundaries

Local production Next.js/FastAPI/PostgreSQL and export worker; synthetic auth
transport and clearly synthetic chart datasets. The new starter document has
section headings, without invented research claims or financial values.
Existing raw research, stopped collectors and input files remain untouched.
No mobile QA, remote deployment, email delivery or real-provider verification
is claimed. This task does not close NI-079's real-data/model/container gates.

## Publication handoff

On 13 November the owner explicitly deferred all Git commits/pushes/PRs while
continuing local feedback. No commit or push was made for this batch. Local
acceptance is complete; remote final-head CI and publication remain deferred.
The earlier full E2E attempt passed 21 cases but stopped at the superseded
wall-clock-empty expectation. It was replaced with checks for coverage-anchored
implicit dates and an explicit out-of-coverage window that still stays empty;
the final complete run above passes all 25.

### Delivery resumed — 14 November 2026

The owner explicitly requested committing the accumulated NI-080–086 changes
for another agent. This later instruction lifts the earlier Git hold for the
current batch. [Continuation handoff](../../LOCAL_CORRECTIONS_HANDOFF.md).

A bounded path/text audit by the existing NI-080 agent found only source,
tests, generated contracts, documentation and approved UI images. Coordinator
also scanned all 128 candidate paths: credential-pattern matches were README
database placeholders only. No raw research, secrets, local database/process
state or ignored inputs are included; ignore rules are unchanged. This is a
bounded audit, not a guarantee that every possible secret pattern was detected.

Packaging checks: ESLint, strict TypeScript, OpenAPI/generated-client drift,
1001 relative documentation links and whitespace pass. API history 11/11,
chart registry 30/30 and contracts 7/7 pass using the existing frozen environment.
The full web regression exposed eight test selector ambiguities: NI-083's
accessible plot-zoom status coexists with parameter-drop and sign-in statuses.
Tests now locate the relevant notice and still assert its status role and the
original filter/range/continuation behavior. No application behavior was changed
for this repair. The full run passed 64 files and 676/684 tests before this
selector repair; the two repaired suites then passed 91/91 in a quiet rerun
(13.97 s). An overlapping focused attempt had one unchanged 5-second timeout,
which passed in the quiet run without changing the timeout. Final-head remote
checks remain a handoff gate in the task card; no remote green result is claimed.
