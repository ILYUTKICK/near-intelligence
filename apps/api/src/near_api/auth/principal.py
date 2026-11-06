"""Application principal bootstrap and the FastAPI auth dependency (NI-018).

The owner identity is derived exclusively from the JWT ``sub`` verified by
TokenVerifier; no request payload, query parameter or header can influence it.
The verified subject is upserted into app.users/app.user_profiles inside a
transaction-local near_app context (NI-003 roles), disabled local users are
rejected fail closed, and pooled connections never retain an identity after
the transaction ends.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Header, HTTPException
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import text
from sqlalchemy.engine import Engine

from near_api.auth.jwks import JWKSCache
from near_api.auth.verification import TokenInvalid, TokenVerifier, VerifiedToken
from near_api.auth_settings import get_auth_settings
from near_api.db.session import DatabaseConfigurationError, create_runtime_engine, user_transaction
from near_api.settings import find_repo_root


class UserDisabled(Exception):
    """The verified subject exists locally but has been disabled by the operator."""


class PrincipalConfigurationError(RuntimeError):
    """Runtime database configuration for authenticated routes is unusable."""


class PrincipalBootstrapError(RuntimeError):
    """The verified identity rows were unexpectedly invisible; fail closed."""


@dataclass(frozen=True)
class Principal:
    """Authenticated identity for private routes; never taken from the request."""

    id: UUID
    display_name: str
    display_timezone: str


def bootstrap_principal(engine: Engine, verified: VerifiedToken) -> Principal:
    """Upsert identity rows for the verified subject and return the principal.

    The INSERT policies only ever allow the transaction-local subject, so the
    verified UUID is both the write target and the only readable row. A
    disabled row stays readable (users_self_read) so the caller can reject it.
    """
    with user_transaction(engine, verified.subject) as connection:
        connection.execute(text("INSERT INTO app.users(id) VALUES (:id) ON CONFLICT DO NOTHING"),
                           {"id": verified.subject})
        user = connection.execute(text("SELECT disabled_at FROM app.users WHERE id = :id"),
                                  {"id": verified.subject}).mappings().first()
        if user is None:
            raise PrincipalBootstrapError("Verified user row is not visible to the runtime role")
        if user["disabled_at"] is not None:
            raise UserDisabled("The verified account is disabled")
        connection.execute(
            text("INSERT INTO app.user_profiles(user_id) VALUES (:id) ON CONFLICT DO NOTHING"),
            {"id": verified.subject})
        profile = connection.execute(
            text("SELECT display_name, display_timezone FROM app.user_profiles WHERE user_id = :id"),
            {"id": verified.subject}).mappings().first()
        if profile is None:
            raise PrincipalBootstrapError("Verified profile row is not visible to the runtime role")
    return Principal(id=verified.subject, display_name=profile["display_name"],
                     display_timezone=profile["display_timezone"])


class RuntimeDatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", frozen=True)

    DATABASE_URL: str = Field(min_length=1)


@lru_cache(maxsize=1)
def _get_engine() -> Engine:
    """Lazily build the near_app runtime engine; private routes only."""
    try:
        settings = RuntimeDatabaseSettings(_env_file=find_repo_root() / ".env")
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in item['loc']) or '(unknown)'}: {item['msg']}"
            for item in error.errors())
        raise PrincipalConfigurationError(
            "Authenticated routes need DATABASE_URL (the near_app runtime credential) in the "
            f"root .env. Problems: {problems}") from error
    try:
        return create_runtime_engine(settings.DATABASE_URL)
    except DatabaseConfigurationError as error:
        raise PrincipalConfigurationError(str(error)) from error


@lru_cache(maxsize=1)
def _get_verifier() -> TokenVerifier:
    settings = get_auth_settings()
    return TokenVerifier(settings, JWKSCache(settings.SUPABASE_JWKS_URL))


def get_principal(authorization: Annotated[str | None, Header()] = None) -> Principal:
    """FastAPI dependency for private routes: bearer JWT -> verified Principal."""
    if authorization is None:
        raise HTTPException(401, "Authentication is required")
    scheme, _, token = authorization.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Authentication is required")
    try:
        verified = _get_verifier().verify(token)
    except TokenInvalid as error:
        # Forged, expired, wrong provider, unknown kid or JWKS outage all fail
        # closed here with one generic response; no verification detail leaks.
        raise HTTPException(401, "Authentication is required") from error
    try:
        return bootstrap_principal(_get_engine(), verified)
    except UserDisabled as error:
        raise HTTPException(403, "Operation is not permitted") from error
