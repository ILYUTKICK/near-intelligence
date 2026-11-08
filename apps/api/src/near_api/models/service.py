"""NI-054 public model service: read-only projections of published runs.

Every function here reads immutable ``app.model_runs`` rows through the
unprivileged ``near_app`` role (NI-032 delivery pattern) and projects them
into the response contracts. Nothing runs a model: the module imports no
research code, opens no network connection and holds no cache of unpublished
state — published rows are the only state that exists. Projections are
mechanical: values recorded by the publication gate are served verbatim
(exact strings where recorded as strings, finite floats for statistical
coefficients), missing values stay absent and nothing is fabricated.

Definitions and readiness verdicts are projections of published bundles too:
a specification has a public definition exactly when a run for it is
published, and its readiness verdict is read from the readiness report inside
the latest published bundle. Unpublished or gate-rejected specifications are
``None`` — the routes turn that into the generic 404 with no existence leak.
"""

from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Connection, text

from near_api.schemas.models import (
    ApprovalResponse,
    BUNDLE_TYPE,
    BUNDLE_VERSION,
    CoefficientResponse,
    LimitationsResponse,
    ModelDefinitionResponse,
    ModelReadinessResponse,
    ModelRunDetailResponse,
    ModelRunSummaryResponse,
    ReasonCodeResponse,
    RunSampleResponse,
    TolerancesResponse,
)

# Deterministic definition identity, derived exactly like the metric registry
# identities (metric id + version): a definition UUID never encodes review or
# publication time, only the specification it names.
DEFINITION_ID_DOMAIN = "near-intelligence:model-definition:v1:"

_MAX_DEFINITION_QUESTION_LENGTH = 500


class ModelNotFoundError(Exception):
    """No published row exists for the requested identity (generic 404)."""


def _row_manifests(row) -> dict:
    """The verified manifest set stored on one published row."""
    manifests = row["manifests"]
    if not isinstance(manifests, dict) or "fit_manifest" not in manifests:
        # Fail closed: a row that lost its manifest set is not a servable
        # result (the gate-writes-only invariant makes this unreachable).
        raise ModelNotFoundError("published row carries no manifest set")
    return manifests


def _question(specification: dict) -> str:
    """Compose the definition question from declared specification fields.

    One fixed template over the preregistered specification's own declared
    fields; no authored economic wording is ever generated here.
    """
    explanatory = specification.get("explanatory_variables") or []
    metric_ids = ", ".join(str(variable.get("metric_id"))
                           for variable in explanatory if variable.get("metric_id"))
    dependent = specification.get("dependent_variable") or {}
    question = (
        f"Association of the declared target {specification.get('declared_target')} "
        f"with {metric_ids or 'no explanatory variable'} "
        f"({specification.get('frequency')} frequency, family "
        f"{specification.get('family')}, baseline {specification.get('baseline')}); "
        "the specification declares association only, never causality."
    )
    return question[:_MAX_DEFINITION_QUESTION_LENGTH]


def _limitations_response(limitations: dict) -> LimitationsResponse:
    return LimitationsResponse(
        prohibited_labels=tuple(limitations.get("prohibited_labels") or ()),
        spec_limitation_notes=tuple(limitations.get("spec_limitation_notes") or ()),
        gate_limit_codes=tuple(limitations.get("gate_limit_codes") or ()),
    )


def _sample_response(fit: dict) -> RunSampleResponse:
    window = fit["sample"]["window"]
    return RunSampleResponse(start=window["start"],
                             end_exclusive=window["end_exclusive"],
                             nobs=int(fit["sample"]["nobs"]))


def _summary_response(row) -> ModelRunSummaryResponse:
    fit = _row_manifests(row)["fit_manifest"]
    return ModelRunSummaryResponse(
        run_id=row["run_id"],
        model_id=fit["model"]["model_id"],
        model_version=int(fit["model"]["model_version"]),
        gate_verdict=fit["admission"]["verdict"],
        sample=_sample_response(fit),
        tolerances=TolerancesResponse(
            coefficient_rtol=fit["reproduction"]["coefficient_rtol"],
            coefficient_atol=fit["reproduction"]["coefficient_atol"]),
        code_commit=fit["inputs"]["code_commit"],
        manifest_url=f"/api/model-runs/{row['run_id']}/manifest",
        published_at=row["published_at"],
        published_by=row["published_by"],
    )


