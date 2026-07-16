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

from risk_algorithm_core.daily_detector_runner import build_daily_detector_tables
from risk_algorithm_core.detector_config import load_daily_detector_config
from risk_algorithm_core.detector_config_profiles import load_detector_config_profiles
from risk_algorithm_core.detector_component_validation import validate_detector_component_tables
from risk_algorithm_core.detector_input import filter_detector_eligible_orders, load_cleaned_detector_orders
from risk_result_contracts import write_production_parquet

from .detector_input_snapshot import build_detector_input_snapshot_from_prepared, prepare_detector_orders


DETECTOR_TABLE_NAMES = (
    "detector_catalog",
    "detector_config_profiles",
    "detector_run_config_snapshot",
    "daily_detector_runs",
    "daily_detector_results",
    "daily_detector_clues",
    "high_risk_detector_evidence",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize one independent, fact-only daily Detector batch."
    )
    parser.add_argument("--output-root", default="data/project_result_batches")
    parser.add_argument("--raw-batch-dir", required=True, help="Cleaned Detector input batch directory")
    parser.add_argument("--observation-date", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--detector-id",
        action="append",
        dest="detector_ids",
        required=True,
        help="Publish only this Detector component; repeat to publish multiple independent components.",
    )
    parser.add_argument("--detector-config", default="configs/risk_algorithm_core/daily_detector_rules.yaml")
    parser.add_argument("--detector-config-profiles", required=True)
    parser.add_argument("--manufacturer-code", action="append", dest="manufacturer_codes")
    args = parser.parse_args(argv)
    observation_date = _normalize_observation_date(args.observation_date)
    input_manifest, orders = load_cleaned_detector_orders(args.raw_batch_dir)
    eligible_orders, _eligibility_audit = filter_detector_eligible_orders(orders)
    if args.manufacturer_codes:
        requested = {str(value).strip() for value in args.manufacturer_codes if str(value).strip()}
        eligible_orders = eligible_orders.loc[
            eligible_orders["manufacturer_code"].astype(str).isin(requested)
        ].copy()
        missing = sorted(requested - set(eligible_orders["manufacturer_code"].astype(str)))
        if missing:
            raise ValueError(f"Requested manufacturer codes have no eligible cleaned orders: {missing}")
    prepared_orders = prepare_detector_orders(eligible_orders)
    snapshot = build_detector_input_snapshot_from_prepared(prepared_orders, observation_date)
    config_profiles = load_detector_config_profiles(args.detector_config_profiles)
    results = [
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
        for detector_id in args.detector_ids
    ]
    print(json.dumps({"stage": "daily_detector_components", "status": "completed", "results": results}, ensure_ascii=False))
    return 0


