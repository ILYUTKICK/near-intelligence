# NEAR Intelligence

**Build an investment thesis. Connect it to evidence. Publish research people can find and verify.**

NEAR Intelligence is a browser-based platform for investment research, thesis
authoring and public research publishing. It brings articles, interactive charts,
sources, quantitative models and a private writing workspace into one workflow.

The current research focuses on **NEAR and NEAR Intents**: whether growing
cross-chain activity translates into revenue and measurable value for the token.

[Open the platform](https://near-intelligence.me) ·
[Read the research](https://near-intelligence.me/research) ·
[Explore data](https://near-intelligence.me/data) ·
[Self-hosting guide](docs/SELF_HOSTING.md)

## What you can do

| For | Built capabilities |
| --- | --- |
| Readers | Browse the Blog, read the investment thesis and methodology, inspect interactive charts and follow their sources. |
| Researchers | Create a private research document, start from a thesis template, add charts, notes, hypotheses, risks and supporting or opposing evidence. |
| Analysts | Inspect published model results and diagnostics, compare supported chart selections and keep an exact record of the data behind a conclusion. |
| Authors | Save and reopen versioned research, freeze chart snapshots, create revocable read-only shares and export a saved revision as Markdown ZIP or PDF. |
| Editors | Add reviewed public articles through the publication registry and shared article template. Private drafts are published only through an explicit reviewed workflow. |

A thesis is assembled in the editor from your writing, templates and selected
evidence. Charts keep their definitions, source references and dataset versions;
saved revisions and exports preserve the evidence that was actually used.

### Research publishing, SEO and AI discovery

The publishing direction is simple: turn research into public web articles that
people can read in a browser and discover through Google or AI-assisted search.
Current public pages use server-rendered text, stable routes, page titles and
descriptions, linked sources and a browsable Blog.

Search indexing and AI citations depend on external crawlers and are not
guaranteed. Dedicated sitemap, structured-data and AI-discovery feeds are not
implemented in this release. Public articles are curated in
[the publication registry](apps/web/src/features/blog/publications.ts);
a private draft or share link does not automatically become a Blog article.

The core workflow needs **no LLM API key**. An optional grounded-commentary
adapter exists but is disabled by default; it is not an automatic full-thesis
generator. See [feature scope](docs/FEATURE_SPECIFICATIONS.md).

## The research workflow

1. **Read** a public investment case and its assumptions.
2. **Explore** a chart, select the period and inspect the underlying evidence.
3. **Build** your own thesis in a private workspace.
4. **Connect** charts, model results, notes and contrary evidence to your claims.
5. **Save** a revision with its exact data references.
6. **Share or export** that revision; publish reviewed public research separately.

Missing data is shown as unavailable. Historical observations retain their actual
dates. Gross fees, attributable revenue, treasury payouts, purchases, issuance
and burns remain separate measures.

## Run locally with Docker

This starts the application with a new local database. **It does not download
the deployed research database or populate charts with invented values.**
You can sign in, write research and export prose without a research data bundle.

### 1. Prerequisites and repository access

- Git, Docker Engine with the Compose plugin, and Python 3.12+ for the small
  configuration snippet below. Docker Desktop also supplies Compose.
- A Supabase project for authentication.
- Network access to GitHub, container/package registries and Supabase.

Node, pnpm, Python application packages and the chart renderer are installed
inside the Docker images; host-side frontend/Python installs are not required
for this path.

~~~sh
git clone https://github.com/ILYUTKICK/near-intelligence.git
cd near-intelligence
~~~

A public repository can be cloned without signing in. If you are using a private
copy, your GitHub account needs read access to that copy.

### 2. Create a private local configuration

Run this **once in a new checkout**. It copies the template, generates four
different database passwords and two signing secrets, and refuses to overwrite
an existing `.env`. It does not print secrets.

~~~sh
python3 - <<'PY'
import os
from pathlib import Path
import secrets

values = {
    key: secrets.token_hex(32)
    for key in (
        "DB_BOOTSTRAP_PASSWORD", "DB_RUNTIME_PASSWORD",
        "DB_MIGRATION_PASSWORD", "DB_OPERATOR_PASSWORD",
    )
}
values["AUTH_COOKIE_SIGNING_SECRET"] = secrets.token_urlsafe(48)
values["CSRF_SIGNING_SECRET"] = secrets.token_urlsafe(48)
for key, role, secret in (
    ("DATABASE_URL", "near_app", "DB_RUNTIME_PASSWORD"),
    ("MIGRATION_DATABASE_URL", "near_migrator", "DB_MIGRATION_PASSWORD"),
    ("OPERATOR_DATABASE_URL", "near_operator", "DB_OPERATOR_PASSWORD"),
):
    values[key] = (
        "postgresql+psycopg://" + role + ":" + values[secret]
        + "@localhost:5432/near_intelligence"
    )
lines = Path(".env.example").read_text().splitlines()
body = chr(10).join(
    line.split("=", 1)[0] + "=" + values[line.split("=", 1)[0]]
    if "=" in line and line.split("=", 1)[0] in values else line
    for line in lines
) + chr(10)
fd = os.open(".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as file:
    file.write(body)
print("Created private .env. Configure your own Supabase project next.")
PY
~~~

### 3. Configure your own Supabase project

Edit `.env` and replace the remaining authentication placeholders:

~~~dotenv
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=YOUR_BROWSER_SAFE_PUBLISHABLE_KEY
SUPABASE_JWT_ISSUER=https://YOUR_PROJECT.supabase.co/auth/v1
SUPABASE_JWKS_URL=https://YOUR_PROJECT.supabase.co/auth/v1/.well-known/jwks.json
SUPABASE_JWT_AUDIENCE=authenticated
SUPABASE_JWT_ALGORITHM=ES256
~~~

Use the asymmetric signing algorithm actually configured in your project
(ES256, RS256 or EdDSA). A browser-safe legacy `anon` key is also accepted;
never use a `service_role` or `sb_secret_` key.

Keep these local values:

~~~dotenv
APP_ENV=development
APP_ORIGIN=http://localhost:3000
AUTH_ALLOWED_REDIRECT_ORIGINS=http://localhost:3000
API_INTERNAL_URL=http://api:8000
~~~

In Supabase Authentication:

- Set **Site URL** to `http://localhost:3000`.
- Add `http://localhost:3000/auth/callback` to **Redirect URLs**.
- Enable **Anonymous Sign-Ins** to use the Demo entry. Its email field is only
  a display label, not proof of ownership of that email address.
- Configure email/password signup, confirmation and email delivery for
  persistent accounts.

Detailed provider setup and references:
[authentication configuration](docs/SELF_HOSTING.md#authentication).

### 4. Build, migrate and start

Run from the repository root. Selecting the file explicitly prevents a local
`docker-compose.override.yml` from changing this recipe.

~~~sh
docker compose --env-file .env -f docker-compose.yml build api web
docker compose --env-file .env -f docker-compose.yml up -d --wait db
docker compose --env-file .env -f docker-compose.yml run --rm -T migrate
docker compose --env-file .env -f docker-compose.yml up -d --wait api web
docker compose --env-file .env -f docker-compose.yml ps

curl --fail http://localhost:3000/health
curl --fail http://localhost:8000/health
~~~

Open **[localhost:3000](http://localhost:3000)**. The local web, API and database
ports bind to loopback. Supabase must be reachable for sign-in; there is no
product fake-auth mode.

### 5. Verify a document and an export

Open `/login`, sign in, create a document, write a paragraph, save and reopen
it. Queue a Markdown or PDF export, then run one worker pass:

~~~sh
docker compose --env-file .env -f docker-compose.yml run --rm -T worker
~~~

Return to the export dialog to download the result. The worker is not an
automatically running daemon in local mode.

Stop the local stack while keeping its volumes:

~~~sh
docker compose --env-file .env -f docker-compose.yml down
~~~

Changing a password in `.env` does not rotate a password in an existing
PostgreSQL volume. Avoid `down -v` unless you intentionally want to destroy
that local database. Port conflicts and other fixes are covered in
[troubleshooting](docs/SELF_HOSTING.md#troubleshooting).

## Deploy on your own server

Follow **[the complete self-hosting guide](docs/SELF_HOSTING.md)** for:

- Ubuntu, Docker, DNS and HTTPS setup;
- adapting the existing production profile to your own domain;
- private environment initialization and verified source bundles;
- persistent PostgreSQL and artifact storage;
- explicit migrations, export processing and systemd timers;
- backup, safe updates, rollback boundaries and troubleshooting.

Use the hardened production Compose profile for an internet-facing installation,
not the local Compose file above. The current production profile is tied to
`near-intelligence.me`; the guide explains the required four-file domain
adaptation before packaging. There is no `--domain` option.

## Research data and models

A clone includes application code, the public article, model specifications and
documentation. It does **not** include the production database, raw historical
archive, private documents or a pre-populated published model catalog.

A separate authorized data handoff must preserve source rights, exact values,
definition/dataset versions, model manifests and file hashes. See
[data provisioning](docs/SELF_HOSTING.md#research-data-and-models).
Collectors and automatic source refresh remain off by default.

## License

Original application source code, tooling, tests and associated developer
documentation use the [MIT License](LICENSE). Dependencies and bundled fonts
retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md).
Research datasets, provider outputs, third-party content, artwork and trademarks
are not relicensed by the code license. A source clone does not grant rights to
redistribute provider data or include the production research database.

## Architecture and development

| Layer | Technology |
| --- | --- |
| Web and same-origin auth gateway | Next.js, React, strict TypeScript |
| Research editor and charts | Tiptap, Apache ECharts |
| API and data processing | FastAPI, Pydantic, SQLAlchemy, Python |
| Storage and identity | PostgreSQL, Supabase Auth |
| Models and reproducibility | pandas, NumPy, SciPy, statsmodels; versioned manifests |
| Packaging | Docker Compose; frozen pnpm and uv locks |

For native development, use **Node 24**, **pnpm 12.16.1** and **Python 3.13**:

~~~sh
pnpm install --frozen-lockfile
uv sync --project apps/api --frozen
pnpm build

pnpm lint
pnpm typecheck
pnpm test
pnpm check:contracts
pnpm check:doc-links
pnpm test:api:unit
~~~

Start the native processes using
[the contributor setup](docs/JUDGE_SETUP.md#7-run--native-mode-alternative).
Database integration tests additionally require PostgreSQL 18 binaries:
[testing strategy](docs/TESTING_STRATEGY.md).

| Path | Contents |
| --- | --- |
| `apps/web` | Public website, workspace, editor and auth gateway |
| `apps/api` | Domain services, migrations, datasets, models and export worker |
| `packages/shared-types` | Generated OpenAPI TypeScript contracts |
| `deployment/vps` | Hardened Compose, HTTPS proxy and operator tooling |
| `research` | Research documentation/specifications; permitted local inputs stay separate |
| `docs` | Architecture, contracts, methodology, setup and verification |

[Documentation index](docs/INDEX.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Reproducibility](docs/REPRODUCIBILITY.md) · [Dependency pins](docs/DEPENDENCIES.md)

Contributor and agent execution follows [PLAN.md](PLAN.md), with task status and
acceptance in [TASKS.md](docs/TASKS.md). Deployment evidence and remaining
operational work are recorded in [the release report](docs/verification/ni-067.md).
