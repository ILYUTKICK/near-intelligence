"""NI-054: the operator publication gate for offline model artifacts.

This module is the OFFLINE core of publication: it loads a run bundle (the
NI-051 readiness report, the NI-052 fit manifest, the NI-053 diagnostics
report and the operator's explicit publication approval), verifies the full
data/code/lock/config/design/result manifest set fail-closed, and derives the
immutable run identity. The database write lives in
:mod:`near_api.research.publish_store` and runs only after every check here
passes; the public API (:mod:`near_api.models`) only ever reads the rows this
gate wrote and imports nothing from the research package — so no endpoint can
trigger a fit or a provider call by construction.

A run bundle is one of:

- a bundle DIRECTORY holding ``fit_manifest.json``,
  ``diagnostics_report.json``, ``readiness_report.json`` and
  ``publication_approval.json`` (the local operator layout), or
- a single JSON FILE with the canonical published-bundle document served by
  ``GET /api/model-runs/{run_id}/manifest`` (same shape, so a reviewer can
  re-verify a downloaded bundle offline with ``research verify``).

Review approval mechanics (the recorded justification for the approve file):
publication is an operator CLI flow (API_SPECIFICATION: "Creating
datasets/models/publications uses the operator CLI, not a browser POST API"),
so review is recorded as a content-addressed ``publication_approval.json``
document next to the reviewed artifacts. It carries the reviewer identity, a
review reference (the review that approved the run, e.g. the PR/commit that
reviewed these exact artifacts) and the SHA-256 of each reviewed manifest
computed over the canonical rendering defined below. The gate recomputes
every hash and refuses publication when the reviewed bytes and the published
bytes diverge — an approval can never be silently re-bound to different
artifacts. The approval document is stored verbatim inside the published row,
so the published run carries its own review provenance.

Determinism and hashing: the canonical rendering is exactly the one the
research CLIs use (``json.dumps(..., ensure_ascii=False, sort_keys=True,
indent=2)`` plus a trailing newline), so a manifest file written by
``research fit``/``research diagnostics`` hashes identically when re-rendered
from parsed content — the approval binding is stable across the local-file
bundle and the JSON served from PostgreSQL ``jsonb``. Floats are allowed only
as finite IEEE-754 doubles (DATABASE_SCHEMA: statistical coefficients may be
finite float64 with an explicit numeric policy); NaN/Infinity are contract
errors everywhere, and non-finite values can therefore never enter a hash.

No network, no database access, no subprocess and no archive re-read happen
in this module: verification is pure-file, so ``research verify`` succeeds
offline on permitted inputs and never re-fits anything (the recorded results
are the reviewed ones; reproduction belongs to the reviewer recipe).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from near_api.schemas.models import BUNDLE_TYPE, BUNDLE_VERSION

APPROVAL_TYPE = "model_run_publication_approval"
DECISION_APPROVE = "approve"

FIT_MANIFEST_TYPE = "model_fit_run"
DIAGNOSTICS_REPORT_TYPE = "model_diagnostics_report"
READINESS_REPORT_TYPE = "model_dataset_readiness"

ARTIFACT_KEYS = ("fit_manifest", "diagnostics_report", "readiness_report",
                 "publication_approval")
MANIFEST_KEYS = ("fit_manifest", "diagnostics_report", "readiness_report")

BUNDLE_FILENAMES = {
    "fit_manifest": "fit_manifest.json",
    "diagnostics_report": "diagnostics_report.json",
    "readiness_report": "readiness_report.json",
    "publication_approval": "publication_approval.json",
}

GATE_ADMITTED_VERDICTS = ("READY", "READY_WITH_LIMITS")
READINESS_TEST_STATUSES = ("computed", "undefined", "failed", "not_applicable")

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CODE_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
_SPEC_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,79}$")

# The repository root is five levels above this file
# (<repo>/apps/api/src/near_api/research/publication.py).
REPO_ROOT = Path(__file__).resolve().parents[5]

RUN_ID_DOMAIN = "near-intelligence:model-run:v1:"


class PublicationGateError(ValueError):
    """A run bundle failed the publication gate (fail closed, never published)."""


@dataclass(frozen=True)
class GateCheck:
    """One named verification outcome recorded for the operator."""

    check: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class GateReport:
    """The complete verification outcome; publication requires ``passed``."""

    checks: tuple[GateCheck, ...]

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.checks)

    @property
    def failures(self) -> tuple[GateCheck, ...]:
        return tuple(item for item in self.checks if not item.passed)

    def as_report(self) -> dict:
        return {"passed": self.passed,
                "checks": [{"check": item.check, "passed": item.passed,
                            "detail": item.detail} for item in self.checks]}


# --------------------------------------------------------------------------- #
# Canonical rendering and hashing (one definition, used everywhere)
# --------------------------------------------------------------------------- #


def render_canonical(document) -> str:
    """The canonical JSON rendering the research CLIs and this gate share."""
    return json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2,
                      allow_nan=False) + "\n"


def canonical_artifact_hash(document) -> str:
    """SHA-256 over the canonical rendering of one parsed artifact document."""
    return hashlib.sha256(render_canonical(document).encode("utf-8")).hexdigest()


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def derive_run_id(artifact_hashes: dict[str, str]) -> UUID:
    """Derive the immutable run identity from the three manifest hashes.

    The identity covers exactly the scientific artifacts (fit manifest,
    diagnostics report, readiness report); the approval binds them but does
    not change it, so re-approving the same artifacts yields the same run.
    Identical manifests therefore always derive the same ``run_id`` and
    publication is idempotent at the database primary key.
    """
    identity = {key: artifact_hashes[key] for key in MANIFEST_KEYS}
    return uuid5(NAMESPACE_URL, RUN_ID_DOMAIN + _sha256_hex(render_canonical(identity)))


# --------------------------------------------------------------------------- #
# Bundle loading (directory or served JSON file)
# --------------------------------------------------------------------------- #


def _parse_json_bytes(raw: bytes, *, context: str) -> dict:
    try:
        document = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except UnicodeDecodeError:
        raise PublicationGateError(f"{context}: input must be UTF-8 JSON") from None
    except json.JSONDecodeError as error:
        raise PublicationGateError(f"{context}: invalid JSON at offset {error.pos}") from None
    if not isinstance(document, dict):
        raise PublicationGateError(f"{context}: expected a JSON object")
    return document


def _reject_constant(value: str):
    raise PublicationGateError(f"JSON constant {value} is not allowed in a run bundle "
                               "(NaN/Infinity can never be a recorded result)")


def load_bundle(path: Path) -> dict:
    """Load a run bundle from a directory or from a served JSON file.

    Returns ``{"fit_manifest": ..., "diagnostics_report": ...,
    "readiness_report": ..., "publication_approval": ..., "run_id": UUID|None}``.
    A directory bundle carries no run id yet (publication derives it); a
    served bundle file must carry the recorded one and keeps it.
    """
    path = Path(path)
    if path.is_dir():
        documents = {}
        for key, filename in BUNDLE_FILENAMES.items():
            artifact = path / filename
            if not artifact.is_file():
                raise PublicationGateError(
                    f"run bundle {path.name!r} is missing {filename}; publication "
                    "requires the complete data/code/lock/config/design/result "
                    "manifest set and the operator approval")
            documents[key] = _parse_json_bytes(artifact.read_bytes(), context=filename)
        documents["run_id"] = None
        return documents
    if path.is_file():
        document = _parse_json_bytes(path.read_bytes(), context=path.name)
        if document.get("bundle_type") != BUNDLE_TYPE:
            raise PublicationGateError(
                f"{path.name}: not a {BUNDLE_TYPE} document; verify accepts a bundle "
                "directory or the manifest bundle served by the model-run API")
        manifests = document.get("manifests")
        if not isinstance(manifests, dict) or set(manifests) != set(MANIFEST_KEYS):
            raise PublicationGateError(
                f"{path.name}: manifests must hold exactly {MANIFEST_KEYS}")
        approval = document.get("approval")
        if not isinstance(approval, dict):
            raise PublicationGateError(f"{path.name}: the bundle carries no approval")
        return {**manifests, "publication_approval": approval,
                "run_id": _optional_uuid(document.get("run_id"), "run_id")}
    raise PublicationGateError(f"run bundle {path} does not exist")


def _optional_uuid(value, context: str) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        raise PublicationGateError(f"{context}: {value!r} is not a UUID") from None


def bundle_document(run_id: UUID, manifests: dict, artifact_hashes: dict[str, str],
                    approval: dict) -> dict:
    """Assemble the canonical published-bundle document (served and verified)."""
    return {
        "bundle_type": BUNDLE_TYPE,
        "bundle_version": BUNDLE_VERSION,
        "run_id": str(run_id),
        "spec_id": manifests["fit_manifest"]["model"]["model_id"],
        "manifests": {key: manifests[key] for key in MANIFEST_KEYS},
        "artifact_sha256": dict(artifact_hashes),
        "approval": approval,
    }


# --------------------------------------------------------------------------- #
# Verification helpers (each failure is a named check, collected fail-closed)
# --------------------------------------------------------------------------- #


class _Checker:
    """Collects named checks; every failure is recorded, none is swallowed."""

    def __init__(self) -> None:
        self.checks: list[GateCheck] = []

    def require(self, check: str, condition, detail: str) -> bool:
        passed = bool(condition)
        self.checks.append(GateCheck(check=check, passed=passed, detail=detail))
        return passed

    def fail(self, check: str, detail: str) -> bool:
        return self.require(check, False, detail)


def _require_object(checker: _Checker, check: str, value, keys: tuple[str, ...],
                    context: str) -> dict | None:
    if not isinstance(value, dict) or any(key not in value for key in keys):
        checker.fail(check, f"{context}: expected an object with keys {list(keys)}")
        return None
    return value


def _finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) \
        and math.isfinite(value)


def _same_numbers(left, right, rtol: Decimal, atol: Decimal) -> bool:
    if not _finite_number(left) or not _finite_number(right):
        return False
    scale = max(atol, rtol * Decimal(abs(float(right))))
    return Decimal(abs(float(left) - float(right))) <= scale


def _positive_tolerance(value) -> Decimal | None:
    if not isinstance(value, str):
        return None
    try:
        tolerance = Decimal(value)
    except InvalidOperation:
        return None
    return tolerance if tolerance.is_finite() and tolerance > 0 else None


# --------------------------------------------------------------------------- #
# The verification gate
# --------------------------------------------------------------------------- #


def verify_bundle(bundle: dict, *, repo_root: Path | None = None) -> GateReport:
    """Verify a run bundle offline, fail-closed, without re-fitting anything.

    Every check compares the recorded manifests against each other and, where
    the repository checkout provides them, against the committed preregistered
    configs and the frozen dependency lock. No check reads the archive (a
    reviewer without the archive can still verify the recorded set) and no
    check touches the network or the database.
    """
    checker = _Checker()
    fit = bundle.get("fit_manifest")
    diagnostics = bundle.get("diagnostics_report")
    readiness = bundle.get("readiness_report")
    approval = bundle.get("publication_approval")

    # 1. Bundle completeness and artifact types.
    complete = True
    for key, expected_type in (("fit_manifest", FIT_MANIFEST_TYPE),
                               ("diagnostics_report", DIAGNOSTICS_REPORT_TYPE),
                               ("readiness_report", READINESS_REPORT_TYPE)):
        document = bundle.get(key)
        type_field = "manifest_type" if key == "fit_manifest" else "report_type"
        if not isinstance(document, dict) or document.get(type_field) != expected_type:
            complete = False
            checker.fail("bundle_completeness",
                         f"{key} is missing or does not declare {type_field} "
                         f"{expected_type!r}")
    if complete:
        checker.require("bundle_completeness", True,
                        "fit manifest, diagnostics report and readiness report are "
                        "present with their recorded artifact types")
    if not isinstance(approval, dict):
        checker.fail("approval_present", "the operator publication approval is missing")
        return GateReport(checks=tuple(checker.checks))

    # 2. Approval binding: content-addressed operator review.
    _verify_approval(checker, approval, bundle, complete and isinstance(fit, dict))

    if not complete or not isinstance(fit, dict) or not isinstance(diagnostics, dict) \
            or not isinstance(readiness, dict):
        return GateReport(checks=tuple(checker.checks))

    # 3. Data manifest: one archive, pinned by SHA-256 in every artifact.
    _verify_data_manifest(checker, fit, diagnostics, readiness)

    # 4. Code manifest: one commit recorded everywhere.
    fit_commit = _inputs(fit).get("code_commit")
    diag_commit = _inputs(diagnostics).get("code_commit")
    commit_ok = (isinstance(fit_commit, str) and _CODE_COMMIT_PATTERN.match(fit_commit)
                 and fit_commit == diag_commit)
    checker.require("code_manifest", commit_ok,
                    "one recorded code commit (40/64 lowercase hex) matches across "
                    "the fit manifest and the diagnostics report"
                    if commit_ok else
                    f"code commit mismatch or missing: fit={fit_commit!r}, "
                    f"diagnostics={diag_commit!r}")

    # 5. Lock manifest: the frozen dependency lock, verified against this checkout.
    _verify_lock_manifest(checker, fit, diagnostics, repo_root or REPO_ROOT)

    # 6. Config identity: every recorded config hash matches the committed file.
    committed = _verify_config_identity(checker, fit, diagnostics, readiness,
                                        repo_root or REPO_ROOT)

    # 7. Cross-manifest identity: one specification, one sample, one verdict.
    _verify_cross_manifest_identity(checker, fit, diagnostics, readiness)

    # 7b. Readiness report shape: the public readiness API projects the gate
    # verdicts out of this report, so its structure is part of the contract.
    _verify_readiness_report_shape(checker, readiness)

    # 8. Design manifest: the exact declared design, hashed.
    _verify_design_manifest(checker, fit)

    # 9. Result manifest: finite coefficients and estimation summaries.
    _verify_result_manifest(checker, fit, diagnostics)

    # 10. Diagnostics completeness: every declared diagnostic present or undefined
    # with a reason; sensitivity limited to the preregistered presets;
    # interpretation template-rendered.
    _verify_diagnostics_completeness(checker, diagnostics,
                                     committed.get("diagnostics"))

    # 11. Limitations attached verbatim to both artifacts.
    _verify_limitations(checker, fit, diagnostics)

    # 12. Tolerances recorded and consistent.
    _verify_tolerances(checker, fit, diagnostics)

    # 13. Run identity (only recorded on served/published bundles).
    recorded_run_id = bundle.get("run_id")
    if recorded_run_id is not None:
        hashes = {key: canonical_artifact_hash(bundle[key]) for key in MANIFEST_KEYS}
        derived = derive_run_id(hashes)
        checker.require("run_identity", derived == recorded_run_id,
                        f"run_id {recorded_run_id} matches the content-derived identity"
                        if derived == recorded_run_id else
                        f"recorded run_id {recorded_run_id} does not match the "
                        f"content-derived identity {derived}")

    return GateReport(checks=tuple(checker.checks))


def _inputs(manifest: dict) -> dict:
    inputs = manifest.get("inputs")
    return inputs if isinstance(inputs, dict) else {}


def _verify_approval(checker: _Checker, approval: dict, bundle: dict,
                     fit_present: bool) -> None:
    if approval.get("approval_type") != APPROVAL_TYPE:
        checker.fail("approval_present", f"approval_type must be {APPROVAL_TYPE!r}")
        return
    if approval.get("decision") != DECISION_APPROVE:
        checker.fail("approval_decision",
                     f"the recorded decision is {approval.get('decision')!r}; only an "
                     "explicit approve decision publishes a run")
        return
    reviewer = approval.get("reviewer")
    reference = approval.get("review_reference")
    review_ok = (isinstance(reviewer, str) and reviewer.strip()
                 and isinstance(reference, str) and reference.strip())
    checker.require("approval_decision", review_ok,
                    "reviewer identity and review reference are recorded"
                    if review_ok else
                    "the approval must record a non-empty reviewer and review_reference")
    approved = approval.get("approved_artifacts")
    if not isinstance(approved, dict) or set(MANIFEST_KEYS) - set(approved):
        checker.fail("approval_binding",
                     f"approved_artifacts must record the SHA-256 of {MANIFEST_KEYS}")
        return
    mismatches = []
    for key in MANIFEST_KEYS:
        document = bundle.get(key)
        recorded = approved.get(key)
        if not isinstance(document, dict) or not isinstance(recorded, str) \
                or not _SHA256_PATTERN.match(recorded):
            mismatches.append(f"{key}: missing")
            continue
        actual = canonical_artifact_hash(document)
        if actual != recorded:
            mismatches.append(f"{key}: approved {recorded[:12]}…, artifact hashes to "
                              f"{actual[:12]}…")
    checker.require("approval_binding", not mismatches,
                    "the approval binds exactly the canonical bytes of all three "
                    "manifests" if not mismatches else
                    "the approval does not match the artifacts: " + "; ".join(mismatches))


def _verify_readiness_report_shape(checker: _Checker, readiness: dict) -> None:
    evaluations = readiness.get("spec_evaluations")
    evaluations_ok = isinstance(evaluations, list) and len(evaluations) > 0 and all(
        isinstance(entry, dict) and isinstance(entry.get("spec"), dict)
        and isinstance(entry["spec"].get("spec_id"), str)
        and isinstance(entry.get("verdict"), str) and entry["verdict"]
        and isinstance(entry.get("reason_codes"), list)
        for entry in evaluations)
    checker.require("readiness_report_shape", evaluations_ok,
                    f"{len(evaluations) if isinstance(evaluations, list) else 0} "
                    "specification evaluations recorded with verdicts and reason "
                    "codes"
                    if evaluations_ok else
                    "the readiness report must record every specification evaluation "
                    "with its verdict and reason codes")
    selection = readiness.get("selection")
    selection_ok = isinstance(selection, dict) \
        and isinstance(selection.get("overall_verdict"), str) \
        and bool(selection["overall_verdict"])
    checker.require("readiness_report_shape", selection_ok,
                    "the gate selection block (overall verdict, selected "
                    "specification) is recorded"
                    if selection_ok else
                    "the readiness report must record its selection block with the "
                    "overall verdict; the public readiness API serves it")
    prepared = readiness.get("prepared_table")
    prepared_ok = isinstance(prepared, dict) \
        and isinstance(prepared.get("series"), list) and bool(prepared["series"]) \
        and isinstance(prepared.get("known_caveats"), list)
    checker.require("readiness_report_shape", prepared_ok,
                    "the prepared-table profile (per-series profiles, known "
                    "caveats) is recorded"
                    if prepared_ok else
                    "the readiness report must carry its prepared-table profile "
                    "with the per-series profiles and known caveats")


def _verify_data_manifest(checker: _Checker, fit: dict, diagnostics: dict,
                          readiness: dict) -> None:
    files = _inputs(fit).get("files")
    valid = isinstance(files, list) and len(files) > 0 and all(
        isinstance(item, dict) and isinstance(item.get("name"), str)
        and _SHA256_PATTERN.match(str(item.get("sha256")))
        and isinstance(item.get("bytes"), int) and not isinstance(item.get("bytes"), bool)
        and item["bytes"] >= 0
        for item in files)
    checker.require("data_manifest", valid,
                    f"{len(files)} archive files pinned by SHA-256 with byte sizes"
                    if valid else
                    "the fit manifest must pin every archive input file by name, "
                    "SHA-256 and byte size")
    if not valid:
        return
    for name, document in (("diagnostics_report", diagnostics),
                           ("readiness_report", readiness)):
        other = _inputs(document).get("files")
        same = isinstance(other, list) and _file_sets_equal(files, other)
        checker.require("data_manifest", same,
                        f"{name} pins the identical archive file set"
                        if same else
                        f"{name} does not pin the same archive files as the fit "
                        "manifest; one run is one archive state")


def _file_sets_equal(left: list, right: list) -> bool:
    def fingerprint(items):
        return sorted((item.get("name"), item.get("sha256"), item.get("bytes"))
                      for item in items if isinstance(item, dict))
    return fingerprint(left) == fingerprint(right)


def _verify_lock_manifest(checker: _Checker, fit: dict, diagnostics: dict,
                          repo_root: Path) -> None:
    fit_lock = _inputs(fit).get("dependency_lock")
    diag_lock = _inputs(diagnostics).get("dependency_lock")
    fit_hash = fit_lock.get("sha256") if isinstance(fit_lock, dict) else None
    diag_hash = diag_lock.get("sha256") if isinstance(diag_lock, dict) else None
    recorded = (isinstance(fit_hash, str) and _SHA256_PATTERN.match(fit_hash)
                and fit_hash == diag_hash)
    if not recorded:
        checker.fail("lock_manifest",
                     f"the recorded dependency lock hash is missing or inconsistent: "
                     f"fit={fit_hash!r}, diagnostics={diag_hash!r}")
        return
    lock_path = repo_root / "apps" / "api" / "uv.lock"
    if not lock_path.is_file():
        checker.fail("lock_manifest",
                     "apps/api/uv.lock is absent from this checkout; the frozen lock "
                     "identity cannot be verified offline")
        return
    actual = hashlib.sha256(lock_path.read_bytes()).hexdigest()
    checker.require("lock_manifest", actual == fit_hash,
                    "the recorded lock hash matches this checkout's apps/api/uv.lock"
                    if actual == fit_hash else
                    f"recorded lock hash {fit_hash[:12]}… does not match this "
                    f"checkout's apps/api/uv.lock ({actual[:12]}…); publish and verify "
                    "from the exact frozen checkout")


def _verify_config_identity(checker: _Checker, fit: dict, diagnostics: dict,
                            readiness: dict, repo_root: Path) -> dict:
    """Verify every recorded config hash against the committed file.

    Returns the loaded committed documents (the diagnostics config feeds the
    no-surfing preset check); a document is absent when its check already
    failed, so later checks must handle ``None``.
    """
    loaded: dict[str, dict | None] = {}
    # Every manifest must record the hash of the committed preregistered config
    # it ran under; the gate recomputes each hash from the committed file.
    spec_input = _inputs(fit).get("spec_config")
    spec_path = spec_input.get("path") if isinstance(spec_input, dict) else None
    spec_hash = spec_input.get("config_hash") if isinstance(spec_input, dict) else None
    recorded_specs = {"fit_manifest": spec_hash,
                      "diagnostics_report": _inputs(diagnostics).get("spec_config", {})
                      .get("config_hash") if isinstance(
                          _inputs(diagnostics).get("spec_config"), dict) else None}
    loaded["spec"] = _verify_one_config(checker, "spec_config", spec_path,
                                        recorded_specs, repo_root,
                                        "research/models/configs")

    fit_config_id = fit.get("fit_config", {}).get("fit_config_id") \
        if isinstance(fit.get("fit_config"), dict) else None
    fit_config_hash = fit.get("fit_config", {}).get("config_hash") \
        if isinstance(fit.get("fit_config"), dict) else None
    diag_fit_config_hash = _inputs(diagnostics).get("fit_config_hash")
    loaded["fit"] = _verify_one_config(checker, "fit_config",
                                       f"{fit_config_id}.json" if fit_config_id else None,
                                       {"fit_manifest": fit_config_hash,
                                        "diagnostics_report": diag_fit_config_hash},
                                       repo_root, "research/models/fit_configs")

    diagnostics_config = diagnostics.get("diagnostics_config")
    diagnostics_config_id = diagnostics_config.get("diagnostics_config_id") \
        if isinstance(diagnostics_config, dict) else None
    diagnostics_config_hash = diagnostics_config.get("config_hash") \
        if isinstance(diagnostics_config, dict) else None
    diag_recorded = _inputs(diagnostics).get("diagnostics_config_hash")
    if diagnostics_config_hash is not None and diag_recorded is not None \
            and diagnostics_config_hash != diag_recorded:
        checker.fail("config_identity",
                     "the diagnostics report records two different diagnostics config "
                     "hashes (report body vs inputs block)")
    loaded["diagnostics"] = _verify_one_config(
        checker, "diagnostics_config",
        f"{diagnostics_config_id}.json" if diagnostics_config_id else None,
        {"diagnostics_report": diagnostics_config_hash},
        repo_root, "research/models/diagnostics_configs")

    fit_policy = fit.get("gate_policy")
    diag_policy = diagnostics.get("gate_policy")
    readiness_policy = readiness.get("policy")
    policy_hashes = {
        "fit_manifest": fit_policy.get("config_hash")
        if isinstance(fit_policy, dict) else None,
        "diagnostics_report": diag_policy.get("config_hash")
        if isinstance(diag_policy, dict) else None,
        "readiness_report": readiness_policy.get("config_hash")
        if isinstance(readiness_policy, dict) else None,
    }
    loaded["policy"] = _verify_one_config(checker, "gate_policy_config",
                                          "readiness_gate_policy_v1.json",
                                          policy_hashes, repo_root,
                                          "research/models/configs")
    return loaded


def _verify_one_config(checker: _Checker, name: str, recorded_name: str | None,
                       recorded: dict[str, str | None], repo_root: Path,
                       namespace: str) -> dict | None:
    """Verify one config hash; returns the committed document on success."""
    if not recorded_name:
        checker.fail("config_identity", f"{name}: no config file recorded")
        return None
    # Manifests record the config file by name (the spec config additionally
    # carries its repository-relative path; the committed file is the same
    # one).
    config_name = Path(recorded_name).name
    path = repo_root / namespace / config_name
    if not path.is_file():
        checker.fail("config_identity",
                     f"{name}: committed config {namespace}/{config_name} is absent "
                     "from this checkout")
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        checker.fail("config_identity", f"{name}: committed config cannot be read ({error})")
        return None
    actual = _config_hash(document)
    divergent = [key for key, value in recorded.items()
                 if not isinstance(value, str) or not _SHA256_PATTERN.match(value)
                 or value != actual]
    checker.require("config_identity", not divergent,
                    f"{config_name}: every manifest records the committed config "
                    f"hash {actual[:12]}…"
                    if not divergent else
                    f"{config_name}: hash mismatch in {divergent} against the "
                    f"committed file ({actual[:12]}…); a run may only publish under "
                    "the preregistered configs")
    return document if not divergent else None


def _config_hash(document: dict) -> str:
    """The readiness/fit config hash definition (compact canonical JSON)."""
    return _sha256_hex(json.dumps(document, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":")))


def _verify_cross_manifest_identity(checker: _Checker, fit: dict, diagnostics: dict,
                                    readiness: dict) -> None:
    fit_model = fit.get("model") if isinstance(fit.get("model"), dict) else {}
    diag_model = diagnostics.get("model") if isinstance(diagnostics.get("model"), dict) else {}
    spec_id = fit_model.get("model_id")
    identity_ok = (isinstance(spec_id, str) and _SPEC_ID_PATTERN.match(spec_id)
                   and spec_id == diag_model.get("model_id"))
    checker.require("spec_identity", identity_ok,
                    f"one preregistered specification {spec_id!r} across both artifacts"
                    if identity_ok else
                    f"specification identity mismatch: fit={fit_model.get('model_id')!r}, "
                    f"diagnostics={diag_model.get('model_id')!r}")

    fit_window = fit.get("sample", {}).get("window") \
        if isinstance(fit.get("sample"), dict) else None
    diag_window = diagnostics.get("sample", {}).get("window") \
        if isinstance(diagnostics.get("sample"), dict) else None
    window_ok = (isinstance(fit_window, dict)
                 and fit_window.get("start") and fit_window.get("end_exclusive")
                 and fit_window == diag_window)
    checker.require("sample_identity", window_ok,
                    f"one sample window {fit_window} across both artifacts"
                    if window_ok else
                    f"sample window mismatch: fit={fit_window!r}, "
                    f"diagnostics={diag_window!r}")

    verdict = fit.get("admission", {}).get("verdict") \
        if isinstance(fit.get("admission"), dict) else None
    checker.require("gate_admission", verdict in GATE_ADMITTED_VERDICTS,
                    f"the gate verdict recorded for publication is {verdict!r}"
                    if verdict in GATE_ADMITTED_VERDICTS else
                    f"the recorded gate verdict {verdict!r} is not an admitted one; "
                    "unadmitted runs never publish")

    # The readiness report is the gate's own record: the published verdict must
    # be the one the gate recorded for this specification.
    evaluations = readiness.get("spec_evaluations")
    gate_verdict = None
    if isinstance(evaluations, list):
        for entry in evaluations:
            spec = entry.get("spec") if isinstance(entry, dict) else None
            if isinstance(spec, dict) and spec.get("spec_id") == spec_id:
                gate_verdict = entry.get("verdict")
                break
    checker.require("gate_admission", gate_verdict == verdict,
                    "the readiness report records the same verdict for this "
                    "specification"
                    if gate_verdict == verdict and gate_verdict is not None else
                    f"the readiness report records verdict {gate_verdict!r} for "
                    f"{spec_id!r}, not the manifest's {verdict!r}")

    fit_nobs = fit.get("sample", {}).get("nobs") if isinstance(fit.get("sample"), dict) else None
    diag_nobs = diagnostics.get("sample", {}).get("nobs") \
        if isinstance(diagnostics.get("sample"), dict) else None
    checker.require("sample_identity",
                    isinstance(fit_nobs, int) and not isinstance(fit_nobs, bool)
                    and fit_nobs > 0 and fit_nobs == diag_nobs,
                    f"one sample size {fit_nobs} across both artifacts"
                    if isinstance(fit_nobs, int) and fit_nobs == diag_nobs else
                    f"sample size mismatch: fit={fit_nobs!r}, diagnostics={diag_nobs!r}")


def _verify_design_manifest(checker: _Checker, fit: dict) -> None:
    design = fit.get("design") if isinstance(fit.get("design"), dict) else None
    if design is None:
        checker.fail("design_manifest", "the fit manifest carries no design block")
        return
    columns = design.get("columns")
    sample = fit.get("sample") if isinstance(fit.get("sample"), dict) else {}
    nobs = sample.get("nobs")
    design_ok = (isinstance(columns, list) and len(columns) > 0
                 and all(isinstance(column, str) and column for column in columns)
                 and isinstance(design.get("rows"), int)
                 and design.get("rows") == nobs
                 and isinstance(design.get("rank"), int)
                 and isinstance(design.get("condition_number"), (int, float))
                 and math.isfinite(design.get("condition_number"))
                 and _SHA256_PATTERN.match(str(design.get("source_hash")))
                 and _SHA256_PATTERN.match(str(design.get("float64_hex_sha256"))))
    checker.require("design_manifest", design_ok,
                    f"declared design {columns} with {design.get('rows')} hashed rows"
                    if design_ok else
                    "the design block must record the declared columns, the row count "
                    "equal to the sample size, finite rank/condition number and both "
                    "exact-decimal and float64 design hashes")


def _verify_result_manifest(checker: _Checker, fit: dict, diagnostics: dict) -> None:
    coefficients = fit.get("coefficients")
    design = fit.get("design") if isinstance(fit.get("design"), dict) else {}
    columns = design.get("columns") if isinstance(design.get("columns"), list) else []
    valid = isinstance(coefficients, list) and len(coefficients) == len(columns) > 0
    problems: list[str] = []
    if valid:
        for index, coefficient in enumerate(coefficients):
            entry = coefficient if isinstance(coefficient, dict) else {}
            if entry.get("name") != columns[index]:
                problems.append(f"coefficient {index} is not the declared column")
                continue
            for field in ("estimate", "std_error", "t_stat", "p_value",
                          "ci95_low", "ci95_high"):
                if not _finite_number(entry.get(field)):
                    problems.append(f"{entry.get('name')}.{field} is not a finite number")
            p_value = entry.get("p_value")
            if _finite_number(p_value) and not Decimal(str(p_value)).is_finite():
                problems.append(f"{entry.get('name')}.p_value is not finite")
            low, high, estimate = entry.get("ci95_low"), entry.get("ci95_high"), \
                entry.get("estimate")
            if all(_finite_number(value) for value in (low, high)) and low > high:
                problems.append(f"{entry.get('name')} confidence interval is inverted")
            if all(_finite_number(value) for value in (low, high, estimate)) \
                    and not (low <= estimate <= high):
                problems.append(f"{entry.get('name')} estimate falls outside its "
                                "recorded 95% interval")
    checker.require("result_manifest", valid and not problems,
                    f"{len(coefficients)} finite coefficient records bound to the "
                    "declared design columns"
                    if valid and not problems else
                    "coefficient table invalid: " + ("; ".join(problems[:6]) or
                                                     "missing or not bound to the "
                                                     "declared columns"))

    estimation = fit.get("estimation") if isinstance(fit.get("estimation"), dict) else {}
    summary_fields = ("nobs", "df_resid", "r_squared", "adj_r_squared")
    summary_ok = all(_finite_number(estimation.get(field)) for field in summary_fields)
    checker.require("result_manifest", summary_ok,
                    "estimation summary (nobs, df_resid, R², adj-R²) recorded finite"
                    if summary_ok else
                    "the estimation summary is missing a finite "
                    f"{summary_fields} record")

    # Cross-check the diagnostics report's rebuilt coefficient table against the
    # fit manifest's recorded results under the declared tolerances (both are
    # recorded results; nothing is re-fitted here).
    rebuilt = diagnostics.get("estimation_results", {}).get("coefficients") \
        if isinstance(diagnostics.get("estimation_results"), dict) else None
    rtol = _positive_tolerance(fit.get("reproduction", {}).get("coefficient_rtol")) \
        if isinstance(fit.get("reproduction"), dict) else None
    atol = _positive_tolerance(fit.get("reproduction", {}).get("coefficient_atol")) \
        if isinstance(fit.get("reproduction"), dict) else None
    if rtol is None or atol is None or not isinstance(rebuilt, list) \
            or len(rebuilt) != len(coefficients or []):
        checker.fail("result_manifest",
                     "the diagnostics report must rebuild the same coefficient table "
                     "and the fit manifest must record positive decimal tolerances")
        return
    deviations = []
    for recorded, other in zip(coefficients, rebuilt):
        if not isinstance(other, dict) or other.get("name") != recorded.get("name") \
                or not _same_numbers(recorded.get("estimate"), other.get("estimate"),
                                     rtol, atol):
            deviations.append(str(recorded.get("name")))
    checker.require("result_manifest", not deviations,
                    "the diagnostics report's coefficient table matches the fit "
                    "manifest under the declared tolerances"
                    if not deviations else
                    f"coefficient estimates diverge beyond the declared tolerance for "
                    f"{deviations[:4]}")


def _verify_diagnostics_completeness(checker: _Checker, diagnostics: dict,
                                     diagnostics_config: dict | None) -> None:
    stationarity = diagnostics.get("stationarity")
    tests = stationarity.get("tests") if isinstance(stationarity, dict) else None
    statuses = ("computed", "undefined", "failed", "not_applicable")
    tests_ok = isinstance(tests, list) and len(tests) > 0 and all(
        isinstance(entry, dict) and entry.get("status") in statuses
        and (entry.get("status") == "computed" or isinstance(entry.get("reason_code"),
                                                             str) and entry["reason_code"])
        for entry in tests)
    checker.require("diagnostics_completeness", tests_ok,
                    f"{len(tests) if isinstance(tests, list) else 0} stationarity "
                    "results each computed or undefined with a reason code"
                    if tests_ok else
                    "stationarity tests must be present exactly once each with status "
                    f"{statuses}; an undefined test carries a reason, never zero")

    residual = diagnostics.get("residual_diagnostics")
    residual_keys = ("acf", "ljung_box", "heteroskedasticity", "influence")
    residual_ok = isinstance(residual, dict) and all(key in residual for key in residual_keys)
    checker.require("diagnostics_completeness", residual_ok,
                    "residual ACF, Ljung–Box, heteroskedasticity and influence blocks "
                    "present"
                    if residual_ok else
                    f"the residual battery is missing one of {residual_keys}")

    sensitivity = diagnostics.get("sensitivity")
    presets = sensitivity.get("presets") if isinstance(sensitivity, dict) else None
    presets_ok = isinstance(presets, list) and len(presets) > 0 and all(
        isinstance(entry, dict) and entry.get("status")
        in ("estimated", "not_applicable", "failed")
        and (entry.get("status") != "failed" or entry.get("reason_code"))
        for entry in presets)
    checker.require("diagnostics_completeness", presets_ok,
                    f"{len(presets) if isinstance(presets, list) else 0} preregistered "
                    "sensitivity presets each reported with a status"
                    if presets_ok else
                    "the sensitivity block must report every preregistered preset with "
                    "status estimated/not_applicable/failed (never invented variants)")
    # No surfing: the reported presets must be exactly the ones the committed
    # diagnostics config preregistered — nothing invented from data.
    if presets_ok and isinstance(diagnostics_config, dict):
        declared = diagnostics_config.get("sensitivity_presets")
        declared_ids = sorted(entry.get("preset_id") for entry in declared
                              if isinstance(entry, dict)) \
            if isinstance(declared, list) else None
        reported_ids = sorted(entry.get("preset_id") for entry in presets
                              if isinstance(entry, dict))
        surfed = declared_ids is None or declared_ids != reported_ids
        checker.require("diagnostics_completeness", not surfed,
                        f"the reported presets are exactly the preregistered ones "
                        f"({declared_ids})"
                        if not surfed else
                        "the reported sensitivity presets deviate from the committed "
                        f"diagnostics config (declared {declared_ids}, reported "
                        f"{reported_ids}); variants are never invented")

    interpretation = diagnostics.get("interpretation")
    interpretation_ok = isinstance(interpretation, dict) \
        and isinstance(interpretation.get("template_id"), str) \
        and bool(interpretation.get("template_id")) \
        and isinstance(interpretation.get("sentences"), list) \
        and len(interpretation["sentences"]) > 0
    checker.require("diagnostics_completeness", interpretation_ok,
                    "template-rendered bounded interpretation present"
                    if interpretation_ok else
                    "the interpretation must be the template-rendered bounded record "
                    "(template_id plus rendered sentences), never free-form text")

    environment = diagnostics.get("environment")
    fit_environment = None
    checker.require("diagnostics_completeness", isinstance(environment, dict)
                    and bool(environment.get("python_version"))
                    and bool(environment.get("statsmodels_version")),
                    "environment metadata recorded in the diagnostics report"
                    if isinstance(environment, dict) else
                    "the diagnostics report must record its environment")


def _verify_limitations(checker: _Checker, fit: dict, diagnostics: dict) -> None:
    fit_limits = fit.get("limitations") if isinstance(fit.get("limitations"), dict) else {}
    diag_limits = diagnostics.get("limitations") \
        if isinstance(diagnostics.get("limitations"), dict) else {}
    prohibited = fit_limits.get("prohibited_labels")
    notes = fit_limits.get("spec_limitation_notes")
    attached = (isinstance(prohibited, list) and len(prohibited) > 0
                and isinstance(notes, list) and len(notes) > 0
                and all(isinstance(item, str) and item for item in prohibited + notes))
    checker.require("limitations_attached", attached,
                    "prohibited labels and specification limitation notes attached "
                    "verbatim to the fit manifest"
                    if attached else
                    "the fit manifest must attach non-empty prohibited_labels and "
                    "spec_limitation_notes verbatim")
    checker.require("limitations_attached", fit_limits == diag_limits,
                    "both artifacts attach the identical limitations block"
                    if fit_limits == diag_limits else
                    "the fit manifest and the diagnostics report attach different "
                    "limitation blocks; limitations are attached verbatim and never "
                    "edited between artifacts")


def _verify_tolerances(checker: _Checker, fit: dict, diagnostics: dict) -> None:
    fit_reproduction = fit.get("reproduction") if isinstance(fit.get("reproduction"), dict) else {}
    diag_reproduction = diagnostics.get("reproduction") \
        if isinstance(diagnostics.get("reproduction"), dict) else {}
    rtol = _positive_tolerance(fit_reproduction.get("coefficient_rtol"))
    atol = _positive_tolerance(fit_reproduction.get("coefficient_atol"))
    tolerances_ok = (rtol is not None and atol is not None
                     and fit_reproduction.get("coefficient_rtol")
                     == diag_reproduction.get("coefficient_rtol")
                     and fit_reproduction.get("coefficient_atol")
                     == diag_reproduction.get("coefficient_atol")
                     and isinstance(fit_reproduction.get("command"), str)
                     and bool(fit_reproduction["command"]))
    checker.require("tolerances_recorded", tolerances_ok,
                    f"reproduction tolerances rtol={rtol}, atol={atol} recorded with "
                    "the exact reproduction command in both artifacts"
                    if tolerances_ok else
                    "both artifacts must record identical positive decimal "
                    "coefficient tolerances and a non-empty reproduction command")


# --------------------------------------------------------------------------- #
# Verified-row assembly (the publication payload the database store writes)
# --------------------------------------------------------------------------- #


def publication_payload(bundle: dict, run_id: UUID) -> dict:
    """Derive the immutable database row fields from a VERIFIED bundle.

    Call only after :func:`verify_bundle` passed: the denormalized columns are
    mechanical projections of the verified manifests, and the migration's CHECK
    constraints re-assert every projection against the stored ``manifests``
    JSONB so a row can never disagree with itself.
    """
    fit = bundle["fit_manifest"]
    approval = bundle["publication_approval"]
    hashes = {key: canonical_artifact_hash(bundle[key]) for key in ARTIFACT_KEYS}
    sample = fit["sample"]
    return {
        "run_id": run_id,
        "spec_id": fit["model"]["model_id"],
        "spec_version": fit["model"]["model_version"],
        "gate_verdict": fit["admission"]["verdict"],
        "manifests": {key: bundle[key] for key in MANIFEST_KEYS},
        "artifacts": hashes,
        "approval": approval,
        "code_commit": fit["inputs"]["code_commit"],
        "dependency_lock_sha256": fit["inputs"]["dependency_lock"]["sha256"],
        "coefficient_rtol": fit["reproduction"]["coefficient_rtol"],
        "coefficient_atol": fit["reproduction"]["coefficient_atol"],
        "sample_start": sample["window"]["start"],
        "sample_end_exclusive": sample["window"]["end_exclusive"],
        "nobs": sample["nobs"],
    }
