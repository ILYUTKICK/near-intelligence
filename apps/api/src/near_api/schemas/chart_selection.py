"""Canonical bounded chart selection shape; domains belong to definition versions.

Structural validation preserves filters from historical definitions. The
server must still validate the actual keys/values against the referenced
immutable chart's filter_schema before storing or resolving a context.

NI-071 multi-value canonical form: every filter value is a non-empty list of
non-empty strings (one selected value per list entry). Selections persisted
before NI-071 carry a bare string per key; the ``canonical_values``
validator normalizes ``str`` -> ``[str]`` at the model boundary, so stored
saved charts, document revisions and insight contexts keep loading unchanged
while every newly stored selection is uniformly list-shaped. Single-value
legacy context hashes stay stable because ``datasets.delivery._context_hash``
hashes a single-element list back as the bare string.
"""
from typing import Annotated
from pydantic import Field, StringConstraints, field_validator, model_validator
from near_api.schemas.common import Selection

FilterKey = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=80)]
FilterValue = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=200)]
FilterValues = Annotated[list[FilterValue], Field(min_length=1, max_length=32)]

class ChartSelection(Selection):
    filters: dict[FilterKey, FilterValues] = Field(max_length=32)

    @field_validator("filters", mode="before")
    @classmethod
    def canonical_values(cls, value):
        """Normalize legacy bare-string values to the list canonical form."""
        if isinstance(value, dict):
            value = {key: ([item] if isinstance(item, str) else item)
                     for key, item in value.items()}
        return value

    @model_validator(mode="after")
    def registered_dimensions(self):
        from near_api.charts.registry import CHARTS
        keys = {key for chart in CHARTS for key in chart.filter_schema["properties"]}
        if set(self.filters) - keys:
            raise ValueError("Unknown chart filter dimension")
        return self
