"""Document revision service: CAS saves, first empty revision, projections (NI-036).

Implements the persistence algorithm of docs/DATABASE_SCHEMA.md ("Document
content flow"): save locks the document row, checks the expected revision,
validates the canonical schema and every reference, then writes the immutable
version, the derived block/insight/hypothesis/evidence projections and the
advanced revision pointer in ONE transaction — a mismatch or any validation
failure returns without changes, so invalid content creates no partial
revision. Old revisions are immutable rows (no UPDATE grant/policy for the
runtime role); their content and projections are never rewritten.

Compare-and-set semantics (API_SPECIFICATION): the document ETag is the quoted
current revision. ``save_revision`` requires the client's ``expected_revision``
to equal the document's current revision under the row lock; otherwise it
raises :class:`RevisionConflict` carrying the current revision (HTTP 409 with
``current_revision``). The first revision of a new document is the empty
document and is created atomically with the document row (revision 1), so a
document always has content behind its ETag.

Revision numbering: ``documents.revision`` is the revision number of the
current version (1 = the first empty revision created here; every successful
save advances it by one and the new version row carries that number). This is
the service-owned canonical numbering; the raw NI-019 repository helper
``repositories.documents.create_version`` keeps its own next-counter behavior
for its existing callers and is intentionally not used here.

Reference validation boundaries for P0 (each raise :class:`ReferenceInvalid`
with a typed reason, never a silent substitution):

- same-document links (evidence -> hypothesis/insight/chart block,
  insight/risk -> hypothesis) are validated purely by
  :mod:`near_api.documents.schema`;
- ``dataTable.dataset_version_id`` and liveChart
  ``observed_dataset_version_id`` must reference an APPROVED dataset version
  (public data visibility, NI-028 tables);
- liveChart blocks are verified against the NI-031 chart registry (NI-041:
  registered ``available`` definition, allowed selection, pinned dataset
  covering the required metrics — the shared rules of
  :mod:`near_api.documents.chart_blocks`); snapshot chart mode is gated;
- public evidence targets must reference a published model run or a public
  immutable citation artifact;
- Top-level ``observed_contexts`` are compared with server-resolved pins.
  Unchanged chart contexts carry forward verbatim after verification.
- new insight pins are verified against immutable chart inputs, and existing
  insight contexts change only through an explicit replacement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, insert, select, update

from near_api.auth.principal import Principal
from near_api.db.models import Document, DocumentVersion
from near_api.db.security import (
    Page,
    ResourceNotFound,
    owner_scope,
    principal_transaction,
    scoped_page,
)
from near_api.documents.context_resolver import (
    require_approved_dataset,
    resolve_revision_contexts,
    same_chart_pins,
    verify_chart_context,
)
from near_api.documents.projections import build_projections, write_projections
from near_api.documents.schema import (
    MAX_TITLE_CHARS,
    SCHEMA_VERSION,
    CanonicalDocument,
    DocumentSchemaError,
    ReferenceInvalid,
    canonical_context_json,
    empty_document,
    parse_document,
)
from near_api.evidence.targets import validate_public_targets
from near_api.insights.schemas import ResolvedContext
from near_api.repositories.documents import (
    DocumentRow,
    DocumentVersionRow,
    delete_document as _delete_document_row,
    get_version as _get_owned_version_row,
    list_documents,
)


class RevisionConflict(Exception):
    """CAS mismatch: the document moved since the client last saw it (409)."""

    def __init__(self, current_revision: int):
        super().__init__(
            f"Document is at revision {current_revision}; the save was rejected "
            "without changes")
        self.current_revision = current_revision


class ReferenceInUse(Exception):
    """The mutation needs consent to clean up references in this revision."""

    def __init__(self, message: str, details: tuple[tuple[str, str], ...]):
        super().__init__(message)
        self.details = details


@dataclass(frozen=True)
class DocumentDetail:
    """An owned document plus its current (or newly created) revision."""

    document: DocumentRow
    version: DocumentVersionRow
    content: dict
    resolved_contexts: dict


def create_document(engine: Engine, principal: Principal, *, title: str,
                    content: dict | None = None,
                    source_publication_id: UUID | None = None) -> DocumentDetail:
    """Create an owned document together with its first empty revision.

    One transaction inserts the document (revision 1, no pointer yet — the
    current-version composite FK is satisfied after the version insert),
    the immutable empty revision and the pointer. Empty content is the valid
    initial document (EDITOR_SPECIFICATION: "Empty document is valid").
    ``content`` (NI-045) carries the first revision's document JSON for
    non-empty starts (the investment-v1 template); see
    :func:`create_document_in_transaction` for the exact semantics.
    """
    with principal_transaction(engine, principal) as connection:
        return create_document_in_transaction(
            connection, principal, title=title, content=content,
            source_publication_id=source_publication_id)


def create_document_in_transaction(connection: Connection, principal: Principal,
                                   *, title: str,
                                   content: dict | None = None,
                                   source_publication_id: UUID | None = None) -> DocumentDetail:
    """Transaction-scoped :func:`create_document` (used by the idempotent create).

    ``content`` (NI-045) carries the first revision's document JSON when the
    document does not start empty — the ``investment-v1`` template's eight
    headings or a publication duplicate's remapped public projection. It is
    parsed through the canonical validator exactly like any saved revision
    (a template can never drift outside the editor grammar) and carries no
    chart contexts: template headings have no pins, and a duplicate's contexts
    are rebuilt from its immutable pins by the publications service before
    its content revision is written. ``source_publication_id`` records the
    one-time attribution of a duplicated document (never updated afterwards).
    """
    title = _validated_title(title)
    canonical = parse_document(content if content is not None else empty_document())
    document_id, version_id = uuid4(), uuid4()
    connection.execute(_insert_document().values(
        id=document_id, owner_id=principal.id, title=title,
        schema_version=SCHEMA_VERSION, revision=1, current_version_id=None,
        source_publication_id=source_publication_id))
    connection.execute(_insert_version().values(
        id=version_id, document_id=document_id, owner_id=principal.id,
        revision=1, schema_version=SCHEMA_VERSION,
        content=canonical.canonical, resolved_contexts={},
        content_sha256=canonical.content_sha256))
    connection.execute(update(Document)
                       .where(Document.id == document_id,
                              owner_scope(Document.owner_id, principal.id))
                       .values(current_version_id=version_id))
    document = _locked_document(connection, principal, document_id)
    version = _version_row(connection, version_id)
    return DocumentDetail(document=document, version=version,
                          content=version.content,
                          resolved_contexts=version.resolved_contexts or {})


def get_document_detail(engine: Engine, principal: Principal,
                        document_id: UUID) -> DocumentDetail:
    """Return the owned document with its current canonical content."""
    with principal_transaction(engine, principal) as connection:
        document = _owned_document_row(connection, principal, document_id)
        if document.current_version_id is None:
            # Service-created documents always carry the first empty revision;
            # a missing pointer is an inconsistent state, never fabricated content.
            raise ValueError(f"Document {document_id} has no current revision")
        version = _version_row(connection, document.current_version_id)
    return DocumentDetail(document=document, version=version, content=version.content,
                          resolved_contexts=version.resolved_contexts or {})


def list_document_details(engine: Engine, principal: Principal, *, search: str | None = None,
                          limit: int | None = None,
                          offset: int | None = None) -> Page:
    """Owner-scoped, paginated document list (delegates to the NI-019 repository)."""
    with principal_transaction(engine, principal) as connection:
        return list_documents(connection, principal, search=search,
                              limit=limit, offset=offset)


def save_revision(engine: Engine, principal: Principal, document_id: UUID, *,
                  expected_revision: int, document_payload: dict,
                  observed_contexts: list[ResolvedContext | dict] | None = None) -> DocumentDetail:
    """Append one immutable revision with compare-and-set and full projections.

    The whole operation is one transaction: row lock -> CAS -> pure schema
    validation -> database reference validation -> version insert -> projection
    insert -> pointer advance. Any failure (including a simulated crash) rolls
    back everything, so a rejected save leaves zero rows and the previous
    revision stays current and unchanged.
    """
    with principal_transaction(engine, principal) as connection:
        return save_revision_in_transaction(
            connection, principal, document_id, expected_revision=expected_revision,
            document_payload=document_payload, observed_contexts=observed_contexts)


def save_revision_in_transaction(connection: Connection, principal: Principal,
                                 document_id: UUID, *, expected_revision: int,
                                 document_payload: dict,
                                 observed_contexts: list[ResolvedContext | dict] | None = None,
                                 ) -> DocumentDetail:
    """Transaction-scoped :func:`save_revision` (used by the idempotent save)."""
    document, previous = lock_current_revision(
        connection, principal, document_id, expected_revision=expected_revision)
    return save_locked_revision(
        connection, principal, document, previous, document_payload,
        observed_contexts=observed_contexts)


def lock_current_revision(connection: Connection, principal: Principal, document_id: UUID,
                          *, expected_revision: int) -> tuple[DocumentRow, DocumentVersionRow]:
    """Lock the verified owner's document and check CAS before editing its content."""
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) \
            or expected_revision < 1:
        raise DocumentSchemaError("If-Match must be the quoted current revision",
                                  [("If-Match", "invalid_revision")])
    document = _locked_document(connection, principal, document_id)
    if document.revision != expected_revision:
        raise RevisionConflict(document.revision)
    if document.current_version_id is None:
        raise ValueError(f"Document {document.id} has no current revision")
    return document, _version_row(connection, document.current_version_id)


