from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/run_alive_prediction_small_model_experiments.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_alive_prediction_small_model_experiments", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _config():
    return {
        "experiment_name": "test",
        "recurring_definition": {
            "min_purchase_count_asof_cutoff": 3,
            "min_active_month_count_asof_cutoff": 2,
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
        "features": {
            "exclude_columns": [
                "row_uid",
                "order_detail_id",
                "purchase_time",
                "one_shot_business_priority_score",
                "rule_score",
            ],
            "exclude_columns_patterns": [
                "label_alive_H*",
                "label_die_H*",
                "next_purchase_*",
                "churn_probability_H*",
                "business_priority_score_H*",
                "rank_by_probability_H*",
                "rank_by_business_priority_H*",
            ],
            "low_cardinality_categorical_for_logistic": ["province_code", "demand_pattern_type_asof_cutoff"],
            "high_cardinality_categorical": ["manufacturer_code", "hospital_code", "drug_group"],
            "tree_use_high_cardinality": True,
        },
        "metrics": {
            "ranking_group": ["cutoff_month", "manufacturer_code"],
            "min_group_rows_for_topk": 5,
            "k_values": [1],
        },
        "models": {
            "logistic_regression": {
                "class_path": "sklearn.linear_model.LogisticRegression",
                "params": {
                    "max_iter": 100,
                    "C": 1.0,
                    "penalty": "l2",
                    "solver": "lbfgs",
                    "class_weight": None,
                    "random_state": 42,
                }
            },
            "lightgbm_small": {"class_path": "lightgbm.LGBMClassifier", "params": {}},
            "catboost_small": {
                "class_path": "catboost.CatBoostClassifier",
                "params": {"iterations": 2, "verbose": False, "allow_writing_files": False},
            },
            "xgboost_small": {
                "optional_dependency": "xgboost",
                "class_path": "xgboost.XGBClassifier",
                "params": {
                    "objective": "binary:logistic",
                    "n_estimators": 2,
                    "learning_rate": 0.1,
                    "max_depth": 2,
                    "eval_metric": "logloss",
                    "tree_method": "hist",
                    "random_state": 42,
                    "n_jobs": 1,
                },
            },
        },
        "value_at_risk": {
            "amount_columns": {"H3": "value_at_risk_amount_nonnegative_H3_asof_cutoff"}
        },
    }


def _feature_rows() -> pd.DataFrame:
    rows = []
    for cutoff, label_values in {
        "2022-01-31": [0, 1, 0],
        "2022-02-28": [1, 0, 1],
        "2024-01-31": [0, 1, 0],
        "2024-02-29": [1, 0, 1],
    }.items():
        for idx, label in enumerate(label_values):
            rows.append(
                {
                    "manufacturer_code": "m1",
                    "hospital_code": f"h{idx}",
                    "drug_group": f"d{idx}",
                    "cutoff_month": pd.Timestamp(cutoff),
                    "purchase_count_asof_cutoff": 3 + idx,
                    "active_month_count_asof_cutoff": 2,
                    "months_since_last_purchase_asof_cutoff": idx + 1,
                    "months_since_first_purchase_asof_cutoff": idx + 3,
                    "active_month_ratio_asof_cutoff": 0.5,
                    "order_count_last_3m_asof_cutoff": idx + 1,
                    "order_count_last_6m_asof_cutoff": idx + 2,
                    "order_count_last_12m_asof_cutoff": idx + 3,
                    "historical_avg_monthly_amount_asof_cutoff": 100.0 + idx,
                    "historical_avg_monthly_quantity_asof_cutoff": 10.0 + idx,
                    "value_at_risk_amount_nonnegative_H3_asof_cutoff": 300.0 + idx,
                    "value_at_risk_quantity_nonnegative_H3_asof_cutoff": 30.0 + idx,
                    "cold_start_flag": False,
                    "adi_asof_cutoff": 1.0,
                    "cv2_quantity_asof_cutoff": 0.1,
                    "province_code": "340000" if idx < 2 else "350000",
                    "demand_pattern_type_asof_cutoff": "smooth",
                    "label_die_H3": label,
                    "one_shot_high_value_silence_flag": False,
                }
            )
    return pd.DataFrame(rows)


def test_scope_flags_and_split_are_correct():
    module = _load_module()
    df = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m1", "m1"],
            "hospital_code": ["h1", "h2", "h3"],
            "drug_group": ["d1", "d1", "d1"],
            "cutoff_month": [pd.Timestamp("2024-01-31")] * 3,
            "purchase_count_asof_cutoff": [1, 2, 3],
            "active_month_count_asof_cutoff": [1, 1, 2],
            "months_since_first_purchase_asof_cutoff": [3, 3, 3],
            "months_since_last_purchase_asof_cutoff": [4, 4, 4],
            "value_at_risk_amount_nonnegative_H12_asof_cutoff": [1000, 10, 100],
        }
    )
    out = module.add_scope_flags(df, _config(), {"one_shot_high_value_silence": {}})
    scopes = module.split_scopes(out)
    assert out["recurring_candidate_flag"].tolist() == [False, False, True]
    assert out["one_shot_flag"].tolist() == [True, False, False]
    assert len(scopes["all_monitorable"]) == 3
    assert len(scopes["recurring_only"]) == 1
    assert len(scopes["one_shot_only"]) == 1


