# REST API specification

Contract for implementation. NI-004 supplies strict common Pydantic schemas, the health route/error envelope, read-only OpenAPI and a generated TypeScript client; [executable contract workflow](API_CONTRACT.md). The business endpoints below remain specifications until their owning tasks implement them. Base `/api/v1`, same-origin Next.js gateway to FastAPI. [Schema](DATABASE_SCHEMA.md), [security](AUTHENTICATION_SECURITY.md), [journeys](USER_JOURNEYS.md).

## Protocol, roles and errors

JSON UTF-8; UUID opaque IDs; dates ISO 8601 UTC; date windows `[start,end)`; decimal and raw amounts strings, never JSON float money. Reject unknown fields/filters. Success is the described object directly; lists `{items:[...],next_cursor:string|null}`. Cursor opaque, bounded (default 20, max 100), stable order `(updated_at,id)` for private lists. Client cannot supply owner_id. P1/P2 operations are feature-gated; before implementation their unsupported request modes return 422 FEATURE_UNAVAILABLE, never a simulated success. ETag for a document is quoted revision, e.g. `"7"`.

Roles: **Public** only approved datasets/definitions/published content/runs; **Owner** verified principal owns every parent and private reference; **Operator** CLI/service credential outside browser, not a client role claim. Auth-required 401; unknown/not-owned private resource 404 uniformly; 403 for explicit disallowed operator operation. Input validation 422; malformed JSON 400; revision mismatch 409; missing If-Match on document mutation 428; oversized content 413; expired export 410 only after ownership check; rate limit 429 with Retry-After; dependency unavailable 503. Never include secrets or stack traces.

Error object: `{error:{code:string,message:string,request_id:UUID,details?:[{path:string,reason:string}],retryable:boolean}}`. Examples codes: REVISION_CONFLICT, FILTER_UNSUPPORTED, REFERENCE_INVALID, DATA_NOT_READY, EXPORT_EXPIRED. 409 includes current_revision for owned document only. Public availability is usually a typed 200 empty/unavailable response; genuine upstream query failure 503 if no approved last-good dataset exists.

For POST creation/retry use `Idempotency-Key: UUID`; repeated identical owner/route/body returns original result (24h); different body same key→409. State-changing gateway requests require trusted Origin plus CSRF protection. All private responses `Cache-Control: no-store`; public data cache key includes all normalized filters and immutable version. Public latest pointer cached ≤60s; immutable content may be cached by hash.

## Reusable request/response schemas

