from __future__ import annotations

import pandas as pd

from alg.tasks.die_prediction.entity_complete_rebuild import (
    add_baseline_scores,
    metric_row,
    model_topk_metrics,
)


def test_interval_baseline_handles_missing_interval_without_crash() -> None:
    frame = pd.DataFrame(
        {
            "horizon": ["H3", "H3"],
            "cutoff_month": ["2024-01", "2024-01"],
            "months_since_last_purchase_asof_cutoff": [6, 3],
            "median_purchase_interval_days_asof_cutoff": [90.0, None],
            "order_count_last_3m_asof_cutoff": [0, 1],
            "order_count_last_12m_asof_cutoff": [4, 4],
        }
    )

    scored = add_baseline_scores(frame)

    assert pd.notna(scored["interval_overdue_baseline"].iloc[0])
    assert pd.isna(scored["interval_overdue_baseline"].iloc[1])


def test_metric_row_pr_auc_gain_lift_correct() -> None:
    df = pd.DataFrame({"label_die_H": [1, 1, 0, 0], "probability_score": [0.9, 0.8, 0.2, 0.1]})

    metrics = metric_row(df, "probability_score")

    assert metrics["positive_rate"] == 0.5
    assert metrics["pr_auc"] == 1.0
    assert metrics["pr_auc_gain"] == 0.5
    assert metrics["pr_auc_lift"] == 2.0


def test_topk_metrics_runs_with_sorted_ndcg() -> None:
    df = pd.DataFrame(
        {
            "model_name": ["m"] * 5,
            "horizon": ["H3"] * 5,
            "cutoff_month": ["2024-01"] * 5,
            "label_die_H": [1, 0, 1, 0, 0],
            "score": [0.9, 0.8, 0.7, 0.1, 0.0],
        }
    )

    out = model_topk_metrics(df)

    assert not out.empty
    assert out["ndcg_at_k"].notna().any()

