# Self-hosting NEAR Intelligence

This guide covers a new installation: local Docker, or a Linux VPS with your own
domain and Supabase project. It deploys the application; research datasets and
published model runs are a separate input.

For the running owner instance at near-intelligence.me, use
[the existing VPS runbook](VPS_DEPLOYMENT.md). Do not run first-install commands
over an existing database or replace its secrets.

## Choose a path

| Goal | Path |
| --- | --- |
| Try the editor, login and exports locally | [README Docker quickstart](../README.md#run-locally-with-docker) |
| Develop web/API code on the host | [Contributor native setup](JUDGE_SETUP.md#7-run--native-mode-alternative) |
| Publish an HTTPS installation on your own domain | Production steps below |
| Reproduce the deployed charts or empirical model | [Research data and models](#research-data-and-models), in addition to app deployment |

The repository currently requires read access. You need your own server,
domain and Supabase project; no owner credentials or production database are
included in a clone. The core application does not need an LLM, trading or wallet
key.

## Requirements

The production topology is Caddy → Next.js → FastAPI → PostgreSQL, with a private
persistent artifact volume and an explicit export worker. Only Caddy publishes
HTTP/HTTPS ports. Supabase provides authentication; application data lives in
your PostgreSQL instance.

- A Linux VPS with systemd, Git, Python **3.12+**, Docker Engine and the Compose
  plugin supporting `--wait` and JSON configuration.
- A domain you control; inbound TCP **80/443**, plus your SSH access.
- Outbound HTTPS for image/package downloads, Supabase authentication and TLS
  issuance. Application startup does not collect blockchain data.
- A small Ubuntu 24.04 x86_64 deployment was verified with **2 vCPU, 4 GB RAM and
  80 GB SSD**. **4 vCPU / 8 GB** gives more build/export headroom. Actual capacity
  depends on datasets, users and export concurrency; these are not load-test
  guarantees.

Install Docker Engine and the Compose plugin using the
[official Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/).
Verify `docker version`, `docker compose version` and `python3 --version`.
Host Node/pnpm and scientific Python packages are not required for image builds.

The commands below use a POSIX shell. Local Docker packaging was verified on
macOS ARM64 and production on Ubuntu x86_64. Windows-native setup is not verified;
a Linux shell/WSL environment is a separate platform check.

## Authentication

Create and configure **your own Supabase project** before starting the app.
Useful provider references:
[API keys](https://supabase.com/docs/guides/getting-started/api-keys),
[redirect URLs](https://supabase.com/docs/guides/auth/redirect-urls),
[signing keys](https://supabase.com/docs/guides/auth/signing-keys).

| Application setting | Where the value comes from |
| --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL` | Project HTTPS URL, without a trailing slash |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Browser-safe publishable key, or legacy `anon` key |
| `SUPABASE_JWT_ISSUER` | Project URL + `/auth/v1` |
| `SUPABASE_JWKS_URL` | Project URL + `/auth/v1/.well-known/jwks.json` |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` |
| `SUPABASE_JWT_ALGORITHM` | The actual asymmetric signing algorithm: ES256, RS256 or EdDSA |

A `service_role`/`sb_secret_` key is not needed. A legacy HS256 project
configuration does not satisfy this application's asymmetric verification
contract.

In Authentication → URL Configuration, set:

| Mode | Site URL | Redirect URL |
| --- | --- | --- |
| Local | `http://localhost:3000` | `http://localhost:3000/auth/callback` |
| Your VPS | `https://research.example.com` | `https://research.example.com/auth/callback` |

Replace the example hostname with your real domain. Match the app's canonical
origin and use HTTPS in production. If a project intentionally serves both local
and production development, explicitly allowlist the needed callbacks.

Enable **Anonymous Sign-Ins** if you want the Demo entry. The demo email is a
display label; it is not verified email authentication. Configure email/password,
confirmation and SMTP/delivery for durable accounts, and test a delivered signup
or recovery link yourself. A successful demo session does not test email delivery.

Cookie and CSRF signing secrets are generated locally by the application
configuration step. They belong to the web gateway. In the hardened production
profile, FastAPI receives only the four JWT-provider settings, its runtime DB
credential and artifact configuration.
The local development Compose file instead passes the complete local env file;
keep it local and use the hardened profile for production.

## Production: prepare the source

Do this in an authorized checkout on your workstation or build machine. Use a
reviewed release containing the NI-067 auth fixes, not an older checkout.

~~~sh
git clone https://github.com/ILYUTKICK/near-intelligence.git
cd near-intelligence
git log -1 --oneline
~~~

### Adapt the existing domain profile

**The current production helper is tied to near-intelligence.me.** It is not an
arbitrary-domain installer. Editing only `.env.vps` will fail validation.

Before making a source bundle, adapt the exact hostname in four files:

| File | Required change |
| --- | --- |
| `deployment/vps/env.py` | `ORIGIN` must be your exact HTTPS origin |
| `deployment/vps/.env.example` | `APP_ORIGIN` and `AUTH_ALLOWED_REDIRECT_ORIGINS` must use that origin |
| `deployment/vps/Caddyfile` | Replace the site's hostname |
| `deployment/vps/tests/test_env.py` | Keep the literal Caddy-host assertion aligned with that profile |

This bounded source adaptation keeps validation active. There is no `--domain`
flag. The following snippet applies those four replacements; change the example
argument first. It does not contact DNS or Supabase:

~~~sh
python3 - research.example.com <<'PY'
from pathlib import Path
import sys

domain = sys.argv[1]
labels = domain.split(".")
valid = (
    domain == domain.lower()
    and len(labels) >= 2
    and len(domain) <= 253
    and not all(part.isdigit() for part in labels)
    and all(
        part and len(part) <= 63
        and part[0].isalnum() and part[-1].isalnum()
        and all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in part)
        for part in labels
    )
)
if not valid:
    raise SystemExit("Use a lowercase ASCII hostname, without scheme, port or path.")
for name in (
    "deployment/vps/env.py",
    "deployment/vps/.env.example",
    "deployment/vps/Caddyfile",
    "deployment/vps/tests/test_env.py",
):
    path = Path(name)
    text = path.read_text()
    if "near-intelligence.me" not in text:
        raise SystemExit("Expected original profile not found: " + name)
    path.write_text(text.replace("near-intelligence.me", domain))
print("Domain profile updated. Review the diff and run the checks.")
PY

git diff -- deployment/vps
python3 -m unittest discover -s deployment/vps/tests -p 'test_*.py'
~~~

Use the apex domain or a subdomain as one canonical origin. The profile does not
automatically configure `www` or arbitrary host aliases. No application
financial definitions or observations need to change for a domain adaptation.

### Create the verified source bundle

Choose an unused output filename; the bundler refuses to overwrite an archive.

~~~sh
python3 deployment/vps/bundle.py --output /tmp/near-source.tar.gz
sha256sum /tmp/near-source.tar.gz
~~~

On macOS, use `shasum -a 256 /tmp/near-source.tar.gz` for the checksum.
Keep the checksum for comparison on the server.

The bundle contains a per-file `SOURCE_MANIFEST.json` and a unique release tag.
It includes the domain profile you just reviewed. It excludes secrets, developer
overrides, database state, private exports and the raw research archive.
Do not change manifest-bound source files after extraction.

## Production: prepare the server and DNS

Use a **new server** or a deliberately isolated new installation. The examples
assume an SSH admin/root shell, the operator account `near`, and default paths.
A sudo administrator can enter an admin shell with `sudo -i`.

First prepare private upload space in your SSH account:

~~~sh
ssh YOUR_SSH_USER@YOUR_SERVER 'mkdir -p ~/near-incoming && chmod 700 ~/near-incoming'
scp /tmp/near-source.tar.gz YOUR_SSH_USER@YOUR_SERVER:near-incoming/
~~~

Replace the two SSH placeholders; use your normal key/SSH alias. On the server,
compare the archive checksum with the workstation value. If you entered a root
shell from another account, use that original account's upload path below.

~~~sh
sha256sum /path/to/near-incoming/near-source.tar.gz

if ! id near >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash near
fi
usermod -aG docker near
install -d -o near -g near -m 0750 /opt/near-releases
install -d -o near -g near -m 0700 /var/backups/near-intelligence
~~~

Docker group membership is administrative access. `near` is the host operator,
not a public website account.

In your domain's DNS:

1. Set the chosen hostname's A record to the VPS IPv4.
2. Remove conflicting old A records for that same hostname.
3. Add AAAA only if the VPS actually serves IPv6.
4. Leave unrelated mail/TXT records intact.

Allow TCP 80/443 in the provider and host firewall while preserving SSH access.
Do not expose PostgreSQL 5432, API 8000 or web 3000. See Docker's
[firewall behavior](https://docs.docker.com/engine/network/packet-filtering-firewalls/).

## Production: configure and launch

### Extract into a new release directory

Run in the server's admin shell. Replace the archive path and choose a new
candidate directory; never extract over a running release.

~~~sh
set -eu
release_dir=/opt/near-releases/first-release
test ! -e "$release_dir"
install -d -o near -g near -m 0750 "$release_dir"
tar -xzf /path/to/near-incoming/near-source.tar.gz -C "$release_dir" --strip-components=1
chown -R near:near "$release_dir"
cd "$release_dir"

runuser -u near -- python3 deployment/vps/verify_source.py
runuser -u near -- python3 -m unittest discover -s deployment/vps/tests -p 'test_*.py'
release_tag=$(python3 deployment/vps/verify_source.py --release-tag)
runuser -u near -- python3 deployment/vps/env.py init --env-file .env.vps --release-tag "$release_tag"
~~~

The initializer creates a regular file with permissions `0600`, four independent 64-character
hex DB secrets and independent URL-safe cookie/CSRF secrets. It refuses to
overwrite an existing file. Preserve them across image updates.

Edit `.env.vps` on the server as the operator or admin. Set your Supabase values
from [Authentication](#authentication); keep the selected canonical origins and
generated release tag. Do not copy the owner instance's secrets. The file format
is plain `KEY=value`: no quotes, shell interpolation, additional variables or
trailing slash on the Supabase origin.

### Validate, build, migrate, start

~~~sh
runuser -u near -- python3 deployment/vps/env.py validate --env-file .env.vps
runuser -u near -- python3 deployment/vps/env.py check-compose --env-file .env.vps
runuser -u near -- python3 deployment/vps/ops.py validate
runuser -u near -- python3 deployment/vps/ops.py build
runuser -u near -- python3 deployment/vps/ops.py db
runuser -u near -- python3 deployment/vps/ops.py migrate
runuser -u near -- python3 deployment/vps/ops.py up
runuser -u near -- python3 deployment/vps/ops.py status
runuser -u near -- python3 deployment/vps/ops.py check
~~~

Caddy obtains TLS for the configured hostname after DNS reaches the VPS.
Health endpoints validate configuration; `ops.py check` also verifies migration
revision, runtime grants, DB connectivity, artifact access and internal routes.
Neither check proves that a research dataset/model has been provisioned.

The helper intentionally refuses remote rollout if NI-079 is not DONE for the
candidate. Use an accepted release and recheck your changes; do not edit a task
status or pass a rehearsal flag to bypass release acceptance.

When invoking these commands in a shell script streamed over SSH, redirect their
stdin from `/dev/null` unless you intentionally supply input. A Docker one-shot
container can otherwise consume the rest of the streamed script.

### Verify the real HTTPS workflow

Replace the hostname in these probes:

~~~sh
curl --fail https://research.example.com/health
curl --head http://research.example.com/
~~~

Check the actual browser workflow:

1. Overview → Blog → article → Data. Empty data states are expected before import.
2. Sign in, create a document, save, reload and reopen it.
3. Export that saved revision, process the worker and download ZIP/PDF.
4. Use a second user and confirm the first user's private document/download is denied.
5. Verify confirmation/recovery links and final-domain callbacks when email is enabled.

The callback must return to your HTTPS domain, not localhost. Private cookies
must be Secure/HttpOnly/SameSite and private responses must not be publicly cached.

## Exports and scheduled operations

From the active release directory, process one bounded batch:

~~~sh
runuser -u near -- python3 deployment/vps/ops.py worker
runuser -u near -- python3 deployment/vps/ops.py sweep
~~~

For the supplied systemd units, point the canonical path at your verified
candidate. The following is for the **first installation** only:

~~~sh
release_dir=$(pwd -P)
test ! -e /opt/near-intelligence
ln -s "$release_dir" /opt/near-intelligence
install -m 0644 deployment/vps/systemd/near-*.service deployment/vps/systemd/near-*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now near-exports.timer near-export-sweep.timer near-backup.timer
systemctl list-timers 'near-*'
~~~

The units assume operator `near`, canonical path `/opt/near-intelligence` and
backup directory `/var/backups/near-intelligence`. Adapt them explicitly if you
choose different paths. The timers process exports every minute, sweep expired
export bytes hourly and make a local nightly backup around 03:15 UTC. They do not
start blockchain refresh, model fitting or legacy collectors.

All operator commands use the same user/project lock. Do not run a separate
writer or enable a collector outside that lock while making a coherent backup.

## Research data and models

A clean install can run authentication, private writing, revisions and prose
exports. It cannot reproduce the public instance's charts or published model
merely by cloning code.

To provision research, obtain a permitted, versioned handoff containing the
necessary source metadata, definitions, approved observations, active pointers,
artifact bytes/hashes and published model bundle. Exclude unrelated users,
private documents and credentials. A useful handoff records:

- source rights/status and actual observation/retrieval dates;
- exact metric and dataset definition/version IDs;
- decimal-string observations, units, bounds and missing-value reasons;
- manifest/artifact SHA-256 and byte sizes;
- model specification, dataset/code/lock/config hashes and interpretation limits.

The implemented operator modules are:

| Operation | Existing entry point |
| --- | --- |
| Import a permitted saved archive | `python -m near_api.ingestion.archive` |
| Compute prepared manifests offline | `python -m near_api.metrics build` |
| Stage, validate, publish datasets | `python -m near_api.datasets` |
| Fit, diagnose, verify or publish a model | `python -m near_api.research` |

Use their `--help`, [data pipeline](DATA_PIPELINE.md) and
[reproduction contracts](REPRODUCIBILITY.md) for required bindings and permissions.
These run with the appropriate operator role, not a browser request. There is
no universal `seed-demo-data` command or bundled production-data download.
Model fitting/reproduction runs from a source checkout with the versioned
`research/models` modules and separately supplied inputs; the runtime image
intentionally excludes the `research/` tree.

Versioned registries are registered through the existing
`register_definitions` and `register_charts` Python functions in an operator
transaction, after source provisioning. They are not a standalone seed CLI.
Register charts from the current code rather than copying retired chart rows
from an old database.

Preserve DB/artifact references together. Importing only observations or copying
the whole raw archive into a public folder is not a complete handoff. Keep
artifacts on the private volume; HTTP routes enforce permitted access.
Without approved inputs the product must keep its unavailable states.

## Persistence, backup and updates

The production Compose uses persistent volumes for PostgreSQL, artifacts and
Caddy state. Do not rename the Compose project casually: that selects different
volume names. `docker compose down -v` destroys data.

Create a coherent backup from the active directory, using an unused destination:

~~~sh
runuser -u near -- python3 deployment/vps/ops.py backup /var/backups/near-intelligence/manual-before-update
~~~

This briefly stops API/web, then restores their previous running state.
It hashes the DB dump and artifact archive. Credentials/env and TLS keys are
not included in that bundle; preserve them separately in a secret manager or
other protected backup. Nightly copies on the VPS are not offsite protection.
Configure encrypted external copies, retention, alerts and restore drills for
a production service.

The restore helper supports a **new isolated rehearsal project**, not in-place
production restore. Follow [the recovery runbook](VPS_DEPLOYMENT.md#резервная-копия-и-восстановление);
do not remove its existing-volume guards.

For an update:

1. Stop the supplied timers and record the current source/image release tag.
2. Take a coherent backup and verify the migration's compatibility.
3. Prepare a new reviewed bundle in a new release directory.
4. Reuse the existing private secrets; change only the new source release tag and
   deliberately reviewed configuration. Keep the same Compose project/volumes.
5. Validate, build, explicitly migrate, start and re-run the HTTPS workflow.
6. Switch the canonical release symlink and resume the timers.

Image rollback needs known schema compatibility and an existing verified image
tag; it never downgrades the DB or rewrites data/model versions. Exact operator
commands and rollback constraints are in [VPS deployment](VPS_DEPLOYMENT.md).

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Repository clone is denied | Obtain read access to the private repository and authenticate Git on your workstation. Do not copy a personal token into README or the server image. |
| `/health` returns 503 | Replace required placeholders; compare the canonical URLs and configured Supabase algorithm. A green health response alone does not prove data/import readiness. |
| Demo entry fails | Enable anonymous sign-ins in your own Supabase project; check issuer/JWKS/algorithm and provider reachability. There is no production synthetic-auth toggle. |
| Callback points to localhost | Use a release containing NI-067, set APP_ORIGIN and Supabase URL Configuration to your final origin, and rebuild the web image. |
| Production validator rejects my domain | Complete all four source-profile edits before bundling; changing only `.env.vps` is insufficient. |
| Build refuses a missing source manifest | Make and extract a bundle with `bundle.py`; a plain clone is not a verified build directory for `ops.py`. |
| Source hash mismatch | Rebuild the bundle after legitimate source changes; do not edit an extracted manifest-bound source or bypass verification. |
| Data or Models is empty | Provision the separately permitted research data/model. Do not treat a fresh clone as a populated scientific database. |
| Export stays queued | Run a worker pass or enable its timer; check a typed failure state rather than continually re-queuing. |
| Local ports are occupied | Set WEB_HOST_PORT/API_HOST_PORT/DB_PORT. Align APP_ORIGIN, redirect allowlist and Supabase callbacks; update localhost DB URLs when using native processes. |
| DB rejects a changed password | Editing env does not change existing database-role passwords. Restore the correct secret or perform an explicit coordinated role rotation. |
| Native web `start` has no build | Run frozen installs and `pnpm build` before `pnpm --filter web start`, or use the dev command for development. |

Use bounded logs in a private operator terminal. Never paste `.env`, resolved
`docker compose config`, full container inspection, JWTs or DB URLs into a
public issue. Current verification evidence:
[local release](verification/ni-079/README.md),
[packaging](JUDGE_SETUP.md#10-verification-record-2026-11-10-ni-066-dispatch-macos-arm64-docker-2992),
[actual VPS release](verification/ni-067.md).
