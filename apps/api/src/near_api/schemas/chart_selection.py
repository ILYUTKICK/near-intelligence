"""Structural validation for persisted selections and resolved chart filters.

Selections use tuples internally. A singleton serializes to the same string
used in pre-NI-071 documents, snapshots and export plans, preserving their
canonical bytes and hashes. Comparisons serialize as arrays in the approved
option order. The server validates actual filter values against the pinned
chart version before storing or resolving a context.
"""
from typing import Annotated

from pydantic import BeforeValidator, Field, PlainSerializer, StringConstraints, field_validator

from near_api.charts.filter_registry import FILTER_DIMENSIONS, MAX_FILTER_VALUES_PER_KEY
from near_api.schemas.common import Selection

FilterKey = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=80)]
FilterValue = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=200)]
FilterValueList = Annotated[list[FilterValue], Field(min_length=1,
                                                   max_length=MAX_FILTER_VALUES_PER_KEY)]


def _normalize_filter_value(value: object) -> object:
    return (value,) if isinstance(value, str) else value


def _serialize_filter_value(values: tuple[str, ...]) -> str | list[str]:
    return values[0] if len(values) == 1 else list(values)


FilterValues = Annotated[
    tuple[FilterValue, ...],
    Field(min_length=1, max_length=MAX_FILTER_VALUES_PER_KEY),
    BeforeValidator(_normalize_filter_value, json_schema_input_type=FilterValue | FilterValueList),
    PlainSerializer(_serialize_filter_value, return_type=FilterValue | FilterValueList),
]


class ChartSelection(Selection):
    filters: dict[FilterKey, FilterValues] = Field(max_length=32)

    @field_validator("filters")
    @classmethod
    def canonical_values(cls, filters: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
        """Order structurally valid values before computing a frozen hash."""
        if filters.keys() - FILTER_DIMENSIONS.keys():
            raise ValueError("Unknown chart filter dimension")
        canonical = {}
        for key, values in filters.items():
            options = FILTER_DIMENSIONS[key].options
            selected = dict.fromkeys(values)
            known = tuple(option for option in options if option in selected)
            unknown = tuple(value for value in selected if value not in options)
            canonical[key] = known + unknown
        return canonical
