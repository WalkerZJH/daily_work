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


def test_daily_detector_stage_publishes_independent_batch_without_monthly_runner(tmp_path) -> None:
    from production_pipeline.run_daily_detector import main
    from risk_algorithm_core.detector_config import load_daily_detector_config
    from risk_algorithm_core.detector_config_profiles import build_manufacturer_config_profiles
    from risk_model_core.repositories import ParquetRiskResultRepository

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "manifest.json").write_text(
        json.dumps(
            {
                "input_batch_id": "clean-fixture",
                "input_stage": "cleaned_detector_facts",
                "source_system": "test_cleaning_chain",
                "table_format": "parquet",
                "table_paths": {"orders": "orders.parquet"},
                "cleaning_contract": {
                    "version": "fixture_v1",
                    "canonical_status_mapping_applied": True,
                    "direct_purchase_unit_price_only": True,
                },
            }
        ),
        encoding="utf-8",
    )
    orders = pd.DataFrame(
        [
            {"row_uid": "r0", "order_id": "o0", "order_date": "2024-10-01", "manufacturer_code": "m1", "hospital_code": "h1", "drug_code": "d1", "order_quantity": 10, "order_amount": 100, "purchase_unit": "盒", "purchase_unit_price": 10, "order_phase_code": 60, "order_terminal_flag": 1, "order_failure_flag": 0, "needs_manual_review": False},
            {"row_uid": "r1", "order_id": "o1", "order_date": "2024-11-01", "manufacturer_code": "m1", "hospital_code": "h1", "drug_code": "d1", "order_quantity": 10, "order_amount": 100, "purchase_unit": "盒", "purchase_unit_price": 10, "order_phase_code": 60, "order_terminal_flag": 1, "order_failure_flag": 0, "needs_manual_review": False},
            {"row_uid": "r2", "order_id": "o2", "order_date": "2024-12-01", "manufacturer_code": "m1", "hospital_code": "h1", "drug_code": "d1", "order_quantity": 10, "order_amount": 100, "purchase_unit": "盒", "purchase_unit_price": 10, "order_phase_code": 70, "order_terminal_flag": 1, "order_failure_flag": 0, "needs_manual_review": False},
            {"row_uid": "r3", "order_id": "o3", "order_date": "2025-01-01", "manufacturer_code": "m1", "hospital_code": "h1", "drug_code": "d1", "order_quantity": 10, "order_amount": 100, "purchase_unit": "盒", "purchase_unit_price": 10, "order_phase_code": 80, "order_terminal_flag": 1, "order_failure_flag": 0, "needs_manual_review": False},
        ]
    )
    write_production_parquet(orders, raw / "orders.parquet")
    profiles = build_manufacturer_config_profiles(
        ["m1"], load_daily_detector_config(), detector_ids=["purchase_interval_ipi"]
    )
    profiles["effective_from"] = "1900-01-01"
    profile_path = tmp_path / "profiles.parquet"
    write_production_parquet(profiles, profile_path)

    assert main([
        "--output-root", str(tmp_path / "results"), "--raw-batch-dir", str(raw),
        "--observation-date", "2025-02-20", "--run-id", "fixture",
        "--detector-id", "purchase_interval_ipi", "--detector-config-profiles", str(profile_path),
    ]) == 0
    batch = tmp_path / "results" / "detector_run_date=2025-02-20" / "detector_id=purchase_interval_ipi" / "batch_id=2025-02-20-fixture"
    clues = pd.read_parquet(batch / "daily_detector_clues.parquet")
    assert not clues.empty
    assert clues["risk_entity_id"].isna().all()
    assert clues["monthly_risk_probability"].isna().all()
    assert not (batch / "risk_entities.parquet").exists()
    repository = ParquetRiskResultRepository(batch)
    assert repository.manifest().report_type == "daily_detector_component"
    assert len(repository.list_daily_detector_runs()) == 1


def test_independent_detector_run_is_available_without_monthly_batch_and_never_date_falls_back(tmp_path) -> None:
    from production_pipeline.rebuild_observation_registry import main as rebuild_registry
    from risk_model_core.repositories import resolve_observation_context_from_rows

    batch = tmp_path / "results" / "detector_run_date=2025-12-05" / "batch_id=2025-12-05-daily-detector-fact-fixture"
    batch.mkdir(parents=True)
    (batch / "manifest.json").write_text(
        json.dumps(
            {
                "batch_id": "2025-12-05-daily-detector-fact-fixture",
                "report_type": "daily_detector",
                "detector_tables": {
                    "detector_catalog": "detector_catalog.parquet",
                    "daily_detector_runs": "daily_detector_runs.parquet",
                    "daily_detector_clues": "daily_detector_clues.parquet",
                    "high_risk_detector_evidence": "high_risk_detector_evidence.parquet",
                },
            }
        ),
        encoding="utf-8",
    )
    write_production_parquet(pd.DataFrame([{"detector_id": "purchase_interval_ipi"}]), batch / "detector_catalog.parquet")
    write_production_parquet(pd.DataFrame([{"detector_run_id": "dr-2025-12-05", "run_date": "2025-12-05"}]), batch / "daily_detector_runs.parquet")
    write_production_parquet(pd.DataFrame([{"detector_clue_id": "dc-1", "run_date": "2025-12-05", "manufacturer_code": "m1"}]), batch / "daily_detector_clues.parquet")
    write_production_parquet(pd.DataFrame([{"risk_entity_id": None}]), batch / "high_risk_detector_evidence.parquet")

    assert rebuild_registry(["--batch-root", str(tmp_path / "results")]) == 0
    contexts = pd.read_parquet(tmp_path / "results" / "observation_registry.parquet")
    exact = resolve_observation_context_from_rows(contexts, observation_date="2025-12-05")
    assert exact["probability_batch_available"] is False
    assert exact["detector_run_available"] is True
    assert exact["detector_batch_dir"].endswith("detector_run_date=2025-12-05/batch_id=2025-12-05-daily-detector-fact-fixture")

    unavailable = resolve_observation_context_from_rows(contexts, observation_date="2025-12-06")
    assert unavailable["detector_run_available"] is False
    assert unavailable["detector_batch_dir"] is None
