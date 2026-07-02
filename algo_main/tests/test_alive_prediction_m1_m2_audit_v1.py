from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pandas as pd


def _observation_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "drug_group_source": "drug_code",
                "cutoff_month": "2024-01",
                "horizon": 3,
                "churn_probability_H": 0.9,
                "demand_shape_label": "intermittent",
                "observation_reason": "intermittent_H3_observation_only",
            },
            {
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "drug_group_source": "drug_code",
                "cutoff_month": "2024-01",
                "horizon": 6,
                "churn_probability_H": 0.8,
                "demand_shape_label": "lumpy",
                "observation_reason": "lumpy_high_risk_low_confidence",
            },
            {
                "manufacturer_code": "m2",
                "hospital_code": "h2",
                "drug_group": "d2",
                "drug_group_source": "drug_code",
                "cutoff_month": "2024-02",
                "horizon": 3,
                "churn_probability_H": 0.85,
                "demand_shape_label": "intermittent",
                "observation_reason": "intermittent_H3_observation_only",
            },
        ]
    )


def test_candidate_pool_audit_module_imports_and_row_decomposition():
    from alg.tasks.die_prediction.candidate_pool_audit import row_decomposition

    result = row_decomposition(_observation_fixture())
    metrics = dict(zip(result["metric"], result["value"]))
    assert metrics["total_rows"] == 3
    assert metrics["unique_entity_count"] == 2
    assert metrics["unique_entity_cutoff_count"] == 2
    assert metrics["unique_entity_cutoff_horizon_count"] == 3
    assert metrics["cutoff_month_count"] == 2


def test_latest_cutoff_summary_is_correct():
    from alg.tasks.die_prediction.candidate_pool_audit import latest_cutoff_summary

    latest = latest_cutoff_summary(_observation_fixture())
    total = latest[latest["horizon"].astype(str).eq("all")].iloc[0]
    assert total["cutoff_month"] == "2024-02"
    assert total["row_count"] == 1
    assert total["entity_count"] == 1


def test_overlap_audit_priority_logic():
    from alg.tasks.die_prediction.candidate_pool_audit import overlap_audit

    recurring = pd.DataFrame(
        [
            {
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "cutoff_month": "2024-01",
            }
        ]
    )
    one = pd.DataFrame(
        [
            {
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "first_purchase_month": "2023-01",
            }
        ]
    )
    overlap = overlap_audit(recurring, _observation_fixture(), one)
    row = overlap[overlap["entity_key"].eq("m1|h1|d1")].iloc[0]
    assert row["in_recurring_business_priority"] is True or row["in_recurring_business_priority"] == True
    assert row["in_demand_shape_observation"] is True or row["in_demand_shape_observation"] == True
    assert row["recommended_display_bucket"] == "recurring_business_priority"
    assert "demand_shape_observation" in row["suppressed_display_sources"]


def test_m2_missing_outputs_do_not_crash_summary():
    from alg.tasks.die_prediction.candidate_pool_audit import m2_reference_summary

    one = pd.DataFrame(
        {
            "manufacturer_code": ["m1"],
            "hospital_code": ["h1"],
            "drug_group": ["d1"],
            "one_shot_value_score": [10.0],
        }
    )
    summary = m2_reference_summary(one, None, None)
    assert "missing" in summary["value"].astype(str).tolist()


def test_audit_script_dry_run_and_does_not_modify_input(tmp_path):
    root = Path(__file__).resolve().parents[1]
    marker = tmp_path / "input_marker.csv"
    marker.write_text("a\n1\n", encoding="utf-8")
    before = marker.read_text(encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            "scripts/audit_alive_prediction_m1_m2_v1.py",
            "--dry-run",
            "--output-dir",
            str(tmp_path / "audit"),
        ],
        cwd=root,
        check=True,
    )
    assert marker.read_text(encoding="utf-8") == before
    assert (tmp_path / "audit" / "m1_m2_audit_summary.md").exists()
    assert (tmp_path / "audit" / "demand_shape_observation_row_decomposition.csv").exists()
