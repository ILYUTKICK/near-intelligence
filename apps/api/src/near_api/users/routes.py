"""Profile read/update API (NI-025).

Identity comes exclusively from the verified bearer (NI-018 principal);
request payloads can never influence the user id. Timezone changes are
display-only by contract — no system timezone is modified. Validation is
defence in depth: pydantic + zoneinfo here, RLS and CHECK constraints
(including app.is_valid_timezone) in the database.
"""

from dataclasses import dataclass
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.engine import Engine

from near_api.auth.principal import (
    Principal,
    get_principal,
    get_runtime_engine,
)

PrincipalDependency = Annotated[Principal, Depends(get_principal)]
RuntimeEngineDependency = Annotated[Engine, Depends(get_runtime_engine)]
from near_api.db.security import principal_transaction

router = APIRouter(prefix="/api/me", tags=["me"])

_NAME_MAX = 80  # mirrors display_name varchar(80)
_TZ_MAX = 64  # mirrors display_timezone varchar(64)


class ProfileResponse(BaseModel):
    subject: str
    display_name: str
    display_timezone: str


class ProfileUpdateRequest(BaseModel):
    display_name: Annotated[str, Field(min_length=1, max_length=_NAME_MAX)]
    display_timezone: Annotated[str, Field(min_length=1, max_length=_TZ_MAX)]

    @field_validator("display_name")
    @classmethod
    def _readable_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("display_name must not be empty")
        if any(ord(char) < 32 for char in stripped):
            raise ValueError("display_name must not contain control characters")
        return stripped

    @field_validator("display_timezone")
    @classmethod
    def _iana_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except Exception as error:  # noqa: BLE001 - mapped to a readable 422
            raise ValueError("display_timezone must be a valid IANA timezone") from error
        return value


@router.get("", response_model=ProfileResponse, operation_id="getMe",
            summary="The verified principal's own profile")
def read_me(principal: PrincipalDependency) -> ProfileResponse:
    return ProfileResponse(
        subject=str(principal.id),
        display_name=principal.display_name,
        display_timezone=principal.display_timezone,
    )


@router.patch("", response_model=ProfileResponse, operation_id="updateMe",
              summary="Update the verified principal's own display name/timezone")
def update_me(
    update: ProfileUpdateRequest,
    principal: PrincipalDependency,
    engine: RuntimeEngineDependency,
) -> ProfileResponse:
    """Update the verified subject's own profile row via the near_app role.

    The profile_self UPDATE policy only ever matches the transaction-local
    subject, so a foreign or disabled profile is unreachable; an empty update
    result is a fail-closed bootstrap error, never a cross-owner write.
    """
    with principal_transaction(engine, principal) as connection:
        updated = connection.execute(
            text(
                "UPDATE app.user_profiles "
                "SET display_name = :display_name, display_timezone = :display_timezone "
                "WHERE user_id = :subject "
                "RETURNING display_name, display_timezone"
            ),
            {
                "display_name": update.display_name,
                "display_timezone": update.display_timezone,
                "subject": principal.id,
            },
        ).mappings().first()
        if updated is None:
            raise HTTPException(
                status_code=500,
                detail="Verified profile row was not writable; request rejected.",
            )
        return ProfileResponse(
            subject=str(principal.id),
            display_name=updated["display_name"],
            display_timezone=updated["display_timezone"],
        )


__all__ = ["ProfileResponse", "ProfileUpdateRequest", "router"]
