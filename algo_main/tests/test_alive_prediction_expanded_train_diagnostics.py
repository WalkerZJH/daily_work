from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/run_alive_prediction_expanded_train_diagnostics.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_alive_prediction_expanded_train_diagnostics", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _config():
    return {
        "horizons_months": [3, 6, 12],
        "time_splits": {
            "train_2022_only": {
                "train_cutoff_start": "2022-01",
                "train_cutoff_end": "2022-12",
                "purge_cutoff_start": "2023-01",
                "purge_cutoff_end": "2023-12",
                "test_cutoff_start": "2024-01",
                "test_cutoff_end": "2024-12",
            },
            "train_2021_2022": {
                "train_cutoff_start": "2021-01",
                "train_cutoff_end": "2022-12",
                "purge_cutoff_start": "2023-01",
                "purge_cutoff_end": "2023-12",
                "test_cutoff_start": "2024-01",
                "test_cutoff_end": "2024-12",
            },
            "expanded_train_2020_2022": {
                "train_cutoff_start": "2020-01",
                "train_cutoff_end": "2022-12",
                "purge_cutoff_start": "2023-01",
                "purge_cutoff_end": "2023-12",
                "test_cutoff_start": "2024-01",
                "test_cutoff_end": "2024-12",
            },
        },
        "trainability_gate": {
            "train_row_count_min": 2,
            "test_row_count_min": 2,
            "train_positive_count_min": 1,
            "train_negative_count_min": 1,
            "test_positive_count_min": 1,
            "test_negative_count_min": 1,
            "train_cutoff_count_min": 1,
            "test_cutoff_count_min": 1,
            "train_manufacturer_count_min": 1,
            "test_manufacturer_count_min": 1,
        },
        "models": {
            "logistic_regression": {
                "class_path": "sklearn.linear_model.LogisticRegression",
                "params": {"max_iter": 100, "solver": "lbfgs", "random_state": 42},
            }
        },
        "features": {
            "exclude_columns": ["one_shot_business_priority_score", "rule_score", "hospital_name"],
            "exclude_columns_patterns": ["label_die_H*", "label_alive_H*", "churn_probability_H*", "business_priority_score_H*"],
            "low_cardinality_categorical_for_logistic": ["province_code", "demand_pattern_type_asof_cutoff"],
            "high_cardinality_categorical": ["manufacturer_code", "hospital_code", "drug_group"],
            "tree_use_high_cardinality": True,
        },
        "metrics": {"ranking_group": ["cutoff_month", "manufacturer_code"], "min_group_rows_for_topk": 1, "k_values": ["top_10_pct"]},
        "value_at_risk": {
            "amount_columns": {
                "H3": "value_at_risk_amount_nonnegative_H3_asof_cutoff",
                "H6": "value_at_risk_amount_nonnegative_H6_asof_cutoff",
                "H12": "value_at_risk_amount_nonnegative_H12_asof_cutoff",
            }
        },
    }


