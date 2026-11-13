# NI-083 backend — saved history and exact descriptive calculations

Verified locally on 14 November 2026 (Europe/Moscow). This is descriptive
research delivery, not a fitted long-run investment model. No provider request,
cloud job, collector restart or Git mutation was performed for this handoff.

## Implemented boundary

- Offline `near_api.research.archive` reads four explicitly supplied saved files,
  checks three source-file SHA-256 values against the supplied manifest, validates
  protocol/date/value shape and prepares a separate NI-028 manifest. It never
  edits the source archive; output inside the archive is refused.
- Canonical `intents-volume` and `gross-fees` append v2, max 730 days. V1 remains
  366 days with the same UUIDs/bindings. Resolution enforces the pinned definition
  maximum in the shared service as well as the public route.
- `GET /api/research/history` reads approved database artifacts only. Provider
  views share one dataset version. The purchases view has its own coverage/pin.
  Original cohort/model definitions and archived outputs remain intact.
- `ResearchPeriodSummary` exposes observed subtotals and coverage separately from
  matched-day subtotals. Weighted effective fee bps uses the matched intersection;
  zero/missing/zero-denominator rules are explicit. Calendar edge buckets keep
  full bounds and stay partial. No monthly revenue is spread into daily rows.

## Actual saved-input reconciliation

The candidate provider manifest contains **2,443 observed source-qualified values**
and **333 explicit missing rows** (2,776 total records):
694 DefiLlama volume, 543 DefiLlama fee, 665 Dashboard volume, 541 Dashboard fee.
The union is `[2024-12-10, 2026-11-04)` UTC. DefiLlama has 543 matched volume/fee
dates and nine source-valued fee zeros. Dashboard has 540 same-provider matched
dates; its gaps are preserved. No cross-source equality or independence is claimed.

| Saved DefiLlama descriptive measure | Exact computed value |
| --- | --- |
| Volume, all 694 observed days | USD 36,386,550,029 |
| Gross fees, 543 observed days | USD 58,276,743.98 |
| Volume on the 543 matching fee dates | USD 36,279,586,984 |
| Weighted matched effective gross fee rate | 16.063232474421820722235595778854 bps |

The full volume total and the fee total cover different periods; the fee-rate
calculation uses the matched volume total, not the full 694-day total. Latest
calendar-closed daily records stop on 3 November; later provider revisions remain
possible. Retrieval time is taken from the supplied manifest, not invented from
the current runtime clock. Files/adapter scope and source disagreements remain
qualified as in [NI-082](../ni-082/README.md).

The existing 90-day emitter was rerun offline from unchanged saved inputs. It
produced 1,710 daily metric records and 34 snapshot records. Reconciliation:

| Recorded cohort measure | Recomputed value |
| --- | --- |
| Successful conversions | 54,991 |
| Observed acquired NEAR | 524480.127692882832410490617319 |
| Matched treasury payouts NEAR | 1405659.135989071036891726256814 |
| Acquired NEAR, first 30 days | 244845.695435056735045138444977 |
| Acquired NEAR, second 30 days | 165809.437170331743839294092522 |
| Acquired NEAR, third 30 days | 113824.995087494353526058079820 |

These reconcile CL-001/002/003. Approximate USD windows remain approximately
437374.277086 / 557914.137141 / 547025.912421 on the saved daily-start price basis,
consistent with CL-004. Purchases and payouts remain separate stages and are not
added together. Neither cohort coverage nor its narrow fee provenance is extended.

## Inputs and integrity

Source-relative SHA-256 (same snapshots audited in NI-082):

| Input | SHA-256 |
| --- | --- |
| `near-dollar/data/llama_volume.json` | `e21e60e9f91adf49b672c6c799a9efded7d32abae4886450bd502bc22fdc293d` |
| `near-dollar/data/llama_fees.json` | `91090ea36c4378c961ada84a7621de0f31caa79970ef9443801c18f3bc48521b` |
| `near-dollar/data/dashboard_efficiency_record.json` | `6d463c602dc4020f9fcf6dafbaad44de0dbb03dc16e84c50cbf7ea72535c433f` |
| `near-dollar/manifest.json` | `8b46305a7479f6fc68ab19bdfa9dbf64795a79063d7e25e43c640f6db2bcb840` |

