# Data engineering pipeline

Target pipeline for [metric catalog](METRIC_CATALOG.md). Existing saved analyses remain unchanged; no ingestion is performed in this documentation phase. Source status and rights: [SOURCE_VERIFICATION.md](SOURCE_VERIFICATION.md).

## Stage contracts

| Stage | Input → output | Mandatory gate and failure behavior |
| --- | --- | --- |
| 1 Ingest | Approved source config → raw byte artifact + request metadata | Exact endpoint/method/query hash, retrieval UTC, provider cutoff/index head, page cursors and auth redaction; complete pagination or explicitly partial cohort |
| 2 Preserve | Raw bytes → immutable artifact + SHA-256 | Original bytes and permitted provenance retained; no secrets, no overwrite, source license controls public download |
| 3 Validate | Raw artifact → validation report | Schema, finite values, expected date/partition coverage, token decimals, successful execution, duplicate identities, timestamp interpretation and source completeness scope |
| 4 Normalize | Validated records → typed canonical records | UTC ns/milliseconds/seconds conversion explicit; raw integer quantities retained; assets mapped by versioned ID, never ticker alone |
| 5 Compute | Canonical records + metric definition version → observations | Pure deterministic registered functions; Decimal sums, period alignment, ratio validity, explicit quality/bound semantics |
| 6 Persist | Observations + manifest → staged dataset version | Transactional writes, membership/FK/uniqueness checks; rejected data cannot become latest |
| 7 Publish | Quality-approved dataset → atomic active pointer | Compare previous coverage/checksums and revision deltas; pointer switch only after complete commit; retain last good on failure |
| 8 Deliver | Approved version → typed API → canonical chart | API resolves exact immutable version once per request, sends units/source/quality; public/private same service |
| 9 Pin | Resolved chart/model context → document revision | Save exact data/definition/filters/calculation context, not just “latest” |
| 10 Reproduce | Manifest/code/locks/config → identical processed data/model inputs | Offline verification, exact financial hashes, documented float tolerances for statistics |

## Canonical event and time policies

NEAR event identity is network + receipt_id + log index + item/action index + event type; retain tx hash as lineage. Outcomes deduplicated before joins. Only successful execution can establish credit/transfer; an API declaration alone cannot. Amount-match within a time tolerance is flagged as such, not presented as a full receipt-parent proof. Store actual matcher version and tolerance (legacy payout matching used up to 300s).

Creation cohorts and execution-date cohorts are distinct datasets. Date boundaries use event execution time for activity and a documented cash/accrual policy for revenue. Preserve `event_time`, `source_as_of`, `retrieved_at`, `published_at`; a fresh retrieval does not make an old observation fresh. Finalized block height/hash is required for new RPC state snapshots. UTC day aggregates use `[00:00, next00:00)`; omit or label incomplete current days, never compare one against a full day.

A dataset may contain multiple source-qualified metrics if an explicit prepared manifest binds each input. Derived observations must share approved frequency/window and definitions. A newer provider revision cannot be mixed into an older dataset or model without a new version.

## Quality and normalization rules

- Missing dates: explicit null/reason; no forward-fill of flows, fees or prices. Proven complete zero activity may be zero. Empty incomplete response is not zero.
- Duplicates: identical canonical events collapse once, count in validation; conflicting duplicate payloads quarantine. Raw response remains available.
- Monetary units: raw yoctoNEAR→NEAR via 10^24, token decimals per asset/version, USD prices by explicit CoinGecko timestamp. USD daily estimates preserve start/end price sensitivity; never imply execution prices.
- Ratios: reject zero/missing denominator; sums of flows use sum before division. Cross-currency ratios require a documented conversion. Monthly revenue cannot produce daily capture rate.
- Revisions: new `dataset_version`, supersedes link, changed-date report and reason; old versions immutable. Source disagreement is represented as parallel qualified metrics, not averaged away.
- Bound data: gross issuance/burn remain lower bounds; do not insert them into exact accounting identities. Separate exact net supply change from incomplete components.
- Coverage: report expected/observed dates and partitions, index-head lag, pagination completeness and cohort scope separately. 90 rows do not prove every blockchain event indexed.

## Adapter boundary and operation

Proposed Python interface: `describe() -> SourceCapability`, `fetch(window,cursor,limits) -> RawPage`, `validate(raw) -> QualityReport`, `normalize(raw,definition_version) -> CanonicalBatch`. Schemas include source ID, auth mode, source version, query identity and license status. HTTP client has timeout, bounded response size, Retry-After handling, jittered exponential backoff capped at 60s and max3 attempts per scheduled invocation. 401/403 disable source and alert; 429 checkpoints and pauses when budget/backoff is exhausted; do not loop indefinitely or bypass limits with endpoint rotation.

Default `INGESTION_ENABLED=false`, empty source allowlist, request/day caps zero. Scheduled enablement requires recorded access/quota/budget/rights and a small validated probe. `STOP_PUBLIC_COLLECTION` and existing supply/provenance pause markers take precedence for legacy collectors; new product adapters cannot evade them. No scheduled job executes saved cloud SQL by default.

Use a PostgreSQL advisory lock per source+window to prevent overlap. Checkpoint cursor only after bytes are durable. Idempotent raw fetch keys include source/request/window/cursor/retrieved version; idempotent normalized keys use event identity and dataset staging run. An interrupted run resumes explicitly from checkpoints; it never marks partial data complete.

## Cadence and freshness targets (planned, not source guarantees)

Lightweight finalized RPC header: every 15 minutes, stale after 60 minutes, only after approval. Provider daily fees/volume: daily at 03:00 UTC, stale when last complete day is >48h old, plus a reviewed 7-day revision lookback. Historic archive: fixed snapshot, no freshness promise; label Historical. At most one adapter refresh is required for the first live release. Prefer consistent lagged complete data over partially observed today.

CLI contract to implement: `python -m near_api.cli ingest import-archive --manifest PATH --dry-run`, `ingest refresh --source ID --start DATE --end DATE --max-requests N`, `datasets validate --id UUID`, `datasets publish --id UUID`. Publication requires reviewed quality report; no browser can call these operators. Monitoring includes run status, last success, coverage, retries and revision magnitude; never report only “job ran”.

## First usable pipeline

Import existing 90-day JSON/SQL manifests read-only, validate legacy content hashes and definitions, emit a new normalized prepared dataset without editing the archive, publish source-qualified purchases/payouts/USD estimates/supply changes and fees/volume where permitted. Keep fee provenance a separate short-window dataset. Refuse exact protocol revenue and full buyback attribution until evidence improves. See NI-026–NI-030 and NI-051.