| Name | Fields / validation |
| --- | --- |
| Principal | `{id:UUID,display_name:string,display_timezone:string}`; authenticated identity, no provider token |
| Selection | `{start:date,end:date,frequency:"day",filters:object}`; start<end, max366 days, filters validated against chart version. All APIs use these names; UI query `start/end` maps directly |
| DataQuality | `{status:"ok"\|"partial"\|"missing"\|"stale"\|"unavailable"\|"revised",bound_kind:"exact"\|"estimate"\|"lower"\|"upper"\|null,reasons:string[],coverage:{observed:number,expected:number},freshness_target_seconds:number\|null}` |
| Metric | `{id:UUID,metric_id:string,version:int,title,definition,formula,unit,frequency,source_id,economic_scope,availability,limitations:string[]}`; no executable user formula |
| DataSource | `{id,name,docs_url,verified_at,license_status,access_status,lineage:string[],expected_update_frequency,last_success_at}`; no auth header/base URL with token |
| Dataset | `{id,dataset_key,version,status,start,end,source_as_of,retrieved_at,pipeline_version,content_sha256,quality:DataQuality,manifest_url:string\|null,supersedes_id:UUID\|null}` |
| Series | `{metric:Metric,dataset:Dataset,selection:Selection,points:[{start:timestamp,end:timestamp,value:decimal_string\|null,quality:DataQuality}],sources:DataSource[]}`; explicit nulls and gap reason |
| ChartDefinition | `{id:UUID,chart_id:string,version:int,title,description,category,metric_definition_ids:UUID[],visualization_type,units,filter_schema,available_ranges:string[],renderer_version,update_frequency}` |
| ChartView | `{definition:ChartDefinition,selection:Selection,dataset:Dataset,series:Series[],resolved_at:timestamp,context_hash:sha256,quality:DataQuality}`; fail incompatible metric versions, do not mix silently |
| ResolvedContext | `{chart_definition_version_id:UUID,dataset_version_id:UUID,selection:Selection,context_hash:sha256,renderer_version,metric_definition_versions:UUID[],resolved_at:timestamp}`; server resolves/verifies all IDs/hash |
| SavedChart | `{id,label:string\|null,mode:"live"\|"snapshot",chart_definition_version_id,selection,snapshot_id:UUID\|null,last_resolved_dataset_version_id,created_at,updated_at}` |
| DocumentSummary | `{id,title,revision:int,schema_version:int,current_version_id:UUID,created_at,updated_at,progress:{headings:int,charts:int,insights:int}}` |
| Document | DocumentSummary plus `{content:EditorDocument,resolved_contexts:Record<blockId,ResolvedContext\|ModelContext>}`; validated schema in editor spec |
| VersionSummary | `{id,document_id,revision,schema_version,content_sha256,created_at}`; VersionDetail adds content/resolved_contexts |
| InsightInput | `{block_id:UUID,type:"observation"\|"hypothesis"\|"risk"\|"conclusion",classification:"supporting"\|"contradicting"\|"uncertain",body:RichText,context:ResolvedContext\|ModelContext,hypothesis_id?:UUID}`; max10k plain-text-equivalent characters |
| Insight | InsightInput plus `{id,document_id,authored_at,modified_at}`; ownership via parent |
| HypothesisInput | `{block_id:UUID,statement:string,assessment:"untested"\|"supported"\|"mixed"\|"weakened"\|"insufficient_data"}` |
| EvidenceInput | `{block_id,hypothesis_id,classification,target_kind:"insight"\|"chart_block"\|"model_run"\|"citation",target_id:UUID,explanation:string}`; target visibility/reference validation required |
| MutationResult<T> | `{document:DocumentSummary,value:T}`; ETag new revision. Document content can be fetched after mutation; never make client guess new revision |
| Snapshot | `{id,chart_definition_version_id,dataset_version_id,selection,calculation_context,content_sha256,created_at}`; private metadata |
| ModelDefinition | `{id,model_id,version,question,specification,required_metric_ids,readiness_rules,limitations}` |
| ModelRun | `{id,definition_version_id,dataset_version_id,status,specification,sample:{start,end,nobs,excluded_dates},coefficients:[{term,estimate,standard_error,ci_low,ci_high,p_value}],tests,diagnostics,interpretation,limitations,code_commit,dependency_lock_hash,config_hash,reproduction_manifest_url,created_at}`; numerical statistics finite; unavailable values null with reason |
| ExportJob | `{id,document_id,document_version_id,format:"markdown_zip"\|"pdf",status:"queued"\|"running"\|"succeeded"\|"failed"\|"expired",error_code:string\|null,download_path:string\|null,expires_at}` |

A chart view pins a single prepared dataset version containing its required metrics; cross-source comparisons require an explicit composite prepared dataset with source-qualified columns. ModelContext is `{model_run_id,dataset_version_id,specification_version,context_hash}`. Editor references are validated recursively on every revision, not just through convenience endpoints.

## Authentication gateway — outside FastAPI prefix

Use provider SDK server-side; application does not store passwords. These handlers are planned Next.js endpoints, not separate identity issuance logic.

| Method/path | Request → response | Auth / authorization | Specific failures |
| --- | --- | --- | --- |
| POST `/api/auth/signup` | `{email,password,display_name?}` → 202 `{status:"check_email"}`; provider verifies address | Anonymous, same-origin CSRF/rate guard | 422 policy; 429; generic response prevents user enumeration |
| POST `/api/auth/login` | `{email,password}` → 200 `{status:"authenticated"}` + secure cookies | Anonymous, same-origin guard | Generic 401 on invalid credentials; 429 |
| POST `/api/auth/logout` | `{}` → 204; clear cookies and revoke provider refresh session | Session, same-origin guard | Idempotent 204 even if expired |
| POST `/api/auth/recovery` | `{email}` → 202 `{status:"check_email"}` | Anonymous, allowlisted recovery redirect | Generic response; 429 |
| GET `/auth/callback` | provider code + state → 303 internal allowlisted route | PKCE/state verified; exchange server-side | Invalid/expired link→safe error page; no external redirect |
| POST `/api/auth/password` | `{password}` → 204 | Valid provider recovery/auth session | 401/422/429 |
| GET `/api/auth/session` | none → `{authenticated:boolean,user?:Principal}` | Cookies; private no-store | 503 provider/JWKS outage; no token serialized |

