"""Canonical bounded chart selection shape; domains belong to definition versions.

Structural validation preserves filters from historical definitions. The
server must still validate the actual keys/values against the referenced
immutable chart's filter_schema before storing or resolving a context.
"""
from typing import Annotated
from pydantic import Field, StringConstraints, field_validator
from near_api.schemas.common import Selection

FilterKey = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=80)]
FilterValue = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=200)]

class ChartSelection(Selection):
    filters: dict[FilterKey, FilterValue] = Field(max_length=32)

    @field_validator("filters")
    @classmethod
    def registered_dimensions(cls, value: dict[str, str]) -> dict[str, str]:
        from near_api.charts.registry import CHARTS
        keys = {key for chart in CHARTS for key in chart.filter_schema["properties"]}
        if set(value) - keys:
            raise ValueError("Unknown chart filter dimension")
        return value
