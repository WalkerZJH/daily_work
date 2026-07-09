from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path("algo_main/data/entity_complete_v2_coverage_expansion/16_multi_month_formal_result_batches")
TARGET_MONTHS = ["2025-09", "2025-10", "2025-11", "2025-12"]


def batch_dir(month: str) -> Path:
    return ROOT / f"report_month={month}" / f"batch_id={month}-monthly-risk-algorithm-formal-v2-raw"


def test_target_months_have_formal_batches() -> None:
    for month in TARGET_MONTHS:
        current = batch_dir(month)
        assert (current / "manifest.json").exists(), month
        assert (current / "report_context.json").exists(), month
        manifest = json.loads((current / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["report_type"] == "monthly"
        assert manifest["report_month"] == month
        assert manifest["detector_score_probability_interpretation"] == "detector_score_is_not_probability"
        assert manifest["raw_orders_mode_ready"] is False
        assert manifest["fact_mode_ready"] is True
        assert manifest["conditional_fact_mode_ready"] is True
        assert "runtime_profile_summary" in manifest


def test_required_tables_exist_for_each_month() -> None:
    for month in TARGET_MONTHS:
        current = batch_dir(month)
        for table in [
            "risk_entities",
            "risk_cards",
            "risk_card_evidence",
            "monthly_reports",
            "proof_cases",
            "entity_display_lookup",
            "detector_catalog",
            "daily_detector_runs",
            "daily_detector_clues",
            "high_risk_detector_evidence",
            "risk_entity_horizon_profiles",
        ]:
            assert any((current / f"{table}.{ext}").exists() for ext in ["parquet", "csv"]), f"{month}:{table}"


def test_available_observation_contexts_has_required_dates() -> None:
    registry = pd.read_csv(ROOT / "available_observation_contexts.csv")
    assert set(["2025-10-01", "2025-11-01", "2025-12-01", "2025-12-05", "2026-01-01"]).issubset(
        set(registry["observation_date"].astype(str))
    )

