# Current local preview — NI-089 recovery

The intended current desktop site is **http://localhost:13002/**, served by the
`near-deploy-web-1` local container from `/Users/ilyutkinn/Desktop/near-deploy`.
It has the approved Overview and Blog navigation. The source baseline for this
recovery is commit `13e9d0c` (local changes are recorded in NI-089).

`http://localhost:13000/` is an obsolete `local/owner-review` development stack
at `/Users/ilyutkinn/Desktop/near-intelligence-review`. It lacks the newer Blog,
Overview, article navigation and integrated product. This chat initially edited
that older stack by mistake. Do not use it as the current product or copy its
page/layout/navigation files into the current checkout.

The current article retains its existing title/emphasis, sticky contents,
hypothesis links, interactive comparisons, long history and duplication action.
Only the reviewed wording of nine recorded findings and their quiet source
control were transferred. Quantities, current dataset references, definitions,
source records and research limits are preserved.

The web runtime image must include `apps/web/public`; otherwise the approved
Overview illustration is absent even though the CSS and page render. Local
recovery rebuilds and recreates only the web service. It does not run migrations,
replace the database/API, enable collectors or publish to external hosting.
