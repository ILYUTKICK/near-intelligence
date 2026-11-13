"""Bounded offline NI-083 preparation from explicitly supplied saved files.

This operator-only module never fetches, edits archives, or runs collectors.
Prepared manifests are local artifacts staged by the existing NI-028 pipeline.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from near_api.datasets.manifest import parse_manifest_document
from near_api.metrics.compute import MetricComputationError, day_period, observation_record
from near_api.metrics.registry import definition_by_metric_id

UTC = dt.timezone.utc
MAX_SAVED_BYTES = 16 * 1024 * 1024
MAX_SAVED_DAYS = 730


def _read(path: Path):
    data = path.read_bytes()
    if len(data) > MAX_SAVED_BYTES:
        raise MetricComputationError("Saved history input exceeds bounded size")
    return json.loads(data, parse_float=Decimal), hashlib.sha256(data).hexdigest()


def _value(raw) -> Decimal:
    if isinstance(raw, bool) or not isinstance(raw, (str, int, Decimal)):
        raise MetricComputationError("Saved history value must be an exact decimal")
    result = Decimal(raw)
    if not result.is_finite() or result < 0:
        raise MetricComputationError("Saved history values must be finite and nonnegative")
    return result


def _daily(rows, *, timestamp_key=None, value_key=None) -> dict[dt.date, Decimal]:
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_SAVED_DAYS:
        raise MetricComputationError("Saved history requires 1–730 daily observations")
    result = {}
    previous = None
    for row in rows:
        if timestamp_key:
            stamp = row[timestamp_key]
            if not isinstance(stamp, str) or len(stamp) != 10:
                raise MetricComputationError("Saved history dates must be ISO calendar dates")
            day, value = dt.date.fromisoformat(stamp), _value(row[value_key])
        else:
            if not isinstance(row, list) or len(row) != 2:
                raise MetricComputationError("Saved history must contain timestamp/value pairs")
            stamp = row[0]
            if isinstance(stamp, bool) or not isinstance(stamp, int):
                raise MetricComputationError("Saved history timestamp must be an integer")
            instant = dt.datetime.fromtimestamp(stamp, UTC)
            if instant.time() != dt.time.min:
                raise MetricComputationError("Saved history daily buckets must start at midnight UTC")
            day, value = instant.date(), _value(row[1])
        if previous is not None and day <= previous:
            raise MetricComputationError("Saved history dates must be strictly ascending and unique")
        result[day] = value
        previous = day
    return result


def prepare_history_manifest(archive_root: Path) -> dict:
    """Source-qualified long history; never relabel provider fee rows as revenue."""
    directory = archive_root / "near-dollar"
    volume_path = directory / "data/llama_volume.json"
    fees_path = directory / "data/llama_fees.json"
    dashboard_path = directory / "data/dashboard_efficiency_record.json"
    manifest_path = directory / "manifest.json"
    volume_doc, vh = _read(volume_path)
    fee_doc, fh = _read(fees_path)
    dashboard_doc, dh = _read(dashboard_path)
    manifest_doc, mh = _read(manifest_path)
    for relative, digest in (("data/llama_volume.json", vh), ("data/llama_fees.json", fh),
                             ("data/dashboard_efficiency_record.json", dh)):
        recorded = manifest_doc.get("files", {}).get(relative, {}).get("sha256")
        if recorded != digest:
            raise MetricComputationError("Saved history manifest input digest mismatch")
    saved_times = [entry.get("saved_at_utc") for entry in manifest_doc.get("http_sources", {}).values()
                   if isinstance(entry, dict) and entry.get("saved_at_utc")]
    retrieved_at = max(saved_times) if saved_times else None
    for document in (volume_doc, fee_doc):
        if document.get("name") != "NEAR Intents" or document.get("module") != "near-intents":
            raise MetricComputationError("Saved history protocol identity mismatch")
    if not isinstance(dashboard_doc, list) or len(dashboard_doc) != 4 or not isinstance(dashboard_doc[3], dict):
        raise MetricComputationError("Saved dashboard envelope mismatch")
    dashboard = dashboard_doc[3]
    series = {
        ("SRC-LLAMA", "provider_intents_volume_usd"): _daily(volume_doc["totalDataChart"]),
        ("SRC-LLAMA", "provider_gross_fees_usd"): _daily(fee_doc["totalDataChart"]),
        ("SRC-DASHBOARD", "provider_intents_volume_usd"): _daily(dashboard["intentVolumeSeries"], timestamp_key="date_at", value_key="volume_usd"),
        ("SRC-DASHBOARD", "provider_gross_fees_usd"): _daily(dashboard["totalFeesSeries"], timestamp_key="date_at", value_key="fees_usd"),
    }
    days = [day for values in series.values() for day in values]
    start, end = min(days), max(days) + dt.timedelta(days=1)
    if (end - start).days > MAX_SAVED_DAYS:
        raise MetricComputationError("Saved history span exceeds 730 days")
    observations = []
    for (source, metric), values in sorted(series.items()):
        definition = definition_by_metric_id(metric)
        day = start
        while day < end:
            value = values.get(day)
            period_start, period_end = day_period(day)
            quality = {"source_reported": True}
            if value is None:
                if day < min(values):
                    reason = "No saved observation before this source's coverage"
                elif day > max(values):
                    reason = "No saved observation after this source's coverage"
                else:
                    reason = "Missing date in saved source history"
                quality = {"reason": reason}
            elif metric == "provider_gross_fees_usd" and value == 0:
                quality["reason"] = "Source reports zero fees; economic zero has not been independently verified"
            observations.append(observation_record(
                definition, period_start=period_start, period_end=period_end,
                dimensions={"source": source}, value=value,
                bound_kind="exact" if value is not None else None,
                quality_status="verified" if value is not None else "missing", quality=quality))
            day += dt.timedelta(days=1)
    # Retrieval provenance must come from the supplied manifest, not wall clock.
    # Preserve each original file and its manifest as NI-028 input artifacts.
    result = {
        "schema_version": 1, "dataset_key": "research.history.daily", "frequency": "daily",
        "window": {"start": start.isoformat(), "end_exclusive": end.isoformat()},
        "pipeline_version": "ni083-saved-history-v1", "code_commit": None,
        "config_hash": None, "dependency_lock_hash": None,
        "source_as_of": None, "retrieved_at": retrieved_at,
        "quality": {"note": "Saved provider history, not protocol revenue; separate source definitions and revisions",
                    "input_sha256": {"llama_volume": vh, "llama_fees": fh, "dashboard": dh, "manifest": mh},
                    "missing_dates": "Explicit null rows, never zeros; no interpolation, source splicing or monthly-to-daily allocation"},
        "member_metrics": [str(definition_by_metric_id(metric).id) for metric in
                           ("provider_intents_volume_usd", "provider_gross_fees_usd")],
        "inputs": [{"kind": "file", "path": str(path), "role": "raw", "source_id": source,
                    "query_hash": None, "license_status": "unverified"}
                   for path, source in ((volume_path, "SRC-LLAMA"), (fees_path, "SRC-LLAMA"),
                                        (dashboard_path, "SRC-DASHBOARD"), (manifest_path, None))],
        "observations": observations,
    }
    parse_manifest_document(result, context="NI-083 saved history")
    return result


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.archive_root.resolve(strict=True)
    output = args.output.resolve()
    if output.is_relative_to(root):
        parser.error("Output must be outside the preserved source archive")
    document = prepare_history_manifest(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n")
    print(f"Prepared {len(document['observations'])} source-qualified observations; not published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