def save_locked_revision(connection: Connection, principal: Principal, document: DocumentRow,
                         previous: DocumentVersionRow, document_payload: dict, *,
                         observed_contexts: list[ResolvedContext | dict] | None = None,
                         replace_insight_context_id: UUID | None = None) -> DocumentDetail:
    """Validate and commit a complete revision after :func:`lock_current_revision`."""
    if observed_contexts is None:
        observed_contexts = []
    if not isinstance(observed_contexts, list):
        raise DocumentSchemaError("observed_contexts must be an array",
                                  [("observed_contexts", "must_be_array")])
    canonical = parse_document(document_payload)
    if canonical.insights:
        canonical = _prepare_insights(connection, canonical, previous,
                                      replace_context_id=replace_insight_context_id)
    if canonical.hypotheses:
        canonical = _prepare_hypotheses(canonical, previous)
    if canonical.evidence:
        _validate_evidence_identities(canonical, previous)
    resolved_contexts = resolve_revision_contexts(
        connection, canonical, previous, observed_contexts=observed_contexts)
    return _commit_new_revision(connection, principal, document, canonical=canonical,
                                resolved_contexts=resolved_contexts)


def _commit_new_revision(connection: Connection, principal: Principal,
                         document: DocumentRow, *, canonical: CanonicalDocument,
                         resolved_contexts: dict) -> DocumentDetail:
    """Shared revision tail: version row + projections + pointer, one step.

    Used by the whole-document save (:func:`save_revision_in_transaction`)
    and the chart-block insertion
    (:func:`near_api.documents.chart_blocks.append_chart_block_in_transaction`)
    so both write the immutable version, its projections and the advanced
    pointer identically inside their transaction.
    """
    _validate_database_references(connection, canonical)
    new_revision = document.revision + 1
    version_id = uuid4()
    connection.execute(_insert_version().values(
        id=version_id, document_id=document.id, owner_id=principal.id,
        revision=new_revision, schema_version=SCHEMA_VERSION,
        content=canonical.canonical, resolved_contexts=resolved_contexts,
        content_sha256=canonical.content_sha256))
    write_projections(connection, principal, document_id=document.id,
                      version_id=version_id,
                      projections=build_projections(canonical))
    connection.execute(update(Document)
                       .where(Document.id == document.id,
                              owner_scope(Document.owner_id, principal.id))
                       .values(revision=new_revision, current_version_id=version_id))
    document = _locked_document(connection, principal, document.id)
    version = _version_row(connection, version_id)
    return DocumentDetail(document=document, version=version, content=version.content,
                          resolved_contexts=version.resolved_contexts or {})


