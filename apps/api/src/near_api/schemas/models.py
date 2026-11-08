"""NI-054 public model contracts: definitions, readiness verdicts and
published runs.

These models pin the response side of the API_SPECIFICATION "Snapshots, models
and public research" rows implemented here (``/model-definitions``,
``/model-definitions/{modelId}/readiness``, ``/model-runs``, ``/model-runs/
{runId}``, ``/model-runs/{runId}/manifest``). Every response is a projection
of an immutable published ``app.model_runs`` row written exclusively by the
NI-054 operator publication gate — no response is ever derived by running a
model, and no route in this package imports the research package.

Implemented deltas recorded in API_SPECIFICATION.md:

- ``ModelDefinition.question`` is mechanically composed from the
  preregistered specification's declared fields (declared target, explanatory
  metric ids, family, baseline) with one fixed template — it describes what
  the specification declares it estimates and is never an authored economic
  claim. Definitions exist publicly only when a run for that specification is
  published; an unpublished or gate-rejected specification has no public
  definition (404, no existence leak).
- The readiness endpoint serves the NI-051 gate verdict for the specification
  as recorded in the readiness report of the latest published run (the full
  gate report travels inside every published bundle). The specification's
  ``dataset_version`` query parameter is not implemented: published runs bind
  the offline archive manifests recorded in their data manifests, not a
  database dataset version; a dataset-bound readiness check stays with its
  owning future task.
- Statistical coefficients are finite float64 numbers by the recorded
  DATABASE_SCHEMA numeric policy (``allow_inf_nan`` is False at the contract
  boundary; the publication gate already refuses non-finite values). Financial
  aggregates remain decimal strings elsewhere in the API; nothing here is a
  money amount.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field
from typing import Annotated
from pydantic import StringConstraints

from near_api.schemas.common import ContractModel

SPEC_ID_PATTERN = r"^[a-z][a-z0-9_]{2,79}$"
SHA256_HEX = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")]

# The manifest-bundle document shape (the downloadable reproduction bundle and
# the document ``research verify`` accepts offline). Defined in the shared
# contracts module so the publication gate (writer) and the public API
# (reader) cannot drift; the API never imports the research package.
BUNDLE_TYPE = "model_run_manifest_bundle"
BUNDLE_VERSION = 1

GateVerdict = Literal["READY", "READY_WITH_LIMITS"]
FiniteFloat = Field(float, allow_inf_nan=False)


class CoefficientResponse(ContractModel):
    """One recorded coefficient of a published fit (API_SPECIFICATION ``ModelRun``
    ``coefficients`` row: term/estimate/standard_error/ci bounds/p_value).

    Values are the fit manifest's finite float64 records verbatim; the
    publication gate refuses NaN/Infinity, so a published coefficient is
    always finite. ``p_value`` is recorded evidence, never a selection input.
    """

    name: str = Field(min_length=1, max_length=120)
    estimate: Annotated[float, FiniteFloat]
    std_error: Annotated[float, FiniteFloat]
    t_stat: Annotated[float, FiniteFloat]
    p_value: Annotated[float, FiniteFloat]
    ci95_low: Annotated[float, FiniteFloat]
    ci95_high: Annotated[float, FiniteFloat]


class ReasonCodeResponse(ContractModel):
    """One NI-051 gate reason code, verbatim (code, severity, detail)."""

    code: str = Field(min_length=1, max_length=80)
    severity: Literal["rejecting", "limit", "informational"]
    detail: str = Field(min_length=1)


class RunSampleResponse(ContractModel):
    """The published sample window and size (half-open, gate-exact)."""

    start: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    end_exclusive: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    nobs: int = Field(strict=True, ge=1)


class TolerancesResponse(ContractModel):
    """The declared reproduction tolerances of a published fit."""

    coefficient_rtol: str = Field(pattern=r"^[0-9]+(\.[0-9]+)?$")
    coefficient_atol: str = Field(pattern=r"^[0-9]+(\.[0-9]+)?$")


class LimitationsResponse(ContractModel):
    """Limitations attached verbatim to the published run."""

    prohibited_labels: tuple[str, ...] = Field(min_length=1)
    spec_limitation_notes: tuple[str, ...] = Field(min_length=1)
    gate_limit_codes: tuple[str, ...] = Field(default=())


class ApprovalResponse(ContractModel):
    """The recorded operator review provenance of a published run."""

    decision: Literal["approve"]
    reviewer: str = Field(min_length=1, max_length=200)
    review_reference: str = Field(min_length=1, max_length=300)
    reviewed_at: str | None = None
    notes: str | None = None


class ModelRunSummaryResponse(ContractModel):
    """One published run in the catalog (API_SPECIFICATION ``/model-runs`` row).

    The catalog lists published runs only; unpublished, failed or rejected
    runs do not exist in the backing table and are indistinguishable from
    absent ones.
    """

    run_id: UUID
    model_id: str = Field(pattern=SPEC_ID_PATTERN)
    model_version: int = Field(strict=True, ge=1)
    gate_verdict: GateVerdict
    sample: RunSampleResponse
    tolerances: TolerancesResponse
    code_commit: str = Field(pattern=r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
    manifest_url: str = Field(min_length=1)
    published_at: datetime
    published_by: str = Field(min_length=1, max_length=120)


class ModelRunListResponse(ContractModel):
    items: tuple[ModelRunSummaryResponse, ...]
    next_cursor: str | None


class ModelRunDetailResponse(ModelRunSummaryResponse):
    """One published run with its recorded results.

    Every block is a projection of the verified manifests stored on the row:
    the specification and design verbatim, the coefficient table, the
    estimation summary, the NI-053 diagnostics battery, the template-rendered
    interpretation, the limitations verbatim, the recorded environment and
    reproduction contract, and the review approval. The full manifest set is
    downloadable at ``manifest_url``.
    """

    specification: dict[str, object]
    admission_reasons: tuple[ReasonCodeResponse, ...] = ()
    design: dict[str, object]
    estimation: dict[str, object]
    coefficients: tuple[CoefficientResponse, ...] = Field(min_length=1)
    diagnostics: dict[str, object]
    interpretation: dict[str, object]
    limitations: LimitationsResponse
    environment: dict[str, object]
    reproduction: dict[str, object]
    approval: ApprovalResponse


class ModelDefinitionResponse(ContractModel):
    """One public model definition (API_SPECIFICATION ``ModelDefinition`` row).

    Served from the latest published run of the specification: an unpublished
    or rejected specification has no public definition. ``question`` is
    mechanically composed from the specification's declared fields (see the
    module docstring) — never an authored claim.
    """

    id: UUID
    model_id: str = Field(pattern=SPEC_ID_PATTERN)
    version: int = Field(strict=True, ge=1)
    question: str = Field(min_length=1, max_length=500)
    specification: dict[str, object]
    required_metric_ids: tuple[str, ...] = Field(min_length=1, max_length=16)
    readiness_rules: dict[str, object]
    limitations: LimitationsResponse
    latest_published_run_id: UUID


class ModelDefinitionListResponse(ContractModel):
    items: tuple[ModelDefinitionResponse, ...]
    next_cursor: str | None


class ModelReadinessResponse(ContractModel):
    """The NI-051 gate verdict for one specification (public readiness record).

    ``ready`` is true only for the admitted verdicts; every reason code the
    gate recorded travels verbatim, and ``recorded_in_run_id`` names the
    published run whose readiness report carries the verdict. A specification
    never evaluated by a published readiness report is 404 — an unpublished
    gate report never looks like a verdict.
    """

    model_id: str = Field(pattern=SPEC_ID_PATTERN)
    ready: bool
    verdict: str = Field(min_length=1, max_length=40)
    reasons: tuple[ReasonCodeResponse, ...] = ()
    overall_verdict: str = Field(min_length=1, max_length=60)
    selected_specification: str | None = None
    recorded_in_run_id: UUID
