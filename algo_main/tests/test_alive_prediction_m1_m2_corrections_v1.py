from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pandas as pd


def _obs() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "drug_group_source": "drug_code",
                "cutoff_month": "2024-01",
                "horizon": 3,
                "churn_probability_H": 0.95,
                "demand_shape_label": "intermittent",
                "demand_shape_route": "longer_horizon_only",
                "observation_reason": "intermittent_H3_observation_only",
                "purchase_count_asof_cutoff": 2,
                "active_month_count_asof_cutoff": 1,
                "months_observed_asof_cutoff": 5,
                "adi_asof_cutoff": 1.5,
                "cv2_quantity_asof_cutoff": 0.5,
                "historical_avg_monthly_amount_asof_cutoff": 100.0,
            },
            {
                "manufacturer_code": "m2",
                "hospital_code": "h2",
                "drug_group": "d2",
                "drug_group_source": "drug_code",
                "cutoff_month": "2024-01",
                "horizon": 12,
                "churn_probability_H": 0.9,
                "demand_shape_label": "lumpy",
                "demand_shape_route": "observation_only",
                "observation_reason": "lumpy_high_risk_low_confidence",
                "purchase_count_asof_cutoff": 5,
                "active_month_count_asof_cutoff": 3,
                "months_observed_asof_cutoff": 20,
                "adi_asof_cutoff": 2.0,
                "cv2_quantity_asof_cutoff": 1.0,
                "historical_avg_monthly_amount_asof_cutoff": 100.0,
            },
        ]
    )


def test_candidate_pool_corrections_import_and_history_flags():
    from alg.tasks.die_prediction.candidate_pool_corrections import add_history_sufficiency_flags

    flagged = add_history_sufficiency_flags(_obs())
    assert flagged.loc[0, "history_sufficiency_flag"] == "history_insufficient"
    assert flagged.loc[1, "history_sufficiency_flag"] == "history_sufficient"


def test_display_ready_filter_runs_and_does_not_modify_raw():
    from alg.tasks.die_prediction.candidate_pool_corrections import display_ready_observations

    raw = _obs()
    before_cols = raw.columns.tolist()
    display, audit = display_ready_observations(raw)
    assert raw.columns.tolist() == before_cols
    assert not audit.empty
    assert len(display) == 1
    assert display.iloc[0]["drug_group"] == "d2"


def test_one_shot_check_detects_churn_probability_pollution():
    from alg.tasks.die_prediction.candidate_pool_corrections import check_one_shot_attention

    one = pd.DataFrame(
        {
            "manufacturer_code": ["m1"],
            "hospital_code": ["h1"],
            "drug_group": ["d1"],
            "one_shot_value_score": [10.0],
            "attention_reason": ["x"],
            "probability_available": [False],
            "probability_interpretation": ["not_recurring_churn_probability"],
            "churn_probability_H": [0.9],
        }
    )
    checked = check_one_shot_attention(one)
    assert checked["erroneous_churn_probability_column_present"].all()
    assert not checked["semantic_check_pass"].all()


def test_recurring_check_detects_duplicate_entity_cutoff():
    from alg.tasks.die_prediction.candidate_pool_corrections import check_recurring_business_priority

    rec = pd.DataFrame(
        [
            {
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "drug_group_source": "drug_code",
                "cutoff_month": "2024-01",
                "selected_horizons": "H3,H6",
                "primary_horizon": "H6",
                "primary_churn_probability": 0.5,
                "primary_relative_value_at_risk": 100.0,
                "primary_relative_business_priority_score": 50.0,
            },
            {
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "drug_group_source": "drug_code",
                "cutoff_month": "2024-01",
                "selected_horizons": "H3,H6",
                "primary_horizon": "H6",
                "primary_churn_probability": 0.5,
                "primary_relative_value_at_risk": 100.0,
                "primary_relative_business_priority_score": 50.0,
            },
        ]
    )
    checked = check_recurring_business_priority(rec)
    assert checked["duplicate_entity_cutoff_flag"].all()
    assert not checked["semantic_check_pass"].all()


def test_missing_m2_outputs_audit_does_not_fail():
    from alg.tasks.die_prediction.candidate_pool_corrections import audit_m2_semantics

    audit = audit_m2_semantics(None)
    assert audit.loc[0, "status"] == "missing"


def test_fix_script_dry_run_and_does_not_modify_input(tmp_path):
    root = Path(__file__).resolve().parents[1]
    marker = tmp_path / "input_marker.csv"
    marker.write_text("a\n1\n", encoding="utf-8")
    before = marker.read_text(encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            "scripts/fix_alive_prediction_m1_m2_v1.py",
            "--dry-run",
            "--output-dir",
            str(tmp_path / "corrections"),
        ],
        cwd=root,
        check=True,
    )
    assert marker.read_text(encoding="utf-8") == before
    assert (tmp_path / "corrections" / "m1_m2_correction_summary.md").exists()
    assert (tmp_path / "corrections" / "demand_shape_observation_display_ready.csv").exists()
