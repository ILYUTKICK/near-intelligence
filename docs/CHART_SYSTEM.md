# Canonical chart system

One versioned chart catalog and rendering adapter for public explorer, workspace, editor and exports. [Metrics](METRIC_CATALOG.md), [API](API_SPECIFICATION.md), [editor](EDITOR_SPECIFICATION.md).

## Definition versus instance versus observation

ChartDefinition is immutable and contains UUID version ID, stable chart_id slug, integer version, title, description, category, metric definition version IDs/series roles, visualization type, units, source lineage, expected update frequency, available ranges, supported filter JSON Schema and renderer version. Last-updated, data quality and actual date coverage belong to the resolved ChartView dataset, not a mutable definition.

SavedChart is a user's label/mode/selection and chart-definition version reference; it is not a copied chart implementation. A document chart block stores the same canonical definition reference plus selected context. ResolvedContext pins exact dataset/metric/renderer versions and selection hash. Snapshot adds an immutable private object and rendered/data artifacts for explicit P1 management. P0 document save pins already preserve reproducibility.

## Initial catalog (only publish when inputs validate)

| chart_id | Question / metrics | Visualization / qualification |
| --- | --- | --- |
| intents-volume | Is activity growing? provider_intents_volume_usd | Daily line/area, source-qualified; provider turnover not token value |
| gross-fees | What gross fees are reported? provider_gross_fees_usd | Daily bars/line; accrual definitions and revisions visible |
| observed-conversions | How much NEAR was acquired by the observed cohort? observed_near_purchases, conversion_count | Separate aligned panels; no dual-axis implication |
| treasury-payouts | What cash transfers reached selected wallets? treasury_payouts_near | Bars by allowed wallet filter; excludes internal hops |
| quantity-usd-sensitivity | Does price explain token quantity changes? observed_near_purchases, estimated_purchase_usd | Indexed comparison only with explicitly chosen base; accessible raw-value table; estimate badge |
| supply-context | How large are purchases relative to supply growth? net_supply_change_near, observed_near_purchases | Matched-period bars/table; scale comparison, no subtraction from total supply |
| fee-volume-association | Is the fee relationship mechanical? provider_intents_volume_usd, provider_gross_fees_usd | Scatter with date labels and published-model overlay only if fitted |
| model-diagnostics | Are residuals consistent with specification? published model artifact | Residual/time/ACF panels from run ID, never invented plot values |

Exact protocol revenue, capture-rate and fee-funded-buyback charts stay unavailable until their metric gates pass. Do not create apparent history from monthly values or publish a trend from three windows as a fitted model.

## Query/render contract

ChartView resolves one approved prepared dataset containing required metric versions. `start/end/frequency/filters` are validated centrally; date range≤366 days initially. Default presets7/30/90 days relative to latest complete observation, not wall-clock if historical. A custom range outside coverage shows missing values, explains overlap and does not silently shrink. Supported filters include approved recipient/source mappings only; unknown options rejected. Currency switch chooses an actual alternative metric/calculation context.

Query keys include chart definition ID/version, dataset version, canonical selection and metric versions. Latest pointer resolution ≤60s cache; immutable versions cache by content hash. TanStack Query deduplicates identical public requests; private saved metadata no-store and cache cleared on logout. Never cache arbitrary user filters under a shared incomplete key.

Plot adapter receives normalized typed series, not provider responses. Use ECharts modular imports and SVG renderer where possible; no SSR import through browser globals. Lazy mount visible charts, debounce user range requests, cancel stale requests, preserve last successful plot with refreshing badge. Axis units/zero/truncation explicit; avoid dual axes unless a documented need and clear labels. No interpolation across missing flows; bounds displayed as bounds, not exact bars. Tooltips show date/time convention, unit, exact source value and estimate/bound label.

## Interaction, provenance and accessibility

Every frame includes definitions, sources and lineage, last observation/retrieval times, quality, mode, permitted actions and an equivalent data table. Keyboard range controls and point/table inspection must work; charts cannot require hover. Source drawer links metric formula and sanitized manifest. Enable ECharts ARIA component explicitly and add concise manual summary/table; [official ARIA guidance](https://echarts.apache.org/handbook/en/best-practices/aria/) does not imply fully keyboard-operable charts automatically.

States: loading skeleton; refreshing with last good; empty confirmed no observations; missing/incomplete coverage; stale historical/live; unavailable source; query validation error; reconstruction error for missing pinned artifact. Do not show zero in a KPI because plot array is empty.

Save Chart creates an owned instance. Add to Research validates destination and appends chart block using inspected immutable dataset version. Add Insight stores inspected context, not whatever chart happens to show on the next refresh. Refresh is an explicit latest-version query for a live view; snapshot/historical view offers “compare to latest” rather than overwriting.

## Static export and reproducibility

Implement a pure chart-option builder shared by browser and `apps/web/scripts/render-charts.mjs`. Node ECharts SSR renders bounded validated data into SVG without DOM/network/user HTML. Python export worker invokes this fixed renderer as a subprocess with typed JSON stdin, no shell; export image includes the Node package/lock. Include renderer version, dataset hash, selection/config hash and source references in manifest. If SVG is unsupported by a future PDF path, convert via a reviewed rasterizer without changing series data.

Archive chart-ready CSV/normalized series with each exported chart. Exact-data/hash reconstruction is required; pixel identity across platforms is not. Text/table renderers consume the same frozen series. Required tests: definition→query→render path reused across public/editor/export; gap/bounds/large-number handling; URL filters validation; table equality; source revision leaves old export unchanged; selected chart interactions do not break editor keyboard selection.
