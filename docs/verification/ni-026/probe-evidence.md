# NI-026 bounded finalized-header probe evidence

Role B, dispatch #4, Claude agent. Operator authorization: OQ-03 RESOLVED
2026-11-06 (operator ILYUTKICK, recorded in [OPEN_QUESTIONS.md](../../OPEN_QUESTIONS.md)
and [PR #27](https://github.com/ILYUTKICK/near-intelligence/pull/27)): one bounded
probe against the public NEAR mainnet RPC, budget 0, header-only response with the
implemented byte caps, public on-chain header data. No other source was contacted;
no retry, pagination or second request was permitted or made.

## Observation

| Field | Value |
| --- | --- |
| Request time (UTC) | 2026-11-06T19:13:45Z (`retrieved_at` 2026-11-06T19:13:45.258335Z) |
| Endpoint | `https://rpc.mainnet.near.org` |
| Method | `POST`, JSON-RPC 2.0, `{"method": "block", "params": {"finality": "final"}}` |
| Auth | none (no account, key or credential exists or was transmitted) |
| HTTP status | 200 (the probe returns only on 200; any other status raises `ProbeFailed` without retry) |
| Response size | 18 496 bytes (response body, identity encoding, stream-consumed) |
| Approved byte cap | 65 536 bytes per the single-use `ProbeApproval` — cap respected, oversized bodies would abort before parsing |
| Block height (final) | 223357966 |
| Block hash (final) | `7gsbtD5R8A2hasDzVDXWF6hdnV6kKL4VW3Sg5QCXBwZo` |
| Block timestamp | `timestamp_nanosec` = `1793992425071630189` = 2026-11-06T19:13:45Z |
| Total supply (raw) | `1311012246333893718750000181969746` yoctoNEAR (integer decimal string; ≈ 1 311 012 246.33 NEAR — display conversion only, the stored value is the raw string) |
| Response SHA-256 | `906932e1f9eec24d37e8a40baffb91b5f37d7dc1fb5ad199d54e73ad29ce7821` |

Block height, hash, timestamp and total supply are public on-chain header facts.

## Boundary compliance

- Exactly one network request. The `HeaderProbe` instance is single-use; reuse
  raises `ProbeDenied`. The driver called `run()` once with no retry logic;
  local `requests_per_day` cap was 1 and `max_requests` was 1.
- The request went through the guarded implementation
  `apps/api/src/near_api/ingestion/capabilities/probe.py` with the approved
  source record in `registry.py`: no redirect (`follow_redirects=False`),
  no retries, no environment proxies (`trust_env=False`), identity encoding
  enforced, byte cap enforced while streaming, non-200 and JSON-RPC errors fail
  closed without exposing provider messages.
- Output sanitization: the recorded result is the fixed sanitized
  `FinalizedHeader` field set above. Provider headers, JSON-RPC envelopes and
  any unexpected response fields are excluded; no secret exists in the flow
  (auth type none) and none appears in this file.
- Sources contacted in this session: only this endpoint (one request) and the
  documentation page `https://docs.near.org/api/rpc/providers` (link check the
  dispatch requested). The dispatch's singular variant
  `https://docs.near.org/api/rpc/provider` returned HTTP 404 on 2026-11-06; the
  plural `providers` page is live and is the recorded rights/documentation
  evidence.
- No SQL, paid service, bulk collection, collector restart, research archive
  access or repository change outside the NI-026 scope occurred.

## Reproduction

This is a single-use observation, not a repeatable command: rerunning it would
be a new provider request and needs a fresh operator approval. The implementation
check that guards this path is the offline suite
(`PYTHONPATH=apps/api/src apps/api/.venv/bin/python -m unittest discover -s apps/api/tests`),
12 capability/guard tests with mock transports, all passing on 2026-11-06.
The one-shot driver used for the request stays outside the repository as
operator process state; the committed code, registry and caps fully determine
its behavior.