SDK refresh occurs server-side through gateway/session handlers with cookie rotation, not a second public refresh-token API.

## Profile and home

| Method/path | Request → response | Auth / authorization | Errors |
| --- | --- | --- | --- |
| GET `/me` | none → Principal | Owner: JWT subject only | 401/503 |
| PATCH `/me` | `{display_name?,display_timezone?}` → Principal | Owner; forbid id/email/owner edits | 422 |
| GET `/workspace/home` | none → `{recent_documents:DocumentSummary[],recent_charts:SavedChart[],recent_insights:Insight[],indicators:Series[]}` | Owner lists; public indicators reused | 401; individual unavailable indicator typed, not whole-page failure |

**Implemented (NI-022 / NI-024):** `GET /api/home` uses only the verified
`get_principal` identity and transaction-local RLS. Every response is
`Cache-Control: no-store` (401 invalid/missing session; 403 disabled account;
absent/not-owned references share generic 404). `counts:{documents:int}` is an
owner-scoped total; `recent_documents`, `recent_charts` and `recent_insights`
are each query-capped at 5. Documents and saved charts use stable
`(updated_at DESC,id)` ordering. Document progress counts canonical
`heading`/`liveChart`/`insight` blocks only in each current revision; historical
versions never inflate completion. These are workflow counts, never confidence.
Saved charts reuse `SavedChartResponse`; no home read changes recency or pins.
`HomeInsightSummary` is a read projection of existing canonical current-revision
insights (`insight_id,document_id,document_title,block_id,type,classification,
modified_at,excerpt`); excerpt is at most 280 plain-text characters. It exposes
no independent insight authoring capability ahead of NI-047.

At most 3 `HomeIndicator` entries use the registered `intents-volume`,
`gross-fees` and `observed-conversions` definitions. Each carries
`chart_id,title,chart_version:int|null,status,series:Series|null,reason:string|null`. An available
entry reuses the first role-ordered canonical ChartView series for the last day
of its latest approved dataset (`[end-1 day,end)`), retaining exact decimal
strings, metric/dataset versions, quality, limits, sources and timestamps.
Filters remain the canonical empty selection: ambiguous dimensions return
explicit unavailable observations rather than a guessed source. Missing
observations stay null. Catalog/delivery errors or source SQL failures produce
only that indicator's unavailable state using a savepoint; private documents,
saved contexts and other indicators remain usable. No providers or collectors
are contacted. Private query count is constant (6 statements), plus at most
three bounded canonical indicator resolutions; there is no per-document query.

## Research documents and versions

Implemented note (NI-036 + NI-037): the private document CRUD and version rows below are
implemented in `apps/api/src/near_api/documents/` (exposed under the `/api` prefix):
`GET /documents`, `POST /documents`, `GET /documents/{id}`, `POST /documents/{id}/versions`
(NI-036), plus `PATCH /documents/{id}` (rename), `DELETE /documents/{id}`, `GET
/documents/{id}/versions` and `GET /documents/{id}/versions/{versionId}` (NI-037). Creation
atomically writes the document plus its first EMPTY revision (`revision: 1`, `ETag: "1"`);
the ETag is the quoted current revision and every mutation (save, rename, delete) requires
`If-Match` to carry exactly that quoted value (bare numbers and weak validators are 428). A
stale revision is 409 REVISION_CONFLICT including the current revision for the owned document;
invalid content is a typed 422 (VALIDATION_ERROR / REFERENCE_INVALID), oversize 413, and a
rejected write leaves zero rows. Each revision-creating write re-validates the canonical
schema (EDITOR_SPECIFICATION), enforces same-document evidence/insight/risk links, requires
`dataTable.dataset_version_id` to be an APPROVED dataset version, requires citation targets
to be public artifacts, and gates liveChart blocks, snapshot chart mode and `model_run`
evidence targets until the chart registry (NI-031), research snapshots (NI-035) and model
runs (NI-054) exist — an unverifiable reference is invalid, never tolerated.
`observed_contexts` must be empty until the chart system (NI-041/NI-043) resolves pins
server-side.

