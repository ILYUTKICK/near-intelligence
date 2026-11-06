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
- ``dataTable.dataset_version_id`` (and, once the NI-031 registry lifts the
  chart gate, chart ``observed_dataset_version_id``) must reference an
  APPROVED dataset version (public data visibility, NI-028 tables);
- evidence ``citation`` targets must reference a public immutable artifact;
- liveChart blocks, snapshot chart mode and ``model_run`` evidence targets
  require registries that do not exist yet (NI-031 chart registry, NI-035
  research snapshots, NI-054 model runs) and are rejected until those tasks
  land — an unverifiable reference is invalid, not tolerated;
- insight ``context`` and top-level ``observed_contexts`` are frozen
  inspection records: their shape is validated by the schema module, while
  server-side resolution and pin freezing arrive with the chart system
  (NI-041/NI-043), so a P0 save accepts only an empty context list and does
  not re-resolve historical context ids.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, insert, select, update

from near_api.auth.principal import Principal
from near_api.db.models import Artifact, DatasetVersion, Document, DocumentVersion
from near_api.db.security import (
    Page,
    ResourceNotFound,
    owner_scope,
    principal_transaction,
)
from near_api.documents.projections import build_projections, write_projections
from near_api.documents.schema import (
    MAX_TITLE_CHARS,
    SCHEMA_VERSION,
    CanonicalDocument,
    DocumentSchemaError,
    ReferenceInvalid,
    empty_document,
    parse_document,
)
from near_api.repositories.documents import DocumentRow, DocumentVersionRow, list_documents


class RevisionConflict(Exception):
    """CAS mismatch: the document moved since the client last saw it (409)."""

    def __init__(self, current_revision: int):
        super().__init__(
            f"Document is at revision {current_revision}; the save was rejected "
            "without changes")
        self.current_revision = current_revision


@dataclass(frozen=True)
class DocumentDetail:
    """An owned document plus its current (or newly created) revision."""

    document: DocumentRow
    version: DocumentVersionRow
    content: dict
    resolved_contexts: dict


def create_document(engine: Engine, principal: Principal, *, title: str) -> DocumentDetail:
    """Create an owned document together with its first empty revision.

    One transaction inserts the document (revision 1, no pointer yet — the
    current-version composite FK is satisfied after the version insert),
    the immutable empty revision and the pointer. Empty content is the valid
    initial document (EDITOR_SPECIFICATION: "Empty document is valid").
    """
    if not isinstance(title, str) or not title.strip() or len(title) > MAX_TITLE_CHARS:
        raise DocumentSchemaError("Document title must be 1-200 characters",
                                  [("title", "invalid_title")])
    canonical = parse_document(empty_document())
    document_id, version_id = uuid4(), uuid4()
    with principal_transaction(engine, principal) as connection:
        connection.execute(_insert_document().values(
            id=document_id, owner_id=principal.id, title=title,
            schema_version=SCHEMA_VERSION, revision=1, current_version_id=None))
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
                  observed_contexts: list | None = None) -> DocumentDetail:
    """Append one immutable revision with compare-and-set and full projections.

    The whole operation is one transaction: row lock -> CAS -> pure schema
    validation -> database reference validation -> version insert -> projection
    insert -> pointer advance. Any failure (including a simulated crash) rolls
    back everything, so a rejected save leaves zero rows and the previous
    revision stays current and unchanged.
    """
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) \
            or expected_revision < 1:
        raise DocumentSchemaError("If-Match must be the quoted current revision",
                                  [("If-Match", "invalid_revision")])
    if observed_contexts is None:
        observed_contexts = []
    if not isinstance(observed_contexts, list):
        raise DocumentSchemaError("observed_contexts must be an array",
                                  [("observed_contexts", "must_be_array")])
    with principal_transaction(engine, principal) as connection:
        document = _locked_document(connection, principal, document_id)
        if document.revision != expected_revision:
            raise RevisionConflict(document.revision)
        canonical = parse_document(document_payload)
        _validate_database_references(connection, canonical)
        resolved_contexts = _resolve_observed_contexts(canonical, observed_contexts)
        new_revision = document.revision + 1
        version_id = uuid4()
        connection.execute(_insert_version().values(
            id=version_id, document_id=document_id, owner_id=principal.id,
            revision=new_revision, schema_version=SCHEMA_VERSION,
            content=canonical.canonical, resolved_contexts=resolved_contexts,
            content_sha256=canonical.content_sha256))
        write_projections(connection, principal, document_id=document_id,
                          version_id=version_id,
                          projections=build_projections(canonical))
        connection.execute(update(Document)
                           .where(Document.id == document_id,
                                  owner_scope(Document.owner_id, principal.id))
                           .values(revision=new_revision, current_version_id=version_id))
        document = _locked_document(connection, principal, document_id)
        version = _version_row(connection, version_id)
    return DocumentDetail(document=document, version=version, content=version.content,
                          resolved_contexts=version.resolved_contexts or {})


