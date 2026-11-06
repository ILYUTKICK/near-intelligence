"""Bounded JWKS cache for the single configured provider URL (NI-018).

Keys come exclusively from the https JWKS URL in AuthSettings. JWT-supplied
``jku``/``x5u`` headers are never read and never fetched. The cache is bounded
in time (TTL) and size (maximum number of advertised keys); an unknown ``kid``
triggers exactly one forced refresh, after which verification fails closed.
"""

import threading
import time
from dataclasses import dataclass
from typing import Callable
from typing import Final

import httpx
import jwt


class JWKSUnavailable(Exception):
    """The trusted JWKS could not be fetched or contains no usable bound set."""


class UnknownKeyID(Exception):
    """The token key id is absent even after the single forced refresh."""


DEFAULT_TTL_SECONDS: Final = 600.0
MAX_JWKS_KEYS: Final = 32
MAX_JWKS_BYTES: Final = 1024 * 1024
FETCH_TIMEOUT_SECONDS: Final = 5.0
_ALLOWED_KEY_TYPES: Final = frozenset({"EC", "RSA", "OKP"})

Fetcher = Callable[[str], dict]


def _http_fetcher(url: str) -> dict:
    """Default fetcher: one bounded GET of the configured https URL."""
    response = httpx.get(url, timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=False)
    response.raise_for_status()
    if len(response.content) > MAX_JWKS_BYTES:
        raise JWKSUnavailable("JWKS document exceeds the size bound")
    document = response.json()
    if not isinstance(document, dict):
        raise JWKSUnavailable("JWKS document is not an object")
    return document


@dataclass(frozen=True)
class _CachedKey:
    key: jwt.PyJWK
    fetched_at: float


class JWKSCache:
    """Expiring, size-bounded kid -> key map for one trusted URL."""

    def __init__(
        self,
        url: str,
        *,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        max_keys: int = MAX_JWKS_KEYS,
        fetcher: Fetcher | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not url.startswith("https://"):
            raise JWKSUnavailable("JWKS URL must be https")
        self._url = url
        self._ttl_seconds = ttl_seconds
        self._max_keys = max_keys
        self._fetcher: Fetcher = fetcher if fetcher is not None else _http_fetcher
        self._clock = clock
        self._entries: dict[str, _CachedKey] = {}
        self._lock = threading.Lock()

    @property
    def url(self) -> str:
        return self._url

    def get_key(self, kid: str) -> jwt.PyJWK:
        """Return the cached key, refreshing at most once on miss/expiry."""
        entry = self._entries.get(kid)
        if entry is not None and self._clock() - entry.fetched_at < self._ttl_seconds:
            return entry.key
        with self._lock:
            entry = self._entries.get(kid)
            if entry is not None and self._clock() - entry.fetched_at < self._ttl_seconds:
                return entry.key
            # Exactly one forced refresh per miss; no retry loop afterwards.
            self._refresh()
            entry = self._entries.get(kid)
            if entry is None:
                raise UnknownKeyID(f"Unknown signing key id after JWKS refresh: {kid!r}")
            return entry.key

    def _refresh(self) -> None:
        try:
            document = self._fetcher(self._url)
        except JWKSUnavailable:
            raise
        except Exception as error:
            raise JWKSUnavailable("JWKS fetch failed") from error
        if not isinstance(document, dict):
            raise JWKSUnavailable("JWKS document is not an object")
        entries = self._parse(document)
        self._entries = entries

    def _parse(self, document: dict) -> dict[str, _CachedKey]:
        """Validate the bound document; anything ambiguous fails closed."""
        keys = document.get("keys")
        if not isinstance(keys, list) or not keys:
            raise JWKSUnavailable("JWKS document has no keys")
        if len(keys) > self._max_keys:
            raise JWKSUnavailable("JWKS document exceeds the key-count bound")
        entries: dict[str, _CachedKey] = {}
        fetched_at = self._clock()
        for item in keys:
            if not isinstance(item, dict):
                raise JWKSUnavailable("JWKS key entry is not an object")
            kid = item.get("kid")
            if not isinstance(kid, str) or not kid or len(kid) > 128:
                raise JWKSUnavailable("JWKS key entry has no usable kid")
            if item.get("kty") not in _ALLOWED_KEY_TYPES:
                # Symmetric (oct) or unknown key types never become trust anchors.
                raise JWKSUnavailable(f"JWKS key entry has an unsupported key type: {kid!r}")
            if item.get("use") not in (None, "sig"):
                raise JWKSUnavailable(f"JWKS key entry is not a signing key: {kid!r}")
            if kid in entries:
                raise JWKSUnavailable(f"JWKS document repeats a kid: {kid!r}")
            try:
                key = jwt.PyJWK(item)
            except jwt.PyJWKError as error:
                raise JWKSUnavailable(f"JWKS key entry is unusable: {kid!r}") from error
            entries[kid] = _CachedKey(key=key, fetched_at=fetched_at)
        return entries
