"""Documentation-qualified candidates, all operationally disabled.

No historical artifact is asserted present in a fresh checkout. Empty coverage
and schema hashes deliberately stay unknown until actual inputs are verified.
"""

from types import MappingProxyType

from .models import SourceCapability


def _candidate(source_id: str, url: str, auth: str, **fields: object) -> SourceCapability:
    return SourceCapability.model_validate({
        "source_id": source_id,
        "documentation_url": url,
        "auth": auth,
        "blockers": ("OQ-03",),
        **fields,
    })


SOURCES = MappingProxyType({source.source_id: source for source in (
    _candidate("SRC-NEAR-RPC", "https://docs.near.org/api/rpc/providers", "none",
               endpoint="https://free.rpc.fastnear.com", method="POST"),
    _candidate("SRC-BQ", "https://docs.cloud.google.com/bigquery/public-data", "cloud_identity"),
    _candidate("SRC-INTENTS", "https://docs.near-intents.org/llms.txt", "bearer",
               blockers=("OQ-01", "OQ-03", "OQ-08")),
    _candidate("SRC-LLAMA", "https://docs.llama.fi/pro-api", "unverified",
               lineage=("SRC-DUNE",), blockers=("OQ-01", "OQ-03", "OQ-11")),
    _candidate("SRC-DASHBOARD", "https://revenue.near.org/", "unverified",
               blockers=("OQ-01", "OQ-03", "OQ-11")),
    _candidate("SRC-DUNE", "https://docs.dune.com/api-reference/overview/authentication", "api_key",
               blockers=("OQ-01", "OQ-03", "OQ-11")),
    _candidate("SRC-PRICE", "https://docs.coingecko.com/reference/coins-id-market-chart-range", "api_key"),
    _candidate("SRC-FASTNEAR", "https://fastnear.com/", "unverified"),
    _candidate("SRC-NEARBLOCKS", "https://nearblocks.io/", "unverified",
               blockers=("OQ-03", "OQ-10")),
    _candidate("SRC-GOV", "https://www.near.org/blog/evolving-near-tokenomics", "none",
               blockers=("OQ-01",)),
)})