NI-037 behavior specifics: a rename (`PATCH`) that changes the title creates a full new
immutable revision with byte-identical canonical content (EDITOR_SPECIFICATION: title and
content attribution stay consistent) and re-validates the content references; a `PATCH` whose
title equals the current title is a no-op that returns the current summary and ETag without
creating a revision. `DELETE` removes the owner-checked document row in one transaction; the
ON DELETE CASCADE chain removes every private child (versions, blocks, insight/hypothesis/
evidence projections) while shared scientific data (datasets, observations, registries,
artifacts) is untouched; there is no revision-delete endpoint — versions are immutable and
disappear only with their document (export jobs arrive with NI-058 and cascade by their
documented document FK). Version listing pages the document's revisions newest-first
(revision DESC — unique per document, so the bounded offset cursor is stable) and version
detail resolves a revision only through its owned parent document (a foreign document's
version id is the same generic 404). Reopen/restore has no dedicated endpoint in the
specification: reopening the working document is `GET /documents/{id}`, historical state is
`GET /documents/{id}/versions/{versionId}`. `Idempotency-Key: UUID` is honored on
`POST /documents` and `POST /documents/{id}/versions`: the response snapshot is committed in
the same transaction as the write, so a repeated identical owner/route/body request replays
the ORIGINAL 2xx result for 24h (`app.idempotency_records`, migration 0009) instead of
creating a second document or revision — the timeout-after-commit guarantee; the same key
with a different body is 409 IDEMPOTENCY_CONFLICT; If-Match is not part of the request
identity (owner/route/body only, per the protocol section); failed writes store nothing and
stay retryable; a malformed key is 422. The opaque list cursor is a bounded offset over the
stable `(updated_at DESC, id)` owner-scoped document order and the revision DESC version
order.

| Method/path | Request → response | Auth / authorization | Errors |
| --- | --- | --- | --- |
| GET `/documents` | query `q?,cursor?,limit?` → paginated DocumentSummary | Owner predicate before pagination/search | 401/422 |
| POST `/documents` | `{title,template_id?:"investment-v1"}` → 201 Document | Owner; empty default P0, template P1 | 422 unavailable template; 409 idempotency collision |
| GET `/documents/{id}` | none → Document + ETag | Parent owner | 404 |
| PATCH `/documents/{id}` | If-Match; `{title}` → DocumentSummary + ETag | Parent owner; title change creates full new revision | 404/409/428 |
| DELETE `/documents/{id}` | If-Match; no body → 204 | Parent owner; delete scoped children only | 404/409/428 |
| GET `/documents/{id}/versions` | pagination → VersionSummary list | Parent owner | 404/422 |
| POST `/documents/{id}/versions` | If-Match; `{schema_version,content:EditorDocument,observed_contexts:ResolvedContext[]}` → 201 VersionDetail + DocumentSummary in `{version,document}` | Parent owner; validate every private reference and server-resolve pins | 404/409/413/422/428; invalid schema explicit |
| GET `/documents/{id}/versions/{versionId}` | none → VersionDetail | Both version parent match and owner | 404 |
| POST `/documents/{id}/duplicate` | `{source_version_id,title}` → 201 Document | Owner; source version belongs to id | 404/422; P1 |
| POST `/documents/{id}/chart-blocks` | If-Match; `{chart_definition_version_id,selection,mode:"live"\|"snapshot",dataset_version_id,snapshot_id?,after_block_id?:UUID}` → 201 MutationResult<`{block_id}`> | Owner; same-owner snapshot, public approved dataset; pins server verified | 404/409/422/428 |

**Implemented (NI-041):** `POST /api/documents/{document_id}/chart-blocks` requires the quoted current `If-Match`, checks the destination owner before resolving references, and appends exactly one server-allocated block/revision atomically with projections and a server-built frozen `resolved_contexts[block_id]`. Idempotency uses the existing owner/route/body replay store; retrying after commit returns the original result/ETag even with a refreshed If-Match. A different body under the key is 409. The inspected approved dataset is used exactly, without latest substitution; unknown/unavailable definitions, unsupported versioned filters, missing required metrics, bad anchors and snapshot mode are rejected. ChartSelection structurally bounds the registered dimension names and string values; the immutable definition's filter_schema remains the option authority. Context hashing reuses the same delivery helper as ChartView. Generic Selection stays the strict-empty bootstrap contract for unfiltered callers. Replay identity now uses the concrete document URL for both chart insertion and whole-document version saves: the same key/body sent to another owned document executes against that destination, and a foreign destination still returns 404. Same-destination replay with a refreshed If-Match remains unchanged.

