"""NI-031 chart registry package.

The immutable, versioned chart definitions live in
:mod:`near_api.charts.registry`; routes and ChartView resolution are NI-032
scope and do not exist here.
"""

from near_api.charts.registry import (
    CHARTS,
    CHART_REGISTRY_NAMESPACE,
    CATEGORIES,
    ChartDefinition,
    ChartRegistryError,
    ChartSeries,
    FREQUENCIES,
    MAX_RANGE_DAYS,
    RENDERER_VERSION,
    SERIES_ROLES,
    VISUALIZATION_TYPES,
    chart_by_chart_id,
    register_charts,
    validate_registry,
    view_contract,
)

__all__ = [
    "CHARTS",
    "CHART_REGISTRY_NAMESPACE",
    "CATEGORIES",
    "ChartDefinition",
    "ChartRegistryError",
    "ChartSeries",
    "FREQUENCIES",
    "MAX_RANGE_DAYS",
    "RENDERER_VERSION",
    "SERIES_ROLES",
    "VISUALIZATION_TYPES",
    "chart_by_chart_id",
    "register_charts",
    "validate_registry",
    "view_contract",
]
