"""Edit hypotheses through the owned document's canonical revision service."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine

from near_api.auth.principal import Principal
from near_api.db.security import ResourceNotFound
from near_api.documents import service as documents
from near_api.documents.schema import ReferenceInvalid
from near_api.insights.schemas import Hypothesis
from near_api.schemas.document_hypotheses import HypothesisCreateRequest, HypothesisPatchRequest


def _hypothesis_response(document_id: UUID, node: dict) -> Hypothesis:
    attrs = dict(node["attrs"])
    return Hypothesis.model_validate({
        "id": attrs.pop("hypothesis_id"), "document_id": document_id, **attrs,
    })


def list_hypotheses(engine: Engine, principal: Principal, document_id: UUID,
                    version_id: UUID | None) -> tuple[Hypothesis, ...]:
    """Read current or historical hypotheses in canonical document order."""
    if version_id is None:
        version = documents.get_document_detail(engine, principal, document_id).version
    else:
        version = documents.get_document_version(engine, principal, document_id, version_id)
    return tuple(_hypothesis_response(document_id, node)
                 for node in version.content["content"] if node["type"] == "hypothesis")


def _hypothesis_position(content: list[dict], hypothesis_id: UUID) -> int:
    for position, node in enumerate(content):
        if node["type"] == "hypothesis" and node["attrs"]["hypothesis_id"] == str(hypothesis_id):
            return position
    raise ResourceNotFound("Hypothesis is absent from this document")


def create_hypothesis(connection: Connection, principal: Principal, document_id: UUID, *,
                      expected_revision: int,
                      payload: HypothesisCreateRequest) -> tuple[documents.DocumentDetail, Hypothesis]:
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
        raise ReferenceInvalid("Only a paragraph can be converted to a hypothesis",
                               [("block_id", "hypothesis_conversion_requires_paragraph")])

    now = datetime.now(UTC).isoformat()
    attrs = payload.model_dump(mode="json", exclude={"after_block_id"})
    attrs.update(hypothesis_id=str(uuid4()), authored_at=now, modified_at=now)
    node = {"type": "hypothesis", "attrs": attrs}
    if replace_position is None:
        content.insert(insert_position, node)
    else:
        insert_position = replace_position
        content[insert_position] = node
    detail = documents.save_locked_revision(
        connection, principal, document, previous, {**previous.content, "content": content})
    return detail, _hypothesis_response(document_id, detail.content["content"][insert_position])


def update_hypothesis(connection: Connection, principal: Principal, document_id: UUID,
                      hypothesis_id: UUID, *, expected_revision: int,
                      payload: HypothesisPatchRequest) -> tuple[documents.DocumentDetail, Hypothesis]:
    document, previous = documents.lock_current_revision(
        connection, principal, document_id, expected_revision=expected_revision)
    content = list(previous.content["content"])
    position = _hypothesis_position(content, hypothesis_id)
    node = content[position]
    changes = payload.model_dump(mode="json", exclude_unset=True)
    content[position] = {**node, "attrs": {**node["attrs"], **changes}}
    detail = documents.save_locked_revision(
        connection, principal, document, previous, {**previous.content, "content": content})
    return detail, _hypothesis_response(document_id, detail.content["content"][position])


def delete_hypothesis(connection: Connection, principal: Principal, document_id: UUID,
                      hypothesis_id: UUID, *, expected_revision: int,
                      remove_evidence_links: bool) -> documents.DocumentDetail:
    document, previous = documents.lock_current_revision(
        connection, principal, document_id, expected_revision=expected_revision)
    content = list(previous.content["content"])
    content.pop(_hypothesis_position(content, hypothesis_id))
    linked_attributes = {
        "evidence": ("hypothesis_id", "linked_evidence"),
        "insight": ("hypothesis_id", "linked_insights"),
        "risk": ("related_hypothesis_id", "linked_risks"),
    }
    counts = {reason: 0 for _, reason in linked_attributes.values()}
    kept = []
    for node in content:
        node_type = node["type"]
        link = linked_attributes.get(node_type)
        if link is not None:
            attribute, reason = link
            if node["attrs"].get(attribute) == str(hypothesis_id):
                counts[reason] += 1
                if node_type == "evidence":
                    continue
                attrs = dict(node["attrs"])
                del attrs[attribute]
                node = {**node, "attrs": attrs}
        kept.append(node)
    if not remove_evidence_links and any(counts.values()):
        raise documents.ReferenceInUse(
            "Confirm cleanup of the evidence and associations linked to this hypothesis",
            tuple(("remove_evidence_links", f"{reason}:{count}")
                  for reason, count in counts.items() if count))
    return documents.save_locked_revision(
        connection, principal, document, previous, {**previous.content, "content": kept})
