"""Centralized request-scoped ownership enforcement for private data (NI-019).

Two independent layers protect every private row:

1. This module and the repositories built on it derive each owner predicate
   from the verified ``Principal`` (JWT ``sub`` only — never a request field),
   validate nested private references compositionally (a child row is
   reachable only through its owned parent in the same query) and scope the
   owner filter into the same statement that paginates, so totals and pages
   can never include another user's rows.
2. PostgreSQL RLS with transaction-local identity (``user_transaction``)
   independently rejects any row the predicates missed; the runtime role is
   not the owner, has no BYPASSRLS and pools reset identity between
   transactions.

Absent and not-owned resources are intentionally indistinguishable: both
raise :class:`ResourceNotFound`, which routes map to one generic 404
(API_SPECIFICATION ownership rule). No code path may catch it to reveal
existence.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, Engine, Select, func, select
from sqlalchemy.sql.elements import ColumnElement

from near_api.auth.principal import Principal
from near_api.db.session import user_transaction

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100

OwnerPredicate = ColumnElement[bool]


class ResourceNotFound(LookupError):
    """A resource does not exist or is not owned by the principal (one 404)."""


class OwnershipViolation(ValueError):
    """A request payload tried to influence ownership; rejected, never trusted."""


def verified_owner_id(payload_owner_id: UUID | None, principal_id: UUID) -> UUID:
    """Return the verified owner, rejecting payload-supplied ownership.

    Request fields named ``owner_id``/``user_id`` are never authorization.
    ``None`` means the field was absent; any other value must equal the
    principal's verified id or the request is rejected outright.
    """
    if payload_owner_id is not None and payload_owner_id != principal_id:
        raise OwnershipViolation(
            "Owner identity must come from the verified session, not from the request")
    return principal_id


def owner_scope(owner_column: ColumnElement[UUID], principal_id: UUID) -> OwnerPredicate:
    """The single allowed owner predicate: equality with the verified id."""
    return owner_column == principal_id


def one_or_not_found(row: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Raise the standardized 404-equivalent for a missing or not-owned row."""
    if row is None:
        raise ResourceNotFound("Resource does not exist for this owner")
    return row


@dataclass(frozen=True)
class Page:
    """A pagination result whose query and count were both owner-scoped."""

    items: tuple[Mapping[str, Any], ...]
    total: int
    limit: int
    offset: int


def bounded_page_args(limit: int | None, offset: int | None, *,
                      max_limit: int = MAX_PAGE_LIMIT) -> tuple[int, int]:
    """Validate pagination bounds; callers map ValueError to 422.

    The cap prevents resource exhaustion; it is applied together with the
    owner predicate so oversized requests cannot widen any result set.
    """
    effective_limit = DEFAULT_PAGE_LIMIT if limit is None else limit
    effective_offset = 0 if offset is None else offset
    if isinstance(effective_limit, bool) or not isinstance(effective_limit, int):
        raise ValueError("limit must be an integer")
    if isinstance(effective_offset, bool) or not isinstance(effective_offset, int):
        raise ValueError("offset must be an integer")
    if not 1 <= effective_limit <= max_limit:
        raise ValueError(f"limit must be between 1 and {max_limit}")
    if effective_offset < 0:
        raise ValueError("offset must not be negative")
    return effective_limit, effective_offset


def scoped_page(connection: Connection, query: Select, owner_predicate: OwnerPredicate, *,
                limit: int | None, offset: int | None,
                max_limit: int = MAX_PAGE_LIMIT) -> Page:
    """Page ``query`` with the owner predicate applied BEFORE pagination.

    The owner predicate is a required argument: it is impossible to call this
    helper without one. Owner filtering and any search filter live in the same
    WHERE as LIMIT/OFFSET, and the returned total counts only rows visible to
    the same owner scope — private list/search is scoped before pagination by
    construction, not by caller discipline.
    """
    page_limit, page_offset = bounded_page_args(limit, offset, max_limit=max_limit)
    scoped = query.where(owner_predicate)
    count_query = select(func.count()).select_from(scoped.order_by(None).subquery())
    total = connection.execute(count_query).scalar_one()
    rows = connection.execute(scoped.limit(page_limit).offset(page_offset)).mappings().all()
    return Page(items=tuple(rows), total=total, limit=page_limit, offset=page_offset)


def principal_transaction(engine: Engine, principal: Principal):
    """Open a transaction-local identity context for the verified principal.

    The standard entry point for private repository work: ``principal.id`` is
    the JWT-verified subject, set as ``app.user_id`` for this transaction only
    and cleared when the pooled connection returns.
    """
    return user_transaction(engine, principal.id)
