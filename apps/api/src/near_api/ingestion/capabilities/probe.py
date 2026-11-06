"""One finalized-header verification request, guarded before any network I/O.

This is an operator probe, not NI-030's scheduled ingestion adapter. It never
retries, rotates endpoints, fetches history or invokes a legacy collector.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Literal

import httpx
from pydantic import Field

from .models import EvidenceModel, ProbeApproval, SourceCapability


class ProbeDenied(RuntimeError):
    """The requested verification has no sufficient operational evidence."""


class ProbeFailed(RuntimeError):
    """A bounded request failed. Provider messages/headers are never exposed."""


class ProbeControls(EvidenceModel):
    enabled: bool = False
    source_allowlist: frozenset[str] = frozenset()
    requests_per_day: int = Field(default=0, ge=0)
    requests_used_today: int = Field(default=0, ge=0)
    stop_paths: tuple[Path, ...] = ()


class FinalizedHeader(EvidenceModel):
    """Sanitized selected fields only. Monetary values retain integer strings."""

    source_id: Literal["SRC-NEAR-RPC"] = "SRC-NEAR-RPC"
    finality: Literal["final"] = "final"
    height: int = Field(strict=True, ge=0)
    block_hash: str = Field(pattern=r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
    timestamp_nanosec: str = Field(pattern=r"^[0-9]+$")
    total_supply_yocto: str = Field(pattern=r"^[0-9]+$")
    retrieved_at: datetime
    response_bytes: int = Field(strict=True, ge=0)
    response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class HeaderProbe:
    """A single-use probe. Reuse cannot silently reset the invocation budget."""

    def __init__(self, source: SourceCapability, approval: ProbeApproval,
                 controls: ProbeControls, repo_root: Path):
        self.source = source
        self.approval = approval
        self.controls = controls
        self.repo_root = repo_root.resolve()
        self._used = False
        self._lock = Lock()

    def _authorize(self) -> None:
        source, approval, controls = self.source, self.approval, self.controls
        if self._used:
            raise ProbeDenied("Probe invocation already consumed")
        if not self.repo_root.is_dir():
            raise ProbeDenied("Repository root is unavailable")
        markers = (
            self.repo_root / "STOP_PUBLIC_COLLECTION",
            *self.repo_root.glob("research/**/STOP_PUBLIC_COLLECTION"),
            *controls.stop_paths,
        )
        if any(path.exists() for path in markers):
            raise ProbeDenied("Collection stop or pause marker is present")
        if not controls.enabled or source.source_id not in controls.source_allowlist:
            raise ProbeDenied("Probe disabled or source not allowlisted")
        if controls.requests_used_today >= controls.requests_per_day:
            raise ProbeDenied("Daily request budget exhausted")
        if (source.documented_requests_per_day is not None
                and controls.requests_per_day > source.documented_requests_per_day):
            raise ProbeDenied("Local cap exceeds the documented provider quota")
        if source.blockers or not source.access_verified:
            raise ProbeDenied("Source access or open questions remain unresolved")
        if source.rights != "approved" or not source.quota_evidence_url:
            raise ProbeDenied("Source rights or quota evidence is missing")
        if approval.expires_at <= datetime.now(UTC):
            raise ProbeDenied("Probe approval expired")
        if source.source_id != approval.source_id or source.endpoint != approval.endpoint:
            raise ProbeDenied("Approval does not match the exact source endpoint")
        if (source.source_id != "SRC-NEAR-RPC" or source.auth != "none"
                or source.endpoint != "https://rpc.mainnet.near.org" or source.method != "POST"):
            raise ProbeDenied("Only the operator-approved finalized-header endpoint is implemented")

    def run(self, *, transport: httpx.BaseTransport | None = None) -> FinalizedHeader:
        with self._lock:
            self._authorize()
            self._used = True
        request = {"jsonrpc": "2.0", "id": "ni-026", "method": "block",
                   "params": {"finality": "final"}}
        try:
            with httpx.Client(transport=transport, timeout=self.approval.timeout_seconds,
                              follow_redirects=False, trust_env=False) as client:
                with client.stream("POST", self.source.endpoint, json=request,
                                   headers={"Accept-Encoding": "identity"}) as response:
                    if response.status_code != 200:
                        raise ProbeFailed(f"Probe HTTP status {response.status_code}; no retry")
                    if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                        raise ProbeFailed("Encoded probe responses are not accepted")
                    raw = bytearray()
                    for chunk in response.iter_bytes(chunk_size=65_536):
                        if len(raw) + len(chunk) > self.approval.max_response_bytes:
                            raise ProbeFailed("Probe response exceeds approved byte cap")
                        raw.extend(chunk)
            data = json.loads(raw)
            if data.get("jsonrpc") != "2.0" or data.get("id") != "ni-026" or "error" in data:
                raise ProbeFailed("Invalid JSON-RPC response")
            header = data["result"]["header"]
            return FinalizedHeader(
                height=header["height"], block_hash=header["hash"],
                timestamp_nanosec=header["timestamp_nanosec"],
                total_supply_yocto=header["total_supply"], retrieved_at=datetime.now(UTC),
                response_bytes=len(raw), response_sha256=hashlib.sha256(raw).hexdigest(),
            )
        except ProbeFailed:
            raise
        except Exception:
            # Provider exceptions and validation errors can embed response bodies.
            raise ProbeFailed("Probe transport or response validation failed") from None
