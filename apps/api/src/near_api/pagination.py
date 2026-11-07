"""Shared bounded page-cursor handling for public catalog lists (NI-032).

API_SPECIFICATION: lists are ``{items,next_cursor}`` with an opaque bounded
cursor, default limit 20 and max limit 100. The cursor is a base64url
non-negative offset over a stable catalog order; it carries no filter state,
so a cursor issued for one query can never widen another, and an oversized or
malformed cursor is a plain validation failure.
"""

import base64
import binascii

from fastapi import Depends, HTTPException, Query
from typing import Annotated

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100
_MAX_CURSOR_OFFSET = 10**9


def encode_page_cursor(offset: int) -> str:
    """Encode the next page offset as an opaque bounded cursor."""
    return base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii")


def decode_page_cursor(cursor: str | None) -> int:
    """Decode an opaque page cursor; any malformed value is a validation error."""
    if cursor is None:
        return 0
    try:
        value = int(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii"))
    except (ValueError, UnicodeError, binascii.Error):
        raise HTTPException(422, "Request failed validation") from None
    if value < 0 or value > _MAX_CURSOR_OFFSET:
        raise HTTPException(422, "Request failed validation")
    return value


def public_page(cursor: Annotated[str | None, Query(max_length=64)] = None,
                limit: Annotated[int | None, Query(ge=1, le=MAX_PAGE_LIMIT)] = None,
                ) -> tuple[int, int]:
    """FastAPI dependency yielding ``(offset, limit)`` for a catalog page."""
    return decode_page_cursor(cursor), DEFAULT_PAGE_LIMIT if limit is None else limit


PublicPage = Annotated[tuple[int, int], Depends(public_page)]
