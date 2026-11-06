"""Synthetic archive builder for NI-027 tests. No research data, no network.

Every byte, hash, name and timestamp is invented test data; the builder
constructs a disposable archive tree, its ``shasum -a 256`` manifest (written
OUTSIDE the tree) and a matching cohort scope registry, mirroring the real
handoff layout (manifest paths under a common leading directory).
"""

import hashlib
import json
from pathlib import Path

READ_CHUNK = 1024 * 1024

ALPHA_COHORT = "alpha-cohort"
BETA_COHORT = "beta-cohort"
SECRET_TOKEN = "SECRETVALUE9x8y7z"

COHORT_WINDOW = ("2026-01-01", "2026-01-31")
SAVED_AT = "2026-01-15T00:00:00Z"

# Distinctive marker sentences used to prove file contents never reach the DB.
ALPHA_PAYLOAD = "synthetic-alpha-response-payload-4f2b"
BETA_PAYLOAD = "synthetic-beta-snapshot-payload-9c1d"

REGISTRY = {
    "schema_version": 1,
    "description": "Synthetic test registry; no research data.",
    "sources": {
        "SRC-EXAMPLE": {
            "name": "Synthetic example provider",
            "docs_url": "https://docs.example.test/synthetic",
            "base_url": "https://api.example-provider.test",
            "access_status": "documented",
            "license_status": "unverified",
            "lineage": ["Synthetic lineage note for tests"],
        },
    },
    "cohorts": {
        ALPHA_COHORT: {
            "window_start": COHORT_WINDOW[0],
            "window_end_exclusive": COHORT_WINDOW[1],
            "coverage_scope": "aggregate_window",
            "partial_audit": "Synthetic partial-audit note.",
            "license_status": "unverified",
            "sources": ["SRC-EXAMPLE"],
            "basis": "synthetic fixture",
        },
        BETA_COHORT: {
            "window_start": None,
            "window_end_exclusive": None,
            "coverage_scope": "point_in_time_snapshot",
            "partial_audit": "Synthetic manifest-less cohort.",
            "license_status": "unverified",
            "sources": ["SRC-EXAMPLE"],
            "basis": "synthetic fixture",
        },
    },
}

_ALPHA_MANIFEST = {
    "window_utc_start": COHORT_WINDOW[0],
    "window_utc_end_exclusive": COHORT_WINDOW[1],
    "http_sources": {
        "data/response.json": {
            "url": f"https://api.example-provider.test/v1/data?api_key={SECRET_TOKEN}",
            "saved_at_utc": SAVED_AT,
            "http_status": 200,
        },
    },
    "files": {
        "README.md": {"bytes": None, "sha256": None},
        "data/response.json": {"bytes": None, "sha256": None},
    },
    "jobs": [
        {"id": "job_synthetic0001", "sql": "sql/01_extract.sql", "result": "data/result_raw.json"},
    ],
}

ALPHA_FILES = {
    "README.md": "Synthetic alpha cohort README.\n",
    "analysis/summary.json": '{"total": "3"}\n',
    "data/response.json": f'{{"rows": "{ALPHA_PAYLOAD}"}}\n',
    "data/result_raw.json": '{"raw_export": true}\n',
    "scripts/analyze.py": "print('synthetic')\n",
    "manifest.json": json.dumps(_ALPHA_MANIFEST, indent=2, sort_keys=True) + "\n",
}
BETA_FILES = {
    "NOTES.md": "Synthetic beta cohort without a cohort manifest.\n",
    "data/snapshot.json": f'{{"snapshot": "{BETA_PAYLOAD}"}}\n',
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_archive(root: Path) -> Path:
    """Create the synthetic archive tree under ``root`` and return the manifest path."""
    research = root / "research"
    files: dict[str, bytes] = {}
    for cohort, contents in ((ALPHA_COHORT, ALPHA_FILES), (BETA_COHORT, BETA_FILES)):
        for relative, text in contents.items():
            files[f"research/{cohort}/{relative}"] = text.encode("utf-8")
    for relative, data in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    # Resolve the cohort-internal checksum listing against the written bytes.
    manifest = json.loads(files[f"research/{ALPHA_COHORT}/manifest.json"])
    for relative, spec in manifest["files"].items():
        data = files[f"research/{ALPHA_COHORT}/{relative}"]
        spec["bytes"] = len(data)
        spec["sha256"] = _sha256_bytes(data)
    alpha_manifest_path = research / ALPHA_COHORT / "manifest.json"
    alpha_manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                                   encoding="utf-8")
    files[f"research/{ALPHA_COHORT}/manifest.json"] = alpha_manifest_path.read_bytes()

    # Strict shasum -a 256 text listing, sorted for determinism. The manifest
    # lives OUTSIDE the archive tree, mirroring the real handoff layout.
    lines = [f"{_sha256_bytes(data)}  {relative}" for relative, data in sorted(files.items())]
    manifest_path = root.parent / f"{root.name}-manifest.sha256"
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest_path


def write_registry(root: Path, registry: dict | None = None) -> Path:
    path = root / "cohort-registry.json"
    path.write_text(json.dumps(registry or REGISTRY, indent=2, sort_keys=True), encoding="utf-8")
    return path


def tree_digest(root: Path) -> dict[str, str]:
    """SHA-256 of every file under root, keyed by relative path (bytes identity)."""
    state: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            state[path.relative_to(root).as_posix()] = _sha256_bytes(path.read_bytes())
    return state
