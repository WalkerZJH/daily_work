from __future__ import annotations

from pathlib import Path

import pandas as pd


BATCH_DIR = Path("data/entity_complete_v2_coverage_expansion/11_business_detector_adaptation/risk_result_batches/batch_id=2025-12-business-detector-v1")
REPORT_DIR = Path("reports/entity_complete_v2_coverage_expansion/15_business_detector_adaptation")


def test_one_shot_does_not_show_recurring_churn_probability() -> None:
    entities = pd.read_parquet(BATCH_DIR / "risk_entities.parquet", columns=["is_one_shot", "palive_display", "risk_probability_value"])
    one_shot = entities[entities["is_one_shot"]]

    assert not one_shot.empty
    assert one_shot["risk_probability_value"].isna().all()
    assert one_shot["palive_display"].astype(str).str.contains("不展示|涓嶅睍绀", regex=True).all()


def test_demand_shape_observation_is_not_high_risk() -> None:
    entities = pd.read_parquet(BATCH_DIR / "risk_entities.parquet", columns=["is_observation", "is_high_risk", "risk_level"])
    observation = entities[entities["is_observation"]]

    assert not observation.empty
    assert observation["is_high_risk"].eq(False).all()
    assert not observation["risk_level"].isin(["red", "orange"]).any()


def test_adaptation_reports_exist() -> None:
    assert (REPORT_DIR / "one_shot_frontend_adaptation.md").exists()
    assert (REPORT_DIR / "demand_shape_frontend_adaptation.md").exists()
    assert (REPORT_DIR / "business_adaptation_gap_list.md").exists()
    assert (REPORT_DIR / "export_readiness_for_reports.md").exists()

