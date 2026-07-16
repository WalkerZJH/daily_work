"""Materialize independent daily Detector partitions from one raw-fact read."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from risk_algorithm_core.raw_input import read_raw_orders_from_batch
from risk_algorithm_core.detector_config import load_daily_detector_config

from .detector_input_snapshot import build_detector_input_snapshot_from_prepared, prepare_detector_orders
from .run_daily_detector import (
    _published_component_batch_dir,
    materialize_daily_detector_batch,
    materialize_detector_component_batch,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize date-partitioned, fact-only daily Detector batches.")
    parser.add_argument("--output-root", default="data/project_result_batches")
    parser.add_argument("--raw-batch-dir", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--schema-mapping-path")
    parser.add_argument("--resume-existing", action="store_true")
    parser.add_argument("--detector-id", action="append", dest="detector_ids")
    parser.add_argument("--detector-config", default="configs/risk_algorithm_core/daily_detector_rules.yaml")
    args = parser.parse_args(argv)
    dates = pd.date_range(_date(args.start_date), _date(args.end_date), freq="D")
    if dates.empty:
        raise ValueError("The requested Detector date range is empty.")
    raw_manifest, orders = read_raw_orders_from_batch(args.raw_batch_dir, args.schema_mapping_path)
    prepared_orders = prepare_detector_orders(orders)
    detector_config = load_daily_detector_config(args.detector_config) if args.detector_ids else None
    status_path = _status_path(args.output_root, args.run_id)
    results: list[dict[str, object]] = []
    for timestamp in dates:
        observation_date = timestamp.date().isoformat()
        if args.detector_ids:
            snapshot = build_detector_input_snapshot_from_prepared(prepared_orders, observation_date)
            for detector_id in args.detector_ids:
                existing_component = _published_component_batch_dir(
                    args.output_root,
                    observation_date,
                    detector_id,
                    detector_config.detector_version(detector_id),
                    args.run_id,
                )
                if existing_component.exists() and args.resume_existing:
                    results.append({
                        "observation_date": observation_date,
                        "detector_id": detector_id,
                        "status": "already_published",
                        "batch_dir": str(existing_component).replace("\\", "/"),
                    })
                    continue
                results.append(
                    materialize_detector_component_batch(
                        snapshot_frame=snapshot,
                        output_root=args.output_root,
                        observation_date=observation_date,
                        detector_id=detector_id,
                        run_id=args.run_id,
                        raw_batch_id=raw_manifest.raw_batch_id,
                        detector_config_path=args.detector_config,
                    )
                )
            _write_status(status_path, args, raw_manifest.raw_batch_id, results, complete=False)
            continue
        existing = _published_batch_dir(args.output_root, observation_date, args.run_id)
        if existing.exists():
            if not args.resume_existing:
                raise FileExistsError(f"Published Detector batch already exists: {existing}")
            _validate_resume_batch(existing, observation_date, raw_manifest.raw_batch_id)
            results.append({"observation_date": observation_date, "status": "already_published", "batch_dir": str(existing).replace("\\", "/")})
        else:
            results.append(
                materialize_daily_detector_batch(
                    prepared_orders=prepared_orders,
                    output_root=args.output_root,
                    observation_date=observation_date,
                    run_id=args.run_id,
                    raw_batch_id=raw_manifest.raw_batch_id,
                )
            )
        _write_status(status_path, args, raw_manifest.raw_batch_id, results, complete=False)
    _write_status(status_path, args, raw_manifest.raw_batch_id, results, complete=True)
    print(json.dumps({"stage": "daily_detector_range", "status": "completed", "dates": len(dates), "components": len(results), "status_file": str(status_path).replace("\\", "/")}, ensure_ascii=False))
    return 0


def _date(value: str) -> str:
    return datetime.fromisoformat(value).date().isoformat()


def _published_batch_dir(output_root: str | Path, observation_date: str, run_id: str) -> Path:
    return Path(output_root) / f"detector_run_date={observation_date}" / f"batch_id={observation_date}-daily-detector-fact-{run_id}"


def _validate_resume_batch(batch_dir: Path, observation_date: str, raw_batch_id: str) -> None:
    manifest = json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))
    required_tables = manifest.get("detector_tables")
    if (
        manifest.get("report_type") != "daily_detector"
        or str(manifest.get("observation_date")) != observation_date
        or str(manifest.get("source_raw_batch_id")) != raw_batch_id
        or not isinstance(required_tables, dict)
        or not all((batch_dir / str(required_tables.get(name) or "")).is_file() for name in (
            "detector_catalog", "daily_detector_runs", "daily_detector_clues", "high_risk_detector_evidence"
        ))
    ):
        raise ValueError(f"Existing Detector batch is not a resumable published result: {batch_dir}")


def _status_path(output_root: str | Path, run_id: str) -> Path:
    return Path(output_root) / f"daily_detector_range_{run_id}.json"


def _write_status(status_path: Path, args: argparse.Namespace, raw_batch_id: str, results: list[dict[str, object]], *, complete: bool) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "daily_detector_range",
        "run_id": args.run_id,
        "raw_batch_id": raw_batch_id,
        "start_date": _date(args.start_date),
        "end_date": _date(args.end_date),
        "completed": complete,
        "completed_dates": len({str(item.get("observation_date") or "") for item in results}),
        "completed_components": len(results),
        "results": results,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    temporary = status_path.with_name(f".{status_path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, status_path)


if __name__ == "__main__":
    raise SystemExit(main())
