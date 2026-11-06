"""NI-027 unit tests: manifest parsing, byte verification ordering, redaction,
classification and registry contracts. No database, no research data."""

import datetime as dt
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from archive_fixture import (
    ALPHA_COHORT,
    ALPHA_FILES,
    ALPHA_PAYLOAD,
    BETA_COHORT,
    REGISTRY,
    SECRET_TOKEN,
    build_archive,
    tree_digest,
    write_registry,
)

from near_api.ingestion import archive
from near_api.ingestion.archive import (
    ArchiveVerificationError,
    ManifestFormatError,
    MetadataContractError,
    classify_role,
    common_manifest_prefix,
    coverage_for_role,
    parse_manifest,
    redact_credentials,
    verify_archive,
)


class ManifestParsingTests(unittest.TestCase):
    def test_strict_shasum_text_listing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "m.sha256"
            path.write_text(
                "a" * 64 + "  research/alpha/FINDINGS.md\n"
                + "b" * 64 + "  research/alpha/data/x.json\n",
                encoding="utf-8")
            digest, entries = parse_manifest(path)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0].relative_path, "research/alpha/FINDINGS.md")
            self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_format_contract_failures(self):
        cases = {
            "binary mode marker": "a" * 64 + " *research/x\n",
            "single space": "a" * 64 + " research/x\n",
            "short hash": "a" * 32 + "  research/x\n",
            "absolute path": "a" * 64 + "  /etc/passwd\n",
            "traversal": "a" * 64 + "  research/../../etc/passwd\n",
            "duplicate": "a" * 64 + "  research/x\n" + "a" * 64 + "  research/x\n",
            "empty line": "\n",
            "backslash": "a" * 64 + "  research\\x\n",
        }
        for name, content in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "m.sha256"
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ManifestFormatError):
                    parse_manifest(path)

    def test_empty_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "m.sha256"
            path.write_text("", encoding="utf-8")
            with self.assertRaises(ManifestFormatError):
                parse_manifest(path)


