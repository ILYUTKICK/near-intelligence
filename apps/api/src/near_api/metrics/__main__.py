"""Operator CLI for NI-029 metric emission.

``python -m near_api.metrics build --spec PATH --out-dir DIRECTORY`` reads a
bounded JSON spec, loads the canonical aggregate inputs read-only, computes
the registered-definition observations and writes one prepared-manifest JSON
per dataset. The manifests are staged with the NI-028 pipeline
(``python -m near_api.datasets stage``); this CLI never touches the
database, never writes inside the inputs and never calls the network.

Spec schema (strict, v1)::

    {
      "schema_version": 1,
      "window": {"start": "YYYY-MM-DD", "end_exclusive": "YYYY-MM-DD"},
      "inputs": {
        "flows": "PATH", "daily_flows": "PATH",
        "supply": "PATH|null", "treasury": "PATH|null"
      },
      "manifest_inputs": [
        {"name": "flows", "role": "raw", "source_id": "SRC-BQ"}, ...
      ],
      "pipeline": {"pipeline_version": "...", "code_commit": null,
                    "config_hash": null, "dependency_lock_hash": null,
                    "source_as_of": null, "retrieved_at": null,
                    "quality": {}}
    }

Exit codes: 0 success; 4 spec/contract failure.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from near_api.datasets.canonical import load_json_strict
from near_api.metrics.emit import (
    DatasetSpec,
    ManifestInputSpec,
    build_all_manifests,
)
from near_api.metrics.loaders import load_metric_inputs
from near_api.datasets.canonical import CanonicalFormatError
from near_api.metrics.compute import MetricComputationError

MAX_SPEC_BYTES = 1024 * 1024
INPUT_NAMES = ("flows", "daily_flows", "supply", "treasury")
REQUIRED_INPUTS = ("flows", "daily_flows")
INPUT_ROLES = ("raw", "normalized", "price", "sql", "config")

EXIT_OK = 0
EXIT_CONTRACT = 4


def _parse_spec(data: bytes) -> dict:
    try:
        document = load_json_strict(data, context="metrics spec")
    except CanonicalFormatError as error:
        raise MetricComputationError(str(error)) from None
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise MetricComputationError("the metrics spec requires schema_version 1")
    unknown = sorted(set(document) - {"schema_version", "window", "inputs",
                                      "manifest_inputs", "pipeline"})
    if unknown:
        raise MetricComputationError(f"unknown spec fields {unknown}")
    window = document.get("window")
    if not isinstance(window, dict) or set(window) != {"start", "end_exclusive"}:
        raise MetricComputationError("spec.window requires start and end_exclusive")
    inputs = document.get("inputs")
    if not isinstance(inputs, dict):
        raise MetricComputationError("spec.inputs must be an object of file paths")
    for name in REQUIRED_INPUTS:
        if not isinstance(inputs.get(name), str) or not inputs[name]:
            raise MetricComputationError(f"spec.inputs.{name} is required")
    for name, value in inputs.items():
        if name not in INPUT_NAMES:
            raise MetricComputationError(f"unknown spec input {name!r}")
        if value is not None and (not isinstance(value, str) or not value):
            raise MetricComputationError(f"spec.inputs.{name} must be a path or null")
    entries = document.get("manifest_inputs")
    if not isinstance(entries, list) or not entries:
        raise MetricComputationError("spec.manifest_inputs must be a non-empty list")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"name", "role", "source_id"}:
            raise MetricComputationError("manifest_inputs entries need name/role/source_id")
        if entry["name"] not in INPUT_NAMES or inputs.get(entry["name"]) is None:
            raise MetricComputationError(
                f"manifest input {entry.get('name')!r} has no declared input path")
        if entry["role"] not in INPUT_ROLES:
            raise MetricComputationError(f"manifest input role {entry['role']!r} is invalid")
    pipeline = document.get("pipeline")
    if not isinstance(pipeline, dict) or not isinstance(pipeline.get("pipeline_version"), str) \
            or not pipeline["pipeline_version"]:
        raise MetricComputationError("spec.pipeline.pipeline_version is required")
    return document


def build_from_spec(spec_path: Path, out_dir: Path) -> dict:
    """Load inputs per the spec and write one manifest per dataset."""
    try:
        data = spec_path.read_bytes()
    except OSError as error:
        raise MetricComputationError(f"cannot read spec {spec_path}: {error}") from None
    if len(data) > MAX_SPEC_BYTES:
        raise MetricComputationError(f"spec exceeds {MAX_SPEC_BYTES} bytes")
    document = _parse_spec(data)
    window = document["window"]
    inputs = document["inputs"]
    paths = {name: (Path(inputs[name]) if inputs.get(name) else None)
             for name in INPUT_NAMES}
    manifest_inputs = tuple(
        ManifestInputSpec(name=entry["name"], path=paths[entry["name"]], role=entry["role"],
                          source_id=entry["source_id"] or None)
        for entry in document["manifest_inputs"])
    pipeline = document["pipeline"]
    dataset_spec = DatasetSpec(
        pipeline_version=pipeline["pipeline_version"],
        quality=pipeline.get("quality") or {},
        code_commit=pipeline.get("code_commit"),
        config_hash=pipeline.get("config_hash"),
        dependency_lock_hash=pipeline.get("dependency_lock_hash"),
        source_as_of=(dt.datetime.fromisoformat(str(pipeline["source_as_of"]).replace("Z", "+00:00"))
                      if pipeline.get("source_as_of") else None),
        retrieved_at=(dt.datetime.fromisoformat(str(pipeline["retrieved_at"]).replace("Z", "+00:00"))
                      if pipeline.get("retrieved_at") else None))
    bundle = load_metric_inputs(
        window_start=dt.date.fromisoformat(window["start"]),
        window_end_exclusive=dt.date.fromisoformat(window["end_exclusive"]),
        flows_path=paths["flows"], daily_flows_path=paths["daily_flows"],
        supply_path=paths["supply"], treasury_path=paths["treasury"])
    manifests = build_all_manifests(bundle, dataset_spec=dataset_spec,
                                    manifest_inputs=manifest_inputs)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for dataset_key, manifest in manifests.items():
        target = out_dir / f"{dataset_key}.manifest.json"
        target.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")) + "\n", encoding="utf-8")
        written[dataset_key] = str(target)
    return {"datasets": written,
            "observation_counts": {key: len(value["observations"])
                                   for key, value in manifests.items()}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m near_api.metrics",
        description="NI-029 exact metric computations: emit registered-definition "
                    "prepared manifests for the NI-028 staging pipeline (offline, "
                    "read-only inputs).")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="compute observations and write manifests")
    build.add_argument("--spec", type=Path, required=True, help="computation spec JSON")
    build.add_argument("--out-dir", type=Path, required=True, help="manifest output directory")
    arguments = parser.parse_args(argv)
    try:
        summary = build_from_spec(arguments.spec, arguments.out_dir)
    except MetricComputationError as error:
        print(f"METRIC COMPUTATION FAILED (nothing emitted): {error}", file=sys.stderr)
        return EXIT_CONTRACT
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