The web destination picker lists only owned documents, supports search/pagination or Create New, and inserts only after confirmation. Creation and insertion keep separate retry keys; retry fetches the current document revision while retaining the original input/key. Password/demo sign-in preserve the server-validated internal continuation; public chart action URLs pin the inspected dataset UUID before navigating to login. The fixed-path same-origin documents gateway enforces cookie/CSRF/Origin/body bounds and forwards ETag/If-Match/idempotency semantics. Existing document CRUD/autosave transports now supply CSRF through the same boundary. Unchanged inserted contexts carry forward verbatim on a subsequent prose save; changed chart contexts and submitted observed_contexts remain rejected pending NI-043. Interactive node controls/renderer behavior remain NI-042; no fabricated chart is rendered in their place. Same-subject revalidation temporarily hides the modal without losing its destination/draft, creation key, insertion key or acknowledged result. Closing and reopening an uncertain attempt retains those keys; a different verified subject discards the attempt. A new confirmation after acknowledged success creates a fresh intent.

Whole-document save creates a new revision for all structural editing including table/divider/text CRUD. No low-level block endpoint can bypass document validation. Public Add Chart follows the same insertion endpoint after login/destination selection. Server accepts the inspected dataset version to prevent data changing between preview and insertion; if it is unavailable, reject explicitly rather than substitute latest.

## Charts and data — public except saved instances

| Method/path | Request → response | Auth / authorization | Errors |
| --- | --- | --- | --- |
| GET `/charts` | `q?,category?,cursor?,limit?` → ChartDefinition list (latest definitions) | Public; approved catalog only | 422 category/query |
| GET `/charts/{chartId}` | `version?:int` → ChartDefinition | Public; chartId stable slug | 404 |
| GET `/charts/{chartId}/view` | `definition_version:int,start,end,frequency=day,dataset_version=latest\|UUID,filters=<urlencoded JSON>` → ChartView | Public; approved datasets only | 404/422/503 |
| GET `/metrics` | `category?,availability?,cursor?,limit?` → Metric list | Public | 422 |
| GET `/metrics/{metricId}` | `version?:int` → Metric | Public stable metric slug | 404 |
| GET `/metrics/{metricId}/series` | `definition_version:int,start,end,dataset_version=latest\|UUID,frequency=day,filters?` → Series | Public; member definition required | 404/422/503 |
| GET `/data-sources` | pagination → DataSource list | Public sanitized projection | 422 |
| GET `/data-sources/{sourceId}` | none → DataSource | Public | 404 |
| GET `/datasets/{versionId}` | none → Dataset | Public approved only | 404 |
| GET `/datasets/{versionId}/manifest` | none → sanitized manifest JSON or download | Public license-approved artifacts only | 404 for restricted/staged; no raw secrets |
| GET `/saved-charts` | `q?,category?,cursor?,limit?` → SavedChart list | Owner | 401/422 |
| POST `/saved-charts` | `{chart_definition_version_id,label?,selection,mode,dataset_version_id,snapshot_id?}` → 201 SavedChart | Owner; validate snapshot ownership and immutable/public refs | 404/422/409 |
| GET `/saved-charts/{id}` | none → `{saved_chart:SavedChart,view:ChartView}` | Owner | 404; unavailable data explicit |
| PATCH `/saved-charts/{id}` | `{label?,selection?,mode?,dataset_version_id?,snapshot_id?}` → SavedChart | Owner; explicit contextual change | 404/422 |
| DELETE `/saved-charts/{id}` | none → 204 | Owner | 404 |

