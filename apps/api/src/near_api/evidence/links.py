"""Read and edit evidence through the owned document's immutable revisions."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, func, or_, select
from sqlalchemy.dialects.postgresql import distinct_on

from near_api.auth.principal import Principal
from near_api.db.models import DocumentVersion, EvidenceLink
from near_api.db.security import ResourceNotFound, owner_scope, principal_transaction
from near_api.documents import service as documents
from near_api.documents.schema import ReferenceInvalid
from near_api.insights.schemas import Evidence
from near_api.repositories.documents import DocumentVersionRow, get_document, get_version
from near_api.schemas.document_evidence import EvidenceCreateRequest, EvidencePatchRequest


def _evidence_timestamps(connection: Connection, version: DocumentVersionRow,
                         ids: list[UUID]) -> dict[UUID, tuple[datetime, datetime]]:
    """Find the first appearance and last change at or before the requested revision."""
    state = func.jsonb_build_array(EvidenceLink.block_id, EvidenceLink.hypothesis_id,
                                  EvidenceLink.classification, EvidenceLink.target_kind,
                                  EvidenceLink.target_id, EvidenceLink.explanation)
    order = {"partition_by": EvidenceLink.evidence_id, "order_by": DocumentVersion.revision}
    history = (
        select(EvidenceLink.evidence_id, DocumentVersion.revision, DocumentVersion.created_at,
               state.label("state"), func.lag(state).over(**order).label("previous_state"),
               func.lag(DocumentVersion.revision).over(**order).label("previous_revision"),
               func.first_value(DocumentVersion.created_at).over(**order).label("authored_at"))
        .select_from(EvidenceLink)
        .join(DocumentVersion, DocumentVersion.id == EvidenceLink.document_version_id)
        .where(EvidenceLink.document_id == version.document_id,
               owner_scope(EvidenceLink.owner_id, version.owner_id),
               DocumentVersion.revision <= version.revision,
               EvidenceLink.evidence_id.in_(ids))
        .subquery()
    )
    # A gap in revision numbers means the link was removed and restored.
    # Reordering the same block or saving unrelated content leaves its state intact.
    timestamps = connection.execute(
        select(history.c.evidence_id, history.c.authored_at, history.c.created_at)
        .where(or_(history.c.previous_revision.is_distinct_from(history.c.revision - 1),
                   history.c.previous_state.is_distinct_from(history.c.state)))
        .ext(distinct_on(history.c.evidence_id))
        .order_by(history.c.evidence_id, history.c.revision.desc())
    )
    return {evidence_id: (authored_at, modified_at)
            for evidence_id, authored_at, modified_at in timestamps}


def _evidence_responses(connection: Connection, version: DocumentVersionRow,
                        nodes: list[dict]) -> tuple[Evidence, ...]:
    if not nodes:
        return ()
    ids = [UUID(node["attrs"]["evidence_id"]) for node in nodes]
    timestamps = _evidence_timestamps(connection, version, ids)
    if len(timestamps) != len(ids):
        raise ResourceNotFound("Evidence is absent from this document revision")
    result = []
    for evidence_id, node in zip(ids, nodes, strict=True):
        attrs = dict(node["attrs"])
        del attrs["evidence_id"]
        authored_at, modified_at = timestamps[evidence_id]
        result.append(Evidence.model_validate({
            **attrs, "id": evidence_id, "document_id": version.document_id,
            "authored_at": authored_at, "modified_at": modified_at,
        }))
    return tuple(result)


def list_evidence(engine: Engine, principal: Principal, document_id: UUID, *,
                  version_id: UUID | None, hypothesis_id: UUID | None) -> tuple[Evidence, ...]:
    """Read current or historical evidence in canonical order."""
    with principal_transaction(engine, principal) as connection:
        if version_id is None:
            version_id = get_document(connection, principal, document_id).current_version_id
            if version_id is None:
                raise ResourceNotFound("Document has no current revision")
        version = get_version(connection, principal, document_id, version_id)
        nodes = version.content["content"]
        hypothesis = str(hypothesis_id)
        if hypothesis_id is not None and not any(
                node["type"] == "hypothesis" and node["attrs"]["hypothesis_id"] == hypothesis
                for node in nodes):
            raise ResourceNotFound("Hypothesis is absent from this document revision")
        evidence = [node for node in nodes if node["type"] == "evidence"
                    and (hypothesis_id is None or node["attrs"]["hypothesis_id"] == hypothesis)]
        return _evidence_responses(connection, version, evidence)


def _evidence_position(content: list[dict], evidence_id: UUID) -> int:
    for position, node in enumerate(content):
        if node["type"] == "evidence" and node["attrs"]["evidence_id"] == str(evidence_id):
            return position
    raise ResourceNotFound("Evidence is absent from this document")


def create_evidence(connection: Connection, principal: Principal, document_id: UUID, *,
                    expected_revision: int,
                    payload: EvidenceCreateRequest) -> tuple[documents.DocumentDetail, Evidence]:
    document, previous = documents.lock_current_revision(
        connection, principal, document_id, expected_revision=expected_revision)
    content = list(previous.content["content"])
    positions = {node["attrs"]["block_id"]: position for position, node in enumerate(content)}
    replace_position = positions.get(str(payload.block_id))
    insert_position = len(content)
    if payload.after_block_id is not None:
        anchor_position = positions.get(str(payload.after_block_id))
        if anchor_position is None:
            raise ReferenceInvalid("after_block_id does not reference a block in this revision",
                                   [("after_block_id", "dangling_after_block_reference")])
        if replace_position is not None:
            raise ReferenceInvalid("Inserting after a block requires a new block_id",
                                   [("block_id", "duplicate_block_id")])
        insert_position = anchor_position + 1
    if replace_position is not None and content[replace_position]["type"] != "paragraph":
        raise ReferenceInvalid("Only a paragraph can be converted to evidence",
                               [("block_id", "evidence_conversion_requires_paragraph")])

    attrs = payload.model_dump(mode="json", exclude={"after_block_id"})
    attrs["evidence_id"] = str(uuid4())
    node = {"type": "evidence", "attrs": attrs}
    if replace_position is None:
        content.insert(insert_position, node)
    else:
        insert_position = replace_position
        content[insert_position] = node
    detail = documents.save_locked_revision(
        connection, principal, document, previous, {**previous.content, "content": content})
    return detail, _evidence_responses(connection, detail.version,
                                       [detail.content["content"][insert_position]])[0]


def update_evidence(connection: Connection, principal: Principal, document_id: UUID,
                    evidence_id: UUID, *, expected_revision: int,
                    payload: EvidencePatchRequest) -> tuple[documents.DocumentDetail, Evidence]:
    document, previous = documents.lock_current_revision(
        connection, principal, document_id, expected_revision=expected_revision)
    content = list(previous.content["content"])
    position = _evidence_position(content, evidence_id)
    node = content[position]
    changes = payload.model_dump(mode="json", exclude_unset=True)
    content[position] = {**node, "attrs": {**node["attrs"], **changes}}
    detail = documents.save_locked_revision(
        connection, principal, document, previous, {**previous.content, "content": content})
    return detail, _evidence_responses(connection, detail.version,
                                       [detail.content["content"][position]])[0]


def delete_evidence(connection: Connection, principal: Principal, document_id: UUID,
                    evidence_id: UUID, *, expected_revision: int) -> documents.DocumentDetail:
    document, previous = documents.lock_current_revision(
        connection, principal, document_id, expected_revision=expected_revision)
    content = list(previous.content["content"])
    content.pop(_evidence_position(content, evidence_id))
    return documents.save_locked_revision(
        connection, principal, document, previous, {**previous.content, "content": content})
