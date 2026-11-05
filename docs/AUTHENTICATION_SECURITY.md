# Authentication, authorization and privacy

Security model for implementation. [API](API_SPECIFICATION.md), [database](DATABASE_SCHEMA.md). MVP has individual users; no teams, roles editable by users, collaboration or public private-document sharing.

## Identity/session flow

Supabase Auth handles email/password registration, verification, login, recovery and refresh. Use a separate dev project or local Supabase Auth setup; production sign-up requires email verification and allowlisted callback URLs. Browser submits credentials to same-origin server handlers over TLS. Never log passwords or provider bodies containing tokens.

Use server-managed HttpOnly, Secure production, SameSite=Lax cookies; SDK integration must explicitly enforce these attributes rather than assume defaults. Refresh token remains server-readable only; browser application JS receives no tokens. Next.js gateway refreshes/rotates cookies using provider SDK and forwards only access JWT to the internal API. Supabase publishable key is public configuration, not privileged authorization; no service-role key is required by normal application paths.

FastAPI verifies signature with a configured issuer JWKS URL, exact issuer/audience, expiry/not-before, subject UUID, and an allowlisted asymmetric algorithm that matches project configuration. Never follow a JWT-supplied jku or accept alg=none/HS256 fallback. Bounded JWKS cache; on unknown kid refresh once, fail closed if unavailable. [Supabase JWT docs](https://supabase.com/docs/guides/auth/jwts) explain asymmetric key verification; deployment must validate actual key settings. Target 10-minute access tokens; provider refresh rotation and disabled-user behavior must be tested. Logout revokes refresh session; already-issued JWTs can remain valid until expiry. Sensitive disabled-user access also checks local users.disabled_at.

Protect gateway mutations with Origin/Host allowlist and CSRF token bound to the server session (signed double-submit or synchronizer implementation), not SameSite alone. Auth callback validates state/PKCE and internal returnTo allowlist; never accept arbitrary external redirect URLs. Strict CORS if API is ever exposed; default API is internal and still authenticates every private request.

## Ownership invariants

Derive user ID from verified sub; ignore/reject owner_id/user_id fields in request payloads. Every read/list/search/create/update/delete/export/download verifies parent owner and all private foreign references. Use 404 for absent and not-owned IDs. Alice's document cannot attach Bob's saved chart/snapshot/insight even if UUID is known. Global approved data/chart/model definitions are read-only. Publication uses explicit reviewed projection; ordinary users have no publish permission.

Repositories include owner predicates; PostgreSQL RLS provides defense in depth with transaction-local identity. Runtime app role is not owner/superuser/BYPASSRLS; pooled sessions reset identity at transaction end. Public queries have a distinct limited role/context. Worker derives identity from claimed export_job and sets it explicitly per transaction, never bypasses ownership globally. Scientific operator imports use a separate credential with narrowly scoped privileges.

## Input/content/resource defenses

Validate every editor node and mark; reject unknown types/attrs and arbitrary HTML, scripts, embedded iframes, javascript: URLs and remote asset fetches. Allow only http/https citation links and safe internal IDs. Render rich text through a schema-controlled renderer; sanitize exports. No arbitrary user SQL/Python/formula evaluation. Node SSR export subprocess receives bounded typed JSON over stdin with no shell and no network access.

Document size/block/table limits, query point bounds and export concurrency limits prevent resource exhaustion. Login/reset per-IP and per-account bucket targets must be calibrated in staging; begin conservatively (5 login attempts/minute per IP, 20 recovery/hour per IP) and avoid account enumeration. API private writes target 60/minute/user; exports 3/minute/user and one active job/user. These are local policy targets, not provider quotas.

SSRF: only server allowlisted provider URLs; source details never become fetch targets directly. Path traversal: artifact storage key generated server-side, resolve beneath ARTIFACT_ROOT, no symlink escapes. ZIP export filenames sanitized, no arbitrary user paths. CSV cells from user text escape spreadsheet formula prefixes when exported for spreadsheet use; numeric metric CSV uses explicit decimal columns.

## Privacy and browser controls

Private responses and server components no-store; include identity in any private in-memory cache or avoid it. Clear TanStack Query/editor state on logout/account change; do not retain another account's content. Cross-tab signals clear auth-sensitive caches. No service worker caching of private responses. Default recovery buffer in memory; opt-in device storage encrypted-at-rest is not promised by browser storage, so disclose local persistence and provide Clear Local Drafts.

Content Security Policy with nonce-based script policy, frame-ancestors 'none', object-src 'none', restricted connect-src; HSTS in production, Referrer-Policy and nosniff. Validate chart tooltip HTML handling to avoid XSS; plain text formatted values preferred. Do not put private content or tokens in URLs/analytics/errors. Logs contain request IDs, resource IDs and operation outcomes, not notes or source credentials.

## Secrets and operations

Use environment/secret manager, separate production/dev credentials, least-privilege DB roles, restricted artifact volumes and TLS database connections. Exclude .env, raw auth headers and private exports from Git. Legacy research raw files require a secret/privacy/license scan before a public repository release. No credentials were needed or generated for this documentation phase.

Back up DB and artifacts together; restore/reconcile manifests before traffic. P0 account deletion is operator-assisted and documented; P2 self-service must revoke sessions and implement an explicit retention policy. Target private export TTL 24h, audit metadata 90d, failed staging artifacts 7d; immutable published evidence retained for the lifetime of published findings. Exact legal retention/data residency remains OQ-07.

## Required security tests

Alice/Bob matrix for every private endpoint family; IDOR by nested version/snapshot/export/reference; pooled RLS identity reset; forged/expired/wrong issuer/audience/algorithm tokens; revoked refresh and disabled users; CSRF/open redirects; private cache bleed; XSS in text/link/tooltip/export; path traversal and oversized document/query/export. A release with any unauthorized read/write is blocked. See NI-062 and [testing](TESTING_STRATEGY.md).
