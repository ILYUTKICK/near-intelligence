"""NI-026 synthetic verification fixtures. No provider requests or research data."""

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from pydantic import ValidationError

from near_api.ingestion.capabilities.models import ProbeApproval, SourceCapability
from near_api.ingestion.capabilities.probe import HeaderProbe, ProbeControls, ProbeDenied, ProbeFailed
from near_api.ingestion.capabilities.registry import SOURCES


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = SourceCapability(
            source_id="SRC-NEAR-RPC",
            documentation_url="https://docs.near.org/api/rpc/providers",
            endpoint="https://free.rpc.fastnear.com", method="POST", auth="none",
            access_verified=True,
            quota_evidence_url="https://example.org/synthetic/quota",
            rights="approved", rights_evidence_url="https://example.org/synthetic/rights",
        )
        self.approval = ProbeApproval(
            source_id=self.source.source_id, endpoint=self.source.endpoint,
            approved_by="synthetic-test-operator", approval_reference="synthetic-test-only",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            max_requests=1, max_response_bytes=1024, timeout_seconds=1,
            zero_cost_confirmed=True,
        )
        self.controls = ProbeControls(
            enabled=True, source_allowlist=frozenset({self.source.source_id}),
            requests_per_day=1,
        )
        self.calls = []

    def probe(self, *, source=None, approval=None, controls=None):
        return HeaderProbe(source or self.source, approval or self.approval,
                           controls or self.controls, self.root)

    def response(self, request):
        self.calls.append(request)
        return httpx.Response(200, json={
            "jsonrpc": "2.0", "id": "ni-026", "result": {"header": {
                "height": 123, "hash": "1" * 32,
                "timestamp_nanosec": "1793914540000000000",
                "total_supply": "1234567890123456789012345678901234",
                "secret_response_field": "synthetic-canary",
            }},
        })

    def assert_denied(self, probe):
        with self.assertRaises(ProbeDenied):
            probe.run(transport=httpx.MockTransport(self.response))
        self.assertEqual(self.calls, [])

    def test_all_candidates_remain_disabled_with_explicit_blockers(self):
        self.assertEqual(len(SOURCES), 10)
        for source in SOURCES.values():
            with self.subTest(source=source.source_id):
                self.assertFalse(source.access_verified)
                self.assertTrue(source.blockers)
                self.assertIsNone(source.history_start)
                self.assertIsNone(source.response_schema_sha256)
                self.assertNotEqual(source.raw_redistribution, "approved")
        self.assert_denied(self.probe(source=SOURCES["SRC-NEAR-RPC"]))

    def test_defaults_allowlist_and_budget_prevent_network(self):
        for values in ({}, {"source_allowlist": frozenset()}, {"requests_per_day": 0},
                       {"requests_used_today": 1}, {"enabled": False}):
            with self.subTest(values=values):
                controls = ProbeControls() if values == {} else self.controls.model_copy(update=values)
                self.assert_denied(self.probe(controls=controls))

    def test_evidence_and_approval_must_be_complete(self):
        for values in ({"access_verified": False}, {"rights": "pending"},
                       {"quota_evidence_url": None}, {"blockers": ("OQ-03",)}):
            self.assert_denied(self.probe(source=self.source.model_copy(update=values)))
        for values in ({"source_id": "SRC-PRICE"}, {"endpoint": "https://example.org"},
                       {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}):
            self.assert_denied(self.probe(approval=self.approval.model_copy(update=values)))
        self.assert_denied(self.probe(source=self.source.model_copy(update={
            "documented_requests_per_day": 1,
        }), controls=self.controls.model_copy(update={"requests_per_day": 2})))

    def test_stop_and_pause_markers_take_precedence(self):
        for marker in (self.root / "STOP_PUBLIC_COLLECTION",
                       self.root / "research/near-weekly/data/STOP_PUBLIC_COLLECTION",
                       self.root / "custom.pause"):
            with self.subTest(marker=marker):
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.touch()
                controls = self.controls.model_copy(update={"stop_paths": (marker,)})
                self.assert_denied(self.probe(controls=controls))
                marker.unlink()

    def test_urls_unknown_fields_and_unsupported_endpoints_fail_closed(self):
        for url in ("http://example.org", "https://user:secret@example.org",
                    "https://example.org?api_key=secret", "https://example.org/#secret"):
            with self.assertRaises(ValidationError):
                SourceCapability.model_validate({**self.source.model_dump(), "endpoint": url})
        with self.assertRaises(ValidationError):
            SourceCapability.model_validate({**self.source.model_dump(), "api_key": "secret"})
        source = self.source.model_copy(update={"endpoint": "https://example.org"})
        approval = self.approval.model_copy(update={"endpoint": source.endpoint})
        self.assert_denied(self.probe(source=source, approval=approval))

    def test_evidence_consistency(self):
        for values in ({"rights_evidence_url": None},
                       {"rights": "pending", "raw_redistribution": "approved"},
                       {"documented_requests_per_day": 10, "quota_evidence_url": None},
                       {"history_start": datetime.now(UTC)},
                       {"history_start": datetime(2026, 1, 1), "history_end": datetime(2026, 1, 2)}):
            with self.assertRaises(ValidationError):
                SourceCapability.model_validate({**self.source.model_dump(), **values})
        for values in ({"max_requests": 0}, {"timeout_seconds": float("nan")},
                       {"max_response_bytes": 2_000_000}, {"zero_cost_confirmed": False},
                       {"expires_at": datetime(2026, 1, 1)}):
            with self.assertRaises(ValidationError):
                ProbeApproval.model_validate({**self.approval.model_dump(), **values})

    def test_success_preserves_exact_amount_and_sanitizes_output(self):
        probe = self.probe()
        result = probe.run(transport=httpx.MockTransport(self.response))
        self.assertEqual(result.total_supply_yocto, "1234567890123456789012345678901234")
        self.assertEqual(result.height, 123)
        self.assertEqual(len(result.response_sha256), 64)
        self.assertNotIn("synthetic-canary", result.model_dump_json())
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(json.loads(self.calls[0].content)["params"], {"finality": "final"})
        self.assertEqual(self.calls[0].headers["Accept-Encoding"], "identity")
        with self.assertRaises(ProbeDenied):
            probe.run(transport=httpx.MockTransport(self.response))
        self.assertEqual(len(self.calls), 1)

    def test_failure_is_single_use_without_redirect_or_retry(self):
        for status in (302, 401, 403, 429, 500):
            with self.subTest(status=status):
                calls = []

                def fail(request):
                    calls.append(request)
                    return httpx.Response(status, headers={"Location": "https://example.org"},
                                          text="synthetic-secret-token")

                probe = self.probe()
                with self.assertRaises(ProbeFailed) as raised:
                    probe.run(transport=httpx.MockTransport(fail))
                self.assertNotIn("synthetic-secret-token", str(raised.exception))
                with self.assertRaises(ProbeDenied):
                    probe.run(transport=httpx.MockTransport(fail))
                self.assertEqual(len(calls), 1)

    def test_concurrent_reuse_consumes_at_most_one_request(self):
        probe = self.probe()

        def run():
            try:
                probe.run(transport=httpx.MockTransport(self.response))
                return "passed"
            except ProbeDenied:
                return "denied"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: run(), range(2)))
        self.assertCountEqual(results, ["passed", "denied"])
        self.assertEqual(len(self.calls), 1)

    def test_oversized_malformed_and_provider_error_are_sanitized(self):
        bodies = (b"x" * 1025, b"not-json-synthetic-secret",
                  b'{"error":{"message":"synthetic-secret"}}', b'[]',
                  b'{"jsonrpc":"2.0","id":"ni-026","result":{"header":{}}}')
        for body in bodies:
            with self.subTest(body=body[:10]):
                with self.assertRaises(ProbeFailed) as raised:
                    self.probe().run(transport=httpx.MockTransport(
                        lambda request: httpx.Response(200, content=body)))
                self.assertNotIn("synthetic-secret", str(raised.exception))

    def test_encoded_responses_are_rejected_before_decoding(self):
        with self.assertRaisesRegex(ProbeFailed, "Encoded probe responses"):
            self.probe().run(transport=httpx.MockTransport(lambda request: httpx.Response(
                200, headers={"Content-Encoding": "gzip"}, stream=httpx.ByteStream(b"invalid-gzip"),
            )))


if __name__ == "__main__":
    unittest.main()
