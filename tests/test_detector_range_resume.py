from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import production_pipeline.materialize_daily_detector_range as module
from risk_algorithm_core.detector_config import load_daily_detector_config


def test_resume_complete_date_skips_snapshot_build(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "results"
    raw = tmp_path / "clean-input"
    raw.mkdir()
    (raw / "manifest.json").write_text(json.dumps({
            "input_batch_id": "clean-fixture",
            "input_stage": "cleaned_detector_facts",
            "table_paths": {"orders": "orders.parquet"},
            "cleaning_contract": {
                "version": "cleaned_detector_input_v1",
                "canonical_status_mapping_applied": True,
                "direct_purchase_unit_price_only": True,
            },
    }), encoding="utf-8")
    pd.DataFrame([{
        "row_uid": "r1", "order_id": "o1", "order_date": "2025-01-01", "manufacturer_code": "m1",
        "hospital_code": "h1", "drug_code": "d1", "order_quantity": 1,
        "order_amount": 10, "purchase_unit": "box", "purchase_unit_price": 10,
        "order_phase_code": 60, "order_terminal_flag": 1, "order_failure_flag": 0,
        "needs_manual_review": False,
    }]).to_parquet(raw / "orders.parquet", index=False)
    detector_id = "purchase_interval_ipi"
    config = load_daily_detector_config()
    published = module._published_component_batch_dir(
        root, "2025-01-01", detector_id, config.detector_version(detector_id), "resume-v1"
    )
    published.mkdir(parents=True)
    monkeypatch.setattr(
        module,
        "build_detector_input_snapshot_from_prepared",
        lambda *_: (_ for _ in ()).throw(AssertionError("snapshot must not be rebuilt")),
    )

    assert module.main([
        "--output-root", str(root), "--raw-batch-dir", str(raw),
        "--start-date", "2025-01-01", "--end-date", "2025-01-01",
        "--run-id", "resume-v1", "--detector-id", detector_id, "--resume-existing",
    ]) == 0
    status = json.loads((root / "daily_detector_range_resume-v1.json").read_text(encoding="utf-8"))
    assert status["completed"] is True
    assert status["completed_dates"] == 1
    assert status["results"][0]["status"] == "already_published"
