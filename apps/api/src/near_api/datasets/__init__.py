"""Immutable dataset staging and publication (NI-028).

Public surface:

- :mod:`near_api.datasets.canonical` — deterministic canonical JSON, decimal
  and timestamp forms plus the SHA-256 manifest digest.
- :mod:`near_api.datasets.manifest` — strict prepared-manifest parsing.
- :mod:`near_api.datasets.storage` — content-addressed artifact byte storage.
- :mod:`near_api.datasets.service` — transactional stage/validate/publish and
  the query API for historical versions.
- :mod:`near_api.datasets.from_import` — NI-027 integration: stage from a
  verified archive import batch (offline, no network).
- :mod:`near_api.datasets.cli` — operator CLI (``python -m near_api.datasets``).
"""

from near_api.datasets.canonical import CanonicalFormatError
from near_api.datasets.manifest import (
    Observation,
    PreparedManifest,
    manifest_document,
    parse_manifest_document,
)
from near_api.datasets.service import (
    DatasetContractError,
    DatasetLookupError,
    DatasetVerificationError,
    PublishRefused,
    ResolvedInput,
    StagedVersion,
    active_version,
    create_dataset_operator_engine,
    get_version,
    list_inputs,
    list_observations,
    publish,
    stage,
    validate,
    version_history,
)

__all__ = [
    "CanonicalFormatError",
    "DatasetContractError",
    "DatasetLookupError",
    "DatasetVerificationError",
    "Observation",
    "PreparedManifest",
    "PublishRefused",
    "ResolvedInput",
    "StagedVersion",
    "active_version",
    "create_dataset_operator_engine",
    "get_version",
    "list_inputs",
    "list_observations",
    "manifest_document",
    "parse_manifest_document",
    "publish",
    "stage",
    "validate",
    "version_history",
]