def materialize_detector_component_batch(
    *,
    snapshot_frame: pd.DataFrame,
    output_root: str | Path,
    observation_date: str,
    detector_id: str,
    run_id: str,
    raw_batch_id: str,
    detector_config_path: str | Path | None = None,
    config_profiles: pd.DataFrame | None = None,
) -> dict[str, object]:
    """Publish one immutable Detector component without touching its peers."""
    config = load_daily_detector_config(detector_config_path)
    detector_version = config.detector_version(detector_id)
    batch_dir = _published_component_batch_dir(
        output_root, observation_date, detector_id, detector_version, run_id
    )
    _validate_windows_readable_publish_path(batch_dir)
    if batch_dir.exists():
        raise FileExistsError(f"Refusing to overwrite published Detector component: {batch_dir}")
    batch_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(output_root) / ".detector_staging" / uuid.uuid4().hex
    try:
        staging_dir.mkdir(parents=True, exist_ok=False)
        tables = build_daily_detector_tables(
            risk_entities=pd.DataFrame(),
            scan_features=snapshot_frame,
            report_month=_expected_probability_report_month(observation_date),
            run_date=observation_date,
            source_raw_batch_id=raw_batch_id,
            source_result_batch_id="",
            detector_config=config,
            detector_ids=[detector_id],
            config_profiles=config_profiles,
        )
        if tables["daily_detector_results"]["eligibility_status"].astype(str).eq("config_missing").any():
            missing = sorted(
                tables["daily_detector_results"].loc[
                    tables["daily_detector_results"]["eligibility_status"].astype(str).eq("config_missing"),
                    "manufacturer_code",
                ].astype(str).unique()
            )
            raise ValueError(
                f"Refusing to publish {detector_id}; manufacturer-specific configs are missing: {missing}"
            )
        validation = validate_detector_component_tables(
            tables,
            detector_id=detector_id,
            observation_date=observation_date,
        )
        for table_name in DETECTOR_TABLE_NAMES:
            write_production_parquet(tables[table_name], staging_dir / f"{table_name}.parquet")
        (staging_dir / "detector_validation_report.json").write_text(
            json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        batch_id = batch_dir.name.removeprefix("batch_id=")
        payload = {
            "batch_id": batch_id,
            "result_batch_id": batch_id,
            "report_type": "daily_detector_component",
            "schema_version": "daily_detector_component_v2",
            "data_backend": "parquet",
            "observation_date": observation_date,
            "detector_run_date": observation_date,
            "expected_probability_report_month": _expected_probability_report_month(observation_date),
            "detector_id": detector_id,
            "detector_version": detector_version,
            "detector_run_id": str(tables["daily_detector_runs"].iloc[0]["detector_run_id"]),
            "source_raw_batch_id": raw_batch_id,
            "source_cleaned_input_batch_id": raw_batch_id,
            "detector_tables": {name: f"{name}.parquet" for name in DETECTOR_TABLE_NAMES},
            "detector_validation_report": "detector_validation_report.json",
            "engineering_gate_status": validation["engineering_gate_status"],
            "business_gate_status": validation["business_gate_status"],
            "detector_score_probability_interpretation": "detector_score_is_not_probability",
            "caveats": [
                "detector_score_is_not_probability",
                "daily_detector_uses_cleaned_purchase_facts_only",
                "no_monthly_model_dependency",
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        (staging_dir / "manifest.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        _publish_staging_directory(staging_dir, batch_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    return {
        "detector_id": detector_id,
        "detector_version": detector_version,
        "observation_date": observation_date,
        "batch_dir": str(batch_dir).replace("\\", "/"),
        "result_count": len(tables["daily_detector_results"]),
        "clue_count": len(tables["daily_detector_clues"]),
    }


def _expected_probability_report_month(observation_date: str) -> str:
    current = datetime.fromisoformat(observation_date).date().replace(day=1)
    previous = current.replace(day=1) - pd.Timedelta(days=1)
    return previous.strftime("%Y-%m")


def _normalize_observation_date(value: str) -> str:
    return datetime.fromisoformat(value).date().isoformat()


def _published_component_batch_dir(
    output_root: str | Path,
    observation_date: str,
    detector_id: str,
    detector_version: str,
    run_id: str,
) -> Path:
    for label, value in {"detector_id": detector_id, "detector_version": detector_version, "run_id": run_id}.items():
        if not str(value).strip() or any(character in str(value) for character in "\\/:"):
            raise ValueError(f"{label} must be a non-empty path-safe identifier")
    batch_id = f"{observation_date}-{run_id}"
    return (
        Path(output_root)
        / f"detector_run_date={observation_date}"
        / f"detector_id={detector_id}"
        / f"batch_id={batch_id}"
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


def _validate_windows_readable_publish_path(batch_dir: Path) -> None:
    """Fail before writing when normal Python/registry APIs cannot reopen the batch."""
    if os.name != "nt":
        return
    manifest_path = (batch_dir / "manifest.json").resolve()
    if len(str(manifest_path)) >= 240:
        raise ValueError(
            "Detector publish path is too long for reliable Windows/Python reads "
            f"({len(str(manifest_path))} chars): {manifest_path}. Use a shorter --output-root or --run-id."
        )


if __name__ == "__main__":
    raise SystemExit(main())
