from __future__ import annotations

import argparse
import json
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from risk_algorithm_core.raw_input import read_raw_orders_from_batch
from risk_algorithm_core.daily_detector_runner import build_daily_detector_tables
from risk_result_contracts import write_production_parquet

from .detector_input_snapshot import build_detector_input_snapshot_from_prepared, prepare_detector_orders


DETECTOR_TABLE_NAMES = (
    "detector_catalog",
    "daily_detector_runs",
    "daily_detector_clues",
    "high_risk_detector_evidence",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize one independent, fact-only daily Detector batch."
    )
    parser.add_argument("--output-root", default="data/project_result_batches")
    parser.add_argument("--raw-batch-dir", required=True)
    parser.add_argument("--observation-date", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--schema-mapping-path")
    args = parser.parse_args(argv)
    observation_date = _normalize_observation_date(args.observation_date)
    raw_manifest, orders = read_raw_orders_from_batch(args.raw_batch_dir, args.schema_mapping_path)
    result = materialize_daily_detector_batch(
        prepared_orders=prepare_detector_orders(orders),
        output_root=args.output_root,
        observation_date=observation_date,
        run_id=args.run_id,
        raw_batch_id=raw_manifest.raw_batch_id,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


def materialize_daily_detector_batch(
    *,
    prepared_orders: pd.DataFrame,
    output_root: str | Path,
    observation_date: str,
    run_id: str,
    raw_batch_id: str,
) -> dict[str, object]:
    """Publish one immutable fact-only Detector date partition atomically."""
    batch_dir = _published_batch_dir(output_root, observation_date, run_id)
    if batch_dir.exists():
        raise FileExistsError(
            "Refusing to overwrite published daily Detector batch: "
            f"{batch_dir}. Use a new --run-id for a new immutable run."
        )
    # Keep the temporary path short on Windows. PyArrow appends another
    # temporary filename while writing, so a descriptive final partition path
    # can otherwise exceed the legacy Windows path limit.
    batch_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(output_root) / ".detector_staging" / uuid.uuid4().hex
    try:
        staging_dir.mkdir(parents=True, exist_ok=False)
        (staging_dir / "materialization_status.json").write_text(
            json.dumps(
                {"stage": "daily_detector", "status": "running", "observation_date": observation_date},
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )
        snapshot_frame = build_detector_input_snapshot_from_prepared(prepared_orders, observation_date)
        tables = build_daily_detector_tables(
            risk_entities=pd.DataFrame(),
            scan_features=snapshot_frame,
            report_month=_expected_probability_report_month(observation_date),
            run_date=observation_date,
            source_raw_batch_id=raw_batch_id,
            source_result_batch_id="",
        )
        write_production_parquet(snapshot_frame, staging_dir / "detector_input_snapshot.parquet")
        for table_name in DETECTOR_TABLE_NAMES:
            write_production_parquet(tables[table_name], staging_dir / f"{table_name}.parquet")
        _write_manifest(
            staging_dir,
            batch_id=batch_dir.name.removeprefix("batch_id="),
            observation_date=observation_date,
            run_id=run_id,
            raw_batch_id=raw_batch_id,
            tables=tables,
        )
        (staging_dir / "materialization_status.json").unlink(missing_ok=True)
        _publish_staging_directory(staging_dir, batch_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    return {
        "stage": "daily_detector",
        "status": "completed",
        "observation_date": observation_date,
        "batch_dir": str(batch_dir).replace("\\", "/"),
        "clue_count": len(tables["daily_detector_clues"]),
    }


def _expected_probability_report_month(observation_date: str) -> str:
    current = datetime.fromisoformat(observation_date).date().replace(day=1)
    previous = current.replace(day=1) - pd.Timedelta(days=1)
    return previous.strftime("%Y-%m")


def _normalize_observation_date(value: str) -> str:
    return datetime.fromisoformat(value).date().isoformat()


def _published_batch_dir(output_root: str | Path, observation_date: str, run_id: str) -> Path:
    normalized_run_id = str(run_id).strip()
    if not normalized_run_id or any(character in normalized_run_id for character in "\\/:"):
        raise ValueError("--run-id must be a non-empty path-safe identifier")
    batch_id = f"{observation_date}-daily-detector-fact-{normalized_run_id}"
    return Path(output_root) / f"detector_run_date={observation_date}" / f"batch_id={batch_id}"


def _write_manifest(
    batch_dir: Path,
    *,
    batch_id: str,
    observation_date: str,
    run_id: str,
    raw_batch_id: str,
    tables: dict,
) -> None:
    payload = {
        "batch_id": batch_id,
        "result_batch_id": batch_id,
        "report_type": "daily_detector",
        "schema_version": "daily_detector_batch_v1",
        "data_backend": "parquet",
        "observation_date": observation_date,
        "detector_run_date": observation_date,
        "expected_probability_report_month": _expected_probability_report_month(observation_date),
        "detector_run_id": str(tables["daily_detector_runs"].iloc[0].get("detector_run_id") or run_id)
        if not tables["daily_detector_runs"].empty
        else "",
        "source_raw_batch_id": raw_batch_id,
        "detector_tables": {name: f"{name}.parquet" for name in DETECTOR_TABLE_NAMES},
        "detector_input_snapshot": "detector_input_snapshot.parquet",
        "detector_default_scope": "independent_detector_batch",
        "detector_score_probability_interpretation": "detector_score_is_not_probability",
        "caveats": [
            "detector_score_is_not_probability",
            "rule_only_does_not_create_risk_entity",
            "daily_detector_uses_raw_purchase_facts_only",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (batch_dir / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _publish_staging_directory(staging_dir: Path, batch_dir: Path) -> None:
    """Retry the Windows directory rename when a scanner briefly holds a handle."""
    last_error: PermissionError | None = None
    for attempt in range(5):
        try:
            os.replace(staging_dir, batch_dir)
            return
        except PermissionError as exc:
            last_error = exc
            if attempt == 4:
                break
            time.sleep(1.0 * (attempt + 1))
    assert last_error is not None
    raise last_error


if __name__ == "__main__":
    raise SystemExit(main())