def rename_document(engine: Engine, principal: Principal, document_id: UUID, *,
                    expected_revision: int, title: str) -> DocumentDetail:
    """Rename an owned document; a title change creates a full new revision.

    EDITOR_SPECIFICATION: "Title rename also creates a version, ensuring
    export title/content attribution are consistent." The new revision carries
    the byte-identical canonical content (and the previous revision's
    resolved contexts) with the next revision number, so the rename is
    visible in history and every export pins a (title, content) pair that
    existed together. The content is re-parsed and re-validated against the
    database references like any other revision — a rename can never publish
    a broken revision even if a shared referenced dataset changed state.

    A PATCH whose title equals the current title changes nothing: the current
    document summary is returned without creating a revision (a no-op rename
    is not a content change and must not pollute immutable history).
    """
    _validated_title(title)
    with principal_transaction(engine, principal) as connection:
        document = _locked_document(connection, principal, document_id)
        if document.revision != expected_revision:
            raise RevisionConflict(document.revision)
        if title == document.title:
            if document.current_version_id is None:
                # Service-created documents always carry the first empty
                # revision; a missing pointer is an inconsistent state.
                raise ValueError(f"Document {document_id} has no current revision")
            version = _version_row(connection, document.current_version_id)
            return DocumentDetail(document=document, version=version,
                                  content=version.content,
                                  resolved_contexts=version.resolved_contexts or {})
        return _append_identical_revision(connection, principal, document, title=title)


