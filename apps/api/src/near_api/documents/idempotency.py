"""Transaction-scoped Idempotency-Key replay for document writes (NI-037).

API_SPECIFICATION: "For POST creation/retry use ``Idempotency-Key: UUID``;
repeated identical owner/route/body returns original result (24h); different
body same key -> 409." A client that loses a committed response (network
timeout after the server commit) can repeat the identical request and receive
the ORIGINAL result instead of silently creating a second document or a second
immutable revision — the failure mode the editor autosave contract
(EDITOR_SPECIFICATION) and NI-040's "network timeout retry cannot duplicate
revisions" acceptance exist for.

Mechanics: :func:`execute_idempotent` opens ONE principal transaction that

1. takes a transaction-scoped advisory lock over (owner, route, key) so two
   concurrent identical requests are fully serialized before either touches
   the document chain (no unique-violation rollback races);
2. returns the stored original response when an unexpired record with the
   same request fingerprint exists (:class:`IdempotentOutcome` with
   ``replay=True``), or raises :class:`IdempotencyConflict` when the same key
   was used with a different body;
3. otherwise runs the caller's ``operation`` on the SAME connection (the
   business transaction), and stores the response snapshot in that same
   transaction — the commit is atomic over the write AND its replay record
   ("timeout-after-commit" guarantee by construction).

Request identity: the fingerprint covers route, verified owner and the
canonical request BODY only. For a document-scoped mutation the route key
contains the concrete document UUID (never the path template), so one
destination cannot replay another destination's result. API_SPECIFICATION defines idempotency over
owner/route/body, not headers. A retried save therefore replays the stored
revision result even if the retry carries a refreshed If-Match (the stored
result is exactly the state that payload's save produced); a genuinely
different payload with the same key is a 409 collision, never a replay.

Boundaries: only successful (2xx) results are stored (migration CHECK); a
failed operation writes nothing and stays retryable. Records live 24h,
are write-once (no UPDATE), expire lazily on key reuse, and are owner-scoped
by RLS (migration 0009). No other module reads the table.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, delete, func, insert, select, text

from near_api.auth.principal import Principal
from near_api.db.models import IdempotencyRecord
from near_api.db.security import principal_transaction
from near_api.documents.schema import DocumentSchemaError

ROUTE_CREATE_DOCUMENT = "POST /api/documents"
ROUTE_SAVE_DOCUMENT_VERSION = "POST /api/documents/{document_id}/versions"
ROUTE_ADD_CHART_BLOCK = "POST /api/documents/{document_id}/chart-blocks"
ROUTE_ADD_MODEL_BLOCK = "POST /api/documents/{document_id}/model-blocks"

# API_SPECIFICATION: repeated identical owner/route/body requests return the
# original result for 24h. Evaluated server-side against now() at read time.
RETENTION = timedelta(hours=24)


class IdempotencyConflict(Exception):
    """The same key was used for a different request body (409)."""


class IdempotencyKeyInvalid(DocumentSchemaError):
    """The supplied Idempotency-Key header is not a UUID (422)."""


@dataclass(frozen=True)
class IdempotentOutcome:
    """Either the freshly executed result or the stored original one."""

    replay: bool
    status: int
    body: dict


def parse_idempotency_key(header_value: str | None) -> UUID | None:
    """Parse the Idempotency-Key header: a UUID when present, else None.

    A present but malformed key is a validation error (422), never silently
    ignored: ignoring it would turn an intended retry into a duplicate write.
    """
    if header_value is None:
        return None
    try:
        return UUID(str(header_value).strip())
    except (ValueError, AttributeError):
        raise IdempotencyKeyInvalid(
            "Idempotency-Key must be a UUID",
            [("Idempotency-Key", "invalid_idempotency_key")]) from None


def request_fingerprint(route_key: str, owner_id: UUID, body: Any) -> str:
    """Stable sha256 over (route, owner, canonical JSON body).

    The body is the Pydantic-validated request model dump; ``sort_keys`` makes
    the fingerprint independent of client key order, so the same request with
    re-serialized JSON still replays.
    """
    material = json.dumps(
        {"route": route_key, "owner": str(owner_id), "body": body},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def execute_idempotent(engine: Engine, principal: Principal, *, route_key: str,
                       idempotency_key: UUID, request_hash: str,
                       operation: Callable[[Connection], tuple[int, dict]],
                       ) -> IdempotentOutcome:
    """Run ``operation`` once per key; replay the stored original result after.

    The whole flow — lock, replay check, business operation, record insert —
    is one principal transaction. ``operation`` receives that transaction's
    connection and returns ``(status, body)`` where ``body`` is the exact JSON
    response snapshot to store for replays. Any exception from ``operation``
    aborts the transaction with no stored record, so failed writes stay
    retryable with the same key.
    """
    with principal_transaction(engine, principal) as connection:
        _serialize_same_key(connection, principal.id, route_key, idempotency_key)
        stored = _active_record(connection, principal.id, route_key, idempotency_key)
        if stored is not None:
            if stored["request_hash"] != request_hash:
                raise IdempotencyConflict(
                    "This Idempotency-Key was already used with a different request; "
                    "a new key is required for a new payload")
            return IdempotentOutcome(replay=True, status=stored["response_status"],
                                     body=stored["response_body"])
        status, body = operation(connection)
        _record_result(connection, principal.id, route_key, idempotency_key,
                       request_hash, status, body)
        return IdempotentOutcome(replay=False, status=status, body=body)


def _serialize_same_key(connection: Connection, owner_id: UUID, route_key: str,
                        idempotency_key: UUID) -> None:
    """Advisory-lock the (owner, route, key) pair for this transaction.

    Two concurrent identical requests cannot both pass the replay check before
    either commits: the second blocks here until the first commits, then sees
    its record. The lock is transaction-scoped and released automatically; a
    hash collision with an unrelated key costs only a momentary mutual
    exclusion, never correctness.
    """
    connection.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:material, 0))"),
        {"material": f"idempotency:{owner_id}:{route_key}:{idempotency_key}"})


def _active_record(connection: Connection, owner_id: UUID, route_key: str,
                   idempotency_key: UUID) -> dict | None:
    """The unexpired stored result for this key, if any."""
    row = connection.execute(
        select(IdempotencyRecord.request_hash, IdempotencyRecord.response_status,
               IdempotencyRecord.response_body)
        .where(IdempotencyRecord.owner_id == owner_id,
               IdempotencyRecord.route_key == route_key,
               IdempotencyRecord.idempotency_key == idempotency_key,
               IdempotencyRecord.expires_at > func.now())
    ).mappings().first()
    return dict(row) if row is not None else None


def _record_result(connection: Connection, owner_id: UUID, route_key: str,
                   idempotency_key: UUID, request_hash: str, status: int,
                   body: dict) -> None:
    """Store the response snapshot atomically with the write (write-once).

    An expired row under the same key is removed first (records have no UPDATE
    grant; replacement is DELETE + INSERT inside this transaction).
    """
    connection.execute(
        delete(IdempotencyRecord)
        .where(IdempotencyRecord.owner_id == owner_id,
               IdempotencyRecord.route_key == route_key,
               IdempotencyRecord.idempotency_key == idempotency_key,
               IdempotencyRecord.expires_at <= func.now()))
    connection.execute(
        insert(IdempotencyRecord).values(
            owner_id=owner_id, route_key=route_key,
            idempotency_key=idempotency_key, request_hash=request_hash,
            response_status=status, response_body=body,
            expires_at=func.now() + RETENTION))
