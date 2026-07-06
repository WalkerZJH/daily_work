from __future__ import annotations

from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction.model_failure_segmentation import (
    add_alternative_baseline_scores,
    alternative_baseline_comparison,
    build_segment_metric_matrix,
    build_segment_metric_matrix_by_horizon,
    classify_segment,
    dry_run_inputs,
    enrich_recurring_frame,
    full_universe_artifact_status,
    run_model_failure_segmentation,
    segment_metric_dict,
)


def _fixture_frame() -> pd.DataFrame:
    recurring, history, survival, detector, features = dry_run_inputs()
    return enrich_recurring_frame(
        recurring,
        history_flags=history,
        survival=survival,
        detector=detector,
        features=features,
    )


def test_segmentation_metric_function_runs() -> None:
    frame = _fixture_frame()
    matrix = build_segment_metric_matrix(frame, dimensions=["horizon", "demand_shape_label"])

    assert not matrix.empty
    assert {"auc", "pr_auc", "ece", "lift_at_top_10pct"}.issubset(matrix.columns)
    assert matrix["segment_dimension"].isin(["overall", "horizon", "demand_shape_label"]).all()


def test_single_class_segment_does_not_crash() -> None:
    frame = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m1"],
            "hospital_code": ["h1", "h2"],
            "drug_group": ["d1", "d1"],
            "drug_group_source": ["drug_code", "drug_code"],
            "label_die_H": [1, 1],
            "churn_probability_H": [0.9, 0.8],
        }
    )

    metrics = segment_metric_dict(frame, segment_dimension="unit_test", segment_value="single")

    assert pd.isna(metrics["auc"])
    assert metrics["data_quality_note"].startswith("single_class_or_too_few_samples")
    assert metrics["not_predictable_segment"] is True


def test_pr_auc_baseline_gain_lift_are_correct() -> None:
    frame = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m1", "m1", "m1"],
            "hospital_code": ["h1", "h2", "h3", "h4"],
            "drug_group": ["d1", "d1", "d1", "d1"],
            "drug_group_source": ["drug_code"] * 4,
            "label_die_H": [1, 1, 0, 0],
            "churn_probability_H": [0.9, 0.8, 0.2, 0.1],
        }
    )

    metrics = segment_metric_dict(frame, segment_dimension="unit_test", segment_value="balanced")

    assert metrics["positive_rate"] == 0.5
    assert metrics["pr_auc"] == 1.0
    assert metrics["pr_auc_gain"] == 0.5
    assert metrics["pr_auc_lift"] == 2.0


def test_ece_by_segment_runs() -> None:
    frame = _fixture_frame()
    by_horizon = build_segment_metric_matrix_by_horizon(frame, dimensions=["demand_shape_label"])

    assert not by_horizon.empty
    assert by_horizon["ece"].notna().any()


def test_segment_classification_rules() -> None:
    good = classify_segment(
        {
            "row_count": 120,
            "positive_count": 60,
            "negative_count": 60,
            "auc": 0.63,
            "lift_at_top_10pct": 1.2,
            "ece": 0.10,
            "pr_auc_gain": 0.04,
            "segment_dimension": "manufacturer_code",
            "segment_value": "m1",
            "horizon": "all",
        }
    )
    weak = classify_segment(
        {
            "row_count": 120,
            "positive_count": 60,
            "negative_count": 60,
            "auc": 0.55,
            "lift_at_top_10pct": 1.0,
            "ece": 0.12,
            "pr_auc_gain": 0.01,
            "segment_dimension": "manufacturer_code",
            "segment_value": "m2",
            "horizon": "all",
        }
    )
    hidden = classify_segment(
        {
            "row_count": 120,
            "positive_count": 60,
            "negative_count": 60,
            "auc": 0.70,
            "lift_at_top_10pct": 1.5,
            "ece": 0.05,
            "pr_auc_gain": 0.10,
            "segment_dimension": "history_sufficiency_flag",
            "segment_value": "history_insufficient",
            "horizon": "all",
        }
    )

    assert good["good_segment"] is True
    assert weak["weak_segment"] is True
    assert hidden["not_predictable_segment"] is True


def test_alternative_baseline_score_runs() -> None:
    frame = _fixture_frame()
    scored = add_alternative_baseline_scores(frame)
    comparison = alternative_baseline_comparison(frame)

    assert {"recency_only_baseline", "frequency_decay_baseline", "interval_overdue_baseline"}.issubset(
        scored.columns
    )
    assert {"global_logistic_scorer", "recency_only_baseline", "interval_overdue_baseline"}.issubset(
        set(comparison["baseline_name"])
    )


def test_missing_optional_full_universe_artifact_does_not_crash(tmp_path: Path) -> None:
    status = full_universe_artifact_status(tmp_path)

    assert status["has_comparable_full_universe_metrics"] is False
    assert status["sanity_dirs"] == []


def test_run_does_not_modify_input_files(tmp_path: Path) -> None:
    root = tmp_path / "algo_main"
    input_dir = root / "reports" / "alive_prediction_row_level_backtest_frame_v1"
    input_dir.mkdir(parents=True)
    source = input_dir / "recurring_backtest_frame.csv"
    recurring, _, _, _, _ = dry_run_inputs()
    recurring.to_csv(source, index=False)
    before = source.read_bytes()

    output_dir = tmp_path / "out"
    outputs = run_model_failure_segmentation(root, output_dir, dry_run=False)
    after = source.read_bytes()

    assert before == after
    assert (output_dir / "model_failure_segmentation_summary.md").exists()
    assert len(outputs["segment_metric_matrix"]) > 0
