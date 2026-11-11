"""Deterministic Markdown rendering of the frozen export plan (NI-058).

Renders the NI-056 ``ExportIr`` of ONE immutable revision into the
``research.md`` of the export ZIP (docs/MVP_SCOPE.md: the Markdown bundle is
the single reliable MVP export). The renderer is a pure function of the plan
and the chart asset filenames — no clock, no registry lookup, no latest
pointer — so rendering the same plan twice yields byte-identical Markdown.

Honesty rules carried over from the IR:

- Every value comes from the plan. Missing chart points stay missing: the
  CSV asset carries their recorded quality reasons, and the Limitations
  section names them. Bounds stay bounds (``lower``/``upper`` are labelled,
  never presented as exact).
- Attribution is the revision's own: title, author, revision number, content
  hash and the revision's recorded creation time. Nothing is refreshed.
- Unrenderable content does not exist here: the NI-056 builder already
  failed closed on anything outside the export contract, so this module
  maps every block the plan can carry — exhaustively, with a typed refusal
  as the drift guard (never a silent skip).
- User text is rendered inert: Markdown/HTML structure characters are
  escaped, so prose can never inject structure, raw HTML or remote
  references into the export (AUTHENTICATION_SECURITY export sanitization).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import NamedTuple
from uuid import UUID

from near_api.insights.schemas import (
    ModelContext,
    RichTextBody,
    RichTextListItem,
    RichTextList,
    RichTextParagraph,
    RichTextRun,
)
from near_api.schemas.export import (
    ExportBlock,
    ExportChartBlock,
    ExportDataTableBlock,
    ExportDividerBlock,
    ExportEvidenceBlock,
    ExportHeadingBlock,
    ExportHypothesisBlock,
    ExportInsightBlock,
    ExportIr,
    ExportListBlock,
    ExportModelResultBlock,
    ExportParagraphBlock,
    ExportRiskBlock,
)

_BUNDLE_IR_VERSION = 1
"""The only IR version this renderer accepts (a mismatch is a typed drift
failure — the bundle of an unknown plan version is never fabricated)."""

_MAX_RENDER_ERROR_DETAILS = 20


class MarkdownRenderError(ValueError):
    """The frozen plan cannot become the Markdown bundle.

    Typed drift guard: a plan this module does not understand fails closed
    instead of rendering a partial document.
    """

    def __init__(self, message: str, details: tuple[tuple[str, str], ...] = ()):
        super().__init__(message)
        self.details = tuple(details)[:_MAX_RENDER_ERROR_DETAILS]


class ChartAssetFiles(NamedTuple):
    """The exported asset filenames of one chart block (already-safe names
    derived by :func:`near_api.exports.charts.safe_chart_asset_name`)."""

    svg_name: str
    csv_name: str


# --------------------------------------------------------------------------- #
# Inert text rendering (sanitize exports)
# --------------------------------------------------------------------------- #

_MARKDOWN_STRUCTURE = str.maketrans({
    "\\": "\\\\", "`": "\\`", "*": "\\*", "_": "\\_", "[": "\\[", "]": "\\]",
    "<": "&lt;", ">": "&gt;", "&": "&amp;", "|": "\\|", "#": "\\#",
    "!": "\\!", "\n": " ", "\r": "", "\t": " ",
})
"""Escape the Markdown/HTML structure characters of user prose and flatten
line breaks to spaces. The result is plain text in every CommonMark
renderer: no heading/emphasis/link/table structure can be injected (a
newline can no longer start a new line) and no raw HTML tag can pass
through."""


def escape_text(value: str) -> str:
    """Render one user-text fragment inert (deterministic escaping)."""
    return value.translate(_MARKDOWN_STRUCTURE)


def _escape_link(href: str) -> str:
    """Make one canonical link target safe inside ``[text](href)``.

    Canonical rich text only admits http(s) and same-document block anchors;
    the parentheses/angle brackets that could break out of the destination
    are percent-encoded and control characters are dropped.
    """
    cleaned = "".join(char for char in href if ord(char) >= 0x20)
    return (cleaned.replace("%", "%25").replace("(", "%28").replace(")", "%29")
            .replace("<", "%3C").replace(">", "%3E"))


def _render_run(run: RichTextRun) -> str:
    text = escape_text(run.text)
    bold = any(mark.type == "bold" for mark in run.marks)
    italic = any(mark.type == "italic" for mark in run.marks)
    if bold:
        text = f"**{text}**"
    if italic:
        text = f"*{text}*"
    for mark in run.marks:
        if mark.type == "link":
            text = f"[{text}]({_escape_link(mark.attrs.href)})"
    return text


def _render_runs(runs: Iterable[RichTextRun]) -> str:
    return "".join(_render_run(run) for run in runs)


def _render_list_items(items: tuple[RichTextListItem, ...], *, ordered: bool,
                       indent: str) -> list[str]:
    """Render list items recursively (the canonical nested-list grammar).

    A nested list starts on its own lines under its parent item, indented by
    two more spaces; the rendering never depends on item numbering state
    outside this function.
    """
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        marker = f"{index}." if ordered else "-"
        inline: list[str] = []
        nested: list[str] = []
        for child in item.content:
            if isinstance(child, RichTextParagraph):
                inline.append(_render_runs(child.content))
            elif isinstance(child, RichTextList):
                nested.extend(_render_list_items(
                    child.content, ordered=child.type == "ordered_list",
                    indent=f"{indent}  "))
            else:  # pragma: no cover - the typed union is closed
                raise MarkdownRenderError(
                    "The frozen plan contains a list child the Markdown "
                    "renderer does not support",
                    [("list_item", "unsupported_list_child")])
        lines.append(f"{indent}{marker} {' '.join(inline)}".rstrip())
        lines.extend(nested)
    return lines


def _render_body(body: RichTextBody, *, prefix: str = "") -> list[str]:
    """Render an annotation body (paragraphs and nested lists)."""
    lines: list[str] = []
    for child in body:
        if isinstance(child, RichTextParagraph):
            lines.append(f"{prefix}{_render_runs(child.content)}")
        elif isinstance(child, RichTextList):
            rendered = _render_list_items(child.content,
                                          ordered=child.type == "ordered_list",
                                          indent="")
            lines.extend(f"{prefix}{item}" for item in rendered)
        else:  # pragma: no cover - the typed union is closed
            raise MarkdownRenderError(
                "The frozen plan contains an annotation body the Markdown "
                "renderer does not support",
                [("body", "unsupported_body_child")])
    return lines


# --------------------------------------------------------------------------- #
# Card rendering (pinned contexts)
# --------------------------------------------------------------------------- #


def _context_lines(context) -> list[str]:
    """The pinned-context provenance lines of an insight card."""
    if isinstance(context, ModelContext):
        return [f"model run `{context.model_run_id}`"]
    selection = context.selection
    return [
        f"chart definition version `{context.chart_definition_version_id}`",
        f"dataset version `{context.dataset_version_id}`",
        f"window {selection.start} to {selection.end} ({selection.frequency})",
        f"resolved at {context.resolved_at}",
        f"context hash `{context.context_hash}`",
    ]


def _render_insight(block: ExportInsightBlock) -> list[str]:
    lines = [f"> **Insight ({escape_text(str(block.insight_type))}, "
             f"{escape_text(block.classification)})** — authored {block.authored_at}",
             ">"]
    lines.extend(_render_body(block.body, prefix="> "))
    lines.append(">")
    lines.append("> Pinned context: " + "; ".join(_context_lines(block.context)) + ".")
    if block.hypothesis_id is not None:
        lines.append(f"> Related hypothesis: `{block.hypothesis_id}`.")
    return lines


def _render_hypothesis(block: ExportHypothesisBlock) -> list[str]:
    return [f"> **Hypothesis ({escape_text(block.assessment)})** — "
            f"authored {block.authored_at}",
            ">",
            f"> {escape_text(block.statement)}"]


def _render_evidence(block: ExportEvidenceBlock) -> list[str]:
    if block.target_kind == "insight":
        target = f"insight `{block.target_id}`"
    elif block.target_kind == "chart_block":
        target = f"chart block `{block.target_id}`"
    elif block.target_kind == "model_run":
        target = f"published model run `{block.target_id}`"
    else:
        target = f"public citation artifact `{block.target_id}`"
    return [f"> **Evidence ({escape_text(block.classification)})** → {target} — "
            f"{escape_text(block.explanation)}"]


def _render_risk(block: ExportRiskBlock) -> list[str]:
    lines = [f"> **Risk: {escape_text(block.title)}**", ">"]
    lines.extend(_render_body(block.body, prefix="> "))
    if block.related_hypothesis_id is not None:
        lines.append(">")
        lines.append(f"> Related hypothesis: `{block.related_hypothesis_id}`.")
    return lines


def _render_chart(block: ExportChartBlock, number: int,
                  assets: Mapping[UUID, ChartAssetFiles]) -> list[str]:
    asset = assets[block.block_id]
    caption = (
        f"*Figure {number}. Frozen chart view of block `{block.block_id}` — "
        f"chart definition version `{block.chart_definition_version_id}`, dataset "
        f"version `{block.observed_dataset_version_id}`, resolved "
        f"{block.view.resolved_at}. Exact values: "
        f"[CSV]({_escape_link(asset.csv_name)}).*")
    return [
        f"![Chart {block.block_id}]({_escape_link(asset.svg_name)})",
        "",
        caption,
    ]


def _recorded_number(value: float) -> str:
    """The recorded statistical value verbatim (the shortest round-trip
    spelling, never rounded or locale-formatted)."""
    return str(value)


def _render_model_result(block: ExportModelResultBlock) -> list[str]:
    """Render one pinned model result from the plan's frozen projection.

    Every number comes from ``block.summary`` — the NI-056 projection of the
    immutable published run row — never from the document JSON (which stores
    no statistical value at all). The interpretation renders as prose; the
    recorded limitations of the run always precede the coefficients.
    """
    summary = block.summary
    lines = [
        f"> **Model result** — pinned published run `{summary.run_id}` "
        f"(specification `{escape_text(block.spec_id)}` version {block.spec_version}).",
        ">",
        f"> Gate verdict: {escape_text(summary.gate_verdict)} · sample "
        f"{escape_text(summary.sample_start)} to {escape_text(summary.sample_end_exclusive)} "
        f"(end exclusive) · {summary.nobs} observations.",
        f"> Recorded reproduction tolerances: rtol {escape_text(summary.coefficient_rtol)} / "
        f"atol {escape_text(summary.coefficient_atol)}.",
        ">",
        f"> Recorded limitations apply to every value below; the run's own limitation "
        f"notes travel in the published bundle. Coefficients are associations recorded "
        f"by the publication gate — never causal effects.",
        ">",
        "> Recorded coefficients:",
        ">",
        "> | Term | Estimate | Std. error | t | p | 95% CI |",
        "> | --- | --- | --- | --- | --- | --- |",
    ]
    for coefficient in summary.coefficients:
        cells = (
            escape_text(coefficient.name), _recorded_number(coefficient.estimate),
            _recorded_number(coefficient.std_error), _recorded_number(coefficient.t_stat),
            _recorded_number(coefficient.p_value),
            f"[{_recorded_number(coefficient.ci95_low)}, "
            f"{_recorded_number(coefficient.ci95_high)}]",
        )
        lines.append("> | " + " | ".join(cells) + " |")
    lines.append(">")
    lines.append("> Recorded diagnostics: "
                 + escape_text(json.dumps(summary.diagnostics, sort_keys=True,
                                          separators=(",", ":"), default=str)) + ".")
    lines.append(">")
    lines.append(f"> Source: the recorded manifest bundle of this run "
                 f"([{escape_text(summary.manifest_url)}]({_escape_link(summary.manifest_url)})) "
                 f"— verify offline with the bundle's hashes; the block pins run "
                 f"`{summary.run_id}` and dataset version `{block.dataset_version_id}`.")
    lines.append(">")
    lines.extend(_render_body(block.interpretation, prefix="> "))
    return lines


def _render_data_table(block: ExportDataTableBlock) -> list[str]:
    header = [escape_text(column.label)
              + (f" ({escape_text(column.unit)})" if column.unit else "")
              for column in block.columns]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in block.columns) + " |",
    ]
    if block.rows is not None:
        for row in block.rows:
            cells = [escape_text(cell) if isinstance(cell, str)
                     else ("" if cell is None else ("true" if cell else "false"))
                     for cell in row]
            lines.append("| " + " | ".join(cells) + " |")
    else:
        dataset = block.dataset
        assert dataset is not None  # the export contract keeps exactly one payload
        lines.append("")
        lines.append(
            f"Projected from approved dataset `{escape_text(dataset.dataset_key)}` "
            f"version {dataset.version} (content `{dataset.content_sha256}`). "
            "The projection resolves through this immutable dataset version, "
            "never a latest pointer.")
    return lines


# --------------------------------------------------------------------------- #
# Block dispatch (exhaustive over the export contract)
# --------------------------------------------------------------------------- #


def _render_block(block: ExportBlock, *, chart_number: int,
                  assets: Mapping[UUID, ChartAssetFiles]) -> tuple[list[str], int]:
    """Render one plan block; returns the lines and the chart counter."""
    if isinstance(block, ExportParagraphBlock):
        return [_render_runs(block.runs)], chart_number
    if isinstance(block, ExportHeadingBlock):
        return ["#" * (block.level + 1) + " " + _render_runs(block.runs)], chart_number
    if isinstance(block, ExportListBlock):
        return _render_list_items(block.items,
                                  ordered=block.block_type == "ordered_list",
                                  indent=""), chart_number
    if isinstance(block, ExportChartBlock):
        chart_number += 1
        return _render_chart(block, chart_number, assets), chart_number
    if isinstance(block, ExportDataTableBlock):
        return _render_data_table(block), chart_number
    if isinstance(block, ExportInsightBlock):
        return _render_insight(block), chart_number
    if isinstance(block, ExportHypothesisBlock):
        return _render_hypothesis(block), chart_number
    if isinstance(block, ExportEvidenceBlock):
        return _render_evidence(block), chart_number
    if isinstance(block, ExportRiskBlock):
        return _render_risk(block), chart_number
    if isinstance(block, ExportModelResultBlock):
        return _render_model_result(block), chart_number
    if isinstance(block, ExportDividerBlock):
        return ["---"], chart_number
    raise MarkdownRenderError(
        "The frozen plan contains a block the Markdown renderer does not "
        "support",
        [(f"blocks.{getattr(block, 'block_id', '?')}", "unsupported_block_type")])


def render_markdown(plan: ExportIr, assets: Mapping[UUID, ChartAssetFiles]) -> str:
    """Render the bundle's ``research.md`` from the frozen plan.

    Deterministic: the output is a pure function of the plan and the asset
    filenames. The registries and limitations at the end carry the recorded
    identities and reason codes of the revision (nothing is re-resolved).
    """
    if plan.ir_version != _BUNDLE_IR_VERSION:
        raise MarkdownRenderError(
            f"The export plan uses IR version {plan.ir_version}; this renderer "
            f"renders version {_BUNDLE_IR_VERSION} only",
            [("ir_version", "unsupported_ir_version")])

    meta = plan.document
    author = escape_text(meta.author.display_name) if meta.author.display_name \
        else f"`{meta.author.owner_id}`"
    lines: list[str] = [
        f"# {escape_text(meta.title)}",
        "",
        f"Exported revision {meta.revision} of document `{meta.document_id}`",
        f"(version `{meta.version_id}`, content `{meta.content_sha256}`, "
        f"schema version {meta.schema_version}) authored by {author}, "
        f"created {meta.created_at}.",
        "",
        "This bundle is the frozen export of exactly this revision; later "
        "edits, renames or newer dataset publications do not change it.",
    ]

    chart_number = 0
    for block in plan.blocks:
        rendered, chart_number = _render_block(
            block, chart_number=chart_number, assets=assets)
        lines.append("")
        lines.extend(rendered)

    lines.extend(_render_registries(plan))
    lines.extend(_render_limitations(plan))
    return "\n".join(lines).rstrip() + "\n"


def _render_registries(plan: ExportIr) -> list[str]:
    lines = ["", "## Sources", ""]
    if plan.sources:
        lines.extend(f"- `{source.source_id}` — {escape_text(source.name)}"
                     for source in plan.sources)
    else:
        lines.append("- No data sources are referenced by this revision.")
    lines.extend(["", "## Model runs", ""])
    if plan.model_runs:
        lines.extend(f"- `{run.run_id}` — specification `{escape_text(run.spec_id)}` "
                     f"version {run.spec_version}" for run in plan.model_runs)
    else:
        lines.append("- No published model runs are referenced by this revision.")
    lines.extend(["", "## Citations", ""])
    if plan.citations:
        lines.extend(f"- Public citation artifact `{citation.artifact_id}`"
                     for citation in plan.citations)
    else:
        lines.append("- No public citation artifacts are referenced by this revision.")
    return lines


def limitations_of(plan: ExportIr) -> list[str]:
    """The recorded limitations of the frozen evidence (never fabricated).

    Shared by ``research.md`` (rendered as the Limitations section) and the
    ZIP manifest (``limitations``): the absence reason codes and bound kinds
    the plan's chart evidence actually carries, plus the frozen-revision
    statement. Deterministic order.
    """
    reasons: list[str] = []
    bounds: set[str] = set()
    for block in plan.blocks:
        if isinstance(block, ExportChartBlock):
            for series in block.view.series:
                for point in series.points:
                    if point.quality.bound_kind is not None:
                        bounds.add(point.quality.bound_kind)
                    if point.quality.status in {"missing", "unavailable"}:
                        for reason in point.quality.reasons:
                            label = str(reason)
                            if label not in reasons:
                                reasons.append(label)
    lines = ["This export reflects only the revision pinned above; it is "
             "never refreshed with current data.",
             "Missing or unavailable chart values are absent in the CSV "
             "assets with their recorded reasons — they are never zero-filled."]
    if bounds:
        lines.append("Bound-preserving series carry their bound kinds "
                     f"({', '.join(sorted(bounds))}); bounds are never presented "
                     "as exact values.")
    if reasons:
        lines.append("Recorded absence reasons in this revision's chart data: "
                     + "; ".join(escape_text(reason) for reason in reasons) + ".")
    lines.append("Every export bundle pins the chart renderer identity and "
                 "per-file SHA-256 hashes in `manifest.json` for verification.")
    return lines


def _render_limitations(plan: ExportIr) -> list[str]:
    lines = ["", "## Limitations", ""]
    lines.extend(f"- {item}" for item in limitations_of(plan))
    return lines
