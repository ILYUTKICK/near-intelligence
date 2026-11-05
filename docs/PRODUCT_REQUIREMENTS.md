# Product requirements

Version 1.0 • 5 November 2026 • normative planned behavior. Related: [scope](MVP_SCOPE.md), [features](FEATURE_SPECIFICATIONS.md), [journeys](USER_JOURNEYS.md).

## Problem, audience and outcome

Blockchain adoption statistics do not by themselves establish investment value. Researchers need to trace activity through fees, economically attributable revenue, conversion into NEAR, treasury retention and actual supply effects, while preserving the evidence used in a thesis. NEAR Intelligence combines public original research, shared analytical data and private research authoring.

Primary audiences: hackathon reviewer reproducing a finding; individual analyst checking the thesis; investor recording an independent counterargument. The core output is an evidence-backed document, not a price target, trading signal, portfolio tracker or chatbot.

The public thesis is mandatory. A generic workspace without published research does not meet the challenge. A static presentation with no working analytics/editor does not meet the product requirement.

## Requirements and traceability

| ID | Requirement | Priority | Acceptance outcome | Owning tasks |
| --- | --- | --- | --- | --- |
| PR-01 | Public landing, original thesis and methodology | P0 | Anonymous visitor reads findings and traces a claim to calculation | NI-011–NI-015, NI-070 |
| PR-02 | Real shared analytics with definitions and timestamps | P0 | Public/private views return the same dataset and values for identical queries | NI-026–NI-035 |
| PR-03 | Conditional H1–H4 assessment including contradictory evidence | P0 | Each hypothesis has status, evidence scope, limitation and falsification condition | NI-014, NI-070 |
| PR-04 | Independent private users and sessions | P0 | Alice cannot enumerate/read/mutate/export Bob's resources | NI-016–NI-020, NI-062 |
| PR-05 | Research-oriented workspace shell/home | P0 | User resumes a recent persisted document within two actions | NI-021–NI-025 |
| PR-06 | Searchable reusable chart catalog and saved chart instances | P0 | Save/reopen preserves chart version, range and allowed filters | NI-031–NI-035 |
| PR-07 | Block editor and persistent versioned documents | P0 | Create, rename, reorder, duplicate, remove, save and reopen work | NI-036–NI-040 |
| PR-08 | Add Chart and Add Insight with evidence context | P0 | Correct owner, block, time window and dataset survive reopen | NI-041–NI-050 |
| PR-09 | Deterministic quantitative research and public results | P0 | Clean offline execution reproduces published model metadata and statistics | NI-051–NI-055 |
| PR-10 | Stable saved evidence and export | P0 | Revision/export contains exact referenced data, charts, notes and sources | NI-043, NI-056–NI-058 |
| PR-11 | Deployment and complete demonstration | P0 | Fresh user completes read → data → chart → insight → document → export | NI-066–NI-070 |
| PR-12 | Templates, public duplication and model-result embedding | P1 | Independent copies retain immutable public data references | NI-044–NI-045, NI-055 |
| PR-13 | PDF, advanced filters and sharing | P1/P2 | PDF P1; read-only sharing P2 with separate permissions | NI-059–NI-060, NI-071 |
| PR-14 | Advisory integrity checks and AI assistance | P2 | Optional; metadata checks separated from interpretations | NI-065 |

## Evidence contract

Every displayed quantitative claim stores a citation to an immutable research artifact or metric calculation, with data scope, units, observation time, retrieval time, definition version and status. Distinguish provider-reported observations, independently reconciled observations, estimates, lower/upper bounds and user assumptions. Never calculate a ratio across unmatched units or silently allocate monthly revenue into daily values.

Current research supports regular observed NEAR conversions/payouts within a bounded cohort. It does not establish that all conversions are fee-funded or that value capture offsets issuance. [Investment thesis](INVESTMENT_THESIS.md) is the initial editorial foundation; it contains no invented regression results.

## Nonfunctional acceptance targets

- Ownership: all private operations are server-authorized; zero cross-user leaks in adversarial tests. Encryption in transit and managed backups are release requirements.
- Reproducibility: frozen input manifest, pipeline/model code, resolved dependency lock, config and deterministic command for every published run. Missing inputs block publication.
- Accessibility: WCAG 2.2 AA target; keyboard flows and chart table equivalents; no information by color alone. Verify actual token combinations.
- Responsiveness: 360 px phone, 768 px tablet and 1440 px desktop tested; only explicit data tables/plots may scroll horizontally.
- Initial performance budgets: public LCP ≤2.5s under documented test conditions; document load ≤2s for 200 blocks/20 mounted chart references on a warm service; chart series p95 ≤800ms for 366 daily points at 10 concurrent clients. These are acceptance targets, not measurements.
- Reliability: failed refresh leaves last good version intact and marked stale; editor never reports saved before an acknowledged revision. Autosave recovers conflicts without overwriting another tab.
- Maintenance: no duplicated economic definitions, no arbitrary user code, no mandatory LLM services.

## Product success and release

Measure successful claim-to-source traces, completed research documents, save/reopen reliability, export success and reviewer reproduction, without collecting document text in analytics. A walkthrough must include a contradicting finding and an unavailable metric. [MVP gates](MVP_SCOPE.md) determine release; optional enhancements cannot substitute for missing P0 evidence or authorization.