def _rows() -> pd.DataFrame:
    rows = []
    for period in pd.period_range("2020-01", "2024-12", freq="M"):
        for idx in range(4):
            label = int((period.month + idx) % 2 == 0)
            rows.append(
                {
                    "manufacturer_code": "m1",
                    "hospital_code": f"h{idx}",
                    "drug_group": f"d{idx}",
                    "cutoff_month": period.to_timestamp("M"),
                    "recurring_candidate_flag": True,
                    "one_shot_flag": False,
                    "one_shot_high_value_silence_flag": False,
                    "label_die_H3": label,
                    "label_die_H6": label,
                    "label_die_H12": label,
                    "months_since_last_purchase_asof_cutoff": idx + 1,
                    "months_since_first_purchase_asof_cutoff": idx + 12,
                    "purchase_count_asof_cutoff": idx + 3,
                    "active_month_count_asof_cutoff": 2,
                    "months_observed_asof_cutoff": 12,
                    "active_month_ratio_asof_cutoff": 0.5,
                    "order_count_last_3m_asof_cutoff": idx + 1,
                    "order_count_last_6m_asof_cutoff": idx + 2,
                    "order_count_last_12m_asof_cutoff": idx + 3,
                    "historical_avg_monthly_amount_asof_cutoff": 100.0 + idx,
                    "historical_avg_monthly_quantity_asof_cutoff": 10.0 + idx,
                    "value_at_risk_amount_nonnegative_H3_asof_cutoff": 100.0 + idx,
                    "value_at_risk_amount_nonnegative_H6_asof_cutoff": 200.0 + idx,
                    "value_at_risk_amount_nonnegative_H12_asof_cutoff": 400.0 + idx,
                    "value_at_risk_quantity_nonnegative_H3_asof_cutoff": 10.0 + idx,
                    "value_at_risk_quantity_nonnegative_H6_asof_cutoff": 20.0 + idx,
                    "value_at_risk_quantity_nonnegative_H12_asof_cutoff": 40.0 + idx,
                    "province_code": "p1",
                    "demand_pattern_type_asof_cutoff": "smooth",
                    "hospital_name": "forbidden",
                    "business_priority_score_H3": 999,
                }
            )
        rows.append(
            {
                "manufacturer_code": "m1",
                "hospital_code": f"one_{period}",
                "drug_group": "d_one",
                "cutoff_month": period.to_timestamp("M"),
                "recurring_candidate_flag": False,
                "one_shot_flag": True,
                "one_shot_high_value_silence_flag": False,
                "label_die_H3": 0,
                "label_die_H6": 0,
                "label_die_H12": 0,
            }
        )
    return pd.DataFrame(rows)


def test_expanded_split_keeps_2023_purge_gap_and_excludes_one_shot():
    module = _load_module()
    cfg = _config()
    split = cfg["time_splits"]["expanded_train_2020_2022"]
    train, test = module.split_train_test(_rows(), split)

    assert pd.to_datetime(train["cutoff_month"]).dt.to_period("M").max() == pd.Period("2022-12")
    assert pd.to_datetime(test["cutoff_month"]).dt.to_period("M").min() == pd.Period("2024-01")
    assert not set(pd.to_datetime(train["cutoff_month"]).dt.to_period("M")).intersection(set(pd.period_range("2023-01", "2023-12", freq="M")))
    assert not train["one_shot_flag"].any()


def test_training_window_comparison_csv_is_generated(tmp_path):
    module = _load_module()
    cfg = _config()
    out = module.run_window_comparison(cfg, _rows(), tmp_path, ["logistic_regression"])

    assert (tmp_path / "training_window_comparison.csv").exists()
    assert (tmp_path / "training_window_comparison.md").exists()
    assert {"train_2022_only", "train_2021_2022", "train_2020_2022"} <= set(out["train_window_name"])
    assert set(out["status"]) == {"trained_in_memory"}
    assert not list(tmp_path.glob("*.joblib"))
    assert not list(tmp_path.glob("*.pkl"))


def test_ablation_feature_selection_excludes_forbidden_columns():
    module = _load_module()
    cfg = _config()
    ablation_cfg = {
        "feature_groups": {
            "base_recency_frequency": ["months_since_last_purchase_asof_cutoff", "business_priority_score_H3", "hospital_name"],
            "static_category_features": ["province_code", "manufacturer_code"],
        },
        "ablations": {"base_plus_static": {"include_groups": ["base_recency_frequency", "static_category_features"]}},
    }
    numeric, categorical, missing = module.ablation_feature_columns(_rows(), cfg, ablation_cfg, "logistic_regression", "base_plus_static")
    selected = set(numeric + categorical)

    assert "months_since_last_purchase_asof_cutoff" in selected
    assert "province_code" in selected
    assert "business_priority_score_H3" not in selected
    assert "hospital_name" not in selected
    assert any("business_priority_score_H3" in item for item in missing)
