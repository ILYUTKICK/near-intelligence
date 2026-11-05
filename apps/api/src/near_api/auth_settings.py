"""Authentication configuration for the API (NI-016).

Separate from the base Settings on purpose: /health must stay independent of
auth provisioning, and JWT verification actually consumes these values only
from NI-018. Values come from the same root .env as the web app; placeholders
from .env.example fail with a readable error. Per
docs/AUTHENTICATION_SECURITY.md only asymmetric algorithms are accepted.
"""

from functools import lru_cache

from pydantic import AnyHttpUrl, Field, TypeAdapter, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from near_api.settings import SettingsError, find_repo_root


class AuthSettingsError(SettingsError):
    """Raised when authentication configuration is missing or invalid."""


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        frozen=True,
    )

    SUPABASE_JWT_ISSUER: str = Field(min_length=1)
    SUPABASE_JWKS_URL: str = Field(min_length=1)
    SUPABASE_JWT_AUDIENCE: str = Field(min_length=1)
    SUPABASE_JWT_ALGORITHM: str = Field(min_length=1)
    # Comma/space-separated list as a plain string: pydantic-settings would
    # JSON-decode a list field from env before any validator could run.
    AUTH_ALLOWED_REDIRECT_ORIGINS: str = Field(min_length=1)
    AUTH_COOKIE_SIGNING_SECRET: str = Field(min_length=32)
    CSRF_SIGNING_SECRET: str = Field(min_length=32)

    @field_validator("SUPABASE_JWKS_URL")
    @classmethod
    def _jwks_must_be_https(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("SUPABASE_JWKS_URL must be https.")
        return value

    @field_validator("SUPABASE_JWT_ALGORITHM")
    @classmethod
    def _algorithm_must_be_asymmetric(cls, value: str) -> str:
        if value not in ("ES256", "RS256", "EdDSA"):
            raise ValueError(
                "SUPABASE_JWT_ALGORITHM must be an asymmetric algorithm (ES256, RS256 "
                "or EdDSA). HS256/shared secrets are rejected by the security specification."
            )
        return value

    @field_validator(
        "SUPABASE_JWT_ISSUER",
        "SUPABASE_JWKS_URL",
        "SUPABASE_JWT_AUDIENCE",
        "AUTH_COOKIE_SIGNING_SECRET",
        "CSRF_SIGNING_SECRET",
    )
    @classmethod
    def _reject_placeholders(cls, value: str, info) -> str:
        stripped = value.strip()
        if not stripped or "REPLACE" in stripped.upper():
            raise ValueError(
                f"{info.field_name} still has its placeholder value; set the real "
                "development value in the root .env (docs/AUTHENTICATION_SECURITY.md)."
            )
        return stripped

    @model_validator(mode="after")
    def _validate_redirect_origins(self) -> "AuthSettings":
        origins = [
            origin
            for origin in self.AUTH_ALLOWED_REDIRECT_ORIGINS.replace(",", " ").split()
            if origin
        ]
        if not origins:
            raise ValueError("AUTH_ALLOWED_REDIRECT_ORIGINS is empty.")
        TypeAdapter(list[AnyHttpUrl]).validate_python(origins)
        return self

    @property
    def allowed_redirect_origins(self) -> list[str]:
        """Parsed allowlist from AUTH_ALLOWED_REDIRECT_ORIGINS."""
        return [
            origin
            for origin in self.AUTH_ALLOWED_REDIRECT_ORIGINS.replace(",", " ").split()
            if origin
        ]


@lru_cache(maxsize=1)
def get_auth_settings() -> AuthSettings:
    """Return validated auth settings, failing with a readable message."""
    try:
        return AuthSettings(_env_file=find_repo_root() / ".env")
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in item['loc']) or '(unknown)'}: {item['msg']}"
            for item in error.errors()
        )
        raise AuthSettingsError(
            f"Invalid authentication configuration. Problems: {problems}"
        ) from error
