"""Split legacy date-wide Detector batches into independently publishable components."""

from __future__ import annotations

import argparse
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from risk_algorithm_core.detector_config import load_daily_detector_config
from risk_algorithm_core.detector_results import DAILY_DETECTOR_RUN_COLUMNS
from risk_result_contracts import write_production_parquet

from .run_daily_detector import DETECTOR_TABLE_NAMES, _expected_probability_report_month, _publish_staging_directory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Split immutable date-wide Detector Parquet into detector_id components.")
    parser.add_argument("--batch-root", default="data/project_result_batches")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--detector-config", default="configs/risk_algorithm_core/daily_detector_rules.yaml")
    parser.add_argument("--resume-existing", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.batch_root)
    config = load_daily_detector_config(args.detector_config)
    results: list[dict[str, object]] = []
    for timestamp in pd.date_range(args.start_date, args.end_date, freq="D"):
        run_date = timestamp.date().isoformat()
        source = _latest_aggregate_batch(root, run_date)
        if source is None:
            raise FileNotFoundError(f"No legacy aggregate Detector batch for {run_date}")
        results.extend(_split_batch(source, root, run_date, args.run_id, config, args.resume_existing))
    status = {
        "stage": "split_daily_detector_batches",
        "status": "completed",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "component_batch_count": len(results),
        "results": results,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    status_path = root / "run_metadata" / f"run_id={args.run_id}" / "detector_component_split.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in status.items() if key != "results"}, ensure_ascii=False))
    return 0


def _latest_aggregate_batch(root: Path, run_date: str) -> Path | None:
    manifests = sorted(root.glob(f"detector_run_date={run_date}/batch_id=*/manifest.json"), reverse=True)
    return manifests[0].parent if manifests else None


def _split_batch(source: Path, root: Path, run_date: str, run_id: str, config, resume: bool) -> list[dict[str, object]]:
    source_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    tables = {name: pd.read_parquet(source / f"{name}.parquet") for name in DETECTOR_TABLE_NAMES}
    source_run = tables["daily_detector_runs"].iloc[0].to_dict()
    enabled = [item for item in str(source_run.get("enabled_detectors") or "").split(",") if item]
    clue_ids = set(tables["daily_detector_clues"].get("detector_id", pd.Series(dtype=str)).dropna().astype(str))
    detector_ids = list(dict.fromkeys([*enabled, *sorted(clue_ids)]))
    results = []
    split_clue_count = 0
    for detector_id in detector_ids:
        version = config.detector_version(detector_id)
        batch_id = f"{run_date}-{run_id}"
        target = root / f"detector_run_date={run_date}" / f"detector_id={detector_id}" / f"batch_id={batch_id}"
        if target.exists():
            if not resume:
                raise FileExistsError(f"Refusing to overwrite Detector component: {target}")
            results.append({"run_date": run_date, "detector_id": detector_id, "status": "already_published", "batch_dir": _path(target)})
            continue
        catalog = tables["detector_catalog"].loc[
            tables["detector_catalog"]["detector_id"].astype(str).eq(detector_id)
        ].reset_index(drop=True)
        clues = tables["daily_detector_clues"].loc[
            tables["daily_detector_clues"]["detector_id"].astype(str).eq(detector_id)
        ].copy().reset_index(drop=True)
        evidence = tables["high_risk_detector_evidence"].loc[
            tables["high_risk_detector_evidence"]["detector_id"].astype(str).eq(detector_id)
        ].copy().reset_index(drop=True)
        component_run_id = f"{source_run.get('report_month')}-{detector_id}-{version}-{run_date}"
        for frame in (clues, evidence):
            if "detector_run_id" in frame:
                frame["detector_run_id"] = component_run_id
        if "display_rank" in clues:
            clues["display_rank"] = range(1, len(clues) + 1)
        run = pd.DataFrame([{**source_run, "detector_run_id": component_run_id, "detector_id": detector_id,
                             "detector_version": version, "detector_config_version": version,
                             "enabled_detectors": detector_id, "clue_count": len(clues),
                             "attached_high_risk_count": len(evidence)}])
        for column in DAILY_DETECTOR_RUN_COLUMNS:
            if column not in run:
                run[column] = pd.NA
        component_tables = {
            "detector_catalog": catalog,
            "daily_detector_runs": run[DAILY_DETECTOR_RUN_COLUMNS],
            "daily_detector_clues": clues,
            "high_risk_detector_evidence": evidence,
        }
        _publish_component(target, component_tables, source_manifest, detector_id, version, component_run_id, run_id)
        split_clue_count += len(clues)
        results.append({"run_date": run_date, "detector_id": detector_id, "status": "published",
                        "batch_dir": _path(target), "clue_count": len(clues)})
    if not resume and split_clue_count != len(tables["daily_detector_clues"]):
        raise ValueError(f"Clue row conservation failed for {run_date}: {split_clue_count} != {len(tables['daily_detector_clues'])}")
    return results


def _publish_component(target: Path, tables: dict[str, pd.DataFrame], source_manifest: dict, detector_id: str,
                       version: str, detector_run_id: str, run_id: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parents[2] / ".detector_staging" / uuid.uuid4().hex
    try:
        staging.mkdir(parents=True, exist_ok=False)
        for name, frame in tables.items():
            write_production_parquet(frame, staging / f"{name}.parquet")
        payload = {
            "batch_id": target.name.removeprefix("batch_id="), "result_batch_id": target.name.removeprefix("batch_id="),
            "report_type": "daily_detector_component", "schema_version": "daily_detector_component_v1",
            "data_backend": "parquet", "observation_date": source_manifest["observation_date"],
            "detector_run_date": source_manifest["detector_run_date"],
            "expected_probability_report_month": source_manifest.get("expected_probability_report_month") or _expected_probability_report_month(source_manifest["observation_date"]),
            "detector_id": detector_id, "detector_version": version, "detector_run_id": detector_run_id,
            "source_raw_batch_id": source_manifest.get("source_raw_batch_id", ""),
            "source_aggregate_batch_id": source_manifest.get("batch_id", ""), "migration_run_id": run_id,
            "detector_tables": {name: f"{name}.parquet" for name in DETECTOR_TABLE_NAMES},
            "caveats": source_manifest.get("caveats", []), "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        (staging / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _publish_staging_directory(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _path(path: Path) -> str:
    return str(path).replace("\\", "/")


if __name__ == "__main__":
    raise SystemExit(main())