def delete_document(engine: Engine, principal: Principal, document_id: UUID, *,
                    expected_revision: int) -> None:
    """Delete an owned document with compare-and-set; children cascade.

    One transaction: row lock -> CAS -> owner-checked DELETE of the parent row.
    The ON DELETE CASCADE chain (documents -> document_versions -> blocks/
    insights/hypotheses/evidence_links, DATABASE_SCHEMA.md "Delete document")
    removes every private child projection of this document inside the same
    statement; the deferrable current-version pointer is released with the
    parent row. Shared scientific data (datasets, observations, registries,
    artifacts) is referenced read-only and RESTRICT/cascade-free from this
    chain, so a document deletion can never remove it. There is no
    general direct revision-delete endpoint: versions are immutable rows that
    disappear only with their document (export jobs arrive with NI-058 and
    will cascade by their documented document FK).
    """
    with principal_transaction(engine, principal) as connection:
        document = _locked_document(connection, principal, document_id)
        if document.revision != expected_revision:
            raise RevisionConflict(document.revision)
        _delete_document_row(connection, principal, document_id)


def list_document_versions(engine: Engine, principal: Principal, document_id: UUID, *,
                           limit: int | None = None,
                           offset: int | None = None) -> Page:
    """Page an owned document's revisions, newest first (revision DESC).

    The owner predicate is applied before LIMIT/OFFSET through
    :func:`scoped_page`; the ordering column is unique per document, so the
    offset cursor is stable. Foreign/absent documents are the same 404.
    """
    with principal_transaction(engine, principal) as connection:
        _owned_document_row(connection, principal, document_id)
        query = (
            select(DocumentVersion.id, DocumentVersion.document_id,
                   DocumentVersion.owner_id, DocumentVersion.revision,
                   DocumentVersion.schema_version, DocumentVersion.content_sha256,
                   DocumentVersion.created_at)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.revision.desc())
        )
        return scoped_page(connection, query,
                           owner_scope(DocumentVersion.owner_id, principal.id),
                           limit=limit, offset=offset)


def get_document_version(engine: Engine, principal: Principal, document_id: UUID,
                         version_id: UUID) -> DocumentVersionRow:
    """Return one immutable revision only through its owned parent document.

    Compositional ownership (NI-019 repository): the version must line up
    with the owned document by (id, document, owner) — knowing a version UUID
    grants no access and a foreign document's version id is the same 404.
    """
    with principal_transaction(engine, principal) as connection:
        return _get_owned_version_row(connection, principal, document_id, version_id)


# --------------------------------------------------------------------------- #
# Internal helpers (all inside the principal transaction)
# --------------------------------------------------------------------------- #


def _insert_document():
    return insert(Document)


def _insert_version():
    return insert(DocumentVersion)


def _validated_title(title: str) -> str:
    """The shared create/rename title rule (1-200 chars, not whitespace-only)."""
    if not isinstance(title, str) or not title.strip() or len(title) > MAX_TITLE_CHARS:
        raise DocumentSchemaError("Document title must be 1-200 characters",
                                  [("title", "invalid_title")])
    return title


