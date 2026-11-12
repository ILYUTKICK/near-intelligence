"""Clone a published research release into a new private document (NI-045).

EDITOR_SPECIFICATION ("Templates, duplication and export"): "Public
duplication clones a specified public release into new private IDs and
retains attribution/data/model pins. Public subsequent edits do not mutate
copies."

Mechanics, in one transaction per duplicate:

1. The publication's stored public projection is re-parsed through the
   canonical validator (a malformed seed can never duplicate; the seed gate
   already parsed it, this is defense in depth).
2. :func:`remap_publication_content` — a pure, fully in-memory graph rewrite
   — allocates a NEW ``block_id`` for every top-level block and NEW
   ``insight_id``/``hypothesis_id``/``evidence_id`` for every annotation
   entity, then rewrites the whole in-document reference graph in one pass
   (evidence ``hypothesis_id`` and insight/chart_block ``target_id``,
   insight ``hypothesis_id``, risk ``related_hypothesis_id``). A missing
   reference is a typed 422, never a partial rewrite. Public immutable
   references are carried VERBATIM: evidence ``model_run``/``citation``
   targets, liveChart pins, dataTable dataset pins and modelResult run/dataset
   pins. The public projection rejects owner-scoped snapshot references.
3. The retained attribution is written two ways, deliberately:
   ``documents.source_publication_id`` (migration 0015) records the release
   structurally (RESTRICT — the provenance cannot be orphaned), and a
   leading attribution paragraph names the source release (slug, version)
   in visible content, so the attribution survives in every export and
   revision view. The paragraph is factual release metadata, not fabricated
   thesis content.
4. The copy is created as an ordinary private document (empty revision 1,
   revision 2 the remapped projection) through the SHARED revision pipeline
   (:mod:`near_api.documents.service.save_revision_in_transaction`). That
   path re-validates everything with the duplicate's fresh identities in the
   requester's owner scope: new insight ids are "new" pins, so every insight
   context is re-verified against the immutable chart inputs
   (:func:`~near_api.documents.context_resolver.verify_chart_context` — an
   unavailable pinned dataset or definition fails the duplicate with an
   explicit typed 422, never a latest substitution), chart contexts are
   rebuilt for the new block ids, annotations get fresh server-authored
   timestamps (no private editorial metadata is copied), evidence targets
   are re-checked against the public catalogs, and the projections are
   written for the requesting owner.
5. Public source unchanged by construction: the copy is a separate
   ``app.documents``/``app.document_versions`` row set; the publication row
   is immutable and is never touched by the duplicate path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from sqlalchemy import Connection, Engine

from near_api.auth.principal import Principal
from near_api.db.security import ResourceNotFound, principal_transaction
from near_api.documents import service
from near_api.documents.schema import (
    CanonicalDocument,
    ReferenceInvalid,
    parse_document,
)
from near_api.publications.store import PublicationRow, get_published_publication

ATTRIBUTION_TEXT = "Duplicated from the public research release “{title}” ({slug}, version {version})."
"""The visible attribution paragraph copied documents start with."""


@dataclass(frozen=True)
class PublicationIdRemapping:
    """Old→new identity maps of one remap (test/diagnostic oracle)."""

    block_ids: dict[str, str] = field(default_factory=dict)
    insight_ids: dict[str, str] = field(default_factory=dict)
    hypothesis_ids: dict[str, str] = field(default_factory=dict)
    evidence_ids: dict[str, str] = field(default_factory=dict)


def _new_id(mapping: dict[str, str], old: str) -> str:
    new = str(uuid4())
    mapping[old] = new
    return new


def _mapped(mapping: dict[str, str], old: str, path: str, what: str) -> str:
    new = mapping.get(old)
    if new is None:
        raise ReferenceInvalid(
            f"The release references a {what} that does not exist in the same "
            "document; the projection cannot be duplicated",
            [(path, f"dangling_{what}_reference")])
    return new


def attribution_paragraph(attribution_text: str) -> dict:
    """The visible attribution paragraph with a fresh block id."""
    return {
        "type": "paragraph",
        "attrs": {"block_id": str(uuid4())},
        "content": [{"type": "text", "text": attribution_text}],
    }


def parse_publication_content(content: dict) -> CanonicalDocument:
    """Validate the editor shape and the references allowed in a public release."""
    canonical = parse_document(content)
    if any(chart.snapshot_id is not None for chart in canonical.live_charts):
        raise ReferenceInvalid(
            "Public releases cannot reference owner-scoped chart snapshots",
            [("content", "private_snapshot_reference")])
    if any("model_run_id" in insight.context for insight in canonical.insights):
        raise ReferenceInvalid(
            "Public release insights must use chart contexts",
            [("content", "unsupported_insight_context")])
    return canonical


def remap_publication_content(content: dict, *,
                              attribution_text: str | None = None,
                              ) -> tuple[dict, PublicationIdRemapping]:
    """Allocate new private IDs and rewrite the in-document reference graph.

    Pure function over a canonical document (parse it before/after — the
    duplicate flow does both). ``attribution_text`` prepends the retained
    source-attribution paragraph to the copy. The input is never mutated:
    every rewritten node is a fresh dict. All public immutable pins are
    carried verbatim; every in-document identity is rewritten.
    """
    nodes = [{"type": node["type"], "attrs": dict(node["attrs"]),
              **({"content": node["content"]} if "content" in node else {})}
             for node in content["content"]]
    remapping = PublicationIdRemapping()

    # Pass one: allocate every new identity up front so references can be
    # rewritten regardless of node order (an evidence may target an insight
    # or chart block defined later in the document).
    for node in nodes:
        attrs = node["attrs"]
        attrs["block_id"] = _new_id(remapping.block_ids, attrs["block_id"])
        if node["type"] == "insight":
            attrs["insight_id"] = _new_id(remapping.insight_ids,
                                          attrs["insight_id"])
        elif node["type"] == "hypothesis":
            attrs["hypothesis_id"] = _new_id(remapping.hypothesis_ids,
                                             attrs["hypothesis_id"])
        elif node["type"] == "evidence":
            attrs["evidence_id"] = _new_id(remapping.evidence_ids,
                                           attrs["evidence_id"])

    # Pass two: rewrite every in-document reference through the maps.
    for position, node in enumerate(nodes):
        attrs = node["attrs"]
        path = f"content[{position}]"
        if node["type"] == "insight":
            if "hypothesis_id" in attrs:
                attrs["hypothesis_id"] = _mapped(
                    remapping.hypothesis_ids, attrs["hypothesis_id"],
                    f"{path}.attrs.hypothesis_id", "hypothesis")
            # The pinned inspection context (chart definition version, dataset
            # version, selection, hash) is a public immutable pin: verbatim.
        elif node["type"] == "evidence":
            attrs["hypothesis_id"] = _mapped(
                remapping.hypothesis_ids, attrs["hypothesis_id"],
                f"{path}.attrs.hypothesis_id", "hypothesis")
            kind = attrs["target_kind"]
            if kind == "insight":
                attrs["target_id"] = _mapped(
                    remapping.insight_ids, attrs["target_id"],
                    f"{path}.attrs.target_id", "insight")
            elif kind == "chart_block":
                attrs["target_id"] = _mapped(
                    remapping.block_ids, attrs["target_id"],
                    f"{path}.attrs.target_id", "chart block")
            # model_run/citation targets are public immutable references:
            # carried verbatim (validated against the catalogs on save).
        elif node["type"] == "risk":
            if "related_hypothesis_id" in attrs:
                attrs["related_hypothesis_id"] = _mapped(
                    remapping.hypothesis_ids, attrs["related_hypothesis_id"],
                    f"{path}.attrs.related_hypothesis_id", "hypothesis")
        # The remaining nodes, including modelResult, change only block_id.

    output_nodes = ([attribution_paragraph(attribution_text)] if attribution_text else []) \
        + nodes
    return {**content, "content": output_nodes}, remapping


def duplicate_publication_in_transaction(connection: Connection, principal: Principal,
                                         publication: PublicationRow,
                                         *, title: str | None) -> service.DocumentDetail:
    """Transaction-scoped clone of one loaded published release.

    The caller supplies the transaction (the idempotent replay path runs this
    inside the idempotency transaction, so the record and the copy commit
    atomically). ``title=None`` falls back to the publication's own title.
    The whole clone is empty revision 1, then the remapped projection as
    revision 2 through the shared save pipeline, so an invalid pin anywhere
    leaves zero rows.
    """
    canonical = parse_publication_content(publication.content)
    attribution = ATTRIBUTION_TEXT.format(title=publication.title,
                                          slug=publication.slug,
                                          version=publication.version)
    remapped, _mapping = remap_publication_content(canonical.canonical,
                                                   attribution_text=attribution)
    created = service.create_document_in_transaction(
        connection, principal, title=title if title is not None else publication.title,
        source_publication_id=publication.id)
    return service.save_revision_in_transaction(
        connection, principal, created.document.id, expected_revision=1,
        document_payload=remapped)


def duplicate_publication(engine: Engine, principal: Principal, *, slug: str,
                          version: int, title: str | None) -> service.DocumentDetail:
    """Load one published release and clone it into the requester's scope.

    Unknown, mis-slugged and not-published releases are the same generic
    :class:`~near_api.db.security.ResourceNotFound` (404, no existence leak).
    The whole load+clone runs in ONE principal transaction.
    """
    with principal_transaction(engine, principal) as connection:
        return load_and_duplicate_in_transaction(
            connection, principal, slug=slug, version=version, title=title)


def load_and_duplicate_in_transaction(connection: Connection, principal: Principal, *,
                                      slug: str, version: int,
                                      title: str | None) -> service.DocumentDetail:
    """Load the pinned release on the caller's transaction, then clone it."""
    row = get_published_publication(connection, slug, version=version)
    if row is None:
        raise ResourceNotFound("Resource does not exist for this owner")
    return duplicate_publication_in_transaction(connection, principal, row, title=title)


__all__ = [
    "ATTRIBUTION_TEXT",
    "PublicationIdRemapping",
    "attribution_paragraph",
    "duplicate_publication",
    "duplicate_publication_in_transaction",
    "load_and_duplicate_in_transaction",
    "parse_publication_content",
    "remap_publication_content",
]
