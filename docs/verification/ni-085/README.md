# NI-085 — Public Blog and research publications

Local implementation, 14 November 2026 (Europe/Moscow). The owner explicitly
requested implementing the [publication direction](../../BLOG_PUBLICATIONS.md).
No Git publication, remote deployment, CMS dependency or new data collection.

## Implemented behavior

- `/blog` is an anonymous public catalog containing exactly the existing complete
  NEAR/Intents research. It uses the established ivory/navy/green editorial design.
- The typed curated registry is `apps/web/src/features/blog/publications.ts`.
  Shared `PublicationCard` and `PublicationArticle` support another real authored
  entry without copying the complete research route. Synthetic entries exist
  only in tests and are not discoverable in runtime routes.
- The first card links directly to `/research`. Its registered alias
  `/blog/near-thesis-2026-11` permanently redirects (308) to `/research`; unknown
  or malformed slugs return the generic article 404. Existing evidence/claim/
  hypothesis/section anchors and the public release identity remain intact.
- Public navigation now says Blog and remains active while reading `/research`;
  the article and footer link back to Blog. Workspace routes remain unchanged.
- The first card records the known November 2026 release label and the actual
  original cohort scope. No exact publication day, author or second article is
  invented. Each card's question/highlights come from its own metadata.
- Existing full research and real interactive history are retained. Adding Blog
  neither refreshes data nor updates prior editorial conclusions. No private
  document, shared private revision or synthetic demo release is enumerated.
- Relative HTML canonical metadata was omitted because the app has no confirmed
  metadata base; no default localhost hostname is presented as a production
  canonical domain. Compatibility is provided by stable links and the 308 alias.

## Verification

Dedicated task agent ran five focused frontend suites: **55/55 passed**. After
removing unverified canonical metadata, Blog follow-up tests: **8/8 passed**.
Coverage includes actual first-publication identity/metadata, unknown slugs,
alias policy, active navigation, keyboard/a11y, existing thesis and figures,
future test-only article rendering, escaped source text and related-link rules.
TypeScript and lint passed. The first focused pass exposed the expected new
`/blog` internal-link allowlist requirement and a stale NI-081 methodology-copy
assertion; both were corrected with their actual invariants retained.

Detailed local logs: `/private/tmp/ni085-focused-final.log`,
`/private/tmp/ni085-blog-final.log`, `/private/tmp/ni085-typecheck.log`,
`/private/tmp/ni085-lint.log`.

## Coordinator production/browser acceptance

- Production build passed with TypeScript: `7apX5U1Dn0wC518_nfqTU`.
  `/blog` is statically rendered; `/blog/[slug]` serves the registered route.
- The source fingerprint is
  `b43f4f3e85d2cb77093d812b8e5fa06ce0a7c5bd9b3448784e49dfa0d77928b7`
  over 377 source files under web/API/shared-types source roots. Encoding:
  sorted relative path, uint64 big-endian path byte length, path bytes,
  uint64 big-endian content byte length, content bytes; extensions
  `.ts/.tsx/.py/.json/.css`, excluding Python bytecode.
- Final preview: `http://127.0.0.1:54480/blog`; isolated API
  `http://127.0.0.1:54479`, explicitly seeded from the real saved archive.
  Authentication transport remains synthetic; the public catalog does not use
  private or synthetic publication records. The actual API/database/data path
  is real and isolated; this is local acceptance, not deployment.
- Desktop browser, 1440×900: one real catalog card; Blog active in the header;
  keyboard Enter opened full `/research`; the alias with `#h1` reached
  `/research#h1`; original full article and evidence navigation remained.
- Article history rendered 694 volume/543 fee/543 matched days. Keyboard zoom
  narrowed visible dates and Reset restored them. Sources & definitions opened
  real DefiLlama metadata and Escape closed the dialog. The article backlink
  returned to Blog. An unknown article showed the generic Article not found
  screen and its Back to Blog link returned correctly. No horizontal overflow
  was visible at desktop size. No new mobile pass was performed.
- Independent loopback HTTP checks: catalog **200**, first alias **308** with
  `Location: /research`, unknown slug **404**. Same-origin history gateway
  reconciled **694/543/543** and an approved real dataset pin. Sanitized machine
  evidence remains local in `.local/ni085/http-checks.json`; preview handoff is
  `.local/ni085-preview/handoff.json`.
- Documentation links resolve; task identities/dependencies are unique and
  topologically ordered (83 execution rows); whitespace check passed.

[Desktop catalog proof](blog-desktop.png). The preview remains running for the
owner. No raw archive was rewritten, provider queried or Git index mutated by
this task. NI-079, research-model, refresh and deployment gates stay separate.
