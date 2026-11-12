"""Editor document templates (NI-045).

EDITOR_SPECIFICATION ("Templates, duplication and export"): P0 starts empty;
the P1 ``investment-v1`` template carries the eight fixed section headings —
**Executive Summary, Investment Hypothesis, Adoption Evidence, Revenue
Analysis, Token Economics, Econometric Results, Risks, Conclusion** — and
nothing else: "No fabricated paragraphs or numerical placeholder claims."

The template is a pure module: it renders the canonical document JSON with
freshly allocated ``block_id`` UUIDs per creation, so every document created
from it owns unique stable block ids (never shared, never derived from
content), and the result is re-validated by the canonical parser before it is
stored, so the template can never drift outside the editor grammar. Heading
level 1 is the top section level of the outline (the document title is
separate metadata; the Markdown export renders level 1 as ``##`` under the
title's ``#``).
"""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from near_api.documents.schema import SCHEMA_VERSION, DocumentSchemaError

TemplateId = Literal["investment-v1"]

INVESTMENT_V1: TemplateId = "investment-v1"

TEMPLATE_IDS: tuple[TemplateId, ...] = (INVESTMENT_V1,)

INVESTMENT_V1_HEADINGS: tuple[str, ...] = (
    "Executive Summary",
    "Investment Hypothesis",
    "Adoption Evidence",
    "Revenue Analysis",
    "Token Economics",
    "Econometric Results",
    "Risks",
    "Conclusion",
)

TEMPLATE_HEADING_LEVEL = 1


def template_document(template_id: TemplateId) -> dict:
    """Render one template's canonical document JSON (headings only).

    Unknown template ids raise :class:`DocumentSchemaError` (the request
    contract already restricts ``template_id``, so this is defense in depth).
    The document is NOT parsed here — the creation service parses the rendered
    result through :func:`near_api.documents.schema.parse_document` so one
    validator owns the grammar.
    """
    if template_id not in TEMPLATE_IDS:
        raise DocumentSchemaError(
            f"Unknown document template {template_id!r}",
            [("template_id", "unknown_template")])
    if template_id == INVESTMENT_V1:
        content = [
            {
                "type": "heading",
                "attrs": {"block_id": str(uuid4()), "level": TEMPLATE_HEADING_LEVEL},
                "content": [{"type": "text", "text": heading}],
            }
            for heading in INVESTMENT_V1_HEADINGS
        ]
        return {"schema_version": SCHEMA_VERSION, "type": "doc", "content": content}
    raise DocumentSchemaError(
        f"Unknown document template {template_id!r}",
        [("template_id", "unknown_template")])


__all__ = [
    "INVESTMENT_V1",
    "INVESTMENT_V1_HEADINGS",
    "TEMPLATE_HEADING_LEVEL",
    "TEMPLATE_IDS",
    "template_document",
]
