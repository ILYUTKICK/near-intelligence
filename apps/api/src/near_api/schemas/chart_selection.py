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

NI-071 canonical value order: a multi-value selection's per-key order is the
dimension's declared option order (the same order every chart version's
``filter_schema`` enum declares), never the request order. Reordering here —
at the one model every persisted selection passes through — makes the
document-context hash (``documents.context_resolver.build_resolved_context``)
agree byte-exactly with the resolved view hash
(``datasets.delivery.build_chart_view``, which canonicalizes against the
chart schema) for any honest request order, so a saved multi-value block
always reconstructs from its frozen evidence.
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
        """Normalize to the canonical list form in the declared option order."""
        if isinstance(value, dict):
            from near_api.charts.filter_registry import FILTER_DIMENSIONS
            canonical: dict = {}
            for key, item in value.items():
                items = [item] if isinstance(item, str) else item
                options = FILTER_DIMENSIONS[key].options \
                    if isinstance(key, str) and key in FILTER_DIMENSIONS else ()
                if isinstance(items, list):
                    chosen = set(items)
                    ordered = [option for option in options if option in chosen]
                    ordered.extend(item for item in items if item not in ordered)
                    items = ordered
                canonical[key] = items
            value = canonical
        return value

    @model_validator(mode="after")
    def registered_dimensions(self):
        from near_api.charts.registry import CHARTS
        keys = {key for chart in CHARTS for key in chart.filter_schema["properties"]}
        if set(self.filters) - keys:
            raise ValueError("Unknown chart filter dimension")
        return self
