from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd


def _sample_scored_rows() -> pd.DataFrame:
    rows = []
    for manufacturer, count in [("m1", 10), ("m2", 10), ("m3", 2)]:
        for idx in range(count):
            rows.append(
                {
                    "manufacturer_code": manufacturer,
                    "hospital_code": f"h{idx}",
                    "drug_group": f"d{idx}",
                    "drug_group_source": "drug_code",
                    "cutoff_month": "2024-01",
                    "horizon": 6,
                    "churn_probability_H": 0.5 + idx / 100,
                    "relative_value_at_risk_H": float(100 + idx),
                    "relative_business_priority_score_H": (0.5 + idx / 100) * float(100 + idx),
                    "demand_shape_label": "smooth",
                    "probability_candidate_version": "test",
                }
            )
    return pd.DataFrame(rows)


def test_candidate_pool_module_imports_and_business_priority_calculation():
    from alg.tasks.die_prediction import candidate_pool

    df = pd.DataFrame(
        {
            "manufacturer_code": ["m1"],
            "hospital_code": ["h1"],
            "drug_group": ["d1"],
            "cutoff_month": ["2024-01"],
            "historical_avg_monthly_amount_asof_cutoff": [10.0],
        }
    )
    scored = candidate_pool.make_horizon_scored_frame(df, horizon=6, probability=[0.25])
    assert np.isclose(scored.loc[0, "relative_value_at_risk_H"], 60.0)
    assert np.isclose(scored.loc[0, "relative_business_priority_score_H"], 15.0)
    assert scored.loc[0, "drug_group_source"] == "drug_code"


def test_global_top5_and_manufacturer_min_fill_on_small_fixture():
    from alg.tasks.die_prediction.candidate_pool import CandidatePoolConfig, select_recurring_business_priority_candidates

    selected, audit = select_recurring_business_priority_candidates(
        _sample_scored_rows(),
        config=CandidatePoolConfig(global_top_pct=0.05, manufacturer_min_candidates=3),
    )
    assert "global_top5pct" in selected["selection_reason"].tolist()
    assert "manufacturer_min_fill" in selected["selection_reason"].tolist()
    assert "available_entities_less_than_minimum" in selected["selection_reason"].tolist()
    assert len(selected[selected["manufacturer_code"].eq("m1")]) >= 3
    assert len(selected[selected["manufacturer_code"].eq("m2")]) >= 3
    assert len(selected[selected["manufacturer_code"].eq("m3")]) == 2
    assert audit["selection_reason"].isin(["global_top5pct", "manufacturer_min_fill", "available_entities_less_than_minimum"]).any()


def test_horizons_are_not_collapsed_before_entity_view():
    from alg.tasks.die_prediction.candidate_pool import CandidatePoolConfig, collapse_horizon_candidates, select_recurring_business_priority_candidates

    base = _sample_scored_rows().head(4).copy()
    frames = []
    for horizon, multiplier in [(3, 1.0), (6, 2.0), (12, 1.5)]:
        part = base.copy()
        part["horizon"] = horizon
        part["relative_business_priority_score_H"] *= multiplier
        frames.append(part)
    long_df = pd.concat(frames, ignore_index=True)
    by_horizon, _audit = select_recurring_business_priority_candidates(
        long_df,
        config=CandidatePoolConfig(global_top_pct=1.0, manufacturer_min_candidates=1),
    )
    assert set(by_horizon["horizon"]) == {3, 6, 12}
    entity = collapse_horizon_candidates(by_horizon)
    assert entity["selected_horizons"].str.contains("H3").any()
    assert entity["selected_horizons"].str.contains("H6").any()
    assert entity["selected_horizons"].str.contains("H12").any()
    assert set(entity["primary_horizon"]).issubset({"H6"})


def test_one_shot_table_has_no_recurring_churn_probability():
    from alg.tasks.die_prediction.candidate_pool import build_one_shot_attention_candidates

    source = pd.DataFrame(
        {
            "manufacturer_code": ["m1"],
            "hospital_code": ["h1"],
            "drug_group": ["d1"],
            "first_purchase_month": ["2024-01"],
            "historical_avg_monthly_amount_asof_cutoff": [100.0],
        }
    )
    one_shot, audit = build_one_shot_attention_candidates(source)
    assert "churn_probability_H" not in one_shot.columns
    assert one_shot.loc[0, "probability_available"] is False or one_shot.loc[0, "probability_available"] == False
    assert one_shot.loc[0, "probability_interpretation"] == "not_recurring_churn_probability"
    assert audit.loc[0, "table_name"] == "one_shot_attention_candidates"


def test_demand_shape_observation_is_side_table_not_business_priority_union():
    from alg.tasks.die_prediction.candidate_pool import build_demand_shape_observation_candidates

    scored = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m2"],
            "hospital_code": ["h1", "h2"],
            "drug_group": ["d1", "d2"],
            "drug_group_source": ["drug_code", "drug_code"],
            "cutoff_month": ["2024-01", "2024-01"],
            "horizon": [3, 6],
            "churn_probability_H": [0.9, 0.9],
            "relative_business_priority_score_H": [999.0, 999.0],
            "demand_shape_label": ["intermittent", "lumpy"],
        }
    )
    observation, _audit = build_demand_shape_observation_candidates(scored)
    assert set(observation["observation_reason"]) == {"intermittent_H3_observation_only", "lumpy_high_risk_low_confidence"}
    assert "relative_business_priority_score_H" not in observation.columns
    assert "selection_reason" not in observation.columns


def test_candidate_pool_script_compiles_and_no_model_files_created():
    root = Path(__file__).resolve().parents[1]
    before = set(root.rglob("*.joblib")) | set(root.rglob("*.pkl")) | set(root.rglob("*.skops")) | set(root.rglob("*.cbm")) | set(root.rglob("*.onnx")) | set(root.rglob("*.zip"))
    subprocess.run(
        [sys.executable, "-m", "py_compile", "scripts/run_alive_prediction_candidate_pool_v1.py"],
        cwd=root,
        check=True,
    )
    after = set(root.rglob("*.joblib")) | set(root.rglob("*.pkl")) | set(root.rglob("*.skops")) | set(root.rglob("*.cbm")) | set(root.rglob("*.onnx")) | set(root.rglob("*.zip"))
    assert after == before

