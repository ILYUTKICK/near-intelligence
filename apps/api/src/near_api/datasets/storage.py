"""Content-addressed storage for dataset artifacts (NI-028).

Artifact bytes are written to the operator-provided storage root BEFORE the
database transaction opens (DATABASE_SCHEMA.md: "Actual bytes written before
transaction; abandoned bytes GC after 7 days").  Keys are derived exclusively
from SHA-256 digests and fixed namespaces, so no user-controlled path can
reach the filesystem: ``manifests/<aa>/<sha256>.json`` for canonical dataset
manifests and ``blobs/<aa>/<sha256>`` for copied input files.  A failed stage
leaves at most orphaned bytes, which the retention process may reclaim;
database rows are never written for bytes that failed to persist.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from near_api.datasets.canonical import SHA256_PATTERN

NAMESPACES = ("manifests", "blobs")
_KEY_PATTERN = re.compile(r"^(?P<namespace>[a-z]+)/(?P<shard>[0-9a-f]{2})/(?P<digest>[0-9a-f]{64})"
                          r"(?P<suffix>\.json)?")


class StorageError(RuntimeError):
    """Artifact bytes could not be persisted (CLI exit 5 semantics)."""


class ArtifactStorage:
    """Minimal fsync-backed store for manifest and blob artifacts."""

    def __init__(self, root: Path):
        self.root = root
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise StorageError(f"Cannot create storage root {root}: {error}") from None
        if not root.is_dir():
            raise StorageError(f"Storage root is not a directory: {root}")

    def key_for(self, namespace: str, digest: str, *, suffix: str = "") -> str:
        if namespace not in NAMESPACES:
            raise StorageError(f"Unknown storage namespace {namespace!r}")
        if not SHA256_PATTERN.match(digest):
            raise StorageError("Storage keys require a lowercase SHA-256 digest")
        if suffix not in ("", ".json"):
            raise StorageError(f"Unsupported storage suffix {suffix!r}")
        return f"{namespace}/{digest[:2]}/{digest}{suffix}"

    def store(self, namespace: str, digest: str, data: bytes, *, suffix: str = "") -> str:
        """Persist bytes under their content key and return the relative key."""
        key = self.key_for(namespace, digest, suffix=suffix)
        target = self.root / key
        if target.is_file():
            return key  # content-addressed: identical bytes are already stored
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.tmp-{os.getpid()}")
            with temporary.open("wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except OSError as error:
            raise StorageError(f"Cannot persist artifact {key}: {error}") from None
        return key

    def path_for(self, relative_key: str) -> Path:
        match = _KEY_PATTERN.match(relative_key)
        if match is None:
            raise StorageError(f"Refusing unsafe storage key {relative_key!r}")
        return self.root / relative_key
