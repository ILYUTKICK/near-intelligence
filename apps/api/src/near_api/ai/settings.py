"""Server-only configuration of the optional grounded-commentary adapter (NI-065).

The adapter is OFF by default and is enabled only by explicit operator
configuration in the root .env:

- ``NEAR_AI_COMMENTARY_ENABLED`` (``false`` by default),
- ``NEAR_AI_COMMENTARY_ENDPOINT`` — one clean public HTTPS URL (no query,
  fragment or embedded credentials),
- ``NEAR_AI_COMMENTARY_MODEL`` — the model identifier sent verbatim,
- ``NEAR_AI_COMMENTARY_API_KEY`` — sent only as the server-side Authorization
  bearer; it is never returned to a client, never logged and never embedded
  in an error body.

While disabled the API key is never read into the served configuration at
all: the returned :class:`AICommentaryConfig` carries ``None`` for every
provider field, so a disabled deployment cannot even hold the secret in
memory. Enabling without a complete, clean configuration is a readable
:class:`near_api.settings.SettingsError` — the endpoint then reports the
typed ``adapter_misconfigured`` state instead of improvising.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from near_api.settings import SettingsError, find_repo_root


class AICommentarySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", frozen=True)

    NEAR_AI_COMMENTARY_ENABLED: bool = False
    NEAR_AI_COMMENTARY_ENDPOINT: str | None = None
    NEAR_AI_COMMENTARY_MODEL: str | None = None
    NEAR_AI_COMMENTARY_API_KEY: str | None = None


@dataclass(frozen=True)
class AICommentaryConfig:
    """The served adapter configuration; provider fields stay None while off.

    The credential field is the server-side bearer token (the
    ``NEAR_AI_COMMENTARY_API_KEY`` env value): it travels only in the
    outbound Authorization header and never enters a response, log or error
    body.
    """

    enabled: bool
    endpoint: str | None = None
    model: str | None = None
    bearer_token: str | None = None


def _format_validation_error(error: ValidationError) -> str:
    problems = "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or '(unknown)'}: {item['msg']}"
        for item in error.errors())
    return (
        "Invalid commentary adapter configuration. Set NEAR_AI_COMMENTARY_* "
        f"variables in the root .env or leave the adapter disabled. Problems: {problems}")


@lru_cache(maxsize=1)
def get_ai_commentary() -> AICommentaryConfig:
    """Return the validated adapter configuration, failing readable."""
    try:
        raw = AICommentarySettings(_env_file=find_repo_root() / ".env")
    except ValidationError as error:
        raise SettingsError(_format_validation_error(error)) from error
    if not raw.NEAR_AI_COMMENTARY_ENABLED:
        # Disabled: the key is never read into the served config.
        return AICommentaryConfig(enabled=False)
    problems: list[str] = []
    endpoint = raw.NEAR_AI_COMMENTARY_ENDPOINT
    parts = urlsplit(endpoint or "")
    if not endpoint or parts.scheme != "https" or not parts.hostname \
            or parts.username or parts.password or parts.query or parts.fragment:
        problems.append("NEAR_AI_COMMENTARY_ENDPOINT: must be a clean public HTTPS URL")
    model = raw.NEAR_AI_COMMENTARY_MODEL
    if not model or not model.strip() or len(model) > 80:
        problems.append("NEAR_AI_COMMENTARY_MODEL: must be 1-80 characters")
    api_key = raw.NEAR_AI_COMMENTARY_API_KEY
    if not api_key or len(api_key) > 4096:
        problems.append("NEAR_AI_COMMENTARY_API_KEY: must be 1-4096 characters")
    if problems:
        raise SettingsError(
            "Invalid commentary adapter configuration. " + "; ".join(problems))
    return AICommentaryConfig(enabled=True, endpoint=endpoint, model=model,
                              bearer_token=api_key)
