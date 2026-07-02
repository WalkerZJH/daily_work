from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction.utility_backtest import (
    binary_metrics,
    business_priority_light_check,
    construct_die_label,
    construct_repeat_label,
    detector_outcome_check,
    false_positive_cases,
    historical_true_positive_cases,
    is_label_window_closed,
    proof_case_disclaimer,
    run_utility_backtest,
    status_outcome_check,
)


def test_label_window_closure_logic() -> None:
    assert is_label_window_closed("2024-01", 6, "2024-07-01")
    assert not is_label_window_closed("2024-01", 12, "2024-11-30")


def test_die_fixed_window_label_construction() -> None:
    assert construct_die_label("2024-01", ["2024-03-01"], 3) == 0
    assert construct_die_label("2024-01", ["2024-05-01"], 3) == 1


def test_repeat_fixed_window_label_construction() -> None:
    assert construct_repeat_label("2024-01", ["2024-02-01"], 3) == 1
    assert construct_repeat_label("2024-01", ["2024-06-01"], 3) == 0


def test_m1_probability_metrics_on_mock_data() -> None:
    df = pd.DataFrame({"label_die_H": [1, 1, 0, 0], "churn_probability_H": [0.9, 0.8, 0.2, 0.1]})
    metrics = binary_metrics(df, "label_die_H", "churn_probability_H")

    assert metrics["row_count"] == 4
    assert metrics["auc"] == 1.0
    assert metrics["brier_score"] < 0.05


def test_m2_repeat_metrics_on_mock_data() -> None:
    df = pd.DataFrame({"label_repeat_H": [1, 0, 1, 0], "repeat_probability_H": [0.8, 0.3, 0.7, 0.2]})
    metrics = binary_metrics(df, "label_repeat_H", "repeat_probability_H")

    assert metrics["row_count"] == 4
    assert metrics["auc"] == 1.0
    assert 0.0 <= metrics["ece"] <= 1.0


def test_business_priority_light_check_is_not_probability_accuracy() -> None:
    df = pd.DataFrame(
        {
            "candidate_id": ["a", "b"],
            "horizon": ["H6", "H6"],
            "cutoff_month": ["2024-01", "2024-01"],
            "churn_probability_H": [0.8, 0.2],
            "relative_value_at_risk_H": [10, 100],
            "relative_business_priority_score_H": [8, 20],
        }
    )
    out = business_priority_light_check(df)

    assert not out.empty
    assert out["note"].str.contains("not_probability_accuracy").all()


def test_detector_outcome_check_runs() -> None:
    detector = pd.DataFrame(
        {
            "candidate_id": ["a", "b"],
            "detector_name": ["terminal_loss_warning", "terminal_loss_warning"],
            "hit_flag": [True, False],
        }
    )
    labels = pd.DataFrame(
        {
            "candidate_id": ["a", "b"],
            "label_die_H": [1, 0],
            "churn_probability_H": [0.8, 0.2],
            "relative_business_priority_score_H": [80, 20],
        }
    )
    out = detector_outcome_check(detector, pd.DataFrame(), labels)

    assert set(out["hit_flag"].astype(bool)) == {True, False}
    assert out["observed_die_rate"].notna().all()


def test_status_outcome_check_runs() -> None:
    status = pd.DataFrame(
        {
            "horizon": ["H6", "H6"],
            "candidate_type": ["recurring_business_priority", "one_shot_attention"],
            "final_candidate_status": ["priority_review", "one_shot_attention"],
            "review_priority": ["P1", "P3"],
            "evidence_strength": ["medium", "insufficient"],
            "label_die_H": [1, 1],
            "churn_probability_H": [0.8, None],
            "relative_business_priority_score_H": [80, None],
        }
    )
    out = status_outcome_check(status)

    recurring = out[out["candidate_type"] == "recurring_business_priority"]
    one_shot = out[out["candidate_type"] == "one_shot_attention"]
    assert recurring["observed_die_rate"].iloc[0] == 1.0
    assert pd.isna(one_shot["observed_die_rate"].iloc[0])


def test_proof_cases_only_true_positive() -> None:
    status = pd.DataFrame(
        {
            "candidate_type": ["recurring_business_priority", "recurring_business_priority"],
            "final_candidate_status": ["priority_review", "manual_review"],
            "review_priority": ["P1", "P2"],
            "label_die_H": [1, 0],
            "manufacturer_code": ["m", "m"],
            "hospital_code": ["h1", "h2"],
            "drug_group": ["d", "d"],
            "cutoff_month": ["2024-01", "2024-01"],
            "horizon": ["H6", "H6"],
            "churn_probability_H": [0.8, 0.7],
            "relative_business_priority_score_H": [80, 70],
            "survival_state": ["likely_churn_interval", "normal_interval"],
            "top_detector_reasons": ["terminal_loss_warning", ""],
        }
    )
    cases = historical_true_positive_cases(status)
    false_pos = false_positive_cases(status)

    assert len(cases) == 1
    assert cases["label_die_H"].eq(1).all()
    assert len(false_pos) == 1


def test_proof_case_disclaimer_generated() -> None:
    text = proof_case_disclaimer()

    assert "selected true-positive historical cases only" in text
    assert "not a complete accuracy report" in text


def test_run_utility_backtest_handles_missing_optional_inputs(tmp_path: Path) -> None:
    root = tmp_path / "algo_main"
    out_dir = root / "reports/alive_prediction_utility_backtest_v1"

    outputs = run_utility_backtest(root, out_dir, dry_run=False)

    assert (out_dir / "utility_backtest_summary.md").exists()
    assert (out_dir / "proof_case_disclaimer.md").exists()
    assert outputs["universe"].empty is False


def test_script_dry_run(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_alive_prediction_utility_backtest_v1.py"
    out_dir = tmp_path / "utility_backtest"
    result = subprocess.run(
        [sys.executable, str(script), "--dry-run", "--output-dir", str(out_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "wrote utility backtest outputs" in result.stdout
    assert (out_dir / "m1_probability_backtest_metrics.csv").exists()
