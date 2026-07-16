from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from production_pipeline.run_daily_detector import materialize_detector_component_batch
from production_pipeline.validate_detector_backfill import main as validate_backfill
from risk_algorithm_core.detector_config import load_daily_detector_config


def test_backfill_validator_checks_every_date_and_detector_component(tmp_path: Path) -> None:
    root = tmp_path / "results"
    snapshot = pd.DataFrame([{
        "entity_id": "m1|h1|d1", "manufacturer_code": "m1", "hospital_code": "h1",
        "drug_group": "d1", "days_since_last_purchase": 60,
        "historical_interval_median": 20, "historical_interval_mad": 5,
        "purchase_count_total": 12,
    }])
    config = load_daily_detector_config()
    for detector_id in config.runnable_detector_ids():
        materialize_detector_component_batch(
            snapshot_frame=snapshot, output_root=root, observation_date="2025-01-01",
            detector_id=detector_id, run_id="zz-test-full", raw_batch_id="clean-fixture",
        )
    report_json = tmp_path / "validation.json"
    report_md = tmp_path / "validation.md"
    assert validate_backfill([
        "--batch-root", str(root), "--start-date", "2025-01-01", "--end-date", "2025-01-01",
        "--source-batch-id", "clean-fixture", "--required-run-prefix", "zz-test-full",
        "--report-json", str(report_json), "--report-md", str(report_md),
    ]) == 0
    payload = json.loads(report_json.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert payload["selected_component_count"] == 10
    assert payload["observation_date_count"] == 1
    assert payload["issues"] == []