def test_trainability_reports_missing_cutoffs_and_single_class():
    module = _load_module()
    cfg = _config()
    df = _feature_rows()
    split = {
        "train_cutoff_start": "2021-01",
        "train_cutoff_end": "2021-02",
        "test_cutoff_start": "2024-01",
        "test_cutoff_end": "2024-02",
    }
    report = module.build_trainability_report(df, cfg, split, [3])
    assert report.loc[0, "can_train"] is False or not bool(report.loc[0, "can_train"])
    assert "missing_feature_table_for_train_cutoffs" in report.loc[0, "skip_reason"]

    single = df.copy()
    single["label_die_H3"] = 1
    split_ok = {
        "train_cutoff_start": "2022-01",
        "train_cutoff_end": "2022-02",
        "test_cutoff_start": "2024-01",
        "test_cutoff_end": "2024-02",
    }
    report = module.build_trainability_report(single, cfg, split_ok, [3])
    assert "label_has_single_class" in report.loc[0, "skip_reason"]


def test_temporal_split_overlap_or_reverse_raises():
    module = _load_module()
    with pytest.raises(ValueError):
        module.assert_temporal_split_valid(
            {
                "train_cutoff_start": "2024-01",
                "train_cutoff_end": "2024-06",
                "test_cutoff_start": "2024-06",
                "test_cutoff_end": "2024-12",
            }
        )


def test_one_shot_high_value_silence_rows_are_excluded_from_train_counts():
    module = _load_module()
    df = _feature_rows()
    df.loc[df.index[:2], "one_shot_high_value_silence_flag"] = True
    split = {
        "train_cutoff_start": "2022-01",
        "train_cutoff_end": "2022-02",
        "test_cutoff_start": "2024-01",
        "test_cutoff_end": "2024-02",
    }
    report = module.build_trainability_report(df, _config(), split, [3])
    assert report.loc[0, "train_row_count"] == 4


def test_forbidden_columns_and_labels_do_not_enter_x():
    module = _load_module()
    df = _feature_rows()
    df["business_priority_score_H3"] = 123
    df["rule_score"] = 0.1
    df["hospital_name"] = "name"
    numeric, categorical, _ = module.select_feature_columns(df, _config(), "logistic_regression")
    selected = set(numeric + categorical)
    assert "label_die_H3" not in selected
    assert "business_priority_score_H3" not in selected
    assert "rule_score" not in selected
    assert "hospital_name" not in selected


def test_logistic_pipeline_handles_unseen_test_category_with_train_fit_only():
    module = _load_module()
    df = _feature_rows()
    train = df[module.cutoff_mask(df, "2022-01", "2022-02")].copy()
    test = df[module.cutoff_mask(df, "2024-01", "2024-02")].copy()
    test["province_code"] = "999999"
    probabilities, reason, *_ = module.fit_predict_model("logistic_regression", train, test, "label_die_H3", _config())
    assert reason == ""
    assert probabilities is not None
    assert len(probabilities) == len(test)


def test_optional_dependency_missing_skips_lightgbm(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "check_optional_dependency",
        lambda name: {"ok": False, "traceback": "tb"} if name == "lightgbm" else {"ok": True, "version": "x", "traceback": ""},
    )
    estimator, reason = module.build_sklearn_estimator("lightgbm_small", _config(), ["months_since_last_purchase_asof_cutoff"], [])
    assert estimator is None
    assert reason["status"] == "skipped_optional_dependency"
    assert reason["reason"] == "dependency_not_installed:lightgbm"
    assert reason["traceback"] == "tb"


def test_optional_dependency_missing_skips_xgboost(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "check_optional_dependency",
        lambda name: {"ok": False, "traceback": "tb"} if name == "xgboost" else {"ok": True, "version": "x", "traceback": ""},
    )
    estimator, reason = module.build_sklearn_estimator("xgboost_small", _config(), ["months_since_last_purchase_asof_cutoff"], [])
    assert estimator is None
    assert reason["status"] == "skipped_optional_dependency"
    assert reason["reason"] == "dependency_not_installed:xgboost"
    assert reason["traceback"] == "tb"


def test_xgboost_small_trains_on_synthetic_data():
    pytest.importorskip("xgboost")
    module = _load_module()
    fitted, reason = module.fit_model_in_memory("xgboost_small", _feature_rows(), "label_die_H3", _config())
    assert reason == ""
    assert fitted is not None
    probabilities = module.predict_with_fitted_model(fitted, _feature_rows())
    assert len(probabilities) == len(_feature_rows())
    assert ((probabilities >= 0) & (probabilities <= 1)).all()


def test_class_path_failure_is_class_import_failed(monkeypatch):
    module = _load_module()
    cfg = _config()
    cfg["models"]["lightgbm_small"]["class_path"] = "lightgbm.DoesNotExist"
    monkeypatch.setattr(
        module,
        "check_optional_dependency",
        lambda name: {"ok": True, "version": "4.6.0", "traceback": ""},
    )
    estimator, reason = module.build_sklearn_estimator("lightgbm_small", cfg, ["months_since_last_purchase_asof_cutoff"], [])
    assert estimator is None
    assert reason["status"] == "class_import_failed"


