from __future__ import annotations

from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction import full_universe_interval_backtest as module
from alg.tasks.die_prediction.full_universe_interval_backtest import (
    add_baseline_scores,
    build_full_universe_frame,
    candidate_coverage_metrics,
    dry_run_inputs,
    fixed_window_closed,
    frequency_decay_score,
    gate_for_segment,
    interval_overdue_score,
    metric_dict,
    recency_score,
    run_full_universe_interval_backtest,
)


def test_module_imports() -> None:
    assert module.HORIZONS == [3, 6, 12]


def test_fixed_window_label_closure_logic() -> None:
    assert fixed_window_closed("2024-01", 3, "2024-04-30") is True
    assert fixed_window_closed("2024-01", 6, "2024-04-30") is False


def test_recency_score_direction_correct() -> None:
    df = pd.DataFrame(
        {
            "cutoff_month": ["2024-01", "2024-01"],
            "horizon": ["H3", "H3"],
            "months_since_last_purchase_asof_cutoff": [1, 9],
        }
    )

    score = recency_score(df)

    assert score.iloc[1] > score.iloc[0]


def test_frequency_decay_score_handles_zero_denominator() -> None:
    df = pd.DataFrame(
        {
            "order_count_last_3m_asof_cutoff": [0, 1],
            "order_count_last_12m_asof_cutoff": [0, 0],
        }
    )

    score = frequency_decay_score(df)

    assert score.iloc[0] == 1.0
    assert pd.isna(score.iloc[1])


def test_interval_overdue_score_handles_missing_interval() -> None:
    df = pd.DataFrame(
        {
            "months_since_last_purchase_asof_cutoff": [6, 2],
            "median_purchase_interval_days_asof_cutoff": [90.0, None],
        }
    )

    score, overdue, expected = interval_overdue_score(df)

    assert score.notna().iloc[0]
    assert overdue.notna().iloc[0]
    assert expected.notna().iloc[0]
    assert pd.isna(score.iloc[1])


def test_pr_auc_baseline_gain_lift_correct() -> None:
    df = pd.DataFrame(
        {
            "manufacturer_code": ["m"] * 4,
            "hospital_code": ["h1", "h2", "h3", "h4"],
            "drug_group": ["d"] * 4,
            "drug_group_source": ["drug_code"] * 4,
            "label_window_closed": [True] * 4,
            "label_die_H": [1, 1, 0, 0],
            "score": [0.9, 0.8, 0.2, 0.1],
        }
    )

    metrics = metric_dict(df, "score", "unit_test", "overall")

    assert metrics["positive_rate"] == 0.5
    assert metrics["pr_auc"] == 1.0
    assert metrics["pr_auc_gain"] == 0.5
    assert metrics["pr_auc_lift"] == 2.0


def test_candidate_coverage_calculation_correct() -> None:
    features, labels, candidates, _status, _detector = dry_run_inputs()
    frame = build_full_universe_frame(features, labels)
    frame = module.attach_candidates(frame, candidates)
    frame = add_baseline_scores(frame)

    coverage = candidate_coverage_metrics(frame)
    overall = coverage[(coverage["horizon"] == "overall") & (coverage["cutoff_month"] == "all_2024")].iloc[0]

    assert overall["full_universe_rows"] == 12
    assert overall["candidate_rows"] == 2
    assert overall["candidate_die_recall"] == 2 / 6


def test_probability_availability_gate_classification() -> None:
    allowed = gate_for_segment(
        {
            "row_count": 200,
            "positive_count": 100,
            "negative_count": 100,
            "auc": 0.64,
            "lift_at_top_10pct": 1.2,
            "ece": 0.10,
            "segment_dimension": "province_code",
            "segment_value": "p1",
            "horizon": "H6",
        }
    )
    hidden = gate_for_segment(
        {
            "row_count": 200,
            "positive_count": 100,
            "negative_count": 100,
            "auc": 0.70,
            "lift_at_top_10pct": 1.5,
            "ece": 0.10,
            "segment_dimension": "history_sufficiency_flag",
            "segment_value": "history_insufficient",
            "horizon": "H6",
        }
    )

    assert allowed == "probability_allowed"
    assert hidden == "hide_probability_data_insufficient"


def test_missing_optional_artifacts_do_not_crash(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    outputs = run_full_universe_interval_backtest(tmp_path, out_dir, dry_run=False)

    assert outputs["frame"].empty
    assert (out_dir / "full_universe_frame_audit.md").exists()


def test_run_does_not_modify_input_files(tmp_path: Path) -> None:
    root = tmp_path
    feature_dir = root / "data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/cutoff_2024-01_2024-12"
    feature_dir.mkdir(parents=True)
    features, labels, _candidates, _status, _detector = dry_run_inputs()
    feature_path = feature_dir / "feature_table__status0.parquet"
    label_path = feature_dir / "alive_labels__H3_6_12.parquet"
    features.to_parquet(feature_path, index=False)
    labels.to_parquet(label_path, index=False)
    before_feature = feature_path.read_bytes()
    before_label = label_path.read_bytes()

    outputs = run_full_universe_interval_backtest(root, tmp_path / "out", dry_run=False)

    assert not outputs["frame"].empty
    assert before_feature == feature_path.read_bytes()
    assert before_label == label_path.read_bytes()
