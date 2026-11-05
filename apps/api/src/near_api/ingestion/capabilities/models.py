"""Evidence records describe access separately from collection and publication."""

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceCapability(EvidenceModel):
    schema_version: Literal[1] = 1
    source_id: str = Field(pattern=r"^SRC-[A-Z]+(?:-[A-Z]+)*$")
    documentation_url: str
    endpoint: str | None = None
    method: Literal["GET", "POST"] | None = None
    auth: Literal["none", "bearer", "api_key", "cloud_identity", "unverified"]
    access_verified: bool = False
    quota_evidence_url: str | None = None
    documented_requests_per_day: int | None = Field(default=None, gt=0)
    rights: Literal["pending", "approved", "prohibited"] = "pending"
    rights_evidence_url: str | None = None
    raw_redistribution: Literal["pending", "approved", "prohibited"] = "pending"
    history_start: datetime | None = None
    history_end: datetime | None = None
    response_schema_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    lineage: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    @field_validator("documentation_url", "endpoint", "quota_evidence_url", "rights_evidence_url")
    @classmethod
    def public_https_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parts = urlsplit(value)
        if (parts.scheme != "https" or not parts.hostname or parts.username
                or parts.password or parts.query or parts.fragment):
            raise ValueError("Use an HTTPS URL without credentials, query or fragment")
        return value

    @field_validator("history_start", "history_end")
    @classmethod
    def aware_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Coverage timestamps require an explicit timezone")
        return value

    @model_validator(mode="after")
    def validate_evidence(self) -> "SourceCapability":
        if self.rights == "approved" and self.rights_evidence_url is None:
            raise ValueError("Approved usage requires rights evidence")
        if self.raw_redistribution == "approved" and self.rights != "approved":
            raise ValueError("Raw redistribution requires approved usage rights")
        if self.documented_requests_per_day is not None and not self.quota_evidence_url:
            raise ValueError("A numerical quota requires evidence")
        if (self.history_start is None) != (self.history_end is None):
            raise ValueError("Coverage requires both boundaries")
        if self.history_start and self.history_end and self.history_start >= self.history_end:
            raise ValueError("Coverage uses a non-empty half-open interval")
        return self


class ProbeApproval(EvidenceModel):
    """Explicit one-off operator approval. This does not enable a scheduler."""

    source_id: str
    endpoint: str
    approved_by: str = Field(min_length=1)
    approval_reference: str = Field(min_length=1)
    expires_at: datetime
    max_requests: int = Field(gt=0, le=3)
    max_response_bytes: int = Field(gt=0, le=1_048_576)
    timeout_seconds: float = Field(gt=0, le=15, allow_inf_nan=False)
    zero_cost_confirmed: Literal[True]

    @field_validator("expires_at")
    @classmethod
    def aware_expiry(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Approval expiry requires an explicit timezone")
        return value
