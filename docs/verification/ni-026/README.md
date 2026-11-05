# NI-026 capability verification

Review date 6 November 2026. Role B, BkycnocTbI, Codex session
01a1a2c9-f42d-7422-8e3e-755c9e33551b. Base main cfdd914.

## Evidence and operational status

The published checkout contains application source and Markdown research findings.
It does not contain the original archive manifests, JSON/CSV/SQL or collectors.
The historical coverage numbers in SOURCE_VERIFICATION.md describe the original
machine's earlier inspection. They have not been reproduced from this checkout.

Official documentation was read over HTTP. No operational provider probe, cloud
SQL, paid request, historical backfill or collection restart was executed.

| Source | Evidence inspected in this session | Operational gate |
| --- | --- | --- |
| SRC-NEAR-RPC | [Official directory](https://docs.near.org/api/rpc/providers) lists https://free.rpc.fastnear.com as public/free, with unpublished numeric quota and paid-only archival access. [Block method](https://docs.near.org/api/rpc/block-chunk) documents finality=final. | OQ-03. Exact candidate is POST https://free.rpc.fastnear.com with method block and finality final. No approved operator cap or usage/redistribution decision is available. |
| SRC-BQ | [Public-dataset execution model](https://docs.cloud.google.com/bigquery/public-data) is linked by the source register. Local historical exports and approved project budget are absent. | OQ-03. No SQL execution. Dataset-specific rights and partition completeness still require evidence. |
| SRC-INTENTS | [Documentation index](https://docs.near-intents.org/llms.txt) is reachable. The direct Markdown Explorer page could not be read through the browsing parser. No current endpoint or schema is inferred from this failure. | OQ-01/OQ-03/OQ-08. Account, quota, exact Explorer schema, pagination and permissible use still unverified. |
| SRC-LLAMA | [Pricing/access](https://docs.llama.fi/pro-api) distinguishes open fees/revenue/prices from subscription API quotas. [Current adapter](https://github.com/DefiLlama/dimension-adapters/blob/master/fees/near-intents/index.ts) sources gross fees from Dune and labels selected wallet sweeps as revenue. | OQ-01/OQ-03/OQ-11. Source lineage is not independent revenue attribution. No free-endpoint numerical quota or redistribution entitlement inferred. |
| SRC-DUNE | [Official rate limits](https://docs.dune.com/api-reference/overview/rate-limits) say free access is view-only and API use requires a trial or paid plan. Endpoint limits differ. | OQ-01/OQ-03/OQ-11. No account, trial, credits or execution approved. |
| SRC-PRICE | [Historical range documentation](https://docs.coingecko.com/reference/coins-id-market-chart-range) describes an authenticated Pro endpoint and tier-dependent history/granularity. | OQ-03. No paid account, key, matching free-tier scope or redistribution approval supplied. |
| SRC-DASHBOARD / SRC-FASTNEAR / SRC-NEARBLOCKS / SRC-GOV | Existing register reviewed; no historical payloads inspected locally and no fresh operational verification claimed. | Existing OQ-01/OQ-03/OQ-10/OQ-11 apply as recorded per source. |

The executable registry keeps all ten sources disabled, rights pending, actual
coverage unknown and response-schema hashes empty. Public reachability alone is
not an approval for scheduled collection or raw-data redistribution.

## Implemented boundary

`apps/api/src/near_api/ingestion/capabilities/` defines immutable versioned evidence
records and a single-use finalized-header probe. It rejects unknown fields,
credential-bearing URLs, inconsistent coverage and unsupported endpoint changes.
Before any network action it requires verified source access, no open blockers,
rights/quota evidence, a matching unexpired explicit zero-cost approval, a nonzero
remaining local budget and an allowlisted source. Defaults deny all requests.

Root and nested research STOP_PUBLIC_COLLECTION files, plus explicit operator
pause paths, take precedence. No live API route or scheduler exposes this probe.
It requests only one finalized header, limits response bytes and each HTTP I/O
timeout (not a process-wide wall-clock deadline), rejects encoded payloads,
redirects and consumes its invocation even on failure. Returned selected fields
exclude provider messages/headers and preserve raw supply as a decimal string.
Concurrent reuse of the same instance permits at most one request.

The supplied daily usage is an operator input, not a persisted accounting ledger.
Cross-process daily accounting, locks, retries, publication and scheduling belong
to NI-030 and remain unavailable. Synthetic tests authorize an isolated mock
transport only and do not establish real entitlement or endpoint health.

## Commands

From the repository root after installing the frozen Python dependencies:

```sh
# PowerShell
$env:PYTHONPATH = 'apps/api/src'
apps/api/.venv/Scripts/python.exe -m unittest discover -s apps/api/tests -v

# POSIX
PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m unittest discover -s apps/api/tests -v
```

## Unblocking NI-026

Backlog status: BLOCKED. The 11 local capability/guard tests passed on Windows
11 / CPython 3.13.15 using the frozen requirements; `git diff --check` passed.
These checks validate software guards, not operational provider access.

For a source, supply a reviewed evidence record for the intended endpoint,
auth/secret reference, no-cost or bounded budget, actual account limits,
approved purpose, usage and redistribution decisions, and a short-lived one-off
probe approval with exact request/byte/time caps. Separately resolve legacy pause
markers with their owner. A successful sanitized probe then records observation
time, source cutoff, schema and byte hashes. Until then NI-026 remains BLOCKED.

NI-027 additionally needs an authorized local/offline bundle with exact relative
paths and SHA-256 checksums generated on the archive-owning machine. At minimum
the documented entry inputs include
`research/near-longitudinal/data/flows_90d_raw.json`,
`research/near-dollar/data/coingecko.json`, their actual manifests and the original
analysis scripts listed in docs/REPRODUCIBILITY.md, plus each script's transitive
saved inputs. The exact closed file list and real hashes must be exported from
that machine; none can be calculated from the Markdown findings in this clone.
Raw research remains outside GitHub under the existing sharing policy.
