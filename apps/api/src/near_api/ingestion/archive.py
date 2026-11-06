"""NI-027: read-only import of the existing research archive lineage.

Operator CLI (``python -m near_api.ingestion.archive``) that records the
existing saved research archive in the database WITHOUT copying, moving or
modifying a single byte of it. For every manifest-listed file the import
stores only path, SHA-256, byte size, aggregate/raw role, cohort and coverage
scope; file contents are never persisted. Credential-bearing strings extracted
from cohort manifests are redacted before storage.

Ordering invariant (fail closed): the archive is fully verified against the
hash manifest BEFORE any content is read. Metadata parsing, cohort-manifest
cross-checks and database writes run only after every byte has matched, so a
corrupt archive can never contribute metadata. Any verification divergence —
bad hash, missing file, extra file, symlink — rejects the whole batch: no
partial imports, no silent substitutions, no fixtures standing in for missing
sources.

Idempotency: the manifest SHA-256 is the unique batch key. Re-importing the
same manifest re-verifies every byte and then changes nothing.

Scope boundaries: the original archive stays untouched (this module only
reads); dataset staging/publication and live ingestion runs remain NI-028 and
NI-030; cohort scope declarations come from the versioned registry file
(--cohorts), never from assumptions in code.

Exit codes: 0 success or idempotent no-op; 3 archive verification failure;
4 manifest/registry/metadata contract failure; 5 database failure.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
import posixpath
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from sqlalchemy import NullPool, create_engine, text
from sqlalchemy.engine import Engine, make_url

MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_COHORT_REGISTRY = MODULE_DIR / "archive_cohorts.json"

READ_CHUNK = 1024 * 1024
MAX_METADATA_BYTES = 4096
MAX_MANIFEST_ENTRIES = 100_000

EXIT_OK = 0
EXIT_VERIFICATION = 3
EXIT_CONTRACT = 4
EXIT_DATABASE = 5

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MANIFEST_LINE = re.compile(r"^([0-9a-f]{64})  (.+)$")
COHORT_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,78}$")
SOURCE_ID_PATTERN = re.compile(r"^SRC-[A-Z]+(?:-[A-Z]+)*$")
COVERAGE_SCOPES = frozenset({
    "raw_saved_response", "aggregate_window", "partial_raw_audit",
    "point_in_time_snapshot", "process_documentation",
})
LICENSE_STATUSES = frozenset({"unknown", "unverified", "verified", "prohibited"})
ACCESS_STATUSES = frozenset({"disabled", "documented", "approved"})
FILE_ROLES = frozenset({"raw", "aggregate", "provenance", "editorial", "script"})

# Host/path-to-source mapping for lineage attribution. Unknown remotes stay
# unattributed (NULL) with the redacted URL recorded — never guessed.
_HOST_SOURCES: tuple[tuple[str, str], ...] = (
    ("api.coingecko.com", "SRC-PRICE"),
    ("api.llama.fi", "SRC-LLAMA"),
    ("revenue.near.org", "SRC-DASHBOARD"),
    ("api.nearblocks.io", "SRC-NEARBLOCKS"),
)
_HOST_SUFFIX_SOURCES: tuple[tuple[str, str], ...] = (
    ("fastnear.com", "SRC-FASTNEAR"),
    ("mainnet.near.org", "SRC-NEAR-RPC"),
)
_PATH_SOURCES: tuple[tuple[str, str], ...] = (
    ("DefiLlama/dimension-adapters", "SRC-LLAMA"),
)


class ArchiveImportError(RuntimeError):
    """Base failure; the CLI prints message + exit code and imports nothing."""


class ManifestFormatError(ArchiveImportError):
    """The hash manifest itself is not a strict shasum -a 256 listing."""


class ArchiveVerificationError(ArchiveImportError):
    """Archive bytes diverge from the manifest; the whole batch is rejected."""


class MetadataContractError(ArchiveImportError):
    """Cohort metadata contradicts the registry or exceeds safe bounds."""


class OperatorDatabaseError(ArchiveImportError):
    """The database credential/role is not the expected operator role."""


# --------------------------------------------------------------------------- #
# Credential redaction
# --------------------------------------------------------------------------- #

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{2,}\.[A-Za-z0-9_-]{2,}")
_BEARER_RE = re.compile(
    r"(?i)(?<![\w.-])(bearer|token|password|secret)(?:\s*[:=]\s*|\s+)([A-Za-z0-9._~+/=-]{8,})")
_USERINFO_RE = re.compile(r"(?<=//)([^/@\s:?#]+):([^@\s/?#]+)@")
_SECRET_PARAM_RE = re.compile(
    r"(?i)([?&;][a-z0-9_]*(?:token|key|secret|password|credential|authorization|auth|signature|jwt|session|cookie)[a-z0-9_]*=)"
    r"([^&;\s]+)")
_LONG_RUN_RE = re.compile(r"(?<![A-Za-z0-9_-])([A-Za-z0-9_-]{40,})(?![A-Za-z0-9_-])")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

REDACTED = "[redacted]"


def redact_credentials(value: str) -> str:
    """Return ``value`` with credential-bearing substrings replaced.

    Deterministic and conservative: JWTs, bearer-style assignments, URL
    userinfo, sensitive query parameters and long secret-looking runs are
    redacted. 64-char lowercase hex (SHA-256 hashes) is preserved; hashes
    belong in dedicated columns and are legitimate provenance.
    """
    redacted = _JWT_RE.sub(REDACTED, value)
    redacted = _BEARER_RE.sub(lambda m: f"{m.group(1)} {REDACTED}", redacted)
    redacted = _USERINFO_RE.sub(f"{REDACTED}:{REDACTED}@", redacted)
    redacted = _SECRET_PARAM_RE.sub(lambda m: f"{m.group(1)}{REDACTED}", redacted)
    redacted = _LONG_RUN_RE.sub(
        lambda m: REDACTED if not _HEX64_RE.fullmatch(m.group(1)) else m.group(1), redacted)
    return redacted


def _redact_json(value: Any) -> Any:
    if isinstance(value, str):
        return redact_credentials(value)
    if isinstance(value, list):
        return [_redact_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_json(item) for key, item in value.items()}
    return value


def _bounded_metadata(payload: dict, *, context: str) -> dict:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_METADATA_BYTES:
        raise MetadataContractError(f"Sanitized metadata for {context} exceeds {MAX_METADATA_BYTES} bytes")
    return json.loads(encoded)


# --------------------------------------------------------------------------- #
# Manifest parsing and byte verification
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ManifestEntry:
    sha256: str
    relative_path: str


@dataclass(frozen=True)
class FileFact:
    relative_path: str
    sha256: str
    byte_size: int


def _reject_unsafe_path(relative_path: str) -> None:
    pure = PurePosixPath(relative_path)
    if relative_path.startswith("/") or "\\" in relative_path or not pure.parts:
        raise ManifestFormatError(f"Manifest path must be relative and POSIX-style: {relative_path!r}")
    if any(part in ("..", ".") for part in pure.parts):
        raise ManifestFormatError(f"Manifest path must not traverse directories: {relative_path!r}")


def parse_manifest(manifest_path: Path) -> tuple[str, tuple[ManifestEntry, ...]]:
    """Parse a strict ``shasum -a 256`` text listing (hash, two spaces, path)."""
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ManifestFormatError(f"Manifest is unreadable: {error}") from None
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    entries: list[ManifestEntry] = []
    seen: set[str] = set()
    for number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            raise ManifestFormatError(f"Manifest line {number} is empty")
        match = MANIFEST_LINE.fullmatch(line)
        if not match:
            raise ManifestFormatError(
                f"Manifest line {number} is not '<64-hex>  <path>' text mode: {line[:80]!r}")
        checksum, relative_path = match.group(1), match.group(2)
        _reject_unsafe_path(relative_path)
        if relative_path in seen:
            raise ManifestFormatError(f"Manifest lists {relative_path!r} twice")
        seen.add(relative_path)
        entries.append(ManifestEntry(checksum, relative_path))
    if not entries:
        raise ManifestFormatError("Manifest lists no files")
    if len(entries) > MAX_MANIFEST_ENTRIES:
        raise ManifestFormatError(f"Manifest exceeds {MAX_MANIFEST_ENTRIES} entries")
    return digest, tuple(entries)


def _iter_archive_files(root: Path) -> tuple[set[str], list[str]]:
    """Return (regular relative paths, symlink/irregular violations)."""
    files: set[str] = set()
    violations: list[str] = []
    for base, directories, names in os.walk(root, followlinks=False):
        for name in directories + names:
            path = Path(base) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                violations.append(f"symlink {relative}")
            elif path.is_file():
                files.add(relative)
            elif path.is_dir():
                continue
            else:
                violations.append(f"irregular {relative}")
    return files, violations


def common_manifest_prefix(entries: tuple[ManifestEntry, ...]) -> str:
    """Longest common leading directory of every manifest path ('' if none).

    Leaves at least ``<cohort>/<file>`` so classification always has a cohort
    directory and one file name.
    """
    split_paths = [entry.relative_path.split("/") for entry in entries]
    shortest = min(len(parts) for parts in split_paths)
    common_parts: list[str] = []
    for index in range(shortest - 1):
        candidate = split_paths[0][index]
        if all(parts[index] == candidate for parts in split_paths):
            common_parts.append(candidate)
        else:
            break
    return "/".join(common_parts) + "/" if common_parts else ""


def verify_archive(root: Path, entries: tuple[ManifestEntry, ...],
                   *, hash_only: bool = False) -> dict[str, FileFact]:
    """Verify every manifest entry by streaming bytes; contents are not parsed.

    The whole batch is rejected on the first hash mismatch. The tree
    comparison (missing/extra/symlink) is scoped to the manifest's covered
    subtree (the common leading directory, e.g. ``research/``): the handed-off
    archive is that subtree, and unrelated files beside it — such as a working
    checkout — are not part of the manifest's claim. Within the covered
    subtree the comparison stays strict in both directions.
    ``hash_only`` keeps the tree comparison for the caller (used by the
    content-read stage boundary in tests).
    """
    if not root.is_dir():
        raise ArchiveVerificationError(f"Archive root is not a directory: {root}")
    facts: dict[str, FileFact] = {}
    for entry in sorted(entries, key=lambda item: item.relative_path):
        path = root / entry.relative_path
        if not path.exists():
            raise ArchiveVerificationError(f"Manifest file is missing from the archive: {entry.relative_path}")
        if path.is_symlink() or not path.is_file():
            raise ArchiveVerificationError(
                f"Manifest entry is not a regular file: {entry.relative_path}")
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(READ_CHUNK), b""):
                digest.update(chunk)
                size += len(chunk)
        computed = digest.hexdigest()
        if computed != entry.sha256:
            raise ArchiveVerificationError(
                f"SHA-256 mismatch for {entry.relative_path}: manifest {entry.sha256}, archive {computed}")
        facts[entry.relative_path] = FileFact(entry.relative_path, computed, size)
    if hash_only:
        return facts
    prefix = common_manifest_prefix(entries)
    covered_root = root.joinpath(*prefix.split("/")) if prefix else root
    expected = {entry.relative_path for entry in entries}
    present, violations = _iter_archive_files(covered_root)
    present = {f"{prefix}{relative}" for relative in present}
    violations = [f"{prefix}{violation}" for violation in violations]
    if violations:
        sample = "; ".join(sorted(violations)[:5])
        raise ArchiveVerificationError(
            f"Archive contains {len(violations)} non-regular entries; the batch is rejected: {sample}")
    missing = sorted(expected - present)
    if missing:
        raise ArchiveVerificationError(
            f"{len(missing)} manifest files are absent from the archive tree; the batch is rejected "
            f"(first: {missing[0]})")
    extra = sorted(present - expected)
    if extra:
        raise ArchiveVerificationError(
            f"{len(extra)} archive files are absent from the manifest; the batch is rejected "
            f"(first: {extra[0]})")
    return facts


# --------------------------------------------------------------------------- #
# Cohort scope registry
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SourceDeclaration:
    id: str
    name: str
    docs_url: str | None
    base_url: str | None
    access_status: str
    license_status: str
    verified_at: dt.datetime | None
    lineage: tuple[str, ...]


@dataclass(frozen=True)
class CohortDeclaration:
    name: str
    window_start: dt.date | None
    window_end_exclusive: dt.date | None
    coverage_scope: str
    partial_audit: str
    license_status: str
    sources: tuple[str, ...]
    basis: str


@dataclass(frozen=True)
class CohortRegistry:
    manifest_sha256: str
    sources: dict[str, SourceDeclaration] = field(default_factory=dict)
    cohorts: dict[str, CohortDeclaration] = field(default_factory=dict)


def _parse_date(value: Any, *, context: str) -> dt.date:
    if not isinstance(value, str):
        raise MetadataContractError(f"{context} must be an ISO date string")
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        raise MetadataContractError(f"{context} is not an ISO date: {value!r}") from None


def _parse_utc(value: Any, *, context: str) -> dt.datetime:
    if not isinstance(value, str):
        raise MetadataContractError(f"{context} must be an ISO-8601 UTC timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise MetadataContractError(f"{context} is not ISO-8601: {value!r}") from None
    if parsed.utcoffset() is None:
        raise MetadataContractError(f"{context} requires an explicit timezone: {value!r}")
    return parsed.astimezone(dt.timezone.utc)


def _bounded_text(value: Any, *, limit: int, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise MetadataContractError(f"{context} must be a non-empty string")
    redacted = redact_credentials(value)
    if len(redacted) > limit:
        raise MetadataContractError(f"{context} exceeds {limit} characters")
    return redacted


def load_cohort_registry(path: Path) -> CohortRegistry:
    """Load and validate the versioned cohort scope declarations."""
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise MetadataContractError(f"Cohort registry is unreadable: {error}") from None
    digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    try:
        document = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise MetadataContractError(f"Cohort registry is not valid JSON: {error}") from None
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise MetadataContractError("Cohort registry requires schema_version 1")
    sources: dict[str, SourceDeclaration] = {}
    for source_id, spec in (document.get("sources") or {}).items():
        if not SOURCE_ID_PATTERN.fullmatch(source_id):
            raise MetadataContractError(f"Registry source id is invalid: {source_id!r}")
        verified_at = spec.get("verified_at")
        sources[source_id] = SourceDeclaration(
            id=source_id,
            name=_bounded_text(spec.get("name"), limit=200, context=f"{source_id} name"),
            docs_url=_bounded_text(spec["docs_url"], limit=500, context=f"{source_id} docs_url")
            if spec.get("docs_url") else None,
            base_url=_bounded_text(spec["base_url"], limit=500, context=f"{source_id} base_url")
            if spec.get("base_url") else None,
            access_status=spec.get("access_status", "documented"),
            license_status=spec.get("license_status", "unverified"),
            verified_at=_parse_utc(verified_at, context=f"{source_id} verified_at")
            if verified_at else None,
            lineage=tuple(
                _bounded_text(item, limit=200, context=f"{source_id} lineage item")
                for item in (spec.get("lineage") or ())[:10]),
        )
        if sources[source_id].access_status not in ACCESS_STATUSES:
            raise MetadataContractError(f"{source_id} access_status is invalid")
        if sources[source_id].license_status not in LICENSE_STATUSES:
            raise MetadataContractError(f"{source_id} license_status is invalid")
    cohorts: dict[str, CohortDeclaration] = {}
    for name, spec in (document.get("cohorts") or {}).items():
        if not COHORT_PATTERN.fullmatch(name):
            raise MetadataContractError(f"Registry cohort name is invalid: {name!r}")
        scope = spec.get("coverage_scope")
        if scope not in COVERAGE_SCOPES:
            raise MetadataContractError(f"Cohort {name} has invalid coverage_scope {scope!r}")
        license_status = spec.get("license_status", "unverified")
        if license_status not in LICENSE_STATUSES:
            raise MetadataContractError(f"Cohort {name} has invalid license_status")
        cohort_sources = tuple(spec.get("sources") or ())
        for source_id in cohort_sources:
            if source_id not in sources:
                raise MetadataContractError(
                    f"Cohort {name} references undeclared registry source {source_id!r}")
        cohorts[name] = CohortDeclaration(
            name=name,
            window_start=_parse_date(spec["window_start"], context=f"{name} window_start")
            if spec.get("window_start") else None,
            window_end_exclusive=_parse_date(spec["window_end_exclusive"],
                                             context=f"{name} window_end_exclusive")
            if spec.get("window_end_exclusive") else None,
            coverage_scope=scope,
            partial_audit=_bounded_text(spec.get("partial_audit"), limit=1000,
                                        context=f"{name} partial_audit"),
            license_status=license_status,
            sources=cohort_sources,
            basis=_bounded_text(spec.get("basis"), limit=300, context=f"{name} basis"),
        )
        if (cohorts[name].window_start is None) != (cohorts[name].window_end_exclusive is None):
            raise MetadataContractError(f"Cohort {name} window requires both boundaries")
        if (cohorts[name].window_start is not None
                and cohorts[name].window_end_exclusive <= cohorts[name].window_start):
            raise MetadataContractError(f"Cohort {name} window end must be after start")
    if not cohorts:
        raise MetadataContractError("Cohort registry declares no cohorts")
    return CohortRegistry(manifest_sha256=digest, sources=sources, cohorts=cohorts)


# --------------------------------------------------------------------------- #
# Cohort metadata extraction (runs only after full byte verification)
# --------------------------------------------------------------------------- #


@dataclass
class CohortMetadata:
    name: str
    manifest_relative_path: str | None = None
    manifest_sha256: str | None = None
    window_start: dt.date | None = None
    window_end_exclusive: dt.date | None = None
    documented_raw: set[str] = field(default_factory=set)   # cohort-relative paths
    file_metadata: dict[str, dict] = field(default_factory=dict)
    runs: list[dict] = field(default_factory=list)
    checksum_targets: tuple[tuple[str, str, int | None], ...] = ()

    def metadata_for(self, cohort_relative_path: str) -> dict:
        return self.file_metadata.get(cohort_relative_path, {})


def _window_from_manifest(document: dict) -> tuple[dt.date | None, dt.date | None]:
    for start_key, end_key in (
        ("window_utc_start", "window_utc_end_exclusive"),
        ("period_start_inclusive", "period_end_exclusive"),
        ("history_period_start_inclusive", "history_period_end_exclusive"),
        ("window_start_utc", "window_end_exclusive_utc"),
    ):
        if document.get(start_key) and document.get(end_key):
            return (_parse_date(document[start_key], context=start_key),
                    _parse_date(document[end_key], context=end_key))
    window = document.get("window_utc")
    if isinstance(window, (list, tuple)) and len(window) == 2:
        return (_parse_date(window[0], context="window_utc[0]"),
                _parse_date(window[1], context="window_utc[1]"))
    if document.get("pilot_day_utc"):
        day = _parse_date(document["pilot_day_utc"], context="pilot_day_utc")
        return day, day + dt.timedelta(days=1)
    return None, None


def _source_for_remote(reference: str) -> str | None:
    parts = urlsplit(reference)
    host = (parts.hostname or "").lower()
    for candidate, source_id in _HOST_SOURCES:
        if host == candidate:
            return source_id
    for suffix, source_id in _HOST_SUFFIX_SOURCES:
        if host == suffix or host.endswith(f".{suffix}"):
            return source_id
    for fragment, source_id in _PATH_SOURCES:
        if fragment in reference:
            return source_id
    return None


def _cohort_manifest_document(cohort_dir_prefix: str, facts: dict[str, FileFact],
                              root: Path) -> tuple[str | None, dict]:
    manifest_relative = f"{cohort_dir_prefix}manifest.json"
    if manifest_relative not in facts:
        return None, {}
    path = root / manifest_relative
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MetadataContractError(f"Cohort manifest {manifest_relative} is unreadable: {error}") from None
    if not isinstance(document, dict):
        raise MetadataContractError(f"Cohort manifest {manifest_relative} must be a JSON object")
    return manifest_relative, document


def _checksum_targets(cohort_name: str, manifest_relative: str, document: dict) -> \
        tuple[tuple[str, str, int | None], ...]:
    """Internal checksum listings: (full relative path, sha256, bytes|None)."""
    directory = posixpath.dirname(manifest_relative)
    targets: list[tuple[str, str, int | None]] = []
    listing = document.get("files")
    if isinstance(listing, dict):
        for relative, spec in listing.items():
            expected = spec.get("sha256") if isinstance(spec, dict) else spec
            size = spec.get("bytes") if isinstance(spec, dict) else None
            if not isinstance(expected, str) or not SHA256_PATTERN.fullmatch(expected):
                raise MetadataContractError(
                    f"Cohort {cohort_name} manifest lists an invalid sha256 for {relative!r}")
            targets.append((posixpath.join(directory, str(relative)) if directory else str(relative),
                            expected, int(size) if isinstance(size, int) else None))
    listing = document.get("sha256")
    if isinstance(listing, dict):
        for relative, expected in listing.items():
            if not isinstance(expected, str) or not SHA256_PATTERN.fullmatch(expected):
                raise MetadataContractError(
                    f"Cohort {cohort_name} manifest lists an invalid sha256 for {relative!r}")
            targets.append((posixpath.join(directory, str(relative)) if directory else str(relative),
                            expected, None))
    return tuple(targets)


def _run_row(batch_id: UUID, source_id: str | None, query_identity: str | None,
             retrieval_utc: dt.datetime | None, byte_count: int | None,
             metadata: dict) -> dict:
    return {
        "id": uuid4(),
        "batch_id": batch_id,
        "source_id": source_id,
        "query_identity": redact_credentials(query_identity)[:1024] if query_identity else None,
        "retrieval_utc": retrieval_utc,
        "byte_count": byte_count,
        "request_count": None,
        "metadata": json.dumps(_bounded_metadata(metadata, context=f"source run {query_identity!r}"),
                               ensure_ascii=False, sort_keys=True),
    }


def extract_cohort_metadata(batch_id: UUID, cohort_name: str, cohort_dir_prefix: str,
                            facts: dict[str, FileFact], root: Path,
                            declaration: CohortDeclaration,
                            registry: CohortRegistry | None = None) -> CohortMetadata:
    """Extract sanitized lineage from the cohort's own manifest.json.

    Only documented facts are recorded; a cohort without manifest.json simply
    has none (missing is not fabricated). Cohort-level window/audit scope come
    from the reviewed registry and are cross-checked against the manifest.
    """
    metadata = CohortMetadata(name=cohort_name)
    # Attribution is only allowed to sources the loaded registry declares; a
    # mapping to an undeclared source stays unattributed (NULL) instead of
    # inventing a catalog row.
    def declared(source_id: str | None) -> str | None:
        if source_id is None or registry is None:
            return source_id
        return source_id if source_id in registry.sources else None

    def attributed(source_id: str | None) -> str | None:
        # A documented retrieval with no host mapping inherits the cohort's
        # single declared source; with several candidates it stays NULL.
        result = declared(source_id)
        if result is None and len(declaration.sources) == 1:
            return declaration.sources[0]
        return result

    manifest_relative, document = _cohort_manifest_document(cohort_dir_prefix, facts, root)
    metadata.manifest_relative_path = manifest_relative
    if manifest_relative is None:
        # A cohort without manifest.json simply documents no per-file lineage;
        # registry scope still applies (missing is not fabricated).
        metadata.manifest_sha256 = None
        return metadata
    metadata.manifest_sha256 = facts[manifest_relative].sha256
    metadata.file_metadata[manifest_relative[len(cohort_dir_prefix):]] = {
        "cohort_manifest": metadata.manifest_sha256}

    manifest_start, manifest_end = _window_from_manifest(document)
    if (manifest_start is None) != (declaration.window_start is None) or (
            manifest_start is not None
            and (manifest_start, manifest_end) != (declaration.window_start,
                                                   declaration.window_end_exclusive)):
        raise MetadataContractError(
            f"Cohort {cohort_name} window {manifest_start}..{manifest_end} contradicts the "
            f"registry declaration {declaration.window_start}..{declaration.window_end_exclusive}")
    metadata.window_start, metadata.window_end_exclusive = manifest_start, manifest_end

    # Internal checksum listings must agree with the verified archive bytes.
    metadata.checksum_targets = _checksum_targets(cohort_name, manifest_relative, document)

    # Documented saved HTTP responses: per-file source + retrieval run rows.
    http_sources = document.get("http_sources")
    if isinstance(http_sources, dict):
        for relative, spec in http_sources.items():
            if not isinstance(spec, dict) or not spec.get("url"):
                raise MetadataContractError(
                    f"Cohort {cohort_name} http_sources entry {relative!r} lacks a url")
            url = redact_credentials(str(spec["url"]))
            saved_at = (_parse_utc(spec["saved_at_utc"], context=f"{cohort_name} {relative} saved_at_utc")
                        if spec.get("saved_at_utc") else None)
            http_status = spec.get("http_status")
            full_path = posixpath.join(posixpath.dirname(manifest_relative), str(relative))
            if full_path not in facts:
                raise MetadataContractError(
                    f"Cohort {cohort_name} http_sources references {relative!r}, which is not a "
                    "manifest-listed file; missing sources are never substituted")
            metadata.documented_raw.add(str(relative))
            metadata.file_metadata[str(relative)] = _bounded_metadata(
                {"http": {"url": url, "saved_at_utc": saved_at.isoformat() if saved_at else None,
                          "http_status": http_status}}, context=f"{cohort_name}/{relative}")
            metadata.runs.append(_run_row(
                batch_id, attributed(_source_for_remote(url)), url, saved_at,
                facts[full_path].byte_size, {"http_status": http_status}))

    # Endpoint lists without per-file mapping: run-level lineage only.
    data_sources = document.get("data_sources")
    if isinstance(data_sources, list):
        for reference in data_sources:
            if not isinstance(reference, str) or not reference:
                raise MetadataContractError(f"Cohort {cohort_name} data_sources entries must be URLs")
            metadata.runs.append(_run_row(
                batch_id, attributed(_source_for_remote(reference)), reference, None, None, {}))

    # Path/glob-to-endpoint mappings attribute saved files to sources.
    sources = document.get("sources")
    if isinstance(sources, dict):
        cohort_files = [f[len(cohort_dir_prefix):] for f in facts if f.startswith(cohort_dir_prefix)
                        and f != manifest_relative]
        for pattern, reference in sources.items():
            if not isinstance(reference, str) or not reference:
                raise MetadataContractError(f"Cohort {cohort_name} sources entries must be URLs")
            source_id = _source_for_remote(reference)
            matched = [candidate for candidate in cohort_files
                       if fnmatch.fnmatchcase(candidate, str(pattern))]
            if not matched:
                raise MetadataContractError(
                    f"Cohort {cohort_name} sources pattern {pattern!r} matches no manifest-listed file")
            for candidate in matched:
                metadata.documented_raw.add(candidate)
                metadata.file_metadata.setdefault(candidate, _bounded_metadata(
                    {"source_url": redact_credentials(reference)}, context=f"{cohort_name}/{candidate}"))
                if source_id:
                    previous = metadata.file_metadata[candidate]
                    previous.setdefault("source_id", source_id)

    # BigQuery/explorer job identifiers: documented retrieval runs.
    def job_rows(value: Any, default_source: str) -> None:
        items: list[tuple[str | None, dict]] = []
        if isinstance(value, str):
            items.append((value, {}))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and item.get("id"):
                    items.append((str(item["id"]),
                                  {k: v for k, v in item.items() if k in ("sql", "result")}))
        elif isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, str):
                    items.append((item, {"period": str(key)}))
        for job_id, extra in items:
            metadata.runs.append(_run_row(
                batch_id, attributed(default_source), job_id, None, None,
                _bounded_metadata(extra, context=f"job {job_id!r}")))

    if document.get("jobs") is not None:
        job_rows(document["jobs"], "SRC-BQ")
    for key in ("job", "parent_job"):
        if document.get(key):
            job_rows(document[key], "SRC-BQ")
    if document.get("onchain_export_jobs") is not None:
        job_rows(document["onchain_export_jobs"], "SRC-BQ")
    explorer = document.get("explorer_probe")
    if isinstance(explorer, dict):
        result = explorer.get("result")
        if isinstance(result, str) and posixpath.join(
                posixpath.dirname(manifest_relative), result) not in facts:
            raise MetadataContractError(
                f"Cohort {cohort_name} explorer_probe references unlisted result {result!r}")
        payload = {key: explorer[key] for key in ("result", "http_status", "rows")
                   if key in explorer}
        metadata.runs.append(_run_row(
            batch_id, attributed("SRC-INTENTS"), "explorer_probe", None, None,
            _bounded_metadata(payload, context=f"{cohort_name} explorer_probe")))
    return metadata


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #


def classify_role(sub_path: str, *, documented_raw: bool) -> str:
    """Deterministic, conservative aggregate/raw role for one archive file.

    A file only becomes ``raw`` when the archive itself documents it as a
    saved response/export (endpoint mapping or ``*_raw`` naming); everything
    else stays ``aggregate``/provenance/editorial so an aggregate-only archive
    can never claim raw-chain completeness.
    """
    pure = PurePosixPath(sub_path)
    name = pure.name
    suffix = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if "scripts" in pure.parts or suffix in {"py", "ts", "sql", "sh", "mjs"}:
        return "script"
    if name == "manifest.json" or suffix in {"sha256", "pid"} or name == "STOP_PUBLIC_COLLECTION":
        return "provenance"
    if suffix == "md":
        return "editorial"
    if "analysis" in pure.parts:
        return "aggregate"
    if "_raw" in name or documented_raw:
        return "raw"
    return "aggregate"


def coverage_for_role(role: str, declaration: CohortDeclaration) -> tuple[str, dt.date | None,
                                                                        dt.date | None]:
    if role in ("provenance", "editorial", "script"):
        return "process_documentation", None, None
    return declaration.coverage_scope, declaration.window_start, declaration.window_end_exclusive


# --------------------------------------------------------------------------- #
# Database write (near_operator only)
# --------------------------------------------------------------------------- #


def create_operator_engine(database_url: str) -> Engine:
    try:
        url = make_url(database_url)
    except Exception:
        raise OperatorDatabaseError("Invalid operator database URL") from None
    if (url.drivername != "postgresql+psycopg" or url.username != "near_operator"
            or not url.password or "REPLACE" in url.password.upper()):
        raise OperatorDatabaseError(
            "Archive import requires the dedicated near_operator psycopg credential")
    return create_engine(url, poolclass=NullPool, hide_parameters=True,
                         connect_args={"connect_timeout": 5, "options": "-c timezone=UTC"})


def _assert_operator(connection: Any) -> None:
    role = connection.execute(text("""
        SELECT current_user AS name, session_user AS login, rolsuper, rolbypassrls,
               rolcreatedb, rolcreaterole, rolreplication
        FROM pg_roles WHERE rolname = current_user
    """)).mappings().one()
    if (role["name"] != "near_operator" or role["login"] != "near_operator"
            or any(role[key] for key in ("rolsuper", "rolbypassrls", "rolcreatedb",
                                         "rolcreaterole", "rolreplication"))):
        raise OperatorDatabaseError("Import transaction must run as the unprivileged near_operator")


def _existing_batch(connection: Any, manifest_sha256: str, facts: dict[str, FileFact]) -> UUID | None:
    row = connection.execute(text("""
        SELECT id, manifest_file_count, verified_bytes FROM app.import_batches
        WHERE manifest_sha256 = :digest
    """), {"digest": manifest_sha256}).mappings().first()
    if row is None:
        return None
    stored_files = connection.execute(text("""
        SELECT relative_path, sha256 FROM app.imported_files WHERE batch_id = :batch_id
    """), {"batch_id": row["id"]}).all()
    stored = {path: checksum for path, checksum in stored_files}
    expected = {path: fact.sha256 for path, fact in facts.items()}
    if (row["manifest_file_count"] != len(expected) or row["verified_bytes"]
            != sum(fact.byte_size for fact in facts.values()) or stored != expected):
        raise ArchiveImportError(
            "Stored batch diverges from the re-verified manifest; refusing to mutate "
            "(investigate manually rather than overwriting import history)")
    return row["id"]


def _upsert_sources(connection: Any, registry: CohortRegistry) -> int:
    total = 0
    for source in registry.sources.values():
        result = connection.execute(text("""
            INSERT INTO app.sources(id, name, docs_url, base_url, access_status,
                                    license_status, verified_at, lineage)
            VALUES (:id, :name, :docs_url, :base_url, :access_status,
                    :license_status, :verified_at, CAST(:lineage AS jsonb))
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name, docs_url = EXCLUDED.docs_url,
                base_url = EXCLUDED.base_url, access_status = EXCLUDED.access_status,
                license_status = EXCLUDED.license_status,
                verified_at = EXCLUDED.verified_at, lineage = EXCLUDED.lineage
        """), {
            "id": source.id, "name": source.name, "docs_url": source.docs_url,
            "base_url": source.base_url, "access_status": source.access_status,
            "license_status": source.license_status, "verified_at": source.verified_at,
            "lineage": json.dumps(list(source.lineage), ensure_ascii=False),
        })
        total += result.rowcount
    return total


def _insert_batch(connection: Any, batch_id: UUID, *, manifest_sha256: str, registry: CohortRegistry,
                  manifest_path: str, archive_root: str, facts: dict[str, FileFact],
                  cohorts: dict[str, CohortMetadata], runs: list[dict], importer: str,
                  common_prefix: str = "") -> None:
    connection.execute(text("""
        INSERT INTO app.import_batches(id, manifest_sha256, registry_sha256, manifest_path,
                                       archive_root, manifest_file_count, verified_bytes,
                                       cohort_count, source_count, importer)
        VALUES (:id, :manifest_sha256, :registry_sha256, :manifest_path, :archive_root,
                :manifest_file_count, :verified_bytes, :cohort_count, :source_count, :importer)
    """), {
        "id": batch_id, "manifest_sha256": manifest_sha256,
        "registry_sha256": registry.manifest_sha256,
        "manifest_path": redact_credentials(manifest_path)[:1024],
        "archive_root": redact_credentials(str(archive_root))[:1024],
        "manifest_file_count": len(facts),
        "verified_bytes": sum(fact.byte_size for fact in facts.values()),
        "cohort_count": len(cohorts),
        "source_count": len(registry.sources),
        "importer": importer[:200],
    })
    _upsert_sources(connection, registry)

    file_rows = []
    for full_path, fact in sorted(facts.items()):
        cohort_name, _, sub_path = full_path[len(common_prefix):].partition("/")
        declaration = registry.cohorts[cohort_name]
        cohort_metadata = cohorts[cohort_name]
        documented = sub_path in cohort_metadata.documented_raw
        role = classify_role(sub_path, documented_raw=documented)
        scope, start, end = coverage_for_role(role, declaration)
        source_id = None
        extra = cohort_metadata.metadata_for(sub_path)
        if isinstance(extra.get("source_id"), str):
            source_id = extra["source_id"]
        elif role == "raw":
            # Raw files inherit the cohort's single declared source only when
            # it is unambiguous; otherwise they stay unattributed (NULL).
            if len(declaration.sources) == 1:
                source_id = declaration.sources[0]
        file_rows.append({
            "batch_id": batch_id, "relative_path": full_path, "cohort": cohort_name,
            "sha256": fact.sha256, "byte_size": fact.byte_size, "file_role": role,
            "coverage_scope": scope, "coverage_start": start,
            "coverage_end_exclusive": end, "source_id": source_id,
            "license_status": declaration.license_status,
            "metadata": json.dumps(extra, ensure_ascii=False, sort_keys=True),
        })
    connection.execute(text("""
        INSERT INTO app.imported_files(batch_id, relative_path, cohort, sha256, byte_size,
                                       file_role, coverage_scope, coverage_start,
                                       coverage_end_exclusive, source_id, license_status,
                                       metadata)
        VALUES (:batch_id, :relative_path, :cohort, :sha256, :byte_size, :file_role,
                :coverage_scope, :coverage_start, :coverage_end_exclusive, :source_id,
                :license_status, CAST(:metadata AS jsonb))
    """), file_rows)
    if runs:
        connection.execute(text("""
            INSERT INTO app.source_runs(id, batch_id, source_id, query_identity,
                                        retrieval_utc, byte_count, request_count, metadata)
            VALUES (:id, :batch_id, :source_id, :query_identity, :retrieval_utc,
                    :byte_count, :request_count, CAST(:metadata AS jsonb))
        """), runs)


def import_archive(*, archive_root: Path, manifest_path: Path, registry_path: Path,
                   database_url: str | None, dry_run: bool,
                   importer: str = "near_api.ingestion.archive (NI-027)") -> dict[str, Any]:
    """Verify and import the archive; returns a JSON-serializable summary."""
    manifest_sha256, entries = parse_manifest(manifest_path)
    if manifest_path.resolve().is_relative_to(archive_root.resolve()):
        raise ManifestFormatError("The hash manifest must live outside the archive root")
    facts = verify_archive(archive_root, entries)

    registry = load_cohort_registry(registry_path)
    # The stored relative_path keeps the full manifest path (including any
    # common leading directory such as "research/") so hashes stay checkable
    # against the original manifest; classification strips the prefix.
    common_prefix = common_manifest_prefix(entries)
    cohort_dirs: dict[str, str] = {}
    for entry in entries:
        relative = entry.relative_path[len(common_prefix):]
        cohort, slash, _sub = relative.partition("/")
        if not slash:
            raise ManifestFormatError(
                f"Manifest entry {entry.relative_path!r} has no cohort directory")
        if cohort not in registry.cohorts:
            raise MetadataContractError(
                f"Cohort {cohort!r} is not declared in the registry; declaring it explicitly is "
                "required before import")
        cohort_dirs.setdefault(cohort, f"{common_prefix}{cohort}/")

    batch_id = uuid4()
    cohort_metadata: dict[str, CohortMetadata] = {}
    runs: list[dict] = []
    for cohort_name in sorted(cohort_dirs):
        metadata = extract_cohort_metadata(
            batch_id, cohort_name, cohort_dirs[cohort_name], facts, archive_root,
            registry.cohorts[cohort_name], registry)
        for full_path, expected_sha256, expected_size in metadata.checksum_targets:
            fact = facts.get(full_path)
            if fact is None:
                raise ArchiveVerificationError(
                    f"Cohort {cohort_name} manifest checksum target {full_path!r} is not a "
                    "manifest-listed file; the batch is rejected")
            if fact.sha256 != expected_sha256 or (expected_size is not None
                                                  and fact.byte_size != expected_size):
                raise ArchiveVerificationError(
                    f"Cohort {cohort_name} internal checksum mismatch for {full_path!r}; the "
                    "batch is rejected")
        cohort_metadata[cohort_name] = metadata
        runs.extend(metadata.runs)

    summary: dict[str, Any] = {
        "manifest_sha256": manifest_sha256,
        "registry_sha256": registry.manifest_sha256,
        "archive_root": str(archive_root),
        "files": len(facts),
        "verified_bytes": sum(fact.byte_size for fact in facts.values()),
        "cohorts": sorted(cohort_metadata),
        "sources": sorted(registry.sources),
        "documented_runs": len(runs),
        "dry_run": dry_run,
    }
    if dry_run:
        summary.update({"imported": False, "batch_id": None, "changes": 0})
        return summary
    if database_url is None:
        raise OperatorDatabaseError("--database-url is required unless --dry-run is given")
    engine = create_operator_engine(database_url)
    try:
        with engine.begin() as connection:
            _assert_operator(connection)
            existing = _existing_batch(connection, manifest_sha256, facts)
            if existing is not None:
                summary.update({"imported": False, "batch_id": str(existing), "changes": 0})
                return summary
            _insert_batch(connection, batch_id, manifest_sha256=manifest_sha256,
                          registry=registry, manifest_path=str(manifest_path),
                          archive_root=str(archive_root), facts=facts,
                          cohorts=cohort_metadata, runs=runs, importer=importer,
                          common_prefix=common_prefix)
    finally:
        engine.dispose()
    summary.update({"imported": True, "batch_id": str(batch_id),
                    "changes": len(facts) + len(runs) + len(registry.sources) + 1})
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m near_api.ingestion.archive",
        description="NI-027 read-only archive import: verify bytes against the hash manifest, "
                    "record sanitized lineage metadata, never modify or copy the archive.")
    parser.add_argument("--archive-root", type=Path, required=True,
                        help="Directory the manifest paths are relative to (read-only)")
    parser.add_argument("--manifest", type=Path, required=True,
                        help="shasum -a 256 manifest file (outside the archive root)")
    parser.add_argument("--cohorts", type=Path, default=DEFAULT_COHORT_REGISTRY,
                        help=f"Cohort scope registry JSON (default: {DEFAULT_COHORT_REGISTRY.name})")
    parser.add_argument("--database-url", default=None,
                        help="near_operator psycopg URL (required without --dry-run)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Verify bytes and metadata only; no database connection")
    arguments = parser.parse_args(argv)
    try:
        summary = import_archive(archive_root=arguments.archive_root.resolve(),
                                 manifest_path=arguments.manifest.resolve(),
                                 registry_path=arguments.cohorts.resolve(),
                                 database_url=arguments.database_url, dry_run=arguments.dry_run)
    except ArchiveVerificationError as error:
        print(f"ARCHIVE VERIFICATION FAILED (nothing imported): {error}", file=sys.stderr)
        return EXIT_VERIFICATION
    except (ManifestFormatError, MetadataContractError) as error:
        print(f"IMPORT CONTRACT FAILED (nothing imported): {error}", file=sys.stderr)
        return EXIT_CONTRACT
    except ArchiveImportError as error:
        print(f"ARCHIVE IMPORT FAILED: {error}", file=sys.stderr)
        return EXIT_DATABASE
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
