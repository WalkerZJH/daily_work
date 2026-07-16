"""Materialize immutable cross-day Detector event aggregates from formal result components."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from risk_algorithm_core.detector_event_aggregation import (
    EVENT_KEY_COLUMNS,
    update_detector_event_aggregates,
    validate_detector_event_aggregates,
)
from risk_model_core.repositories import CompositeDetectorResultRepository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize entity-level cross-day aggregates from immutable Daily Detector results."
    )
    parser.add_argument("--batch-root", default="data/project_result_batches")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--detector-id", action="append", dest="detector_ids")
    args = parser.parse_args(argv)

    start_date = _date(args.start_date)
    end_date = _date(args.end_date)
    dates = [value.date().isoformat() for value in pd.date_range(start_date, end_date, freq="D")]
    if not dates:
        raise ValueError("The requested Detector aggregation date range is empty")
    selected_detector_ids = sorted(set(args.detector_ids or []))
    _validate_identifier("run_id", args.run_id)

    root = Path(args.batch_root)
    batch_dir = (
        root
        / "detector_event_aggregates"
        / f"batch_id={end_date}-{args.run_id}"
    )
    if batch_dir.exists():
        raise FileExistsError(f"Refusing to overwrite published Detector event aggregate: {batch_dir}")

    source_batches: list[str] = []
    detectors_seen: set[str] = set()
    generated_at = datetime.now(timezone.utc).isoformat()
    staging_root = root / ".detector_event_aggregation_staging"
    staging_dir = staging_root / f".staging-{end_date}-{args.run_id}-{uuid.uuid4().hex}"
    staging_dir.mkdir(parents=True, exist_ok=False)
    aggregate_path = staging_dir / "detector_event_aggregates.parquet"
    writer: pq.ParquetWriter | None = None
    state: dict[tuple[str, str, str], dict[str, object]] = {}
    row_count = 0
    event_count = 0
    max_current_detector_count = 0
    max_cumulative_hit_count = 0
    dates_with_hits = 0
    for observation_date in dates:
        date_partition = root / f"detector_run_date={observation_date}"
        repository = CompositeDetectorResultRepository(date_partition)
        component_dirs = repository.component_batch_dirs
        if selected_detector_ids:
            component_dirs = [
                path
                for path in component_dirs
                if path.parent.name.removeprefix("detector_id=") in selected_detector_ids
            ]
            found = {path.parent.name.removeprefix("detector_id=") for path in component_dirs}
            missing = sorted(set(selected_detector_ids) - found)
            if missing:
                raise FileNotFoundError(
                    f"Detector components missing for {observation_date}: {missing}"
                )
        date_frames: list[pd.DataFrame] = []
        for component_dir in component_dirs:
            detector_id = component_dir.parent.name.removeprefix("detector_id=")
            result_path = component_dir / "daily_detector_results.parquet"
            columns = [*EVENT_KEY_COLUMNS, "hit_flag"]
            hits = pd.read_parquet(
                result_path,
                columns=columns,
                filters=[("hit_flag", "==", True)],
            )
            if not hits.empty:
                date_frames.append(hits)
            detectors_seen.add(detector_id)
            source_batches.append(str(component_dir.relative_to(root)).replace("\\", "/"))
        date_events = pd.concat(date_frames, ignore_index=True) if date_frames else pd.DataFrame(
            columns=[*EVENT_KEY_COLUMNS, "hit_flag"]
        )
        daily = update_detector_event_aggregates(
            date_events, state, generated_at=generated_at
        )
        if daily.empty:
            continue
        validate_detector_event_aggregates(daily)
        table = pa.Table.from_pandas(daily, preserve_index=False)
        if writer is None:
            writer = pq.ParquetWriter(aggregate_path, table.schema, compression="zstd")
        writer.write_table(table)
        dates_with_hits += 1
        row_count += len(daily)
        event_count += int(daily["current_detector_count"].sum())
        max_current_detector_count = max(max_current_detector_count, int(daily["current_detector_count"].max()))
        max_cumulative_hit_count = max(max_cumulative_hit_count, int(daily["cumulative_hit_count"].max()))
    if writer is not None:
        writer.close()
    if row_count == 0:
        raise ValueError("Refusing to publish an empty Detector event aggregate")
    parquet = pq.ParquetFile(aggregate_path)
    if parquet.metadata.num_rows != row_count:
        raise ValueError(
            f"Detector event aggregate Parquet row mismatch: {parquet.metadata.num_rows} != {row_count}"
        )
    if parquet.schema_arrow.names != list(daily.columns):
        raise ValueError("Detector event aggregate Parquet schema does not match the stable output columns")
    parquet.close()
    validation = {
        "engineering_gate_status": "passed",
        "row_count": row_count,
        "entity_count": len(state),
        "observation_date_count": dates_with_hits,
        "event_count": event_count,
        "max_current_detector_count": max_current_detector_count,
        "max_cumulative_hit_count": max_cumulative_hit_count,
    }
    source_digest = hashlib.sha256("\n".join(sorted(source_batches)).encode("utf-8")).hexdigest()
    (staging_dir / "detector_event_aggregation_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "batch_id": batch_dir.name.removeprefix("batch_id="),
        "report_type": "detector_event_aggregation",
        "schema_version": "detector_event_aggregation_v1",
        "data_backend": "parquet",
        "start_date": start_date,
        "end_date": end_date,
        "run_id": args.run_id,
        "detector_ids": sorted(detectors_seen),
        "source_component_count": len(source_batches),
        "source_component_digest": source_digest,
        "source_table": "daily_detector_results.parquet",
        "aggregate_table": "detector_event_aggregates.parquet",
        "validation_report": "detector_event_aggregation_validation.json",
        "engineering_gate_status": validation["engineering_gate_status"],
        "row_count": validation["row_count"],
        "event_count": validation["event_count"],
        "monthly_pipeline_called": False,
        "source_components_rewritten": False,
        "generated_at": generated_at,
    }
    (staging_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    batch_dir.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging_dir, batch_dir)
    print(json.dumps({
        "stage": "detector_event_aggregation",
        "status": "completed",
        "batch_dir": str(batch_dir).replace("\\", "/"),
        **validation,
    }, ensure_ascii=False))
    return 0


def _date(value: str) -> str:
    return datetime.fromisoformat(value).date().isoformat()


def _validate_identifier(label: str, value: str) -> None:
    if not str(value).strip() or any(character in str(value) for character in "\\/:"):
        raise ValueError(f"{label} must be a non-empty path-safe identifier")


if __name__ == "__main__":
    raise SystemExit(main())
