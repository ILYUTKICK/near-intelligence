"""Canonical serialization, parsing and digests for dataset manifests (NI-028).

The content hash of a dataset version is SHA-256 over one canonical JSON
document, so that *semantically identical* input always produces the same
digest regardless of key order, whitespace, timestamp offset spelling or
decimal spelling (``123.450`` and ``1.2345e2`` hash like ``123.45``). The same
canonicalization runs at stage time (from the operator manifest) and at
validation/publication time (re-derived from the persisted rows), which makes
the stored ``content_sha256`` a verifiable integrity claim, not just a label.

Rules (deterministic, field by field):

- JSON objects: keys sorted, separators ``,``/``:``; duplicate keys are a
  contract error (PostgreSQL ``jsonb`` would silently keep the last one).
- Decimal values: parsed exactly (never float), re-emitted via
  :func:`decimal_string` (normalized, no exponent, ``-0`` collapsed to ``0``).
- Timestamps: strict bounded ISO-8601, normalized to UTC microsecond precision
  and emitted as ``YYYY-MM-DDTHH:MM:SS.ffffffZ``.
- Floats are rejected everywhere: inexact values cannot enter a hash claimed
  as reproducible.  Dates are ``YYYY-MM-DD``.  UUIDs are lowercase hyphenated.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from near_api.db.numeric import exact_numeric

TIMESTAMP_PATTERN = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:?\d{2})$"
)
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

UTC = dt.timezone.utc


class CanonicalFormatError(ValueError):
    """A value cannot be represented in the canonical form (contract error)."""


def _reject_constant(value: str) -> Any:
    raise CanonicalFormatError(f"JSON constant {value!r} is not allowed in canonical input")


def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CanonicalFormatError(f"Duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_json_strict(data: bytes, *, context: str) -> Any:
    """Parse JSON bytes exactly: decimals stay Decimal, floats/constants rejected."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise CanonicalFormatError(f"{context}: input must be UTF-8 JSON") from None
    try:
        return json.loads(text, parse_float=Decimal, parse_constant=_reject_constant,
                          object_pairs_hook=_pairs_without_duplicates)
    except CanonicalFormatError as error:
        raise CanonicalFormatError(f"{context}: {error}") from None
    except json.JSONDecodeError as error:
        raise CanonicalFormatError(f"{context}: invalid JSON at offset {error.pos}") from None


def parse_decimal(value: Any, *, context: str, scale: int = 30) -> Decimal:
    """Parse an exact decimal from a JSON string (floats are a contract error)."""
    if isinstance(value, Decimal):
        amount = value
    elif isinstance(value, str):
        try:
            amount = Decimal(value)
        except InvalidOperation:
            raise CanonicalFormatError(f"{context}: {value!r} is not a decimal string") from None
    else:
        raise CanonicalFormatError(f"{context}: decimals must be JSON strings, never numbers")
    try:
        return exact_numeric(amount, scale=scale)
    except ValueError as error:
        raise CanonicalFormatError(f"{context}: {error}") from None


def decimal_string(value: Decimal) -> str:
    """Deterministic decimal rendering: normalized, plain notation, no ``-0``."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise CanonicalFormatError("Only finite Decimal values are canonical")
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def parse_timestamp(value: Any, *, context: str) -> dt.datetime:
    """Parse a bounded ISO-8601 UTC timestamp with microsecond precision."""
    if not isinstance(value, str):
        raise CanonicalFormatError(f"{context}: timestamps must be strings")
    match = TIMESTAMP_PATTERN.match(value)
    if match is None:
        raise CanonicalFormatError(f"{context}: {value!r} is not an ISO-8601 timestamp")
    year, month, day, hour, minute, second, fraction, offset = match.groups()
    micro = int((fraction or "").ljust(6, "0")) if fraction else 0
    zone = UTC
    if offset != "Z":
        sign = 1 if offset[0] == "+" else -1
        digits = offset[1:].replace(":", "")
        delta = dt.timedelta(hours=int(digits[:2]), minutes=int(digits[2:4]))
        if not dt.timedelta(0) <= sign * delta < dt.timedelta(hours=24):
            raise CanonicalFormatError(f"{context}: {value!r} has an invalid UTC offset")
        zone = dt.timezone(sign * delta)
    try:
        parsed = dt.datetime(int(year), int(month), int(day), int(hour), int(minute),
                             int(second), micro, tzinfo=zone).astimezone(UTC)
    except ValueError as error:
        raise CanonicalFormatError(f"{context}: {value!r} is not a real instant ({error})") from None
    return parsed


def canonical_timestamp(value: dt.datetime) -> str:
    """Deterministic UTC rendering ``YYYY-MM-DDTHH:MM:SS.ffffffZ``."""
    if value.tzinfo is None:
        raise CanonicalFormatError("Naive datetimes cannot be canonicalized")
    value = value.astimezone(UTC)
    return (f"{value.year:04d}-{value.month:02d}-{value.day:02d}"
            f"T{value.hour:02d}:{value.minute:02d}:{value.second:02d}.{value.microsecond:06d}Z")


def parse_date(value: Any, *, context: str) -> dt.date:
    if not isinstance(value, str) or not DATE_PATTERN.match(value):
        raise CanonicalFormatError(f"{context}: dates must be YYYY-MM-DD strings")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as error:
        raise CanonicalFormatError(f"{context}: {value!r} is not a real date ({error})") from None


def canonical_value(value: Any, *, context: str) -> Any:
    """Recursively map a parsed JSON tree onto its canonical representation."""
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, Decimal):
        return decimal_string(value)
    if isinstance(value, dt.datetime):
        return canonical_timestamp(value)
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, float):
        raise CanonicalFormatError(f"{context}: floats are not allowed in canonical data")
    if isinstance(value, dict):
        return {str(key): canonical_value(item, context=context)
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [canonical_value(item, context=context) for item in value]
    raise CanonicalFormatError(f"{context}: value of type {type(value).__name__} is not canonical")


def dump_canonical(document: Any) -> bytes:
    """Serialize a parsed structure to deterministic canonical JSON bytes."""
    canonical = canonical_value(document, context="manifest")
    return json.dumps(canonical, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
