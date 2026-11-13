"""NI-083 exact aggregation, source boundary and immutable range regressions."""
import datetime as dt
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from decimal import Decimal

from near_api.charts.registry import CHARTS
from near_api.datasets.delivery import DeliveryInvalidFilter
from near_api.metrics.compute import MetricComputationError
from near_api.research.archive import _daily, prepare_history_manifest
from near_api.research.history import calendar_summaries, summarize


class ResearchHistoryTests(unittest.TestCase):
    def test_weighted_rate_uses_only_matched_days_not_mean_daily_rates(self):
        a, b, c = [dt.date(2026, 1, day) for day in (1, 2, 3)]
        summary = summarize({a: Decimal(100), b: Decimal(900), c: Decimal(5000)},
                            {a: Decimal(10), b: Decimal(9)}, a, c + dt.timedelta(days=1))
        self.assertEqual(summary.volume_usd, "6000")
        self.assertEqual(summary.gross_fees_usd, "19")
        self.assertEqual(summary.matched_volume_usd, "1000")
        self.assertEqual(summary.effective_gross_fee_bps, "190")
        self.assertEqual(summary.matched_days, 2)
        self.assertFalse(summary.complete)

    def test_source_zero_is_observed_missing_is_not_zero(self):
        a = dt.date(2026, 2, 1)
        summary = summarize({a: Decimal(100)}, {a: Decimal(0)}, a, a + dt.timedelta(days=2))
        self.assertEqual(summary.zero_fee_days, 1)
        self.assertEqual(summary.fee_days, 1)
        self.assertEqual(summary.effective_gross_fee_bps, "0")
        self.assertFalse(summary.complete)
        empty = summarize({}, {}, a, a + dt.timedelta(days=1))
        self.assertIsNone(empty.gross_fees_usd)
        self.assertIsNone(empty.effective_gross_fee_bps)

    def test_zero_volume_does_not_create_infinite_rate(self):
        a = dt.date(2026, 2, 1)
        summary = summarize({a: Decimal(0)}, {a: Decimal(1)}, a, a + dt.timedelta(days=1))
        self.assertIsNone(summary.effective_gross_fee_bps)
        self.assertTrue(summary.complete)

    def test_decimal_precision_is_not_ambient_context(self):
        a, b = dt.date(2026, 2, 1), dt.date(2026, 2, 2)
        v = {a: Decimal("999999999999999999999999.123456789012345678901234"),
             b: Decimal("0.000000000000000000000001")}
        summary = summarize(v, {}, a, b + dt.timedelta(days=1))
        self.assertEqual(summary.volume_usd, "999999999999999999999999.123456789012345678901235")

    def test_edge_month_keeps_full_calendar_bounds_and_partial_flag(self):
        a, end = dt.date(2026, 1, 30), dt.date(2026, 2, 2)
        values = {a + dt.timedelta(days=n): Decimal(1) for n in range(3)}
        months = calendar_summaries(values, values, a, end, months=1)
        self.assertEqual([item.expected_days for item in months], [31, 28])
        self.assertEqual([item.volume_days for item in months], [2, 1])
        self.assertFalse(any(item.complete for item in months))
        self.assertEqual(months[0].start, dt.date(2026, 1, 1))

    def test_full_quarter_and_excluded_selection_days(self):
        a, end = dt.date(2026, 1, 1), dt.date(2026, 4, 1)
        values = {a + dt.timedelta(days=n): Decimal(1) for n in range(91)}
        quarter = calendar_summaries(values, values, a, end, months=3)[0]
        self.assertTrue(quarter.complete)
        self.assertEqual(quarter.volume_usd, "90")
        self.assertEqual(quarter.effective_gross_fee_bps, "10000")

    def test_range_rejects_empty_and_more_than_two_years(self):
        a = dt.date(2026, 1, 1)
        for end in [a, a - dt.timedelta(days=1), a + dt.timedelta(days=731)]:
            with self.assertRaises(DeliveryInvalidFilter):
                summarize({}, {}, a, end)

    def test_new_versions_leave_original_cap_and_identity(self):
        for slug in ("intents-volume", "gross-fees"):
            old, new = [c for c in CHARTS if c.chart_id == slug]
            self.assertEqual(old.version, 1)
            self.assertEqual(old.allowed_ranges["max_days"], 366)
            self.assertEqual(new.version, 2)
            self.assertEqual(new.allowed_ranges["max_days"], 730)
            self.assertNotEqual(old.id, new.id)
            self.assertEqual(old.series, new.series)

    def _saved_history_fixture(self, root: Path):
        data = root / "near-dollar/data"
        data.mkdir(parents=True)
        stamp = int(dt.datetime(2026, 1, 1, tzinfo=dt.UTC).timestamp())
        documents = {
            "llama_volume.json": {"name": "NEAR Intents", "module": "near-intents",
                "totalDataChart": [[stamp + n * 86400, 100] for n in range(3)]},
            "llama_fees.json": {"name": "NEAR Intents", "module": "near-intents",
                "totalDataChart": [[stamp + 2 * 86400, 0]]},
            "dashboard_efficiency_record.json": ["$", "$synthetic", None, {
                "intentVolumeSeries": [{"date_at": f"2026-01-0{n}", "volume_usd": 100} for n in (2, 3)],
                "totalFeesSeries": [{"date_at": "2026-01-03", "fees_usd": 1}]}],
        }
        hashes = {}
        for name, document in documents.items():
            content = json.dumps(document).encode()
            (data / name).write_bytes(content)
            hashes[f"data/{name}"] = {"sha256": hashlib.sha256(content).hexdigest()}
        (data.parent / "manifest.json").write_text(json.dumps({"files": hashes}))
        return data

    def test_prepared_manifest_makes_sparse_coverage_explicit_without_zero_padding(self):
        with TemporaryDirectory(prefix="ni083-synthetic-") as temporary:
            root = Path(temporary)
            self._saved_history_fixture(root)
            manifest = prepare_history_manifest(root)
        records = manifest["observations"]
        self.assertEqual(len(records), 12)
        self.assertEqual(sum(row["value"] is None for row in records), 5)
        for row in records:
            if row["value"] is None:
                self.assertEqual(row["quality_status"], "missing")
                self.assertTrue(row["quality"]["reason"])
                self.assertIsNone(row["bound_kind"])
        zeros = [row for row in records if row["value"] == "0"]
        self.assertEqual(len(zeros), 1)
        self.assertEqual(zeros[0]["quality_status"], "verified")

    def test_preparation_refuses_modified_input_against_saved_manifest(self):
        with TemporaryDirectory(prefix="ni083-synthetic-") as temporary:
            root = Path(temporary)
            data = self._saved_history_fixture(root)
            target = data / "llama_volume.json"
            target.write_text(target.read_text() + " ")
            with self.assertRaisesRegex(MetricComputationError, "digest mismatch"):
                prepare_history_manifest(root)

    def test_saved_daily_input_rejects_duplicate_disordered_intraday_or_bad_value(self):
        stamp = 1733788800
        for rows in ([[stamp, 1], [stamp, 2]], [[stamp + 86400, 1], [stamp, 2]],
                     [[stamp + 1, 1]], [[stamp, Decimal("NaN")]], [[stamp, -1]], [[stamp, 1.2]]):
            with self.assertRaises(MetricComputationError):
                _daily(rows)
        self.assertEqual(len(_daily([[stamp, 1], [stamp + 2 * 86400, 2]])), 2)


if __name__ == "__main__":
    unittest.main()
