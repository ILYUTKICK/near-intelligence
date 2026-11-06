"""Strict bearer-JWT verification against the configured provider (NI-018).

Only the exact asymmetric algorithm configured for the project is accepted;
``alg=none`` and shared-secret algorithms fail closed before any key lookup.
Issuer and audience must match AuthSettings exactly, expiry/not-before are
verified with no leeway, and the subject must be a canonical UUID v4 string.
JWT-supplied ``jku``/``x5u`` headers are deliberately ignored: keys come only
from the configured JWKS URL (see near_api.auth.jwks).
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import jwt

from near_api.auth.jwks import JWKSCache, JWKSUnavailable, UnknownKeyID
from near_api.auth_settings import AuthSettings

_ALLOWED_ALGORITHMS: Final = ("ES256", "RS256", "EdDSA")
# Canonical lowercase 8-4-4-4-12 form, version 4, RFC 4122 variant.
_SUBJECT_PATTERN: Final = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_KID_PATTERN: Final = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class TokenInvalid(Exception):
    """The bearer token failed verification; the request is not authenticated."""


@dataclass(frozen=True)
class VerifiedToken:
    """Claims that passed full verification; trusted backend context only."""

    subject: UUID
    expires_at: datetime
    issued_at: datetime | None


class TokenVerifier:
    """Verify bearer tokens with the configured issuer, audience and algorithm."""

    def __init__(self, settings: AuthSettings, cache: JWKSCache) -> None:
        self._issuer = settings.SUPABASE_JWT_ISSUER
        self._audience = settings.SUPABASE_JWT_AUDIENCE
        self._algorithm = settings.SUPABASE_JWT_ALGORITHM
        if self._algorithm not in _ALLOWED_ALGORITHMS:
            raise TokenInvalid("Configured JWT algorithm is not an allowed asymmetric algorithm")
        self._cache = cache

    def verify(self, token: str) -> VerifiedToken:
        header = self._header(token)
        algorithm = header.get("alg")
        if algorithm != self._algorithm:
            # Rejects alg=none, HS* and any cross-algorithm confusion up front,
            # before a key is selected from the JWKS cache.
            raise TokenInvalid("Token algorithm does not match the configured asymmetric algorithm")
        kid = header.get("kid")
        if not isinstance(kid, str) or not _KID_PATTERN.fullmatch(kid):
            raise TokenInvalid("Token key id header is missing or malformed")
        try:
            key = self._cache.get_key(kid)
        except JWKSUnavailable as error:
            raise TokenInvalid("Signing keys are unavailable") from error
        except UnknownKeyID as error:
            raise TokenInvalid("Signing key is unknown") from error
        try:
            claims = jwt.decode(
                token,
                key=key.key,
                algorithms=[self._algorithm],
                issuer=self._issuer,
                audience=self._audience,
                leeway=0,
                options={
                    "require": ["exp", "sub"],
                    "strict_aud": True,
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )
        except jwt.InvalidTokenError as error:
            raise TokenInvalid("Token claims failed verification") from error
        return self._subject_claims(claims)

    def _header(self, token: str) -> dict:
        if not isinstance(token, str) or not token:
            raise TokenInvalid("Bearer token is missing")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as error:
            raise TokenInvalid("Token is not a well-formed JWT") from error
        if not isinstance(header, dict):
            raise TokenInvalid("Token header is not an object")
        return header

    def _subject_claims(self, claims: dict) -> VerifiedToken:
        subject = claims.get("sub")
        if not isinstance(subject, str) or not _SUBJECT_PATTERN.fullmatch(subject):
            raise TokenInvalid("Token subject is not a canonical UUID v4")
        expires_at = self._timestamp(claims.get("exp"), "exp")
        issued_at_value = claims.get("iat")
        issued_at = None if issued_at_value is None else self._timestamp(issued_at_value, "iat")
        return VerifiedToken(subject=UUID(subject), expires_at=expires_at, issued_at=issued_at)

    def _timestamp(self, value: object, name: str) -> datetime:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TokenInvalid(f"Token {name} claim is not a numeric timestamp")
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (OverflowError, OSError, ValueError) as error:
            raise TokenInvalid(f"Token {name} claim is out of range") from error
