"""NI-004 common contracts. These models contain no provider data or results."""

import re
from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

type DecimalString = Annotated[str, StringConstraints(
    strict=True, pattern=r"^-?(?:0|[1-9][0-9]{0,77})(?:\.[0-9]{1,30})?$", max_length=110,
)]
type RawAmountString = Annotated[str, StringConstraints(
    strict=True, pattern=r"^(?:0|[1-9][0-9]{0,77})$", max_length=78,
)]
type Reason = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ErrorDetail(ContractModel):
    path: str = Field(min_length=1, max_length=200)
    reason: Reason


class ApiError(ContractModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")
    message: str = Field(min_length=1, max_length=1024)
    request_id: UUID
    details: tuple[ErrorDetail, ...] | None = Field(default=None, max_length=20)
    retryable: bool


class ErrorResponse(ContractModel):
    error: ApiError


class SelectionFilters(ContractModel):
    """No filter is approved at bootstrap; NI-031 adds versioned filter rules."""


class Selection(ContractModel):
    start: date
    end: date
    frequency: Literal["day"]
    filters: SelectionFilters

    @field_validator("start", "end", mode="before")
    @classmethod
    def iso_date_only(cls, value):
        if isinstance(value, datetime) or not isinstance(value, (date, str)):
            raise ValueError("Use an ISO calendar date")
        if isinstance(value, str) and not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("Use YYYY-MM-DD")
        return value

    @model_validator(mode="after")
    def half_open_window(self):
        if not 0 < (self.end - self.start).days <= 366:
            raise ValueError("Selection requires a non-empty half-open window of at most 366 days")
        return self


class Coverage(ContractModel):
    observed: int = Field(strict=True, ge=0)
    expected: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def no_overcount(self):
        if self.observed > self.expected:
            raise ValueError("Observed coverage cannot exceed expected coverage")
        return self


class DataQuality(ContractModel):
    status: Literal["ok", "partial", "missing", "stale", "unavailable", "revised"]
    bound_kind: Literal["exact", "estimate", "lower", "upper"] | None
    reasons: tuple[Reason, ...] = Field(max_length=20)
    coverage: Coverage
    freshness_target_seconds: int | None = Field(strict=True, gt=0)

    @model_validator(mode="after")
    def explain_absence(self):
        if self.status in {"missing", "unavailable"} and not self.reasons:
            raise ValueError("Missing/unavailable data requires a reason")
        return self


class Observation(ContractModel):
    start: AwareDatetime
    end: AwareDatetime
    value: DecimalString | None
    quality: DataQuality

    @field_validator("start", "end", mode="before")
    @classmethod
    def no_epoch_numbers(cls, value):
        if not isinstance(value, (str, datetime)):
            raise ValueError("Use a timestamp with an explicit timezone")
        return value

    @field_validator("start", "end")
    @classmethod
    def utc_timestamp(cls, value: datetime):
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def valid_interval_and_value(self):
        if self.end <= self.start:
            raise ValueError("Observation requires a non-empty half-open interval")
        absent = self.quality.status in {"missing", "unavailable"}
        if (self.value is None) != absent:
            raise ValueError("Null values require missing/unavailable quality, never zero substitution")
        if absent and self.quality.bound_kind is not None:
            raise ValueError("An absent value cannot claim an economic bound")
        return self


class HealthResponse(ContractModel):
    status: Literal["ok"]
    service: Literal["api"]
    app_env: Literal["development", "test", "production"] = Field(alias="appEnv")
    checked_at: AwareDatetime = Field(alias="checkedAt")


CONTRACT_MODELS = (ErrorResponse, Selection, DataQuality, Observation, HealthResponse)
