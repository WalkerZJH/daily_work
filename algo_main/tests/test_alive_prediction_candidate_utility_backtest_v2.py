from __future__ import annotations

from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction.utility_backtest_v2 import (
    business_priority_candidate_light_check,
    calibration_bins,
    candidate_false_negative_like_cases,
    candidate_false_positive_cases,
    candidate_probability_metrics,
    historical_true_positive_cases,
    one_shot_repeat_candidate_metrics,
    one_shot_topk_metrics,
    recurring_topk_metrics,
    run_candidate_utility_backtest_v2,
)


def _recurring_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "candidate_id": ["a", "b", "c", "d"],
            "manufacturer_code": ["m"] * 4,
            "hospital_code": ["h1", "h2", "h3", "h4"],
            "drug_group": ["d"] * 4,
            "drug_group_source": ["drug_code"] * 4,
            "cutoff_month": ["2024-01"] * 4,
            "horizon": ["H6"] * 4,
            "churn_probability_H": [0.9, 0.8, 0.2, 0.1],
            "relative_value_at_risk_H": [10, 5, 100, 80],
            "relative_business_priority_score_H": [9, 4, 20, 8],
            "label_die_H": [1, 1, 0, 0],
            "label_alive_H": [0, 0, 1, 1],
            "label_window_closed": [True] * 4,
            "final_candidate_status": ["priority_review", "manual_review", "observation_only", "low_confidence_watch"],
            "review_priority": ["P1", "P2", "P3", "P3"],
            "evidence_strength": ["medium", "weak", "insufficient", "insufficient"],
            "survival_state": ["likely_churn_interval", "materially_overdue", "normal_interval", "normal_interval"],
            "detector_hit_summary": ["terminal_loss_warning", "", "", ""],
        }
    )


def _one_shot_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "horizon": ["H3", "H3", "H3", "H3"],
            "repeat_probability_H": [0.8, 0.7, 0.2, 0.1],
            "one_shot_non_repeat_risk_H": [0.2, 0.3, 0.8, 0.9],
            "selected_attention_score": [10, 8, 7, 6],
            "label_repeat_H": [1, 1, 0, 0],
            "label_non_repeat_H": [0, 0, 1, 1],
            "label_window_closed": [True] * 4,
        }
    )


def test_candidate_level_metrics_run() -> None:
    out = candidate_probability_metrics(_recurring_fixture())

    assert out["row_count"].iloc[0] == 4
    assert out["auc"].iloc[0] == 1.0
    assert out["note"].str.contains("candidate-level").all()


def test_calibration_bins_run() -> None:
    out = calibration_bins(
        _recurring_fixture(),
        label_col="label_die_H",
        score_col="churn_probability_H",
        observed_col="observed_die_rate",
        avg_col="avg_predicted_churn_probability",
        n_bins=2,
    )

    assert not out.empty
    assert {"observed_die_rate", "avg_predicted_churn_probability"}.issubset(out.columns)


def test_topk_metrics_run() -> None:
    out = recurring_topk_metrics(_recurring_fixture())

    assert {"probability_topk", "business_priority_topk"}.issubset(set(out["topk_policy"]))
    assert out["precision_at_k"].notna().any()


def test_business_priority_check_not_probability_accuracy() -> None:
    out = business_priority_candidate_light_check(_recurring_fixture())

    assert out["note"].str.contains("not probability accuracy").all()


def test_one_shot_repeat_and_non_repeat_topk() -> None:
    metrics = one_shot_repeat_candidate_metrics(_one_shot_fixture())
    topk = one_shot_topk_metrics(_one_shot_fixture())

    assert metrics["auc_repeat"].iloc[0] == 1.0
    assert {"repeat_opportunity", "non_repeat_risk", "selected_attention"}.issubset(set(topk["topk_direction"]))


def test_proof_cases_only_label_die_one() -> None:
    proof = historical_true_positive_cases(_recurring_fixture())

    assert not proof.empty
    assert proof["label_die_H"].eq(1).all()


def test_false_positive_only_label_die_zero() -> None:
    fp = candidate_false_positive_cases(_recurring_fixture())

    assert not fp.empty
    assert fp["label_die_H"].eq(0).all()


def test_false_negative_like_naming() -> None:
    fn_like = candidate_false_negative_like_cases(_recurring_fixture())

    assert "candidate_false_negative_like" in set(fn_like["case_type"]) or fn_like.empty
    if not fn_like.empty:
        assert fn_like["error_note"].str.contains("not full-universe miss").all()


def test_missing_optional_files_do_not_crash(tmp_path: Path) -> None:
    root = tmp_path / "algo_main"
    out_dir = root / "reports/alive_prediction_candidate_utility_backtest_v2"
    outputs = run_candidate_utility_backtest_v2(root, out_dir, dry_run=False)

    assert (out_dir / "candidate_backtest_limitations.md").exists()
    assert outputs["recurring"].empty


def test_script_dry_run(tmp_path: Path) -> None:
    import subprocess
    import sys

    script = Path(__file__).resolve().parents[1] / "scripts" / "run_alive_prediction_candidate_utility_backtest_v2.py"
    out_dir = tmp_path / "candidate_backtest"
    result = subprocess.run(
        [sys.executable, str(script), "--dry-run", "--output-dir", str(out_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "candidate utility backtest v2" in result.stdout
    assert (out_dir / "candidate_utility_backtest_summary.md").exists()
