"""``python -m near_api.research`` — offline research commands and the
NI-054 publication gate.

Commands:

- ``fit`` — the NI-052 fixed deterministic econometric estimator
  (``research/models/fit.py``); arguments are forwarded verbatim.
- ``diagnostics`` — the NI-053 diagnostics, robustness and interpretation
  battery (``research/models/diagnostics.py``); arguments are forwarded
  verbatim.
- ``verify`` — the NI-054 offline reproduction verifier: checks a run bundle
  (local report directory or the manifest bundle served by the model-run API)
  against the full data/code/lock/config/design/result manifest set. Pure
  file work: no network, no database, no re-fit — the recorded results are
  the reviewed ones. Requires ``--offline`` to state the contract explicitly.
- ``publish`` — the NI-054 operator publication gate: verifies the bundle
  exactly like ``verify`` and only then writes the immutable run into
  ``app.model_runs`` through the dedicated ``near_operator`` credential.
  Rejected, failed or unreviewed runs never reach the database.

A separate verb (instead of ``fit --with-diagnostics``) keeps one manifest
per command with one byte-identical output contract each: the fit manifest
stays exactly the NI-052 artifact, and the diagnostics report is a separate
artifact with its own preregistered config. Forwarded commands keep the
verbatim-argument contract (``fit --help`` reaches the module's own parser);
``verify``/``publish`` are native to this package and own their arguments.

Exit codes follow the research CLI convention: 0 success, 4
contract/policy failure, 2 usage. The wrapper maps only its own failures
(missing research module, unknown command, gate refusal, publish conflict,
database error) onto exit code 4; argument-parsing failures stay usage
errors (exit 2), including the forwarded modules' own parsing.

Examples::

    uv run --project apps/api python -m near_api.research fit \\
        --archive-root /path/to/research \\
        --out-dir research/models/reports \\
        --code-commit <git sha>
    uv run --project apps/api python -m near_api.research diagnostics \\
        --archive-root /path/to/research \\
        --out-dir research/reports/<run> \\
        --code-commit <git sha>
    uv run --project apps/api python -m near_api.research verify \\
        --bundle research/reports/<run> --offline
    uv run --project apps/api python -m near_api.research publish \\
        --bundle research/reports/<run> \\
        --database-url postgresql+psycopg://near_operator:...@host/db
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import near_api

COMMANDS = ("fit", "diagnostics", "verify", "publish")
FORWARDED = ("fit", "diagnostics")
EXIT_CONTRACT = 4

# The editable install (the documented `uv sync` layout) places the package
# at <repo>/apps/api/src/near_api/, so the repository root is three parents up.
_REPO_ROOT_DEPTH_FROM_PACKAGE = 3

_MODULE_NAMES = {"fit": "ni052_fit_module", "diagnostics": "ni053_diagnostics_module"}
_MODULE_FILES = {"fit": "fit.py", "diagnostics": "diagnostics.py"}


def _load_research_module(command: str, override: Path | None):
    """Locate and import-only load the research module behind a command."""
    candidates = []
    if override is not None:
        candidates.append(override)
    package_file = Path(near_api.__file__).resolve()
    repo_root = package_file.parents[_REPO_ROOT_DEPTH_FROM_PACKAGE]
    candidates.append(repo_root / "research" / "models" / _MODULE_FILES[command])
    candidates.append(Path.cwd() / "research" / "models" / _MODULE_FILES[command])
    for candidate in candidates:
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location(_MODULE_NAMES[command],
                                                          candidate)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return module
    tried = ", ".join(str(candidate) for candidate in candidates)
    print(f"near_api.research: cannot locate the research module for command "
          f"{command!r}; tried: {tried}. Run from a repository checkout (the "
          f"documented `uv sync --project apps/api` layout) or pass the module "
          f"path before the command: python -m near_api.research "
          f"--{command}-module research/models/{_MODULE_FILES[command]} "
          f"{command} ...", file=sys.stderr)
    raise SystemExit(EXIT_CONTRACT)


def _canonical_artifact_hash(document) -> str:
    from near_api.research.publication import render_canonical
    return hashlib.sha256(render_canonical(document).encode("utf-8")).hexdigest()


def _verify_command(arguments: list[str]) -> int:
    from near_api.research.publication import (PublicationGateError, MANIFEST_KEYS,
                                               load_bundle, verify_bundle)
    parser = argparse.ArgumentParser(
        prog="python -m near_api.research verify",
        description="Verify a run bundle offline: hashes, identities and the "
                    "recorded results are checked fail-closed without network, "
                    "database or re-fit. A passing verification prints the "
                    "canonical artifact hashes an operator approval must bind.")
    parser.add_argument("--bundle", type=Path, required=True,
                        help="bundle directory (fit_manifest.json, "
                             "diagnostics_report.json, readiness_report.json, "
                             "publication_approval.json) or the manifest bundle "
                             "JSON served by the model-run API")
    parser.add_argument("--offline", action="store_true",
                        help="required: verification is strictly offline; the flag "
                             "states the contract explicitly (no network, no "
                             "database, no re-fit)")
    args = parser.parse_args(arguments)
    if not args.offline:
        print("near_api.research verify: verification is strictly offline; pass "
              "--offline to state the contract", file=sys.stderr)
        return EXIT_CONTRACT
    try:
        bundle = load_bundle(args.bundle)
        report = verify_bundle(bundle)
    except PublicationGateError as error:
        print(f"near_api.research verify: {error}", file=sys.stderr)
        return EXIT_CONTRACT
    for check in report.checks:
        print(f"[{'PASS' if check.passed else 'FAIL'}] {check.check}: {check.detail}")
    if not report.passed:
        print("Bundle verification FAILED; nothing is published.", file=sys.stderr)
        return EXIT_CONTRACT
    print("Bundle verification PASSED (offline). Canonical artifact hashes for the "
          "operator approval file (publication_approval.json -> approved_artifacts):")
    print(json.dumps({key: _canonical_artifact_hash(bundle[key])
                      for key in MANIFEST_KEYS}, indent=2, sort_keys=True))
    return 0


def _publish_command(arguments: list[str]) -> int:
    from sqlalchemy.exc import SQLAlchemyError

    from near_api.ingestion.archive import OperatorDatabaseError
    from near_api.research.publication import (PublicationGateError,
                                               canonical_artifact_hash, derive_run_id,
                                               load_bundle, verify_bundle)
    from near_api.research.publish_store import (PublishConflictError,
                                                 publish_run)
    parser = argparse.ArgumentParser(
        prog="python -m near_api.research publish",
        description="Operator publication gate: verify the run bundle (the same "
                    "offline checks as verify) and only then write the immutable "
                    "run into app.model_runs with the near_operator credential. "
                    "Rejected, failed or unreviewed runs never reach the database.")
    parser.add_argument("--bundle", type=Path, required=True,
                        help="bundle directory holding the four reviewed artifact "
                             "files (fit manifest, diagnostics report, readiness "
                             "report, publication approval)")
    parser.add_argument("--database-url", required=True,
                        help="near_operator psycopg database URL")
    args = parser.parse_args(arguments)
    try:
        bundle = load_bundle(args.bundle)
        report = verify_bundle(bundle)
    except PublicationGateError as error:
        print(f"near_api.research publish: {error}", file=sys.stderr)
        return EXIT_CONTRACT
    if not report.passed:
        for check in report.failures:
            print(f"[FAIL] {check.check}: {check.detail}", file=sys.stderr)
        print("near_api.research publish: the publication gate refused the bundle; "
              "nothing was written.", file=sys.stderr)
        return EXIT_CONTRACT
    run_id = derive_run_id({key: _canonical_artifact_hash(bundle[key]) for key in
                            ("fit_manifest", "diagnostics_report", "readiness_report")})
    try:
        result = publish_run(args.database_url, bundle, run_id)
    except (PublishConflictError, OperatorDatabaseError, SQLAlchemyError) as error:
        print(f"near_api.research publish: {error}", file=sys.stderr)
        return EXIT_CONTRACT
    print(json.dumps({"published": True, "already_published": result.already_published,
                      "run_id": str(result.run_id), "spec_id": result.spec_id,
                      "published_at": result.published_at,
                      "published_by": result.published_by}, indent=2, sort_keys=True))
    return 0


def main(argv: list | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="python -m near_api.research",
        description="Dispatch to the offline model research code and the NI-054 "
                    "publication gate; the wrapper owns no estimation logic.")
    parser.add_argument("--fit-module", type=Path, default=None,
                        help="path to research/models/fit.py (default: the "
                             "repository checkout of the editable install); "
                             "must be given BEFORE the command")
    parser.add_argument("--diagnostics-module", type=Path, default=None,
                        help="path to research/models/diagnostics.py (default: "
                             "the repository checkout of the editable install); "
                             "must be given BEFORE the command")
    parser.add_argument("command", choices=list(COMMANDS),
                        help="research command to run")
    parser.add_argument("arguments", nargs=argparse.REMAINDER,
                        metavar="...",
                        help="arguments owned by the command (forwarded verbatim "
                             "for fit/diagnostics)")
    arguments = parser.parse_args(argv)
    if arguments.command in FORWARDED:
        override = arguments.fit_module if arguments.command == "fit" \
            else arguments.diagnostics_module
        module = _load_research_module(arguments.command, override)
        return module.main(arguments.arguments)
    if arguments.command == "verify":
        return _verify_command(arguments.arguments)
    return _publish_command(arguments.arguments)


if __name__ == "__main__":
    sys.exit(main())