def _append_identical_revision(connection: Connection, principal: Principal,
                               document: DocumentRow, *, title: str) -> DocumentDetail:
    """Create the next revision with the current canonical content (rename).

    The stored content of the current version is re-parsed into the current
    canonical form, re-validated against the database references, and stored
    as a new immutable version with the next revision number; the document
    row moves to the new title and pointer in the same transaction.
    """
    if document.current_version_id is None:
        raise ValueError(f"Document {document.id} has no current revision")
    previous = _version_row(connection, document.current_version_id)
    canonical = parse_document(previous.content)
    _validate_database_references(connection, canonical)
    resolved_contexts = resolve_revision_contexts(connection, canonical, previous)
    new_revision = document.revision + 1
    version_id = uuid4()
    connection.execute(_insert_version().values(
        id=version_id, document_id=document.id, owner_id=principal.id,
        revision=new_revision, schema_version=SCHEMA_VERSION,
        content=canonical.canonical, resolved_contexts=resolved_contexts,
        content_sha256=canonical.content_sha256))
    write_projections(connection, principal, document_id=document.id,
                      version_id=version_id,
                      projections=build_projections(canonical))
    connection.execute(update(Document)
                       .where(Document.id == document.id,
                              owner_scope(Document.owner_id, principal.id))
                       .values(title=title, revision=new_revision,
                               current_version_id=version_id))
    document = _locked_document(connection, principal, document.id)
    version = _version_row(connection, version_id)
    return DocumentDetail(document=document, version=version, content=version.content,
                          resolved_contexts=version.resolved_contexts or {})


def _locked_document(connection: Connection, principal: Principal,
                     document_id: UUID) -> DocumentRow:
    """Select the owned document FOR UPDATE; absent = not-owned = one 404."""
    row = connection.execute(
        select(Document.id, Document.owner_id, Document.title, Document.revision,
               Document.schema_version, Document.current_version_id,
               Document.created_at, Document.updated_at)
        .where(Document.id == document_id, owner_scope(Document.owner_id, principal.id))
        .with_for_update()
    ).mappings().first()
    if row is None:
        raise ResourceNotFound("Resource does not exist for this owner")
    return DocumentRow(**row)


def _owned_document_row(connection: Connection, principal: Principal,
                        document_id: UUID) -> DocumentRow:
    row = connection.execute(
        select(Document.id, Document.owner_id, Document.title, Document.revision,
               Document.schema_version, Document.current_version_id,
               Document.created_at, Document.updated_at)
        .where(Document.id == document_id, owner_scope(Document.owner_id, principal.id))
    ).mappings().first()
    if row is None:
        raise ResourceNotFound("Resource does not exist for this owner")
    return DocumentRow(**row)


def _version_row(connection: Connection, version_id: UUID) -> DocumentVersionRow:
    row = connection.execute(
        select(DocumentVersion.id, DocumentVersion.document_id, DocumentVersion.owner_id,
               DocumentVersion.revision, DocumentVersion.schema_version,
               DocumentVersion.content, DocumentVersion.resolved_contexts,
               DocumentVersion.content_sha256, DocumentVersion.created_at)
        .where(DocumentVersion.id == version_id)
    ).mappings().one()
    return DocumentVersionRow(**row)


def _validate_database_references(connection: Connection,
                                  canonical: CanonicalDocument) -> None:
    """Validate table and evidence references inside the save transaction."""
    for table in canonical.data_tables:
        if table.dataset_version_id is not None:
            require_approved_dataset(connection, table.dataset_version_id,
                                     "dataTable.dataset_version_id")
    validate_public_targets(connection, canonical)


def _validate_evidence_identities(canonical: CanonicalDocument,
                                  previous: DocumentVersionRow) -> None:
    """A retained evidence block and relationship keep their paired IDs."""
    prior = [node["attrs"] for node in previous.content["content"]
             if node["type"] == "evidence"]
    block_by_evidence = {attrs["evidence_id"]: attrs["block_id"] for attrs in prior}
    evidence_by_block = {attrs["block_id"]: attrs["evidence_id"] for attrs in prior}
    for item in canonical.evidence:
        block_id, evidence_id = str(item.block_id), str(item.evidence_id)
        if (block_by_evidence.get(evidence_id, block_id) != block_id
                or evidence_by_block.get(block_id, evidence_id) != evidence_id):
            raise ReferenceInvalid("Existing evidence keeps its block_id and evidence_id",
                                   [("content", "evidence_identity_mismatch")])


