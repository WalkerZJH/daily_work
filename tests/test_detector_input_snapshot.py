from __future__ import annotations

import json
import pandas as pd
from risk_result_contracts import write_production_parquet


def test_daily_detector_snapshot_uses_only_orders_as_of_observation_date() -> None:
    from production_pipeline.detector_input_snapshot import build_detector_input_snapshot

    orders = pd.DataFrame(
        [
            {"order_date": "2025-01-01", "manufacturer_code": "m1", "hospital_code": "h1", "drug_code": "d1", "order_quantity": 10},
            {"order_date": "2025-01-11", "manufacturer_code": "m1", "hospital_code": "h1", "drug_code": "d1", "order_quantity": 20},
            {"order_date": "2025-01-21", "manufacturer_code": "m1", "hospital_code": "h1", "drug_code": "d1", "order_quantity": 30},
            {"order_date": "2025-02-20", "manufacturer_code": "m1", "hospital_code": "h1", "drug_code": "d1", "order_quantity": 999},
        ]
    )

    snapshot = build_detector_input_snapshot(orders, "2025-02-01")

    row = snapshot.iloc[0]
    assert row["entity_id"] == "m1|h1|d1"
    assert row["purchase_count_total"] == 3
    assert row["days_since_last_purchase"] == 11
    assert row["historical_interval_median"] == 10.0
    assert row["historical_interval_mad"] == 0.0
    assert row["recent_quantity"] == 60.0
    assert row["baseline_quantity"] == 0.0
    assert "churn_probability_H" not in snapshot.columns


def test_daily_detector_stage_reads_snapshot_without_monthly_runner(tmp_path) -> None:
    from production_pipeline.run_daily_detector import main

    snapshot = pd.DataFrame(
        [{"entity_id": "m1|h1|d1", "tenant_id": "default_tenant", "manufacturer_code": "m1", "hospital_code": "h1", "drug_group": "d1", "days_since_last_purchase": 80, "historical_interval_median": 30, "historical_interval_mad": 10, "purchase_count_total": 12, "quantity_ratio": 0.4, "frequency_ratio": 0.4, "purchase_frequency_baseline": 2.0}]
    )
    write_production_parquet(snapshot, tmp_path / "detector_input_snapshot.parquet")
    (tmp_path / "manifest.json").write_text(json.dumps({"batch_id": "fixture", "detector_tables": {}}), encoding="utf-8")

    assert main(["--batch-dir", str(tmp_path), "--observation-date", "2025-02-01"]) == 0
    clues = pd.read_parquet(tmp_path / "daily_detector_clues.parquet")
    assert not clues.empty
    assert clues["risk_entity_id"].isna().all()
    assert clues["monthly_risk_probability"].isna().all()
