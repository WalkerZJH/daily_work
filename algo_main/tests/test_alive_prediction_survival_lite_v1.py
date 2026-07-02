from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd


def test_survival_lite_import_and_history_sufficiency_rules():
    from alg.tasks.die_prediction.survival_lite import add_history_sufficiency

    df = pd.DataFrame(
        {
            "purchase_count_asof_cutoff": [3, 6, 2],
            "active_month_count_asof_cutoff": [2, 4, 1],
            "median_purchase_interval_days_asof_cutoff": [30.0, 30.0, np.nan],
            "std_purchase_interval_days_asof_cutoff": [5.0, 60.0, np.nan],
            "purchase_interval_iqr_asof_cutoff": [5.0, 60.0, np.nan],
            "cv2_quantity_asof_cutoff": [0.2, 2.0, np.nan],
        }
    )
    out = add_history_sufficiency(df)
    assert out.loc[0, "history_sufficiency_flag"] == "history_sufficient"
    assert out.loc[1, "history_sufficiency_flag"] == "history_medium"
    assert out.loc[2, "history_sufficiency_flag"] == "history_insufficient"


def test_expected_interval_and_overdue_ratio():
    from alg.tasks.die_prediction.survival_lite import compute_expected_interval, compute_survival_metrics

    df = pd.DataFrame(
        {
            "history_sufficiency_flag": ["history_sufficient", "history_medium", "history_insufficient"],
            "median_purchase_interval_days_asof_cutoff": [60.875, 30.4375, np.nan],
            "group_prior_interval_days": [100.0, 60.875, 91.3125],
            "purchase_count_asof_cutoff": [6, 3, 1],
            "months_since_last_purchase_asof_cutoff": [4.0, 3.0, 6.0],
        }
    )
    out = compute_survival_metrics(compute_expected_interval(df))
    assert np.isclose(out.loc[0, "expected_interval_months"], 2.0)
    assert out.loc[0, "expected_interval_source"] == "entity_median_interval"
    assert np.isclose(out.loc[0, "overdue_ratio"], 2.0)
    assert out.loc[1, "expected_interval_source"] == "entity_group_mixed_interval"
    assert out.loc[2, "expected_interval_source"] == "group_prior_only"


def test_survival_state_bins_and_demand_route():
    from alg.tasks.die_prediction.survival_lite import add_demand_shape_route, assign_survival_state

    df = pd.DataFrame(
        {
            "history_sufficiency_flag": ["history_sufficient"] * 6 + ["history_insufficient", "history_sufficient"],
            "demand_shape_label": ["smooth", "smooth", "smooth", "smooth", "smooth", "smooth", "smooth", "lumpy"],
            "overdue_ratio": [0.5, 1.0, 1.5, 2.5, 3.2, np.nan, 5.0, 5.0],
        }
    )
    out = assign_survival_state(add_demand_shape_route(df))
    assert out.loc[0, "survival_state"] == "normal_interval"
    assert out.loc[1, "survival_state"] == "near_expected_interval"
    assert out.loc[2, "survival_state"] == "slightly_overdue"
    assert out.loc[3, "survival_state"] == "materially_overdue"
    assert out.loc[4, "survival_state"] == "likely_churn_interval"
    assert out.loc[5, "survival_state"] == "insufficient_interval_data"
    assert out.loc[6, "survival_state"] == "insufficient_history"
    assert out.loc[7, "survival_state"] == "low_confidence_lumpy"
    assert out.loc[7, "demand_shape_route"] == "observation_only"


def test_survival_confidence_and_group_prior_fallback():
    from alg.tasks.die_prediction.survival_lite import compute_group_prior_intervals, attach_best_group_prior, compute_expected_interval, compute_survival_confidence

    features = pd.DataFrame(
        {
            "cutoff_month": ["2024-01", "2024-01"],
            "manufacturer_code": ["m1", "m1"],
            "drug_category_code": ["c1", "c1"],
            "median_purchase_interval_days_asof_cutoff": [30.0, 90.0],
        }
    )
    candidates = pd.DataFrame(
        {
            "cutoff_month": ["2024-01"],
            "manufacturer_code": ["m1"],
            "drug_category_code": ["c1"],
            "history_sufficiency_flag": ["history_insufficient"],
            "purchase_count_asof_cutoff": [1],
            "confidence_multiplier": [1.0],
        }
    )
    prior = compute_group_prior_intervals(features)
    attached = attach_best_group_prior(candidates, prior)
    out = compute_survival_confidence(compute_expected_interval(attached))
    assert np.isclose(out.loc[0, "group_prior_interval_days"], 60.0)
    assert out.loc[0, "expected_interval_source"] == "group_prior_only"
    assert out.loc[0, "survival_confidence"] <= 0.4


def test_refine_survival_excludes_one_shot_and_handles_missing_interval():
    from alg.tasks.die_prediction.survival_lite import refine_survival

    candidates = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m2"],
            "hospital_code": ["h1", "h2"],
            "drug_group": ["d1", "d2"],
            "drug_group_source": ["drug_code", "drug_code"],
            "cutoff_month": ["2024-01", "2024-01"],
            "primary_horizon": ["H6", "H6"],
            "primary_churn_probability": [0.5, 0.7],
            "primary_relative_value_at_risk": [100.0, 100.0],
            "primary_relative_business_priority_score": [50.0, 70.0],
            "demand_shape_label": ["smooth", "smooth"],
        }
    )
    features = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m2"],
            "hospital_code": ["h1", "h2"],
            "drug_group": ["d1", "d2"],
            "drug_group_source": ["drug_code", "drug_code"],
            "cutoff_month": ["2024-01", "2024-01"],
            "months_since_last_purchase_asof_cutoff": [1.0, 2.0],
            "purchase_count_asof_cutoff": [3, 1],
            "active_month_count_asof_cutoff": [2, 1],
            "median_purchase_interval_days_asof_cutoff": [30.0, np.nan],
            "drug_category_code": ["c1", "c2"],
            "province_code": ["p1", "p2"],
            "hospital_level_code": ["L1", "L2"],
            "one_shot_flag": [False, True],
        }
    )
    out, _prior = refine_survival(candidates, features)
    assert len(out) == 1
    assert out.loc[0, "manufacturer_code"] == "m1"


def test_survival_lite_script_dry_run_and_no_model_files(tmp_path):
    root = Path(__file__).resolve().parents[1]
    before = set(tmp_path.rglob("*.joblib")) | set(tmp_path.rglob("*.pkl")) | set(tmp_path.rglob("*.skops")) | set(tmp_path.rglob("*.cbm")) | set(tmp_path.rglob("*.onnx")) | set(tmp_path.rglob("*.zip"))
    subprocess.run(
        [
            sys.executable,
            "scripts/run_alive_prediction_survival_lite_v1.py",
            "--dry-run",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=root,
        check=True,
    )
    assert (tmp_path / "survival_refinement_results.csv").exists()
    assert (tmp_path / "survival_leakage_audit.md").exists()
    after = set(tmp_path.rglob("*.joblib")) | set(tmp_path.rglob("*.pkl")) | set(tmp_path.rglob("*.skops")) | set(tmp_path.rglob("*.cbm")) | set(tmp_path.rglob("*.onnx")) | set(tmp_path.rglob("*.zip"))
    assert after == before
