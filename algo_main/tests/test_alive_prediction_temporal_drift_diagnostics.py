from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/run_alive_prediction_temporal_drift_diagnostics.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_alive_prediction_temporal_drift_diagnostics", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _synthetic_scoped_frame() -> pd.DataFrame:
    rows = []
    for cutoff, labels, recency_base in [
        ("2022-01-31", [1, 1, 0], 6),
        ("2022-02-28", [1, 0, 0], 5),
        ("2024-01-31", [1, 1, 1], 2),
        ("2024-02-29", [1, 1, 0], 1),
    ]:
        period = pd.Timestamp(cutoff).to_period("M")
        for idx, label in enumerate(labels):
            rows.append(
                {
                    "manufacturer_code": "m1",
                    "hospital_code": f"h{idx}",
                    "drug_group": f"d{idx}",
                    "cutoff_month": pd.Timestamp(cutoff),
                    "cutoff_period": period,
                    "all_monitorable_flag": True,
                    "recurring_candidate_flag": True,
                    "one_shot_flag": False,
                    "one_shot_high_value_silence_flag": False,
                    "label_die_H3": label,
                    "label_die_H6": label,
                    "label_die_H12": label,
                    "months_since_last_purchase_asof_cutoff": recency_base + idx,
                    "months_since_first_purchase_asof_cutoff": 24 + recency_base + idx,
                    "order_count_last_3m_asof_cutoff": 3 - idx + (3 if period.year == 2024 else 0),
                    "order_count_last_6m_asof_cutoff": 4 - idx + (4 if period.year == 2024 else 0),
                    "order_count_last_12m_asof_cutoff": 5 - idx + (5 if period.year == 2024 else 0),
                    "active_month_ratio_asof_cutoff": 0.2 if period.year == 2022 else 0.6,
                    "months_observed_asof_cutoff": 30 if period.year == 2022 else 18,
                    "adi_asof_cutoff": 10 if period.year == 2022 else 4,
                    "value_at_risk_amount_nonnegative_H3_asof_cutoff": 100 + idx + (200 if period.year == 2024 else 0),
                    "value_at_risk_amount_nonnegative_H6_asof_cutoff": 200 + idx + (400 if period.year == 2024 else 0),
                    "value_at_risk_amount_nonnegative_H12_asof_cutoff": 400 + idx + (800 if period.year == 2024 else 0),
                }
            )
        rows.append(
            {
                "manufacturer_code": "m1",
                "hospital_code": f"one_{period}",
                "drug_group": "d_one",
                "cutoff_month": pd.Timestamp(cutoff),
                "cutoff_period": period,
                "all_monitorable_flag": True,
                "recurring_candidate_flag": False,
                "one_shot_flag": True,
                "one_shot_high_value_silence_flag": False,
                "label_die_H3": 0,
                "label_die_H6": 0,
                "label_die_H12": 0,
                "months_since_last_purchase_asof_cutoff": 1,
            }
        )
    return pd.DataFrame(rows)


def test_cutoff_label_and_entity_trends_use_recurring_scope():
    module = _load_module()
    df = _synthetic_scoped_frame()

    label_trend = module.build_cutoff_label_rate_trend(df)
    entity_trend = module.build_cutoff_entity_count_trend(df)

    jan_2024 = label_trend[label_trend["cutoff_month"] == "2024-01"].iloc[0]
    entity_jan_2024 = entity_trend[entity_trend["cutoff_month"] == "2024-01"].iloc[0]
    assert jan_2024["entity_count"] == 3
    assert jan_2024["label_die_H3_positive_rate"] == 1.0
    assert entity_jan_2024["all_seen_entity_count"] == 4
    assert entity_jan_2024["recurring_entity_count"] == 3
    assert entity_jan_2024["one_shot_entity_count"] == 1
    assert entity_jan_2024["recurring_rate"] == 0.75


def test_train_vs_test_metrics_and_feature_shift_are_generated():
    module = _load_module()
    df = _synthetic_scoped_frame()
    split = {
        "train_cutoff_start": "2022-01",
        "train_cutoff_end": "2022-12",
        "test_cutoff_start": "2024-01",
        "test_cutoff_end": "2024-12",
    }

    train_vs_test, feature_shift = module.build_train_vs_test_metrics(df, split)

    row = train_vs_test.iloc[0]
    assert row["train_rows"] == 6
    assert row["test_rows"] == 6
    assert row["train_cutoff_count"] == 2
    assert row["test_cutoff_count"] == 2
    assert "standardized_mean_diff" in feature_shift.columns
    selected_features = set(feature_shift["feature"])
    assert "months_since_last_purchase_asof_cutoff" in selected_features
    assert "label_die_H3" not in selected_features
    assert "cutoff_month" not in selected_features


def test_drift_aware_summary_has_required_aggregation_methods(tmp_path):
    module = _load_module()
    root = tmp_path
    report_dir = root / "reports/alive_prediction_small_models"
    report_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "model": "logistic_regression",
                "horizon": 3,
                "scope": "recurring_only",
                "k": "top_10_pct",
                "precision_at_k": 0.7,
                "recall_at_k": 0.2,
                "ndcg_at_k": 0.6,
                "lift_at_k": 1.4,
                "positive_rate": 0.5,
                "row_count_y": 100,
            }
        ]
    ).to_csv(report_dir / "model_metrics_by_scope.csv", index=False)
    cutoff_trend = pd.DataFrame(
        [
            {
                "model": "logistic_regression",
                "horizon": 3,
                "scope": "recurring_only",
                "cutoff_month": cutoff,
                "k": "top_10_pct",
                "precision_at_k": precision,
                "recall_at_k": 0.2,
                "ndcg_at_k": ndcg,
                "lift_at_k": lift,
                "positive_rate": positive_rate,
                "entity_count": entity_count,
            }
            for cutoff, precision, ndcg, lift, positive_rate, entity_count in [
                ("2024-01", 0.4, 0.5, 2.0, 0.2, 10),
                ("2024-05", 0.6, 0.6, 1.5, 0.4, 20),
                ("2024-09", 0.9, 0.9, 1.0, 0.9, 30),
            ]
        ]
    )
    cutoff_trend = module.add_unavailable_metric_columns(cutoff_trend)

    summary = module.build_drift_aware_metric_summary(root, cutoff_trend)

    assert {"raw_overall", "macro_by_cutoff", "early_mid_late_split"} <= set(summary["aggregation_method"])
    assert {"early_2024", "mid_2024", "late_2024"} <= set(summary["period"])
    macro = summary[summary["aggregation_method"] == "macro_by_cutoff"].iloc[0]
    assert round(macro["precision_at_k"], 6) == round((0.4 + 0.6 + 0.9) / 3, 6)