**Implemented (NI-035):** `/api/saved-charts` and `/api/saved-charts/{instance_id}` implement the private rows above. POST honors the shared 24-hour owner/route/body `Idempotency-Key` replay. PATCH permits explicit selection/dataset/label/mode edits, validates the complete result with the canonical chart resolver, and never accepts ownership fields. P0 accepts `live` only: snapshot writes/ids are rejected with 422 REFERENCE_INVALID and are also blocked by database CHECKs until the real P1 snapshot ownership contract exists. GET detail resolves the latest approved dataset for the stored definition/range/filters and returns `{saved_chart,view,dataset_changed:boolean}`; the badge compares with the last successful resolution, which advances only after a successful read and does not reorder the list. Unavailable data is an explicit delivery error; list metadata remains accessible. All responses, including validation/auth errors, are `no-store`. The same-origin web gateway exposes only the collection or one UUID, checks the signed cookie and mutation Origin/CSRF, bounds request bytes, forwards only the cookie's bearer token, and leaves final JWT/owner verification to FastAPI. Client private state is cleared on logout/account-change signals and revalidated on focus/visibility; aborted old-account responses cannot populate it. Same-account action revalidation preserves the save attempt's idempotency key while hiding its UI, and identity changes reset it. CSRF token acquisition reuses the current signed cookie; concurrent first acquisition for one authenticated session is deterministic, so parallel private writes do not invalidate each other's cookie/header pair.

`filters` are canonicalized before hash/cache computation. A missing series still returns its metric and quality with null points. Charts cannot request arbitrary provider URLs, SQL or currency conversions.

**Implemented (NI-032):** the metrics/charts/datasets/data-sources rows above are
implemented under the `/api` prefix (`/api/metrics`, `/api/charts`,
`/api/data-sources`, `/api/datasets`; the spec's `/api/v1` base stays the same
contract, and route-path aliases remain a review decision as recorded for
`/workspace/home`). They are public reads through the unprivileged `near_app`
role with no authorization and no user-identifying input; private saved-chart
rows remain NI-035 scope. Implemented deltas against the rows above, recorded
here for consumers: `ChartDefinition` responses carry `data_status` +
`unavailable_reason` (unavailable charts are never advertised as live),
`source_lineage`, and `available_ranges` as the bounded
`{presets_days:number[],max_days:number}` object (the plain preset-string list
would lose the max-range bound); `Metric.formula` is the registered
computation identifier (`formula_key`), not executable content; `Metric`
list filtering supports `availability` (A/P/B/G) while `category` is rejected
422 FILTER_UNSUPPORTED because definitions carry no category axis. Series and
chart views resolve ONE approved dataset version per request — explicit
`dataset_version` UUIDs are 404 unless `approved` (staged/validated/rejected
never leak existence), and `latest` picks among `active_datasets` rows whose
approved version contains every required metric definition (most recent
`published_at`, then lowest `dataset_key`; cached ≤60 s; no result is a typed
retryable 503 DATA_NOT_READY, never a substitution). Responses carry decimal
strings, per-point quality with explicit reasons, UTC half-open timestamps and
a `context_hash` over definition version + dataset version + canonical
selection + bound metric definition versions; identical selections resolve
identically. Chart `filters` (urlencoded JSON) are validated against the
resolved chart version's closed `filter_schema`; unknown keys/values are 422
FILTER_UNSUPPORTED. A period holding several dimension variants without a
disambiguating approved filter is an explicit null/unavailable point with a
reason — values are never averaged, summed or picked silently. Metric-level
series accept only empty filters until a metric filter domain is registered.
Source projections never serialize the provider endpoint or credentials
(`docs_url` is nulled unless credential-free http(s)); the dataset manifest is
served sanitized from persisted rows (content-addressed storage keys, no
operator paths) and is 404 when the version is not approved or its artifact is
license-`prohibited`. Approved content is served with immutable public cache
headers and a `content_sha256` ETag; latest pointers with `max-age=60`.


## Insights, hypotheses and evidence

Implemented contracts (NI-046, routes pending): `apps/api/src/near_api/insights/schemas.py` implements the `InsightInput`/`Insight`, `HypothesisInput`/`Hypothesis`, `EvidenceInput`/`Evidence` and `RiskInput` models below (plus frozen `ResolvedContext`/`ModelContext` and the typed rich-text shapes) and publishes them in the OpenAPI `components` so the generated TypeScript client already carries the validation types; the convenience routes themselves arrive with NI-047/NI-048/NI-049 and must reuse these models. Fixed rules already enforced at the contract boundary: input models carry no `authored_at`/`modified_at` (server authors timestamps; unknown fields — including client timestamps and `owner_id`/`user_id` — are rejected 422), response models add `id`/`document_id` plus UTC-normalized server timestamps, insight/hypothesis bodies are bounded sanitized rich text (max 10k plain-text-equivalent characters, canonical editor grammar via `documents/schema`), and contexts are the frozen inspection records with selected range/filters/dataset pin/stable ids exactly as the reusable schemas table defines.

