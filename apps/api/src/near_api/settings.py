"""Explicit server configuration for the API runtime (NI-002 skeleton).

Values come from the root .env created by the documented
`cp .env.example .env` onboarding step. Loading is explicit and lazy: the
repository root is located by walking up from the working directory to the
pnpm-workspace.yaml anchor, then pydantic-settings reads that file. Variables
already present in the process environment always win over the .env file.
Client-visible NEXT_PUBLIC_* variables are a web concern and never read here.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyUrl, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

_WORKSPACE_ANCHOR = "pnpm-workspace.yaml"


class SettingsError(RuntimeError):
    """Raised when required server configuration is missing or invalid."""


def find_repo_root() -> Path:
    """Locate the repository root from the pnpm-workspace.yaml anchor."""
    directory = Path.cwd().resolve()
    for _ in range(10):
        if (directory / _WORKSPACE_ANCHOR).is_file():
            return directory
        parent = directory.parent
        if parent == directory:
            return Path.cwd().resolve()
        directory = parent
    return Path.cwd().resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        frozen=True,
    )

    APP_ENV: Literal["development", "test", "production"]
    APP_ORIGIN: AnyUrl
    API_INTERNAL_URL: AnyUrl


def _format_validation_error(error: ValidationError) -> str:
    problems = "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or '(unknown)'}: {item['msg']}"
        for item in error.errors()
    )
    return (
        "Invalid API server configuration. Copy .env.example to .env at the "
        f"repository root and set the required variables. Problems: {problems}"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return validated settings, failing with a readable message."""
    try:
        return Settings(_env_file=find_repo_root() / ".env")
    except ValidationError as error:
        raise SettingsError(_format_validation_error(error)) from error
