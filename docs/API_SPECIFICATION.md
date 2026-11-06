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

**Implemented (NI-022):** `apps/api/src/near_api/workspace/` serves this contract at
`GET /api/home` with authorization solely through the `get_principal` dependency: 401 for a
missing/invalid session, 403 fail closed for a disabled account, and the one generic
`ResourceNotFound` 404 shape for absent/not-owned targets. The response adds an operator-directed
`counts:{documents:int}` object with the owner-scoped total (scoped_page applies the owner
predicate before LIMIT/OFFSET and counts the same scoped statement; two SQL statements total — no
N+1) and caps `recent_documents` at 5 by the query with the stable `(updated_at DESC, id)` order.
`recent_charts`/`recent_insights`/`indicators` are honest empty arrays with schema-level
`maxItems: 0` until their owning tasks land (saved charts NI-035, insights NI-046/NI-047,
public series NI-031/NI-032); individual unavailable indicators will be typed by those tasks, not
this one. `DocumentSummary.progress` counters are documented zeros until the NI-036 revision
service and the NI-041/NI-046 block taxonomy define canonical projection counters. Every response
is `Cache-Control: no-store`.

## Research documents and versions

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

`filters` are canonicalized before hash/cache computation. A missing series still returns its metric and quality with null points. Charts cannot request arbitrary provider URLs, SQL or currency conversions.

## Insights, hypotheses and evidence

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

## Export

| Method/path | Request → response | Auth / authorization | Errors |
| --- | --- | --- | --- |
| POST `/documents/{id}/exports` | `{document_version_id,format:"markdown_zip"\|"pdf"}` → 202 ExportJob | Owner of doc and exact version; PDF P1 only | 404/422/409; references unavailable→422 |
| GET `/exports/{jobId}` | none → ExportJob | Owner, including parent doc/version | 404 |
| GET `/exports/{jobId}/download` | none → ZIP/PDF bytes, Content-Disposition sanitized filename | Owner; succeeded/unexpired artifact | 404/409 not ready/410 expired |

Exports are revision-bound; no silent automatic export of latest content. Client first saves then uses acknowledged version ID. Worker validates every required artifact and stores a manifest. No public signed private-data URLs in MVP. Export file references use server-controlled IDs, never filesystem paths supplied by a client.

## Operational interfaces

GET `/health/live` → `{status:"ok"}` with no auth/secrets. GET `/health/ready` → 200/503 `{status,checks:{database,migrations,artifact_store}}`; internal network only. Metrics/logs redact identities/content. Operator commands ingestion/research/publication/export-worker have validated config schemas in [pipeline](DATA_PIPELINE.md) and [reproduction](REPRODUCIBILITY.md). CI must lint OpenAPI, regenerate TS, reject contract drift, and test all private endpoint families with Alice/Bob.
