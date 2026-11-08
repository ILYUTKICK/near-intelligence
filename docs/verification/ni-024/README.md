# NI-024 acceptance — 8 November 2026

Implemented by `/root/ni024_home` (A) with `/root/ni024_home/home_api` (B).
Independently reviewed and approved by coordinator `/root` (B). Source and
acceptance are recorded in [TASKS](../../TASKS.md); source fixtures are synthetic,
not production financial observations. No new dependency, provider request or
research mutation was used.

## Actual verification

- Full disposable PostgreSQL18 runner: 388 tests / 19 suites, no skips or failures;
  migrations/model drift clean. Home matrix13 includes current-revision counts,
  owned caps, deleted targets, plain-text note projections, exact decimal context
  and a real SQL failure isolated inside one indicator savepoint.
- Web: 417 tests / 36 files, including 10 Home tests; clean final rerun. An earlier
  all-pass run also had a ProseMirror/jsdom teardown exception; it was not counted
  as a successful run. Build, strict typecheck, lint, generated contracts, shared
  client test, API contract/capability tests, doc links and token contrast passed.
- After the production build, run
  `apps/api/.venv/bin/python scripts/run-db-tests.py --pg-bin <PostgreSQL18-bin> --workspace-home-http`.
  This passed 13 Home regressions and1 actual Next -> cookie/Origin/CSRF -> ES256
  JWT/bootstrap -> FastAPI/RLS -> isolated PostgreSQL scenario. First-use create,
  save, current-revision resume, owned charts/notes, independent indicator outage,
  no-store and Bob denial were verified.
- Native Chrome CUA used the same production services and synthetic accounts:
  fresh Bob created a persisted revision1 through keyboard Skip/Create/Enter;
  returning Home showed it. Alice resumed revision2 through Continue/Enter.
  Responsive desktop-emulated360px and1440px checks retained every decimal digit.
  No physical-phone, full-product screen-reader or release-performance claim.
- Home context fixtures now use a temporary DB clone within the disposable
  cluster. Environment/connections/caches are restored and the clone dropped;
  Home13 followed by Archive9 and the complete runner pass without weakening the
  existing archive assertion.

## Page-only proof

[360px Home screenshot](home-360-page-only.png) is a native DevTools page-only
capture, 720×7286 pixels at DPR2. It contains synthetic test document/chart labels
and synthetic exact value12.123456789012345678901234. It excludes unrelated
browser tabs, bookmarks and DevTools. Full-browser captures remain ignored/local.

## Tracked follow-ups

The known client-secret scanner false-positive for the public UI literal
`authenticated` remains under NI-062, with no false passing claim or scanner
weakening. Sidebar alias404s, unused slotted-Button runtime behavior and shared
anchor/primary-link layering are recorded under NI-064. NI-024 uses working
canonical routes and an explicit existing on-accent foreground token.
