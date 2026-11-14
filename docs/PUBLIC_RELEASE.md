# Public repository release

This guide prepares the existing repository for public hackathon review. It does
not change GitHub visibility or submit an application. Task status remains in
[TASKS.md](TASKS.md), NI-098.

## Hackathon requirements checked

The official [HACKATHON.md](https://nearhackathon.com/HACKATHON.md), checked
14 November 2026 UTC, says:

- Q-014 requires a `LICENSE` file, accepts any license and explicitly permits MIT.
  The repository must remain public through judging.
- Q-013 says the team retains its code rights; organizers receive non-exclusive
  promotional rights to the project name, screenshots, video and repository link.
- A submission needs a public repository and a public demo post on X. The
  published deadline is 14 November 2026, 23:59 UTC (15 November, 02:59 Moscow).
- Q-012/Q-017 emphasize a reproducible README and verification that the product
  runs as described. A hosted demo should stay available through 18 November,
  ideally 25 November. This is distinct from the application deadline.

No application, demo post or visibility change was made by this documentation
work. Re-check the live rules before submitting; do not invent an extension or
claim that an application has been accepted.

## License and distributed content

The owner approved MIT for original project code on 15 November 2026 Moscow time.
See [LICENSE](../LICENSE) and [third-party notices](../THIRD_PARTY_NOTICES.md).
Font licenses and dependency licenses remain in force. This approval does not
relicense provider data, third-party captures, logos, artwork or the ignored
research archive.

A clone contains the application, tests, configuration, original research
Markdown, deterministic model code/specifications and design documentation.
It does not contain production database state, private user documents, secrets,
raw provider archives or a ready-made copy of the deployed model/data catalog.
Use [self-hosting](SELF_HOSTING.md) for a clean installation and the explicit
rights-preserving data handoff boundary.

## Bounded content review

An offline review on 14 November 2026 UTC inspected the tracked current tree and
history reachable from all 66 fetched `origin` branches (no remote tags existed).
The remote heads were compared with `git ls-remote --heads --tags origin`.
The snapshot included README branch head `de9ce66` and main `3ec3137`.

- 737 commits and 2,782 distinct blobs were enumerated with `git rev-list --objects`.
- Approximately 160.6 MB of text blobs and commit metadata were scanned for
  private-key headers, common GitHub/AWS/Google/Stripe/Slack/provider-secret
  prefixes, literal JWTs and credential-bearing database URLs.
- 40 pattern hits were reviewed: 34 URLs were explicit password placeholders,
  substitutions, abbreviated documentation examples or synthetic redaction-test
  inputs; 6 private-key markers were strings in the security scanner tests.
  No actual credential was identified by these checks.
- No real `.env`, SSH key, private-key file or database file path appeared in
  that history inventory. The 7 research JSON paths were preregistered model
  specifications/configurations, not raw observation datasets. No raw research
  CSV, SQL, HTML/JS capture or compressed archive path was found in that scope.
- 92 binary blobs were excluded from text-content scanning. A separate current
  asset inventory identified bundled OFL fonts, generated-artwork provenance
  and synthetic QA fixtures. It was not a complete review of screenshot pixels.

This is a bounded review, not proof that every sensitive value is absent. It does
not cover remote-only pull-request refs, GitHub issue/PR discussions, Actions
logs/artifacts, releases, LFS payloads, untracked files or ignored local archives.
Current branch additions were checked separately before publication in the PR.

## Remaining disclosure choices

Tracked operational records include the live server address, provider/project
identifiers, deployment/backup locations and personal workstation paths. Git
commit metadata also exposes contributor identities. These are not passwords,
but they will become public along with existing history. Removing only the latest
file contents would not remove earlier versions.

The current font binaries retain their bundled license texts. New Overview
artwork has generation records. Some older product-plan mockups have no separate
asset-rights statement; no new MIT permission for those assets is asserted.
Provider redistribution remains unresolved where recorded in
[SOURCE_VERIFICATION.md](SOURCE_VERIFICATION.md). Keep excluded archives local.

## Owner release procedure

1. Review and merge the README/license PR after its required checks pass. Only
   the owner merges PRs under the project's current collaboration instructions.
2. Review the disclosure choices above and GitHub-only surfaces, especially
   historical Actions logs/artifacts and discussion attachments. Resolve any
   actual secret finding by rotation and an agreed cleanup; do not force-push or
   delete evidence automatically.
3. When ready, the owner changes repository Settings → General → Danger Zone →
   Change repository visibility → Public and completes GitHub's confirmation.
   Agents need an explicit instruction for this step.
4. In a signed-out browser, verify the repository, README, LICENSE and source are
   accessible. Clone into a fresh directory and follow README with your own
   Supabase configuration. The public website alone does not prove public Git
   access or a successful clean install.
5. Keep the repository public through judging. Supply the repository and demo
   links through the official submission flow with the owner's confirmed details.
   This guide is not a submission receipt.

GitHub documents that changing to public exposes code and Actions history/logs
and allows public forks. Review the current
[visibility-change documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)
before confirming. Making the repository private later does not recall copies
already downloaded or forked.
