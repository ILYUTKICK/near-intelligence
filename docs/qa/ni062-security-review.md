# NI-062 — adversarial ownership and security review

Task: NI-062 "Complete adversarial ownership and security audit" (P0, Epic 13). Date: 2026-11-10.
Dispatch: one parallel-dispatch subagent covering the role-B API-security zone and the role-A web zone per
the 9 November 2026 operator instruction (no independent reviews; coordinator verification is the
acceptance gate). This report is the security review deliverable the card expects; every verdict below is
backed by an executed test listed in [Verification](#verification), not by code reading alone.

**Verdict: no unauthorized read/write/download exists in the implemented product. Zero critical findings.
Three high/medium findings were found and CLOSED in this task (each with the fixing commit); one
low-severity product follow-up stays UNRESOLVED (honest fail-closed behavior, routed to its owners); the
environmental items below are deferred to their owning gates. Release-blocking condition (any unresolved
critical/high) is NOT met.**

## Scope of the audit

- Every private endpoint family, driven as real HTTP through the real dependency chain (stubbed token
  verifier, real RLS-backed PostgreSQL 18 disposable cluster): documents CRUD/revisions/idempotency,
  chart blocks and chart-view, insights/hypotheses/evidence CRUD + evidence-target catalog, export
  create/poll/download, saved charts, workspace home, profile (`/api/me`).
- The database boundary directly with the two application roles and the operator lease role (migration
  0012 column grants, FORCE RLS, pooled identity reset, disabled-owner fail-closed).
- The session/JWT boundary (fail-closed verification matrix at the HTTP layer), the same-origin web
  gateway (CSRF/Origin/cookie flags/forwarding), and the client-side identity-retention boundary
  (workbench, session storage, auth-change consumers).
- Cache/store bleed (no-store on every private response, public caching by design), secret-leak scanning
  of the production client bundle, untrusted content (markdown/editor/XSS/SVG/ZIP/asset names), and
  static subprocess/network/secret sinks of the whole API source tree.
- The recovered WIP (commit `ba30c06`) was audited before being trusted: all five Python suites and two
  web suites were executed, the source edits reviewed and corrected where wrong (see
  [WIP disposition](#recovered-wip-disposition-ba30c06)).

Honest boundaries: no real provider calls (the verifier/JWKS/provider transports are synthetic or stubbed
— the established harness seam), no real Supabase project abuse, no cloud SQL, no collector restarts; the
Linux-container runtime and staging demo evidence stay deferred to the NI-069 gate; desktop-only scope
(8 November 2026). CI verification of this branch is pending the coordinator.

## Per-family ownership verdicts (Alice/Bob HTTP matrix)

Suite: `apps/api/tests/security/test_security_http_ownership.py` (7 cluster tests, run by
`scripts/run-db-tests.py`). Baseline discipline: every foreign refusal is compared BYTE-EQUAL against the
absent-resource answer (`code`/`message`/`details`), so no existence oracle exists; every response is
asserted `Cache-Control: no-store`.

| Family | Verdict | Evidence |
| --- | --- | --- |
| Documents CRUD/revisions (get, list+search, versions list, version detail) | PASS — Bob reads Alice's document/version as the one generic 404 byte-equal to absent; Bob's own list/search/home carry zero Alice content (string-level assertion) | `test_01` |
| Document writes (save/rename/delete/chart-block/annotation mutations) | PASS — all foreign mutations 404 (never 409/428: the id is not even interpreted), Alice's row untouched afterwards; owner's own stale CAS stays a real 409 `REVISION_CONFLICT` and a stale-revision foreign request stays 404 (the revision value leaks nothing) | `test_02`, `test_03` |
| Missing-precondition parity | PASS — 428 for a foreign id is byte-equal to the 428 for an absent id (checked before any id resolution) | `test_03` |
| IDOR cross-referenced UUIDs | PASS — Alice's version UUID under Bob's document, unknown/foreign export job ids, cross-document download paths: one generic 404; Bob pointing evidence at Alice's insight → typed 422 `REFERENCE_INVALID` | `test_04` |
| Exports create/poll/download | PASS — Bob cannot create, poll or download Alice's export (404 incl. cross-document ids); the owner's download is `application/zip`, server-controlled filename, no-store, flat UUID entries, inert markdown (no `<script`, no unescaped link destinations except relative assets), exact decimal strings, manifest pins the served revision | `test_02`, `test_07` |
| Saved charts (list/patch/delete) | PASS — foreign reads/writes 404; Alice's instance survives Bob's attempts unchanged | `test_01`, `test_02` |
| Workspace home, profile `/api/me` | PASS — Bob's home/`/api/me` answer his own identity only; payload `owner_id`/`user_id` identity injection is refused 422 and never rewrites the verified subject | `test_01`, `test_05` |
| Private model surfaces | N/A-safe — no private model endpoints exist (NI-055 is P1/TODO); the public model APIs are read-only, identity-free and cached by design (`max-age=60`) | `test_06` |
| Global scientific data (chart definitions, dataset versions, metric definitions) | PASS-by-design — immutable public read-only data; the matrix deliberately does not 404 them (recorded NI-032 semantics), and no mutation surface exists for ordinary users | `test_06` |
| Public vs private caching | PASS — every private response (200/401/403/404/428/zip) is `no-store`; public catalogs keep their recorded `max-age` | `test_01`–`test_06` |
| Staged data never leaks through private reads | PASS — chart-view pins resolve only through the owned document chain (foreign dataset version UUIDs refuse inside the owned doc via NI-042's owner-scoped view) | `test_01`, `test_02` |

## Database boundary (RLS defense in depth)

Suite: `apps/api/tests/security/test_security_rls_probes.py` (9 cluster tests).

- The pooled `near_app` role reads ZERO foreign rows across every private table (documents, versions,
  blocks, insights, hypotheses, evidence_links, saved_charts, export_jobs incl. plan/bundle bytes,
  idempotency_records, users, user_profiles) while the admin connection sees the same fixtures — the zero
  is the policy, not an empty database.
- Foreign writes through `near_app`: UPDATE/DELETE match nothing (rowcount 0); version immutability,
  owner-column updates and foreign-owner INSERTs are hard 42501 denials.
- `SET row_security = off` and `SET ROLE near_operator` both fail 42501; `near_public` has nothing on
  schema `app`.
- Operator lease credential (migration 0012): can read/write only the derived lifecycle columns; reading
  or writing `plan`, `bundle`, `plan_sha256`, `bundle_sha256`, `bundle_byte_size` is a 42501 column-grant
  denial; DELETE is the only purge power.
- Pooled identity never retains a subject after the transaction (same backend session re-checked).
- A disabled owner loses every private row at the database layer and recovers when re-enabled.

## Session/JWT/web gateway/client retention

- `apps/api/tests/security/test_security_session_boundary.py` (4 offline tests): the real NI-018
  verification chain (synthetic ES256 key, injected JWKS) rejects missing/empty/garbage bearers, expired
  tokens, future nbf, wrong issuer/audience, non-UUID/uppercase/UUIDv1 subjects, alg=none, HS256 and
  tampered signatures with ONE generic 401 envelope — identical body across every reason (no enumeration
  oracle), no reason detail, no subject echo, `no-store` on every 401. Unknown kid forces exactly one
  JWKS refresh then fails closed.
- `apps/web/tests/security/gateway-session-boundary.test.ts` (14 tests): CSRF/Origin enforcement on the
  real gateway handlers before any provider call (missing pair, mismatched pair, cross-origin, missing
  Origin); cookie flag contract (HttpOnly, SameSite=Lax, Path=/, Secure added in production, tokens never
  in a response body); logout clears both cookies even when the provider is unreachable; the session
  endpoint clears tampered cookies; the private forwarding gateway answers 401/403/404/405/413 with
  no-store, never forwards cookies as identity, never leaks the internal API URL, and rejects mutations
  without the CSRF pair. The NI-063 gateway allowlist (892d877) coexists: the added export paths are
  exercised by the NI-058/NI-063 suites and the deep-path 404/405 semantics still hold.
- `apps/web/tests/security/workbench-identity-guard.test.tsx` (6 tests): the cross-tab account-switch
  retention gap CLOSES (finding H-1 below) — a verified different subject unmounts the editor and clears
  the sessionStorage recovery draft; a verified session end keeps the same-owner content (NI-040
  recovery contract) until a different principal verifies; outages never clear; the conflict dialog's
  copy-as-new path is identity-gated end-to-end in `editor-save.test.tsx` (no document is created under
  a changed subject, and the workbench clears).
- `apps/web/tests/security/browser-storage-boundary.test.ts` (8 tests): no token/session payload in Web
  storage; `localStorage.setItem` confined to the opaque auth-change signal; public pages never import
  the private document transport or editor; public API clients send no credentials/authorization; every
  private client rides the CSRF gateway; the auth-change consumer inventory covers WorkspaceHome, owned
  saved-chart data, chart library auth actions, the editor chart provider AND the new full-workbench
  identity guard.

## Untrusted content, downloads and sinks

- `apps/api/tests/security/test_security_untrusted_content.py` (16 offline tests): hostile
  prose/heading/table/link payloads render inert in the frozen export markdown (structure escaped,
  newlines flattened, `javascript:`/`data:` payloads survive only as escaped text with no re-formable
  link structure; exact decimal strings and bounds survive hostile neighbors untouched); the canonical
  editor schema rejects script/iframe/html/embed nodes, event-handler marks and non-http(s)/
  credential-bearing/protocol-relative links BEFORE storage; the NI-057 SVG boundary re-refuses
  script/foreignObject/event-handler/remote-reference vectors and non-UUID asset names; ZIP entries are
  flat server-derived names and hostile archives (`../`, absolute, backslash) fail closed.
- `apps/api/tests/security/test_security_static_sinks.py` (9 offline tests): the ONLY subprocess in
  `apps/api/src` is the pinned NI-057 renderer boundary — one fixed ARGV-list `subprocess.run` with the
  payload on stdin, no `shell` anywhere, no `eval`/`exec`/`os.system`/`os.popen`; outbound HTTP clients
  exist only in the three documented operator/config modules (JWKS fetcher refuses non-https, never
  follows redirects, fetches exactly the configured URL; the stopped collector and the capability probe);
  NO OpenAPI request surface names a fetch target (no URL/webhook/redirect-shaped parameters — the SSRF
  sink inventory is empty by construction); no credential material shapes and no token-shaped logging
  literals exist in source.
- Downloads: the export download is `application/zip` with a server-controlled filename (no user path),
  inert content (verified above), owner-checked, `no-store`, and the expired state is a typed 410 — no
  executable content and no path traversal.

## Secrets and cache/store bleed

- `pnpm --filter web check:client-secrets` (executed against the real production build, real root .env):
  always-on self-test proves BOTH directions on every run (a signing-secret leak must FAIL; the
  `authenticated` audience literal must never flag), then scans the built client — 50 client files, no
  server auth secrets present, exit 0. NI-062 narrowed the generic-word exemption to the JWT audience
  slot alone so a weak signing secret can never lose its scan (finding L-1).
- Public manifests/pages: the automated scans cover every `app/(public)` source and the built bundle
  generically; the landing HTTP integration compares visible HTML against the API's exact decimal
  strings on the same running web process (re-run green). NI-070's release report/evidence manifest are
  on the open `feat/ni-070-research-release` branch (NOT in origin/main at audit time) — audited
  read-only from that branch: no credential/token/internal-URL shapes and no private document references
  in either file, and its public-page changes stay inside `app/(public)` + static content, so the
  same automated no-leak scans apply to them at merge time.
- Private no-store is asserted per-response in the ownership matrix (200/401/403/404/428/zip) including
  the NI-062 API-layer hardening on `GET`/`PATCH /api/me` (finding M-2); the forwarding gateway adds its
  own no-store on every path (gateway suite); server components of private routes are dynamic/force-dynamic
  (NI-020/NI-021 recorded).

## Findings

Severity scale: critical/high block release when unresolved. "Closed" findings name the fixing commit on
this branch.

- **H-1 (HIGH — CLOSED, commit `e2fe708`)** — the recorded NI-042 audit input: the editor workbench
  retained loaded document/recovery content across a cross-tab account switch/logout without any identity
  revalidation (the NI-042 chart provider guarded only chart controls), so an abandoned tab exposed
  Alice's content to Bob and offered copy-as-new/download/draft-restore paths carrying it. Closed by
  `features/editor/persistence/session-owner.ts` (verified-subject revalidation on mount, AUTH_CHANGE,
  cross-tab storage signal, focus, visibility) + the workbench clear-on-different-principal rule + the
  copy-as-new fresh re-verification gate + full coverage. Residual recorded tradeoff (deliberate, tested):
  after a verified session END (401) the tab keeps the SAME verified owner's content for the NI-040
  recovery contract ("sign in again, then retry the save"); every submission path is dead while signed
  out (saves fail typed-401 and stop autosave; copy-as-new refuses without a verified matching subject),
  and any later DIFFERENT verified principal clears memory and the storage draft. The window between an
  identity action and the next verified check is covered by the login/logout `announceAuthChange` event
  plus the cross-tab storage signal; the server-side RLS 404 remains the write backstop throughout.
- **M-2 (MEDIUM — CLOSED, hardening verified from `ba30c06`, direct assertion added in `fd9ca9a`)** —
  `GET/PATCH /api/me` responses carried no `Cache-Control` at the API layer (the same-origin gateway
  overrides headers, but the API contract must not rely on that for its own no-store guarantee). The
  WIP's two-line hardening is correct and in-scope; the ownership matrix now asserts `no-store` on the
  owner's own 200 responses.
- **M-3 (MEDIUM — CLOSED, commit `efda125`)** — the NI-063 recorded finding's error-mapping half was a
  REAL defect: openapi-fetch consumes the body of a non-ok response itself and returns the parsed
  envelope as `error`, so the export client's re-read of `response.json()` always failed and degraded
  EVERY typed refusal (`REVISION_NOT_ACKNOWLEDGED`, expiry/410 detail paths) to the generic fallback —
  the dialog never showed its specific copy. Fixed by parsing the client-captured error object against
  the shared envelope schema; regression pins the specific stale-revision copy.
- **L-1 (LOW — CLOSED, commit `e7b543a`)** — the recovered scanner rewrite exempted EVERY server auth
  variable whose value looked like a bare generic word, so a low-entropy signing secret that matched the
  word shape would silently lose its leak scan. The exemption now applies to `SUPABASE_JWT_AUDIENCE`
  only (the recorded NI-041 false positive); issuer/JWKS/origin URLs and both signing secrets are always
  scanned.
- **P-1 (LOW — UNRESOLVED, does not block release)** — the workbench pins `currentVersionId` at document
  load only (NI-063 finding): exporting immediately after in-session saves targets the stale acknowledged
  revision and the API refuses with typed 409 `REVISION_NOT_ACKNOWLEDGED`. With M-3 fixed the dialog
  renders the specific honest guidance ("This revision is no longer the document's current revision.
  Save or reload, then export the current revision."), the refusal is fail-closed (a stale export can
  never render the wrong revision), and no cross-owner path exists — an availability/UX follow-up, not a
  boundary break. Routed to the NI-058/NI-040 owners (the same routing NI-063 recorded); fixing it here
  would have restructured the save pipeline inside a security audit, which was judged the wrong trade.
- **E-1 (environmental — deferred by scope, not a code finding)** — all executed evidence is macOS-local
  plus CI; the Linux-container runtime, staging demo and reviewer-reproduction gates stay with NI-069;
  the multi-instance rate-limiter note stays with NI-067.

## Recovered WIP disposition (ba30c06)

Kept (executed and verified): all five Python security suites (with the `/api/me` no-store assertion
added), both web security suites (relocated), the discovery-list union, the `users/routes.py` no-store
hardening (M-2), and the scanner rewrite's core design (self-test both directions, URL-shaped values
always scanned) with the exemption narrowed (L-1). Fixed/changed: the scanner's over-broad generic-word
exemption; the web suites' location (the separate `e2e/security` vitest config was never collected by
the standard run and could silently rot — the specs moved into the standard `tests/security` tree and
the config was deleted; Playwright's `*.spec.ts` glob never collected the `.test.ts` files, so the two
runners stay decoupled); the honest-boundary note and consumer inventory updated to the closed state.
Nothing from the WIP was deleted except the redundant local vitest config. The WIP's own Python and web
suites ran green before and after these changes.

## Verification

Recorded real outputs on this branch (worktree `/Users/ilyutkinn/Desktop/near-intelligence-a16`, commits
through `fd9ca9a`):

1. Disposable-cluster suite `uv run --project apps/api python scripts/run-db-tests.py --pg-bin
   /opt/homebrew/opt/postgresql@18/bin` — exit 0, all 25 discovered suites OK, 463 integration tests,
   0 skips (the runner rejects skips), including the two new security suites:
   `test_security_http_ownership` 7 OK and `test_security_rls_probes` 9 OK. The `--suite landing` and
   `--chart-insertion-http` production HTTP gates re-ran green after the web changes (1 test OK each).
2. Full offline discovery `uv run --project apps/api python -m unittest discover -s apps/api/tests -p
   "test_*.py"` — 660 tests OK (skipped=231: exactly the documented cluster/real-archive gated classes —
   baseline 615/215 plus 29 offline and 16 cluster-gated security tests; no new skip state). The three
   offline security suites also verified through the exact CI invocation (`cd apps/api; uv run python
   -m unittest discover -s tests -p test_security_*.py`) — 16 + 4 + 9 OK.
3. Web: `pnpm --filter web test -- --maxWorkers=2` — 48 files / 510 tests pass, including the 28
   relocated/new security tests; `pnpm --filter web lint` — 0 errors/0 warnings; `pnpm --filter web
   typecheck` — clean; `pnpm build` — exit 0; `pnpm --filter web check:contrast` — all token pairs pass;
   `pnpm --filter web check:client-secrets` — self-tests verified, 50 client files scanned, no leaks,
   exit 0.
4. `uv lock --check --project apps/api` — OK (no dependency changes; `apps/api/uv.lock` untouched).
   `node packages/shared-types/scripts/generate.mjs --check` — OpenAPI and TypeScript current.
5. `node scripts/check-doc-links.mjs` — 659 relative documentation links resolve.
6. `.github/workflows/checks.yml` — YAML-validated; the api job now runs the three offline security
   suites; the database job runs the two cluster security suites through discovery.
7. No new npm or Python dependencies; no migration; no API contract change (the `users/routes.py`
   hardening adds a header only — `generate.mjs --check` confirms the OpenAPI is unchanged).