def list_published_runs(connection: Connection, *, limit: int, offset: int,
                        model_id: str | None = None) -> tuple[list[dict], int]:
    """Published run rows newest-first (stable order: published_at, run_id)."""
    # The optional filter is composed server-side as two closed statements
    # (a bind-in-Cast would be the only way to make one optional predicate;
    # both statements are parameterless beyond the bounded page values).
    if model_id is None:
        total = connection.execute(
            text("SELECT count(*) FROM app.model_runs")).scalar_one()
        rows = connection.execute(text("""
            SELECT run_id, spec_id, published_at, published_by, manifests
            FROM app.model_runs
            ORDER BY published_at DESC, run_id
            LIMIT :limit OFFSET :offset
        """), {"limit": limit, "offset": offset}).mappings().all()
    else:
        total = connection.execute(text("SELECT count(*) FROM app.model_runs "
                                        "WHERE spec_id = :spec_id"),
                                   {"spec_id": model_id}).scalar_one()
        rows = connection.execute(text("""
            SELECT run_id, spec_id, published_at, published_by, manifests
            FROM app.model_runs WHERE spec_id = :spec_id
            ORDER BY published_at DESC, run_id
            LIMIT :limit OFFSET :offset
        """), {"spec_id": model_id, "limit": limit, "offset": offset}).mappings().all()
    return list(rows), int(total)


def get_published_run_row(connection: Connection, run_id: UUID) -> dict | None:
    """One published row or ``None``; absent and unknown are the same."""
    row = connection.execute(text("""
        SELECT run_id, spec_id, spec_version, gate_verdict, status, manifests,
               artifacts, publication_approval, code_commit,
               dependency_lock_sha256, coefficient_rtol, coefficient_atol,
               sample_start, sample_end_exclusive, nobs, published_by, published_at
        FROM app.model_runs WHERE run_id = :run_id
    """), {"run_id": str(run_id)}).mappings().first()
    return dict(row) if row is not None else None


def run_summary(row) -> ModelRunSummaryResponse:
    return _summary_response(row)


def run_detail(row) -> ModelRunDetailResponse:
    """The full published-run projection (manifest-derived, nothing re-run)."""
    manifests = _row_manifests(row)
    fit = manifests["fit_manifest"]
    diagnostics = manifests["diagnostics_report"]
    approval = row["publication_approval"]
    coefficients = tuple(
        CoefficientResponse(
            name=entry["name"], estimate=entry["estimate"], std_error=entry["std_error"],
            t_stat=entry["t_stat"], p_value=entry["p_value"],
            ci95_low=entry["ci95_low"], ci95_high=entry["ci95_high"])
        for entry in fit["coefficients"])
    reasons = tuple(
        ReasonCodeResponse(code=entry["code"], severity=entry["severity"],
                           detail=str(entry.get("detail") or ""))
        for entry in fit["admission"].get("reason_codes") or ())
    approval_response = ApprovalResponse(
        decision=approval["decision"],
        reviewer=str(approval["reviewer"]),
        review_reference=str(approval["review_reference"]),
        reviewed_at=approval.get("reviewed_at"),
        notes=approval.get("notes"),
    )
    return ModelRunDetailResponse(
        **_summary_response(row).model_dump(),
        specification=fit["model"]["specification"],
        admission_reasons=reasons,
        design=fit["design"],
        estimation=fit["estimation"],
        coefficients=coefficients,
        diagnostics={
            "stationarity": diagnostics.get("stationarity", {}),
            "residual_diagnostics": diagnostics.get("residual_diagnostics", {}),
            "sensitivity": diagnostics.get("sensitivity", {}),
            "diagnostics_config": diagnostics.get("diagnostics_config", {}),
        },
        interpretation=diagnostics.get("interpretation", {}),
        limitations=_limitations_response(fit["limitations"]),
        environment=fit.get("environment", {}),
        reproduction=fit.get("reproduction", {}),
        approval=approval_response,
    )


def manifest_bundle(row) -> dict:
    """The canonical downloadable bundle document (verify accepts it offline).

    Same shape as the operator's published bundle: the three manifests, the
    per-artifact SHA-256 map and the recorded approval, identified by the
    content-derived ``run_id``. Assembled from the row only — no research
    import, no recomputation.
    """
    manifests = _row_manifests(row)
    return {
        "bundle_type": BUNDLE_TYPE,
        "bundle_version": BUNDLE_VERSION,
        "run_id": str(row["run_id"]),
        "spec_id": row["spec_id"],
        "manifests": manifests,
        "artifact_sha256": dict(row["artifacts"]),
        "approval": dict(row["publication_approval"]),
    }