# --------------------------------------------------------------------------- #
# Internal helpers (all inside the principal transaction)
# --------------------------------------------------------------------------- #


def _insert_document():
    return insert(Document)


def _insert_version():
    return insert(DocumentVersion)


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


def _resolve_observed_contexts(canonical: CanonicalDocument,
                               observed_contexts: list) -> dict:
    """Context pinning arrives with the chart system (NI-041/NI-043).

    resolved_contexts is keyed by block ID and pins chart/model inspection
    state. Because P0 chart blocks cannot exist (the chart registry is a
    NI-031 gate), a non-empty context list can never reference a block of this
    document and is rejected instead of being stored as unverifiable data.
    """
    if observed_contexts:
        raise ReferenceInvalid(
            "observed_contexts pin chart/model inspection state; no chart block of "
            "this document can carry a context until the chart registry lands",
            [("observed_contexts", "reference_unavailable")])
    return {}


def _validate_database_references(connection: Connection,
                                  canonical: CanonicalDocument) -> None:
    """Validate every database-backed reference; runs inside the save transaction."""
    if canonical.live_charts:
        # The chart definition registry (NI-031) does not exist yet: no
        # chart_definition_version_id can be verified, so a liveChart block is
        # an unverifiable reference rather than tolerated dangling data.
        raise ReferenceInvalid(
            "Live chart blocks require the chart definition registry, which is not "
            "available yet (arrives with NI-031)",
            [("content", "reference_unavailable")])
    for table in canonical.data_tables:
        if table.dataset_version_id is not None:
            _require_approved_dataset(connection, table.dataset_version_id,
                                      "dataTable.dataset_version_id")
    for item in canonical.evidence:
        if item.target_kind == "model_run":
            raise ReferenceInvalid(
                "Evidence targets of kind model_run require the model run registry, "
                "which is not available yet (arrives with NI-052/NI-054)",
                [("content", "reference_unavailable")])
        if item.target_kind == "citation":
            exists = connection.execute(
                select(Artifact.id).where(Artifact.id == item.target_id,
                                          Artifact.scope == "public")
            ).first()
            if exists is None:
                raise ReferenceInvalid(
                    "Evidence citation target does not reference a public immutable "
                    "artifact",
                    [("content", "dangling_citation_target")])


def _require_approved_dataset(connection: Connection, dataset_version_id: UUID,
                              path: str) -> None:
    """A pinned dataset must be an approved (public) immutable version."""
    exists = connection.execute(
        select(DatasetVersion.id).where(DatasetVersion.id == dataset_version_id,
                                        DatasetVersion.status == "approved")
    ).first()
    if exists is None:
        raise ReferenceInvalid(
            "Referenced dataset version does not exist or is not an approved "
            "public dataset",
            [(path, "dangling_dataset_reference")])


__all__ = [
    "DocumentDetail",
    "RevisionConflict",
    "create_document",
    "get_document_detail",
    "list_document_details",
    "save_revision",
]
