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

from risk_algorithm_core.detector_event_aggregation import (
    EVENT_KEY_COLUMNS,
    build_detector_event_aggregates,
    validate_detector_event_aggregates,
)
from risk_model_core.repositories import CompositeDetectorResultRepository
from risk_result_contracts import write_production_parquet


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

    event_frames: list[pd.DataFrame] = []
    source_batches: list[str] = []
    detectors_seen: set[str] = set()
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
                event_frames.append(hits)
            detectors_seen.add(detector_id)
            source_batches.append(str(component_dir.relative_to(root)).replace("\\", "/"))

    events = pd.concat(event_frames, ignore_index=True) if event_frames else pd.DataFrame(
        columns=[*EVENT_KEY_COLUMNS, "hit_flag"]
    )
    generated_at = datetime.now(timezone.utc).isoformat()
    aggregates = build_detector_event_aggregates(events, generated_at=generated_at)
    if aggregates.empty:
        raise ValueError("Refusing to publish an empty Detector event aggregate")
    validation = validate_detector_event_aggregates(aggregates)
    source_digest = hashlib.sha256("\n".join(sorted(source_batches)).encode("utf-8")).hexdigest()

    staging_root = root / ".detector_event_aggregation_staging"
    staging_dir = staging_root / f".staging-{end_date}-{args.run_id}-{uuid.uuid4().hex}"
    staging_dir.mkdir(parents=True, exist_ok=False)
    write_production_parquet(aggregates, staging_dir / "detector_event_aggregates.parquet")
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
