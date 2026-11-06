"""Stage a dataset version from an already imported NI-027 archive batch.

``stage-from-import --batch <manifest_sha256> --binding PATH`` is the NI-027
integration of the staging pipeline: the binding declares the dataset header
and which files of the verified import batch feed it; the observation records
themselves are read FROM the imported aggregate files on disk (never from the
binding and never from the network).  Every consumed byte is re-verified
against the ``imported_files`` digest recorded by the read-only archive import
before any content is parsed, so a changed archive can never feed staging.

Binding schema (strict, v1): the same header fields as a prepared manifest,
plus ``aggregate_record_format`` (must be the literal ``"observations_json"``)
and WITHOUT inline ``observations`` — every declared input must be an
``imported`` binding of that batch, and inputs with role ``normalized`` are
parsed as ``{"observations": [...]}`` (or a bare array) of the same
observation record schema used by prepared manifests.  Each record's periods
must lie inside the input file's recorded NI-027 coverage window when that
window is present.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Connection

from near_api.datasets.canonical import CanonicalFormatError, load_json_strict
from near_api.datasets.manifest import (
    Observation,
    PreparedManifest,
    ROLE_MEDIA_TYPES,
    content_digest,
    parse_binding_document,
    parse_observation_record,
)
from near_api.datasets.service import (
    IMPORTED_FILE_ROLE_COMPATIBILITY,
    DatasetContractError,
    DatasetVerificationError,
    ImportedFileFact,
    ResolvedInput,
    StagedVersion,
    _assert_operator,
    _lock_dataset_key,
    _stage_locked,
    lookup_imported_file,
    read_imported_bytes,
)
from near_api.datasets.storage import ArtifactStorage

MAX_BINDING_BYTES = 1024 * 1024


def _read_records(fact: ImportedFileFact, relative_path: str,
                  role: str) -> tuple[Observation, ...]:
    """Parse observation records out of one verified imported aggregate file."""
    if role != "normalized":
        return ()
    data = read_imported_bytes(fact, relative_path)
    try:
        document = load_json_strict(data, context=f"imported file {relative_path}")
    except CanonicalFormatError as error:
        raise DatasetContractError(str(error)) from None
    records = document.get("observations") if isinstance(document, dict) else document
    if not isinstance(records, list):
        raise DatasetContractError(
            f"Imported aggregate {relative_path!r} must be a JSON array or an object "
            "with an 'observations' array")
    observations: list[Observation] = []
    seen: set[tuple[str, str, str]] = set()
    for index, record in enumerate(records):
        observation = parse_observation_record(
            record, context=f"imported file {relative_path}[{index}]")
        identity = (str(observation.metric_definition_id),
                    observation.period_start.isoformat(), observation.dimensions_hash)
        if identity in seen:
            raise DatasetContractError(
                f"Imported aggregate {relative_path!r}: duplicate observation identity "
                f"at record {index}")
        seen.add(identity)
        if fact.coverage_start is not None \
                and observation.period_start.date() < fact.coverage_start:
            raise DatasetVerificationError(
                f"Imported aggregate {relative_path!r}: record {index} starts before the "
                "file's recorded coverage window")
        if (fact.coverage_end_exclusive is not None
                and observation.period_end.date() > fact.coverage_end_exclusive):
            raise DatasetVerificationError(
                f"Imported aggregate {relative_path!r}: record {index} ends after the "
                "file's recorded coverage window")
        observations.append(observation)
    return tuple(observations)


def resolve_imported_batch(connection: Connection, batch_manifest_sha256: str,
                           binding: PreparedManifest) -> tuple[list[ResolvedInput],
                                                               tuple[Observation, ...]]:
    """Verify every declared archive file and read its observation records."""
    resolved: list[ResolvedInput] = []
    observations: list[Observation] = []
    seen_inputs: set[tuple[str, str]] = set()
    for index, item in enumerate(binding.inputs):
        context = f"inputs[{index}]"
        if item.kind != "imported" or item.batch_manifest_sha256 != batch_manifest_sha256:
            raise DatasetContractError(
                f"{context}: stage-from-import bindings accept only 'imported' inputs "
                f"of batch {batch_manifest_sha256}")
        fact = lookup_imported_file(connection, batch_manifest_sha256, item.relative_path)
        if item.role not in IMPORTED_FILE_ROLE_COMPATIBILITY.get(fact.file_role, set()):
            raise DatasetContractError(
                f"Imported file {item.relative_path!r} has file_role {fact.file_role!r}, "
                f"which cannot honestly feed dataset input role {item.role!r}")
        source_id = item.source_id
        if source_id is None:
            source_id = fact.source_id
        elif fact.source_id is not None and fact.source_id != source_id:
            raise DatasetContractError(
                f"Input source_id {source_id!r} contradicts the imported metadata "
                f"{fact.source_id!r} for {item.relative_path!r}")
        entry = ResolvedInput(
            storage_key=f"imported/{fact.batch_id}/{fact.sha256}",
            sha256=fact.sha256, byte_size=fact.byte_size,
            media_type=ROLE_MEDIA_TYPES[item.role], role=item.role,
            source_id=source_id, query_hash=item.query_hash,
            license_status=fact.license_status)
        identity = (entry.storage_key, entry.role)
        if identity in seen_inputs:
            raise DatasetContractError(
                f"{context}: duplicate input for storage key {entry.storage_key} "
                f"and role {entry.role}")
        seen_inputs.add(identity)
        resolved.append(entry)
        observations.extend(_read_records(fact, item.relative_path, item.role))
    if not observations:
        raise DatasetContractError(
            "No observation records were read; at least one 'normalized' input whose "
            "aggregate file contains observation records is required")
    for observation in observations:
        if observation.metric_definition_id not in binding.member_metrics:
            raise DatasetContractError(
                f"Record references metric {observation.metric_definition_id}, which is "
                "not declared in binding member_metrics")
    identities = {(str(observation.metric_definition_id),
                   observation.period_start.isoformat(), observation.dimensions_hash)
                  for observation in observations}
    if len(identities) != len(observations):
        raise DatasetContractError("Duplicate observation identity across input files")
    return resolved, tuple(observations)


def stage_from_import(engine, batch_manifest_sha256: str, binding_path: Path,
                      storage_root: Path) -> StagedVersion:
    """Stage (and validate) a dataset version whose records come from the batch."""
    try:
        data = binding_path.read_bytes()
    except OSError as error:
        raise DatasetContractError(f"Cannot read binding {binding_path}: {error}") from None
    if len(data) > MAX_BINDING_BYTES:
        raise DatasetContractError(f"Binding exceeds the {MAX_BINDING_BYTES} byte limit")
    try:
        document = load_json_strict(data, context="binding")
    except CanonicalFormatError as error:
        raise DatasetContractError(str(error)) from None
    binding = parse_binding_document(document, context="binding")
    storage = ArtifactStorage(storage_root)
    with engine.connect() as connection:
        resolved, observations = resolve_imported_batch(connection, batch_manifest_sha256,
                                                        binding)
    manifest = PreparedManifest(
        schema_version=1,
        dataset_key=binding.dataset_key,
        frequency=binding.frequency,
        window_start=binding.window_start,
        window_end_exclusive=binding.window_end_exclusive,
        pipeline_version=binding.pipeline_version,
        code_commit=binding.code_commit,
        config_hash=binding.config_hash,
        dependency_lock_hash=binding.dependency_lock_hash,
        source_as_of=binding.source_as_of,
        retrieved_at=binding.retrieved_at,
        quality=binding.quality,
        member_metrics=binding.member_metrics,
        inputs=(),
        observations=observations,
    )
    manifest_bytes, digest = content_digest(manifest, resolved)
    manifest_key = storage.store("manifests", digest, manifest_bytes, suffix=".json")
    with engine.begin() as connection:
        _assert_operator(connection)
        _lock_dataset_key(connection, manifest.dataset_key)
        return _stage_locked(connection, manifest, resolved, manifest_key, digest,
                             manifest_bytes)