These are convenience operations on the current document JSON; all writes require If-Match and return a new document revision. Stable IDs persist across versions; GET can take `version_id` for historical views. PATCH schemas are partial corresponding Input schemas, with required final-state validation.

| Method/path | Request → response | Auth / authorization | Errors |
| --- | --- | --- | --- |
| GET `/documents/{id}/insights` | `version_id?` → Insight list | Parent owner and version parent | 404 |
| POST `/documents/{id}/insights` | InsightInput → 201 MutationResult<Insight> | Parent owner, block and context permitted | 404/409/422/428 |
| PATCH `/documents/{id}/insights/{insightId}` | partial InsightInput → MutationResult<Insight> | Same doc current projection; preserve original authored_at | 404/409/422/428 |
| DELETE `/documents/{id}/insights/{insightId}` | `{remove_evidence_links:boolean}` → MutationResult<`{deleted_id}`> | Parent owner; false with references→409 | 404/409/428 |
| GET `/documents/{id}/hypotheses` | `version_id?` → Hypothesis list | Parent owner | 404 |
| POST `/documents/{id}/hypotheses` | HypothesisInput → 201 MutationResult<Hypothesis> | Parent owner, valid node | 404/409/422/428 |
| PATCH `/documents/{id}/hypotheses/{hypothesisId}` | partial HypothesisInput → MutationResult<Hypothesis> | Parent owner | 404/409/422/428 |
| DELETE `/documents/{id}/hypotheses/{hypothesisId}` | `{remove_evidence_links:boolean}` → MutationResult<`{deleted_id}`> | Parent owner; linked removal explicit | 404/409/428 |
| GET `/documents/{id}/evidence` | `hypothesis_id?,version_id?` → Evidence list | Parent owner and parent references | 404/422 |
| POST `/documents/{id}/evidence` | EvidenceInput → 201 MutationResult<Evidence> | Parent owner, same-revision targets or published public run/citation | 404/409/422/428 |
| PATCH `/documents/{id}/evidence/{evidenceId}` | partial EvidenceInput → MutationResult<Evidence> | Parent owner and target validation | 404/409/422/428 |
| DELETE `/documents/{id}/evidence/{evidenceId}` | no body → MutationResult<`{deleted_id}`> | Parent owner | 404/409/428 |

Hypothesis/Evidence responses add stable id, document_id, authored_at and modified_at to their Input schema. Create with an existing block ID converts/updates the selected node after explicit client confirmation; otherwise client supplies a new UUID and the service inserts a block. Rich text body cannot contain arbitrary HTML/scripts. Insight context is immutable unless an explicit replacement context is submitted and displayed as a new revision.

## Snapshots, models and public research

| Method/path | Request → response | Auth / authorization | Errors |
| --- | --- | --- | --- |
| POST `/snapshots` | `{chart_definition_version_id,dataset_version_id,selection}` → 201 Snapshot | Owner; approved public inputs; P1 | 404/422/503 |
| GET `/snapshots` | pagination → Snapshot list | Owner; P1 | 401/422 |
| GET `/snapshots/{id}` | none → Snapshot | Owner; P1 | 404 |
| DELETE `/snapshots/{id}` | none → 204 | Owner; referenced snapshot protected | 404/409 |
| GET `/model-definitions` | pagination → ModelDefinition list | Public registered/published definitions | 422 |
| GET `/model-definitions/{modelId}` | `version?:int` → ModelDefinition | Public | 404 |
| GET `/model-definitions/{modelId}/readiness` | `dataset_version:UUID` → `{ready:boolean,reasons:string[],eligible_specifications:string[],checked_dataset_version_id}` | Public deterministic metadata check, no fitting | 404/422 |
| GET `/model-runs` | `model_id?,dataset_version?,cursor?,limit?` → published ModelRun summaries | Public published only | 422 |
| GET `/model-runs/{runId}` | none → ModelRun | Public published only | 404 |
| GET `/model-runs/{runId}/manifest` | none → sanitized reproduction manifest | Public published and licensed | 404 |
| GET `/publications/{slug}` | `version?:int` → `{id,slug,version,title,content,evidence_manifest,published_at,content_sha256}` | Public published only; latest approved default | 404 |
| POST `/publications/{slug}/duplicate` | `{publication_version:int,title?}` → 201 Document | Owner; published allowed input; P1 | 404/422/409 |