def _prepare_insights(connection: Connection, canonical: CanonicalDocument,
                      previous: DocumentVersionRow, *,
                      replace_context_id: UUID | None) -> CanonicalDocument:
    """Author timestamps and verify new pins on every document save path."""
    prior_by_id = {
        node["attrs"]["insight_id"]: node["attrs"]
        for node in previous.content.get("content", ())
        if node["type"] == "insight"
    }
    content = list(canonical.canonical["content"])
    now = datetime.now(UTC)
    timestamp = now.isoformat()
    replacement_id = str(replace_context_id)
    for position, node in enumerate(content):
        if node["type"] != "insight":
            continue
        attrs = dict(node["attrs"])
        insight_id = attrs["insight_id"]
        prior = prior_by_id.get(insight_id)
        if prior is not None and prior["block_id"] != attrs["block_id"]:
            raise ReferenceInvalid("An existing insight keeps its block_id",
                                   [("block_id", "insight_block_mismatch")])
        if (prior is not None and attrs["context"] != prior["context"]
                and "chart_definition_version_id" in prior["context"]
                and "chart_definition_version_id" in attrs["context"]
                and same_chart_pins(ResolvedContext.model_validate(attrs["context"]),
                                    ResolvedContext.model_validate(prior["context"]))):
            attrs["context"] = prior["context"]
        if prior is None or attrs["context"] != prior["context"]:
            if prior is not None and insight_id != replacement_id:
                raise ReferenceInvalid(
                    "Changing an insight context requires an explicit insight edit",
                    [("context", "insight_context_immutable")])
            if "chart_definition_version_id" not in attrs["context"]:
                raise ReferenceInvalid("New insight contexts must reference a chart",
                                       [("context", "reference_unavailable")])
            verified = verify_chart_context(
                connection, ResolvedContext.model_validate(attrs["context"]), resolved_at=now)
            attrs["context"] = canonical_context_json(verified.model_dump(mode="json"))
        _author_annotation(attrs, prior, timestamp)
        content[position] = {**node, "attrs": attrs}
    if content == canonical.canonical["content"]:
        return canonical
    return parse_document({**canonical.canonical, "content": content})


def _prepare_hypotheses(canonical: CanonicalDocument,
                        previous: DocumentVersionRow) -> CanonicalDocument:
    """Keep hypothesis identity and authorship consistent on full-document saves too."""
    prior_by_id = {
        node["attrs"]["hypothesis_id"]: node["attrs"]
        for node in previous.content.get("content", ())
        if node["type"] == "hypothesis"
    }
    timestamp = datetime.now(UTC).isoformat()
    content = list(canonical.canonical["content"])
    for position, node in enumerate(content):
        if node["type"] != "hypothesis":
            continue
        attrs = dict(node["attrs"])
        prior = prior_by_id.get(attrs["hypothesis_id"])
        if prior is not None and prior["block_id"] != attrs["block_id"]:
            raise ReferenceInvalid("An existing hypothesis keeps its block_id",
                                   [("block_id", "hypothesis_block_mismatch")])
        _author_annotation(attrs, prior, timestamp)
        content[position] = {**node, "attrs": attrs}
    if content == canonical.canonical["content"]:
        return canonical
    return parse_document({**canonical.canonical, "content": content})


def _author_annotation(attrs: dict, prior: dict | None, timestamp: str) -> None:
    if prior is None:
        attrs.update(authored_at=timestamp, modified_at=timestamp)
        return
    attrs.update(authored_at=prior["authored_at"], modified_at=prior["modified_at"])
    if attrs != prior:
        attrs["modified_at"] = timestamp


__all__ = [
    "DocumentDetail",
    "ReferenceInUse",
    "RevisionConflict",
    "create_document",
    "create_document_in_transaction",
    "delete_document",
    "get_document_detail",
    "get_document_version",
    "list_document_details",
    "list_document_versions",
    "lock_current_revision",
    "rename_document",
    "require_approved_dataset",
    "save_locked_revision",
    "save_revision",
    "save_revision_in_transaction",
]
