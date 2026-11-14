# Repository and collaboration setup

Setup date:5 November 2026. Repository:[ILYUTKICK/near-intelligence](https://github.com/ILYUTKICK/near-intelligence), created private and initially pushed on `main`. Verified collaborator account:[BkycnocTbI](https://github.com/BkycnocTbI). Invitation ID341761870 was accepted during setup. GitHub collaborator-permission API verified **active write access** for BkycnocTbI. Membership can change later; re-check current permissions when investigating access issues.

## Current public-release preparation

The owner plans a public hackathon release and approved MIT for original code on15 November2026 Moscow time. [Public release preparation](PUBLIC_RELEASE.md) records the checked rules, content review, remaining disclosures and owner-only visibility procedure. Historical private setup below does not forbid that requested preparation or imply the visibility change has already happened. Raw-data exclusions remain in force.

## Explicit sharing scope

The user chose **documentation and mockups only** for the archive upload and subsequently requested Python dependency manifests for contributors/judges. On 5 November 2026 the user (participant A, ILYUTKICK) additionally authorized implementing role-A tasks and publishing **new application source code, models, tests, configuration and documentation** in this private repository as NI-tasks complete, using feature branches and pull requests into main without force-push or unrequested merges. Include root instructions/plans, docs/*.md, research Markdown findings/READMEs and product-plan Markdown/SVG/PNG designs/prompts. Include .env.example, Git configuration templates, the explicitly requested .python-version and requirements.txt (requirements.in was removed when NI-002 moved declarations into apps/api/pyproject.toml), and the NI-001 workspace tooling manifests (package.json, pnpm-workspace.yaml, .node-version) as onboarding metadata; no real credentials.

Raw research JSON/CSV/TXT/SQL, manifests containing raw data metadata, collection/calculation scripts, captured third-party JS/HTML and process state remain on the original machine and are ignored. The original research archive is roughly149 MB; it is not authorized for GitHub upload. STOP_PUBLIC_COLLECTION stays on disk, and collectors remain stopped.

The unpublished initial full-project commit was replaced before any push. The subsequently authorized application/model source and documentation history may be sent to GitHub; raw local research inputs remain excluded. Never use force-add, push--mirror or broad data uploads to bypass the sharing boundary. Future source-data sharing requires explicit authorization and an agreed channel; being a collaborator does not itself authorize publishing ignored data.

A fresh clone therefore cannot execute legacy offline scripts or open every linked data artifact. Markdown findings remain available for context. Before a data/research task, confirm the actual input bundle and hashes or record the missing-data blocker; do not download paid/bulk data, fabricate inputs or treat a missing archive as zero.

## Clone URL

```sh
git clone https://github.com/ILYUTKICK/near-intelligence.git
cd near-intelligence
```

While the repository is private, an invited account must accept at [repository invitations](https://github.com/ILYUTKICK/near-intelligence/invitations) and authenticate Git with its own credentials. HTTPS cloning a private repository requires GitHub authentication; no shared password/token is stored in this repository.

## Contributor workflow

1. Accept the invitation in the BkycnocTbI account. A pending invitation is not yet accepted access.
2. Clone the verified remote URL in a separate local directory. Configure your own Git author name/email; never copy another contributor's credentials.
3. Read [AGENTS.md](../AGENTS.md), [PLAN.md](../PLAN.md), [task backlog](TASKS.md), [team assignments](TEAM_PLAN.md) and task specifications.
4. Select an available assigned NI-task, coordinate its claim/status, and create a short branch `feat/ni-XXX-description`. Do not overwrite another active claim or edit a generated API client manually.
5. Run appropriate verification and open a pull request into main. The other participant reviews it; merge only after the task's full acceptance checks pass.

The original setup record predates implementation. Use [README](../README.md), [self-hosting](SELF_HOSTING.md) and [DEPENDENCIES.md](DEPENDENCIES.md) for current application commands and pinned tooling.

## Access and safeguards

Originally private visibility with normal collaborator write access, not administrator access. Public-release preparation now follows the owner request above; visibility is a separate owner action. .gitignore excludes ignored research inputs, credentials, caches, environments, logs and private exports. .gitattributes preserves tracked research/design bytes without newline conversion. A bounded local scan initially inspected431 text files and found no obvious token/private-key patterns; this is not a guarantee of absence of every sensitive value.

Branch protection/required CI must be configured and verified separately when repository plan support and actual CI exist; this setup does not claim those protections are enforced.
