"""Edit insights through the owned document's canonical revision service."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine

from near_api.auth.principal import Principal
from near_api.db.security import ResourceNotFound
from near_api.documents import service as documents
from near_api.documents.schema import ReferenceInvalid
from near_api.insights.schemas import Insight, ResolvedContext
from near_api.schemas.chart_selection import ChartSelection
from near_api.schemas.document_insights import InsightCreateRequest, InsightPatchRequest


class EvidenceLinksExist(Exception):
    def __init__(self, count: int):
        super().__init__("Confirm removal of the evidence links that target this insight")
        self.count = count


def _insight_response(document_id: UUID, node: dict) -> Insight:
    attrs = dict(node["attrs"])
    return Insight.model_validate({
        "id": attrs.pop("insight_id"), "document_id": document_id, **attrs,
    })


def list_insights(engine: Engine, principal: Principal, document_id: UUID,
                  version_id: UUID | None) -> tuple[Insight, ...]:
    """Read current or historical insights in canonical document order."""
    if version_id is None:
        version = documents.get_document_detail(engine, principal, document_id).version
    else:
        version = documents.get_document_version(engine, principal, document_id, version_id)
    return tuple(_insight_response(document_id, node)
                 for node in version.content["content"] if node["type"] == "insight")


def _insight_position(content: list[dict], insight_id: UUID) -> int:
    for position, node in enumerate(content):
        if node["type"] == "insight" and node["attrs"]["insight_id"] == str(insight_id):
            return position
    raise ResourceNotFound("Insight is absent from this document")


def _check_anchor(anchor: dict, context: ResolvedContext, *, error_path: str) -> None:
    if anchor["type"] != "liveChart":
        return
    attrs = anchor["attrs"]
    if (attrs["chart_definition_version_id"] != str(context.chart_definition_version_id)
            or attrs["observed_dataset_version_id"] != str(context.dataset_version_id)
            or ChartSelection.model_validate(attrs["selection"]) != context.selection):
        raise ReferenceInvalid(
            "The inspection does not match the chart block in this document revision",
            [(error_path, "chart_anchor_context_mismatch")])


def create_insight(connection: Connection, principal: Principal, document_id: UUID, *,
                   expected_revision: int,
                   payload: InsightCreateRequest) -> tuple[documents.DocumentDetail, Insight]:
    document, previous = documents.lock_current_revision(
        connection, principal, document_id, expected_revision=expected_revision)
    content = list(previous.content["content"])
    positions = {node["attrs"]["block_id"]: position for position, node in enumerate(content)}
    target_position = positions.get(str(payload.block_id))
    insert_position = len(content)
    if payload.after_block_id is not None:
        anchor_position = positions.get(str(payload.after_block_id))
        if anchor_position is None:
            raise ReferenceInvalid("after_block_id does not reference a block in this revision",
                                   [("after_block_id", "dangling_after_block_reference")])
        if target_position is not None:
            raise ReferenceInvalid(
                "Inserting after a block requires a new block_id",
                [("block_id", "duplicate_block_id")])
        _check_anchor(content[anchor_position], payload.context, error_path="after_block_id")
        insert_position = anchor_position + 1
    if target_position is not None and content[target_position]["type"] == "insight":
        raise ReferenceInvalid("Edit the existing insight by its insight_id",
                               [("block_id", "existing_insight_block")])
    if target_position is not None:
        _check_anchor(content[target_position], payload.context, error_path="block_id")

    now = datetime.now(UTC).isoformat()
    attrs = payload.model_dump(mode="json", exclude={"after_block_id"})
    attrs.update(insight_id=str(uuid4()), authored_at=now, modified_at=now)
    node = {"type": "insight", "attrs": attrs}
    if target_position is None:
        content.insert(insert_position, node)
    else:
        insert_position = target_position
        content[insert_position] = node
    detail = documents.save_locked_revision(
        connection, principal, document, previous, {**previous.content, "content": content})
    return detail, _insight_response(document_id, detail.content["content"][insert_position])


def update_insight(connection: Connection, principal: Principal, document_id: UUID,
                   insight_id: UUID, *, expected_revision: int,
                   payload: InsightPatchRequest) -> tuple[documents.DocumentDetail, Insight]:
    document, previous = documents.lock_current_revision(
        connection, principal, document_id, expected_revision=expected_revision)
    content = list(previous.content["content"])
    position = _insight_position(content, insight_id)
    node = content[position]
    changes = payload.model_dump(mode="json", exclude_unset=True)
    content[position] = {**node, "attrs": {**node["attrs"], **changes}}
    detail = documents.save_locked_revision(
        connection, principal, document, previous, {**previous.content, "content": content},
        replace_insight_context_id=insight_id if "context" in changes else None)
    return detail, _insight_response(document_id, detail.content["content"][position])


def delete_insight(connection: Connection, principal: Principal, document_id: UUID,
                   insight_id: UUID, *, expected_revision: int,
                   remove_evidence_links: bool) -> documents.DocumentDetail:
    document, previous = documents.lock_current_revision(
        connection, principal, document_id, expected_revision=expected_revision)
    content = list(previous.content["content"])
    content.pop(_insight_position(content, insight_id))
    kept = [node for node in content if not (
        node["type"] == "evidence" and node["attrs"]["target_kind"] == "insight"
        and node["attrs"]["target_id"] == str(insight_id))]
    linked_count = len(content) - len(kept)
    if linked_count and not remove_evidence_links:
        raise EvidenceLinksExist(linked_count)
    return documents.save_locked_revision(
        connection, principal, document, previous, {**previous.content, "content": kept})