def test_fit_failure_is_model_fit_failed(monkeypatch):
    module = _load_module()

    class FailingEstimator:
        def fit(self, *_args, **_kwargs):
            raise RuntimeError("fit boom")

    monkeypatch.setattr(module, "build_sklearn_estimator", lambda *args, **kwargs: (FailingEstimator(), ""))
    fitted, reason = module.fit_model_in_memory("logistic_regression", _feature_rows(), "label_die_H3", _config())
    assert fitted is None
    assert reason["status"] == "model_fit_failed"


def test_catboost_config_forces_no_training_files(monkeypatch):
    module = _load_module()
    captured = {}

    class FakeCatBoost:
        def __init__(self, **params):
            captured.update(params)

        def fit(self, *_args, **_kwargs):
            return self

    monkeypatch.setattr(
        module,
        "check_optional_dependency",
        lambda name: {"ok": True, "version": "1.2.10", "traceback": ""},
    )
    monkeypatch.setattr(module, "import_class", lambda class_path: FakeCatBoost)
    fitted, reason = module.fit_model_in_memory("catboost_small", _feature_rows(), "label_die_H3", _config())
    assert reason == ""
    assert fitted is not None
    assert captured["allow_writing_files"] is False


def test_environment_diagnostics_files_are_written(tmp_path):
    module = _load_module()
    diagnostics = {
        "sys_executable": "python",
        "sys_version": "3",
        "os_getcwd": "cwd",
        "PYTHONPATH": "src",
        "pythonpath_used_by_script": ["src"],
        "pip_executable": "pip",
        "import_check_lightgbm": True,
        "lightgbm_version": "4.6.0",
        "lightgbm_import_error": "",
        "lightgbm_import_error_full_traceback": "",
        "import_check_catboost": True,
        "catboost_version": "1.2.10",
        "catboost_import_error": "",
        "catboost_import_error_full_traceback": "",
        "xgboost_import_check": True,
        "xgboost_version": "1",
        "xgboost_import_error": "",
        "xgboost_import_error_full_traceback": "",
        "import_check_sklearn": True,
        "sklearn_version": "1",
        "sklearn_import_error": "",
        "sklearn_import_error_full_traceback": "",
        "pandas_version": "2",
        "numpy_version": "2",
    }
    module.write_environment_diagnostics(tmp_path, diagnostics)
    assert (tmp_path / "environment_diagnostics.md").exists()
    assert (tmp_path / "environment_diagnostics.json").exists()


def test_dataframe_to_markdown_falls_back_without_tabulate(monkeypatch):
    module = _load_module()

    def fail_markdown(self, index=False):
        raise ImportError("no tabulate")

    monkeypatch.setattr(pd.DataFrame, "to_markdown", fail_markdown)
    text = module.dataframe_to_markdown(pd.DataFrame({"a": [1]}), index=False)
    assert text.startswith("```csv")
    assert "a" in text


def test_metric_group_coverage_skips_small_and_no_positive_groups():
    module = _load_module()
    df = pd.DataFrame(
        {
            "cutoff_month": [pd.Timestamp("2024-01-31")] * 9,
            "manufacturer_code": ["m1"] * 4 + ["m2"] * 5,
            "label_die_H3": [1, 0, 0, 0] + [0, 0, 0, 0, 0],
        }
    )
    coverage = module.metric_group_coverage(df, "label_die_H3", 3, "recurring_only", ["cutoff_month", "manufacturer_code"], 5)
    reasons = dict(zip(coverage["manufacturer_code"], coverage["skip_reason"]))
    assert reasons["m1"] == "skipped_small_group"
    assert reasons["m2"] == "skipped_no_positive"


def test_metrics_group_by_cutoff_and_manufacturer():
    module = _load_module()
    df = pd.DataFrame(
        {
            "cutoff_month": [pd.Timestamp("2024-01-31")] * 10 + [pd.Timestamp("2024-02-29")] * 10,
            "manufacturer_code": ["m1"] * 5 + ["m2"] * 5 + ["m1"] * 5 + ["m2"] * 5,
            "label_die_H3": [1, 0, 0, 0, 0] * 4,
            "churn_probability_H3": [0.9, 0.1, 0.2, 0.3, 0.4] * 4,
            "value_at_risk_amount_nonnegative_H3_asof_cutoff": [100.0] * 20,
        }
    )
    prob, ranking, value, _ = module.evaluate_predictions(
        df,
        "label_die_H3",
        "churn_probability_H3",
        "value_at_risk_amount_nonnegative_H3_asof_cutoff",
        3,
        "logistic_regression",
        "recurring_only",
        _config(),
    )
    assert prob.loc[0, "row_count"] == 20
    assert len(ranking[["cutoff_month", "manufacturer_code"]].drop_duplicates()) == 4
    assert len(value[["cutoff_month", "manufacturer_code"]].drop_duplicates()) == 4
