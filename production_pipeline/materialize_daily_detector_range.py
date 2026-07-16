"""Materialize independent daily Detector partitions from one raw-fact read."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from risk_algorithm_core.detector_config import load_daily_detector_config
from risk_algorithm_core.detector_config_profiles import load_detector_config_profiles
from risk_algorithm_core.detector_input import filter_detector_eligible_orders, load_cleaned_detector_orders

from .detector_input_snapshot import build_detector_input_snapshot_from_prepared, prepare_detector_orders
from .run_daily_detector import (
    _published_component_batch_dir,
    materialize_detector_component_batch,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize date-partitioned, fact-only daily Detector batches.")
    parser.add_argument("--output-root", default="data/project_result_batches")
    parser.add_argument("--raw-batch-dir", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--resume-existing", action="store_true")
    parser.add_argument("--detector-id", action="append", dest="detector_ids", required=True)
    parser.add_argument("--detector-config", default="configs/risk_algorithm_core/daily_detector_rules.yaml")
    parser.add_argument("--detector-config-profiles", required=True)
    parser.add_argument("--manufacturer-code", action="append", dest="manufacturer_codes")
    args = parser.parse_args(argv)
    dates = pd.date_range(_date(args.start_date), _date(args.end_date), freq="D")
    if dates.empty:
        raise ValueError("The requested Detector date range is empty.")
    input_manifest, orders = load_cleaned_detector_orders(args.raw_batch_dir)
    orders, _eligibility_audit = filter_detector_eligible_orders(orders)
    if args.manufacturer_codes:
        requested = {str(value).strip() for value in args.manufacturer_codes if str(value).strip()}
        orders = orders.loc[orders["manufacturer_code"].astype(str).isin(requested)].copy()
    prepared_orders = prepare_detector_orders(orders)
    detector_config = load_daily_detector_config(args.detector_config)
    config_profiles = load_detector_config_profiles(args.detector_config_profiles)
    status_path = _status_path(args.output_root, args.run_id)
    results: list[dict[str, object]] = []
    for timestamp in dates:
        observation_date = timestamp.date().isoformat()
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
                    raw_batch_id=input_manifest.input_batch_id,
                    detector_config_path=args.detector_config,
                    config_profiles=config_profiles,
                )
            )
        _write_status(status_path, args, input_manifest.input_batch_id, results, complete=False)
    _write_status(status_path, args, input_manifest.input_batch_id, results, complete=True)
    print(json.dumps({"stage": "daily_detector_range", "status": "completed", "dates": len(dates), "components": len(results), "status_file": str(status_path).replace("\\", "/")}, ensure_ascii=False))
    return 0


def _date(value: str) -> str:
    return datetime.fromisoformat(value).date().isoformat()


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
