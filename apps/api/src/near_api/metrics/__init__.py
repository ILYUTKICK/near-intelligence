"""NI-029: exact metric computations and quality.

This package centralizes the real P0 metric computations over the saved
research aggregates:

- :mod:`near_api.metrics.registry` - the immutable, versioned metric
  definition registry (deterministic UUIDs, idempotent content-verified
  registration into ``app.metric_definitions``);
- :mod:`near_api.metrics.events` - canonical NEAR event identity, duplicate
  collapse/quarantine, payout matching (unique amount+receiver candidate
  within the documented tolerance, single use), internal-hop and failed
  transfer exclusion;
- :mod:`near_api.metrics.compute` - pure Decimal computations (no floats),
  half-open UTC periods, quality propagation (missing/unavailable are null
  with reasons, bounds stay bounds, purchases never deducted from supply);
- :mod:`near_api.metrics.loaders` - strict loaders from the saved archive
  aggregates (read-only, offline) to the canonical input bundle;
- :mod:`near_api.metrics.emit` - assembly of prepared-manifest documents
  for the NI-028 staging pipeline (storage is never duplicated).

Values reconcile with the saved summary totals exactly: yoctoNEAR sums are
exact Decimals and stored ratios are compared at the NUMERIC(78,30) storage
scale. Run ``python -m near_api.metrics --help`` for the operator CLI.
"""

from near_api.metrics.emit import (
    DatasetSpec,
    ManifestInputSpec,
    build_all_manifests,
    build_manifest,
)
from near_api.metrics.registry import (
    DEFINITIONS,
    MetricDefinition,
    MetricRegistryError,
    definition_by_id,
    definition_by_metric_id,
    register_definitions,
    validate_registry,
)

__all__ = [
    "DEFINITIONS",
    "DatasetSpec",
    "ManifestInputSpec",
    "MetricDefinition",
    "MetricRegistryError",
    "build_all_manifests",
    "build_manifest",
    "definition_by_id",
    "definition_by_metric_id",
    "register_definitions",
    "validate_registry",
]
