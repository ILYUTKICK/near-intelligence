"""Capability evidence records.

SRC-NEAR-RPC carries the 2026-11-06 operator authorization (OQ-03 RESOLVED,
PR #27): the public NEAR mainnet RPC is approved for bounded finalized-header
polling at zero cost with public on-chain header data. Its single-use probe
evidence lives in docs/verification/ni-026/probe-evidence.md.
Every other candidate stays documentation-qualified and operationally disabled
with its recorded OQ blockers. No historical artifact is asserted present in a
fresh checkout; empty coverage and schema hashes deliberately stay unknown
until actual inputs are verified.
"""

from types import MappingProxyType

from .models import SourceCapability

NEAR_RPC_PROVIDER_DOCS = "https://docs.near.org/api/rpc/providers"
OPERATOR_OQ03_APPROVAL = (
    "https://github.com/ILYUTKICK/near-intelligence/blob/main/docs/OPEN_QUESTIONS.md"
)


def _candidate(source_id: str, url: str, auth: str, **fields: object) -> SourceCapability:
    return SourceCapability.model_validate({
        "source_id": source_id,
        "documentation_url": url,
        "auth": auth,
        "blockers": ("OQ-03",),
        **fields,
    })


SOURCES = MappingProxyType({source.source_id: source for source in (
    SourceCapability.model_validate({
        "source_id": "SRC-NEAR-RPC",
        "documentation_url": NEAR_RPC_PROVIDER_DOCS,
        "endpoint": "https://rpc.mainnet.near.org",
        "method": "POST",
        "auth": "none",
        "access_verified": True,
        "quota_evidence_url": OPERATOR_OQ03_APPROVAL,
        "rights": "approved",
        "rights_evidence_url": NEAR_RPC_PROVIDER_DOCS,
    }),
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