class CommonPrefixTests(unittest.TestCase):
    def test_common_leading_directory_is_stripped(self):
        entries = (archive.ManifestEntry("a" * 64, "research/alpha/x.json"),
                   archive.ManifestEntry("b" * 64, "research/beta/y.md"))
        self.assertEqual(common_manifest_prefix(entries), "research/")

    def test_no_common_directory(self):
        entries = (archive.ManifestEntry("a" * 64, "alpha/x.json"),
                   archive.ManifestEntry("b" * 64, "beta/y.md"))
        self.assertEqual(common_manifest_prefix(entries), "")


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "handoff"
        self.root.mkdir()
        self.manifest = build_archive(self.root)
        self.registry = write_registry(self.root)
        digest, entries = parse_manifest(self.manifest)
        self.digest, self.entries = digest, entries

    def test_verified_facts_match_manifest(self):
        facts = verify_archive(self.root, self.entries)
        self.assertEqual(len(facts), len(self.entries))
        alpha = facts[f"research/{ALPHA_COHORT}/data/response.json"]
        self.assertEqual(alpha.sha256, hashlib.sha256(
            ALPHA_FILES["data/response.json"].encode()).hexdigest())
        self.assertEqual(alpha.byte_size, len(ALPHA_FILES["data/response.json"]))

    def test_files_outside_the_covered_subtree_are_not_part_of_the_claim(self):
        (self.root / "unrelated-checkout-file.txt").write_text("not archive bytes")
        facts = verify_archive(self.root, self.entries)
        self.assertEqual(len(facts), len(self.entries))

    def test_missing_file_rejects_the_whole_batch(self):
        (self.root / f"research/{BETA_COHORT}/data/snapshot.json").unlink()
        with self.assertRaisesRegex(ArchiveVerificationError, "missing from the archive"):
            verify_archive(self.root, self.entries)

    def test_extra_file_inside_the_covered_subtree_rejects_the_batch(self):
        (self.root / f"research/{ALPHA_COHORT}/data/extra.json").write_text("{}\n")
        with self.assertRaisesRegex(ArchiveVerificationError, "absent from the manifest"):
            verify_archive(self.root, self.entries)

    def test_hash_mismatch_rejects_the_batch(self):
        target = self.root / f"research/{ALPHA_COHORT}/data/response.json"
        target.write_text(target.read_text() + "corruption\n")
        with self.assertRaisesRegex(ArchiveVerificationError, "SHA-256 mismatch"):
            verify_archive(self.root, self.entries)

    def test_symlink_inside_the_covered_subtree_rejects_the_batch(self):
        (self.root / f"research/{ALPHA_COHORT}/data/link.json").symlink_to("response.json")
        with self.assertRaisesRegex(ArchiveVerificationError, "non-regular"):
            verify_archive(self.root, self.entries)

    def test_hash_verification_precedes_any_content_reading(self):
        # The cohort manifest is corrupted JSON whose listed hash is stale: if
        # contents were parsed before verification, this would surface as a
        # metadata contract failure instead of the hash mismatch.
        target = self.root / f"research/{ALPHA_COHORT}/manifest.json"
        target.write_text("{ this is not json")
        with self.assertRaises(ArchiveVerificationError) as raised:
            archive.import_archive(archive_root=self.root, manifest_path=self.manifest,
                                   registry_path=self.registry, database_url=None, dry_run=True)
        self.assertNotIsInstance(raised.exception, MetadataContractError)
        self.assertIn("SHA-256 mismatch", str(raised.exception))

    def test_internal_checksum_mismatch_rejects_the_batch_after_verification(self):
        # The outer manifest is re-pointed at the mutated bytes (so byte
        # verification passes), but the cohort manifest's internal checksum
        # listing no longer matches: the divergence still rejects the batch.
        target = self.root / f"research/{ALPHA_COHORT}/data/response.json"
        original = target.read_text()
        target.write_text(original.replace(ALPHA_PAYLOAD, "FFFFF" + ALPHA_PAYLOAD[5:]))
        rewrite_manifest_line(self.manifest, f"research/{ALPHA_COHORT}/data/response.json")
        with self.assertRaisesRegex(ArchiveVerificationError, "internal checksum mismatch"):
            archive.import_archive(archive_root=self.root, manifest_path=self.manifest,
                                   registry_path=self.registry, database_url=None, dry_run=True)


def rewrite_manifest_line(manifest_path: Path, relative_path: str) -> None:
    """Replace one manifest entry's hash with the file's current bytes hash."""
    import hashlib as _hashlib
    archive_root = manifest_path.parent / manifest_path.stem.removesuffix("-manifest")
    data = (archive_root / relative_path).read_bytes()
    lines = manifest_path.read_text().splitlines()
    rewritten = [f"{_hashlib.sha256(data).hexdigest()}  {relative_path}"
                 if line.endswith(f"  {relative_path}") else line for line in lines]
    manifest_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")


class DryRunTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "handoff"
        self.root.mkdir()
        self.manifest = build_archive(self.root)
        self.registry = write_registry(self.root)
        self.before = tree_digest(self.root)

    def test_dry_run_reports_full_summary_without_database(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = archive.main(["--dry-run",
                                 "--archive-root", str(self.root),
                                 "--manifest", str(self.manifest),
                                 "--cohorts", str(self.registry)])
        self.assertEqual(code, archive.EXIT_OK)
        summary = json.loads(stdout.getvalue())
        self.assertTrue(summary["dry_run"])
        self.assertEqual(summary["files"], 8)
        self.assertEqual(summary["cohorts"], [ALPHA_COHORT, BETA_COHORT])
        self.assertEqual(summary["sources"], ["SRC-EXAMPLE"])
        self.assertGreaterEqual(summary["documented_runs"], 2)
        self.assertEqual(tree_digest(self.root), self.before)

    def test_undeclared_cohort_is_rejected(self):
        registry = json.loads(self.registry.read_text())
        del registry["cohorts"][BETA_COHORT]
        self.registry.write_text(json.dumps(registry))
        with self.assertRaisesRegex(MetadataContractError, "not declared in the registry"):
            archive.import_archive(archive_root=self.root, manifest_path=self.manifest,
                                   registry_path=self.registry, database_url=None, dry_run=True)

    def test_registry_window_drift_is_rejected(self):
        registry = json.loads(self.registry.read_text())
        registry["cohorts"][ALPHA_COHORT]["window_start"] = "2026-01-02"
        self.registry.write_text(json.dumps(registry))
        with self.assertRaisesRegex(MetadataContractError, "contradicts"):
            archive.import_archive(archive_root=self.root, manifest_path=self.manifest,
                                   registry_path=self.registry, database_url=None, dry_run=True)

    def test_unreadable_cohort_manifest_is_a_contract_failure_after_verification(self):
        # The outer manifest deliberately keeps a STALE hash for the cohort
        # manifest whose on-disk bytes are corrupt JSON: verification must
        # reject on the hash before any JSON is parsed.
        target = self.root / f"research/{ALPHA_COHORT}/manifest.json"
        stale_hash = hashlib.sha256(b"anything").hexdigest()
        lines = self.manifest.read_text().splitlines()
        rewritten = [f"{stale_hash}  research/{ALPHA_COHORT}/manifest.json"
                     if line.endswith(f"  research/{ALPHA_COHORT}/manifest.json") else line
                     for line in lines]
        self.manifest.write_text("\n".join(rewritten) + "\n")
        target.write_text("{ definitely not json")
        with self.assertRaises(ArchiveVerificationError):
            archive.import_archive(archive_root=self.root, manifest_path=self.manifest,
                                   registry_path=self.registry, database_url=None, dry_run=True)


class RedactionTests(unittest.TestCase):
    def test_credential_bearing_strings_are_redacted(self):
        cases = {
            f"https://api.example.test/v1/data?api_key={SECRET_TOKEN}":
                "https://api.example.test/v1/data?api_key=[redacted]",
            "postgres://admin:p4ssw0rd@db.internal:5432/app":
                "postgres://[redacted]:[redacted]@db.internal:5432/app",
            "auth token: eyJhbGciOiJIUzI1NiJ9.e30.Zm9vYmFy": "auth token: [redacted]",
            "bearer ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789": "bearer [redacted]",
            "staticBearerNotCredential": "staticBearerNotCredential",
        }
        for value, expected in cases.items():
            with self.subTest(value=value[:40]):
                self.assertEqual(redact_credentials(value), expected)
                self.assertNotIn("p4ssw0rd", redact_credentials(value))
                self.assertNotIn("eyJhbGciOiJIUzI1NiJ9", redact_credentials(value))
                self.assertNotIn(SECRET_TOKEN, redact_credentials(value))

    def test_sha256_hashes_and_plain_urls_survive(self):
        digest = "a" * 64
        self.assertEqual(redact_credentials(digest), digest)
        self.assertEqual(redact_credentials("https://api.llama.fi/summary/dexs/near-intents"),
                         "https://api.llama.fi/summary/dexs/near-intents")
        # Long non-hex runs are treated as secret material.
        self.assertEqual(redact_credentials("value gAAAAABmVveryLongTokenPayload0000000000000"),
                         "value [redacted]")


class ClassificationTests(unittest.TestCase):
    def test_documented_and_raw_named_files_are_raw(self):
        self.assertEqual(classify_role("data/response.json", documented_raw=True), "raw")
        self.assertEqual(classify_role("data/flows_90d_raw.json", documented_raw=False), "raw")

    def test_conservative_defaults_never_claim_raw(self):
        self.assertEqual(classify_role("data/reconciliation.csv", documented_raw=False), "aggregate")
        self.assertEqual(classify_role("analysis/summary.json", documented_raw=False), "aggregate")
        self.assertEqual(classify_role("data/snapshot.json", documented_raw=False), "aggregate")

    def test_process_roles(self):
        self.assertEqual(classify_role("scripts/analyze.py", documented_raw=False), "script")
        self.assertEqual(classify_role("sql/01_extract.sql", documented_raw=False), "script")
        self.assertEqual(classify_role("manifest.json", documented_raw=False), "provenance")
        self.assertEqual(classify_role("data/collection.pid", documented_raw=False), "provenance")
        self.assertEqual(classify_role("data/STOP_PUBLIC_COLLECTION", documented_raw=False),
                         "provenance")
        self.assertEqual(classify_role("FINDINGS.md", documented_raw=False), "editorial")

    def test_coverage_follows_role(self):
        declaration = archive.CohortDeclaration(
            name="x", window_start=dt.date(2026, 1, 1), window_end_exclusive=dt.date(2026, 2, 1),
            coverage_scope="partial_raw_audit", partial_audit="note", license_status="unverified",
            sources=(), basis="basis")
        self.assertEqual(coverage_for_role("raw", declaration),
                         ("partial_raw_audit", dt.date(2026, 1, 1), dt.date(2026, 2, 1)))
        self.assertEqual(coverage_for_role("aggregate", declaration),
                         ("partial_raw_audit", dt.date(2026, 1, 1), dt.date(2026, 2, 1)))
        self.assertEqual(coverage_for_role("editorial", declaration),
                         ("process_documentation", None, None))
        self.assertEqual(coverage_for_role("script", declaration),
                         ("process_documentation", None, None))


class RegistryValidationTests(unittest.TestCase):
    def base_registry(self):
        return json.loads(json.dumps(REGISTRY))

    def test_schema_version_is_required(self):
        registry = self.base_registry()
        registry["schema_version"] = 2
        with self.assertRaisesRegex(MetadataContractError, "schema_version"):
            write_and_load(registry)

    def test_cohort_source_must_be_declared(self):
        registry = self.base_registry()
        registry["cohorts"]["alpha-cohort"]["sources"] = ["SRC-UNKNOWN"]
        with self.assertRaisesRegex(MetadataContractError, "undeclared registry source"):
            write_and_load(registry)

    def test_invalid_coverage_scope_rejected(self):
        registry = self.base_registry()
        registry["cohorts"]["alpha-cohort"]["coverage_scope"] = "everything"
        with self.assertRaisesRegex(MetadataContractError, "coverage_scope"):
            write_and_load(registry)

    def test_half_open_window_required(self):
        registry = self.base_registry()
        registry["cohorts"]["alpha-cohort"]["window_end_exclusive"] = None
        with self.assertRaisesRegex(MetadataContractError, "both boundaries"):
            write_and_load(registry)


def write_and_load(registry: dict):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "registry.json"
        path.write_text(json.dumps(registry), encoding="utf-8")
        return archive.load_cohort_registry(path)


class SourceAttributionTests(unittest.TestCase):
    def test_known_hosts_map_to_declared_sources(self):
        cases = {
            "https://api.coingecko.com/api/v3/coins/near/market_chart": "SRC-PRICE",
            "https://api.llama.fi/summary/dexs/near-intents": "SRC-LLAMA",
            "https://revenue.near.org/": "SRC-DASHBOARD",
            "https://api.nearblocks.io/v1/charts": "SRC-NEARBLOCKS",
            "https://tx.main.fastnear.com/v0/transactions": "SRC-FASTNEAR",
            "https://archival-rpc.mainnet.near.org": "SRC-NEAR-RPC",
            "https://raw.githubusercontent.com/DefiLlama/dimension-adapters/master/fees/x/index.ts":
                "SRC-LLAMA",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(archive._source_for_remote(url), expected)

    def test_unknown_remotes_stay_unattributed(self):
        self.assertIsNone(archive._source_for_remote("https://internal.example.test/x"))
        self.assertIsNone(archive._source_for_remote(
            "https://raw.githubusercontent.com/near/nearcore/master/core/block.rs"))


if __name__ == "__main__":
    unittest.main()
