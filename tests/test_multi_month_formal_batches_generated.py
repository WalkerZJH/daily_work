from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path("data/project_result_batches")
TARGET_MONTHS = ["2025-09", "2025-10", "2025-11", "2025-12"]


def batch_dir(month: str) -> Path:
    return ROOT / f"report_month={month}" / f"batch_id={month}-monthly-risk-algorithm-formal-v2-raw"


def test_target_months_have_formal_batches() -> None:
    for month in TARGET_MONTHS:
        current = batch_dir(month)
        assert (current / "manifest.json").exists(), month
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
            assert (current / f"{table}.parquet").exists(), f"{month}:{table}"


def test_available_observation_contexts_has_required_dates() -> None:
    registry = pd.read_parquet(ROOT / "available_observation_contexts.parquet")
    assert set(["2025-10-01", "2025-11-01", "2025-12-01", "2025-12-05", "2026-01-01"]).issubset(
        set(registry["observation_date"].astype(str))
    )


def test_each_target_month_has_next_month_daily_detector_runs() -> None:
    for month in TARGET_MONTHS:
        current = batch_dir(month)
        runs = read_table(current, "daily_detector_runs")
        run_dates = set(runs["run_date"].astype(str))
        year, mon = [int(part) for part in month.split("-")]
        if mon == 12:
            year, mon = year + 1, 1
        else:
            mon += 1
        expected_days = pd.date_range(f"{year:04d}-{mon:02d}-01", periods=pd.Period(f"{year:04d}-{mon:02d}").days_in_month)
        assert {day.date().isoformat() for day in expected_days} == run_dates


def read_table(batch: Path, name: str) -> pd.DataFrame:
    parquet = batch / f"{name}.parquet"
    if parquet.exists():
        return pd.read_parquet(parquet)
    return pd.read_csv(batch / f"{name}.csv")