def _latest_run_per_model(connection: Connection) -> list[dict]:
    """The newest published row per (spec_id, spec_version), ordered by spec."""
    rows = connection.execute(text("""
        SELECT DISTINCT ON (spec_id, spec_version)
               run_id, spec_id, spec_version, manifests, published_at
        FROM app.model_runs
        ORDER BY spec_id, spec_version, published_at DESC, run_id DESC
    """)).mappings().all()
    return [dict(row) for row in rows]


def definition_id(model_id: str, version: int) -> UUID:
    return uuid5(NAMESPACE_URL, f"{DEFINITION_ID_DOMAIN}{model_id}:{version}")


def definition_response(row) -> ModelDefinitionResponse:
    manifests = _row_manifests(row)
    fit = manifests["fit_manifest"]
    specification = fit["model"]["specification"]
    dependent = specification.get("dependent_variable") or {}
    explanatory = specification.get("explanatory_variables") or []
    required = [str(variable["metric_id"]) for variable in explanatory
                if variable.get("metric_id")]
    if dependent.get("metric_id"):
        required.insert(0, str(dependent["metric_id"]))
    readiness_report = manifests["readiness_report"]
    policy = readiness_report.get("policy") or {}
    version = int(fit["model"]["model_version"])
    model_id = fit["model"]["model_id"]
    return ModelDefinitionResponse(
        id=definition_id(model_id, version),
        model_id=model_id,
        version=version,
        question=_question(specification),
        specification=specification,
        required_metric_ids=tuple(required),
        readiness_rules=policy,
        limitations=_limitations_response(fit["limitations"]),
        latest_published_run_id=row["run_id"],
    )


def list_model_definitions(connection: Connection, *, limit: int,
                           offset: int) -> tuple[list[ModelDefinitionResponse], int]:
    rows = _latest_run_per_model(connection)
    return [definition_response(row) for row in rows[offset:offset + limit]], len(rows)


def get_model_definition(connection: Connection, model_id: str,
                         *, version: int | None = None) -> ModelDefinitionResponse | None:
    """The definition for one specification (latest published by default)."""
    for row in _latest_run_per_model(connection):
        if row["spec_id"] != model_id:
            continue
        if version is None or int(row["spec_version"]) == version:
            return definition_response(row)
    return None


def get_model_readiness(connection: Connection, model_id: str) \
        -> ModelReadinessResponse | None:
    """The NI-051 gate verdict for one specification from a published bundle.

    The verdict is read from the readiness report of the newest published run
    whose gate evaluated the specification (every bundle carries the full
    report). A specification never evaluated in a published bundle is ``None``.
    """
    rows = connection.execute(text("""
        SELECT run_id, manifests FROM app.model_runs
        ORDER BY published_at DESC, run_id
    """)).mappings().all()
    for row in rows:
        manifests = _row_manifests(row)
        readiness_report = manifests.get("readiness_report") or {}
        selection = readiness_report.get("selection") or {}
        for entry in readiness_report.get("spec_evaluations") or []:
            spec = entry.get("spec") if isinstance(entry, dict) else None
            if not isinstance(spec, dict) or spec.get("spec_id") != model_id:
                continue
            overall = selection.get("overall_verdict")
            if not isinstance(overall, str) or not overall:
                # Fail closed: a readiness report without its overall verdict
                # is not a servable verdict (the gate rejects such bundles).
                raise ModelNotFoundError("published readiness report is incomplete")
            return ModelReadinessResponse(
                model_id=model_id,
                ready=entry.get("verdict") in ("READY", "READY_WITH_LIMITS"),
                verdict=str(entry.get("verdict")),
                reasons=tuple(
                    ReasonCodeResponse(code=code["code"], severity=code["severity"],
                                       detail=str(code.get("detail") or ""))
                    for code in entry.get("reason_codes") or ()
                    if isinstance(code, dict) and code.get("code")),
                overall_verdict=overall,
                selected_specification=selection.get("selected_spec"),
                recorded_in_run_id=row["run_id"],
            )
    return None