Creating datasets/models/publications uses the operator CLI, not a browser POST API. The MVP exposes fixed published runs only. Do not invent a user-execution endpoint or execute scientific code in GET requests.

**Implemented (NI-054):** the model-definition/readiness/run rows above are implemented under the `/api` prefix (`/api/model-definitions`, `/api/model-runs`) in `apps/api/src/near_api/models/` as public reads through the unprivileged `near_app` role with no authorization and no user-identifying input. They serve ONLY the immutable `app.model_runs` rows written by the operator publication gate (`python -m near_api.research publish`; [reproducibility](REPRODUCIBILITY.md)): an unpublished, failed or gate-rejected run does not exist in the backing table and is the one generic 404 with no existence leak, and every response is a projection of stored verified manifests — no route imports the research package, so endpoint access never triggers a fit or a provider call. Implemented deltas recorded for consumers: definitions exist publicly exactly when a run for that specification is published (a specification the gate evaluated but never published has no public definition row) and `ModelDefinition.question` is mechanically composed from the preregistered specification's declared fields (declared target, explanatory metric ids, family, baseline) — never an authored economic claim; `required_metric_ids` are the registry metric ids the specification declares (strings, not UUIDs). The readiness endpoint serves the NI-051 gate verdict recorded inside the latest published bundle's readiness report (the `dataset_version` query parameter is not implemented: published runs bind the offline archive manifests recorded in their data manifests, not a database dataset version — a dataset-bound readiness check stays with a future task); it returns `ready:false` with the recorded reasons for `NOT_READY`/`REJECTED` specifications evaluated by the same published report (a gate verdict is public information once the report is published, and is never a fitted result), and 404 for a specification no published report ever evaluated. Run summaries carry the gate verdict, sample window (half-open), declared reproduction tolerances, code commit, published_by and a `manifest_url`; run details add the specification verbatim, the coefficient table (finite float64 per the DATABASE_SCHEMA numeric policy; NaN/Infinity are refused by the gate and the contract boundary), the estimation summary, the diagnostics battery, the template-rendered interpretation, the limitations verbatim and the recorded approval. `GET /model-runs/{runId}/manifest` serves the canonical verified bundle (bundle type `model_run_manifest_bundle`: the three manifests, the per-artifact SHA-256 map and the approval) verbatim from the stored JSONB with immutable cache headers and the run-id ETag — `python -m near_api.research verify --bundle <downloaded.json> --offline` re-verifies it without any operator tooling. Published content is immutable: run detail and manifest carry `public, max-age=31536000, immutable`; catalogs carry `max-age=60`. Publications (`/publications/{slug}`) and evidence targets referencing `model_run` (NI-049) remain their owning tasks' scope; snapshots stay P1.

## Export

| Method/path | Request → response | Auth / authorization | Errors |
| --- | --- | --- | --- |
| POST `/documents/{id}/exports` | `{document_version_id,format:"markdown_zip"\|"pdf"}` → 202 ExportJob | Owner of doc and exact version; PDF P1 only | 404/422/409; references unavailable→422 |
| GET `/exports/{jobId}` | none → ExportJob | Owner, including parent doc/version | 404 |
| GET `/exports/{jobId}/download` | none → ZIP/PDF bytes, Content-Disposition sanitized filename | Owner; succeeded/unexpired artifact | 404/409 not ready/410 expired |

Exports are revision-bound; no silent automatic export of latest content. Client first saves then uses acknowledged version ID. Worker validates every required artifact and stores a manifest. No public signed private-data URLs in MVP. Export file references use server-controlled IDs, never filesystem paths supplied by a client.

## Operational interfaces

GET `/health/live` → `{status:"ok"}` with no auth/secrets. GET `/health/ready` → 200/503 `{status,checks:{database,migrations,artifact_store}}`; internal network only. Metrics/logs redact identities/content. Operator commands ingestion/research/publication/export-worker have validated config schemas in [pipeline](DATA_PIPELINE.md) and [reproduction](REPRODUCIBILITY.md). CI must lint OpenAPI, regenerate TS, reject contract drift, and test all private endpoint families with Alice/Bob.