Raw data, generated manifests, calculation summaries and process state stay
local/ignored. A fresh clone lacks the saved archive; use an authorized file/hash
handoff, never silently fetch replacements.

## Commands and verification

```sh
# Read-only preparation; output is a local ignored artifact, not publication.
uv run --project apps/api python -m near_api.research.archive \
  --archive-root /path/to/research --output .local/ni083/history-manifest.json
# Use existing NI-028 stage/publish CLI against an explicitly selected local DB.
# No preparation or publication occurs automatically at API startup.
uv run --project apps/api python scripts/run-db-tests.py \
  --pg-bin /path/to/postgresql-18/bin --suite history
uv run --project apps/api python -m unittest discover \
  -s apps/api/tests -p test_contracts.py -v
node packages/shared-types/scripts/generate.mjs --check
```

Focused isolated PostgreSQL 18.6 history suite: **82/82 passed**, no skips
(registry 30, delivery 41, exact-history 11). Includes real migrations, append-only
registration, 400-day v2 view versus v1 rejection, one approved provider dataset,
exact weighted rate, partial periods, source validation and non-approved 404.
Contract suite: **7/7 passed**. Original-source preparation and 90-day reconciliation
ran offline successfully. The first DB pass found one obsolete test expecting
730 days to fail the structural cap; it was updated to 731 and the complete
focused suite passed on rerun. Browser/UI acceptance is the coordinator's handoff.

Opt-in production harness mode:

```sh
NI_RESEARCH_ARCHIVE_ROOT=/path/to/research \
uv run --project apps/api python apps/web/e2e/harness/stack.py \
  --pg-bin /path/to/postgresql-18/bin --handoff .local/ni083-preview/handoff.json
```

The harness publishes original daily cohort plus long provider history only to
its disposable local DB. Default regression mode stays visibly synthetic. Auth
transport stays synthetic while the configured API/JWT/ownership/data path is real.
This is not deployment, provider authorization, model publication or NI-079 closure.


## Real-archive service rehearsal

The coordinator's final production build was bootstrapped with the explicit
saved-archive opt-in. Real NI-028 staging/publication succeeded for 1,710 daily
cohort records and 2,776 long-history records in the disposable local DB. Public
HTTP checks passed for 694 volume days, 543 fee/matched days, nine source-valued
zeros, the exact weighted rate above, one shared provider dataset pin, the separate
90-day purchase interval, complete October 2026, Dashboard's 540 matched dates,
and v1's 422 rejection of the extended range. Local handoff and machine-readable
HTTP reconciliation remain ignored under `.local/ni083-preview/` and `.local/ni083/`.

Initial bootstrap correctly refused an unpopulated snapshot metric; the unrelated
snapshot dataset was omitted. A subsequent attempt correctly refused uncovered
pre-fee periods; explicit source/date missing rows were added (not zero padding),
and a synthetic sparse-coverage regression now guards that preparation behavior.
The final successful preparation does not invent a treasury stock or older fees.
All 14 archived inputs from the NI-082 digest table were rehashed after the work
and remain unchanged. Root UI/browser acceptance is recorded separately.


### Historical purchase cutoff correction

The saved longitudinal manifest records `[2026-08-06, 2026-11-04)` UTC and
`end_exclusive=true`, but no retrieval timestamp. The local cohort dataset now
sets `source_as_of=2026-11-04T00:00:00Z` explicitly as that recorded observation
cutoff, leaves `retrieved_at=null`, and binds the metadata file as an input.
This is coverage through 3 November, not an invented retrieval time or the
current recomputation clock. An earlier local preview lacked this metadata and
the UI fell back to `resolved_at`; that runtime timestamp did not describe data
freshness and was corrected before final acceptance.
