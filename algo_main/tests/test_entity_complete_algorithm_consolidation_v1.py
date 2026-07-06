from __future__ import annotations

from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction import entity_complete_algorithm_consolidation as module


def test_module_imports() -> None:
    assert module.VERSION == "entity_complete_v1"


def test_leakage_audit_flags_future_like_fields() -> None:
    frame = pd.DataFrame(
        {
            "manufacturer_code": ["m"],
            "hospital_code": ["h"],
            "drug_group": ["d"],
            "drug_group_source": ["drug_code"],
            "cutoff_month": [pd.Timestamp("2024-01-31")],
            "first_purchase_month": [pd.Timestamp("2025-01-31")],
            "months_since_last_purchase_asof_cutoff": [3],
            "label_die_H": [1],
        }
    )

    audit = module.audit_feature_leakage(frame)

    row = audit[audit["feature_name"].eq("first_purchase_month")].iloc[0]
    assert row["audit_result"] == "excluded_or_observe_only"


def test_label_feature_boundary_check_runs() -> None:
    frame = pd.DataFrame(
        {
            "manufacturer_code": ["m"],
            "hospital_code": ["h"],
            "drug_group": ["d"],
            "drug_group_source": ["drug_code"],
            "cutoff_month": [pd.Timestamp("2024-01-31")],
            "months_since_last_purchase_asof_cutoff": [3],
            "order_count_last_3m_asof_cutoff": [1],
            "label_die_H": [1],
        }
    )

    audit = module.audit_feature_leakage(frame)

    assert {"feature_name", "possible_future_leakage", "audit_result"}.issubset(audit.columns)


def test_metric_row_with_topk_pr_auc_gain_lift_correct() -> None:
    df = pd.DataFrame(
        {
            "horizon": ["H3"] * 4,
            "cutoff_period": ["2024-01"] * 4,
            "label_die_H": [1, 1, 0, 0],
            "probability_score": [0.9, 0.8, 0.2, 0.1],
        }
    )

    metrics = module.metric_row_with_topk(df, "probability_score")

    assert metrics["positive_rate"] == 0.5
    assert metrics["pr_auc_gain"] == 0.5
    assert metrics["pr_auc_lift"] == 2.0


def test_ece_is_computed() -> None:
    df = pd.DataFrame(
        {
            "horizon": ["H3"] * 4,
            "cutoff_period": ["2024-01"] * 4,
            "label_die_H": [1, 0, 1, 0],
            "probability_score": [0.8, 0.2, 0.7, 0.3],
        }
    )

    metrics = module.metric_row_with_topk(df, "probability_score")

    assert metrics["ece"] >= 0


def test_feature_group_ablation_empty_input_not_crash(tmp_path: Path) -> None:
    summary, by_horizon, predictions = module.run_feature_group_ablation(
        pd.DataFrame(columns=["split", "horizon", "label_die_H"]),
        {"base_recency_frequency": ["months_since_last_purchase_asof_cutoff"]},
        tmp_path,
    )

    assert summary.shape[0] == 1
    assert by_horizon.empty
    assert predictions.empty


def test_candidate_policy_recall_calculation() -> None:
    predictions = pd.DataFrame(
        {
            "manufacturer_code": ["m"] * 5,
            "hospital_code": [f"h{i}" for i in range(5)],
            "drug_group": ["d"] * 5,
            "drug_group_source": ["drug_code"] * 5,
            "cutoff_month": [pd.Timestamp("2024-01-31")] * 5,
            "cutoff_period": ["2024-01"] * 5,
            "horizon": ["H3"] * 5,
            "label_die_H": [1, 1, 0, 0, 0],
            "label_alive_H": [0, 0, 1, 1, 1],
            "label_window_closed": [True] * 5,
            "probability_score": [0.9, 0.8, 0.2, 0.1, 0.0],
            "interval_overdue_baseline": [5, 4, 3, 2, 1],
            "frequency_decay_baseline": [5, 4, 3, 2, 1],
            "recency_only_baseline": [5, 4, 3, 2, 1],
            "history_sufficiency_flag": ["history_sufficient"] * 5,
            "demand_shape_label": ["smooth"] * 5,
        }
    )

    metrics, reco = module.run_candidate_policy_v2(predictions)
    top20 = metrics[metrics["candidate_policy"].eq("probability_top20")].iloc[0]

    assert top20["candidate_die_recall"] == 0.5
    assert reco["candidate_die_recall"] >= 0.5


def test_hybrid_rank_score_does_not_require_label() -> None:
    df = pd.DataFrame(
        {
            "probability_score": [0.1, 0.9],
            "interval_overdue_baseline": [1, 2],
            "frequency_decay_baseline": [0.0, 1.0],
            "recency_only_baseline": [2, 3],
        }
    )

    scored = module.add_candidate_policy_scores(df, "H3")

    assert "hybrid_rank_50_30_20" in scored
    assert scored["hybrid_rank_50_30_20"].notna().all()


def test_probability_service_gate_rules() -> None:
    decisions = module.build_decisions(
        leakage=pd.DataFrame({"possible_future_leakage": [False]}),
        ablation=pd.DataFrame({"feature_set": ["all_safe_features_without_choice_set"], "auc": [0.82], "ece": [0.02]}),
        model_family=pd.DataFrame({"status": ["ok"], "model_name": ["xgboost_small"], "auc": [0.82], "ece": [0.02]}),
        tuning=pd.DataFrame(
            {
                "selected": [True],
                "test_auc": [0.82],
                "test_pr_auc_gain": [0.3],
                "test_ece": [0.02],
            }
        ),
        calibration=pd.DataFrame({"calibration_method": ["raw"], "ece": [0.02], "brier": [0.1], "logloss": [0.4]}),
        learning_curve=pd.DataFrame({"status": ["ok"], "auc": [0.8]}),
        holdout=pd.DataFrame({"status": ["ok"], "auc": [0.7]}),
        candidate_v2=pd.DataFrame(
            {
                "candidate_policy": ["multi_recall_union_top10"],
                "candidate_die_recall": [0.35],
                "candidate_positive_rate": [0.7],
                "non_candidate_positive_rate": [0.3],
                "candidate_rate": [0.25],
                "lift_vs_non_candidate": [2.0],
                "manual_review_load": [100],
                "stable_segment_coverage": [0.5],
            }
        ),
        selected_config={"config_id": 1},
    )

    assert decisions["internal_allowed"] is True
    assert decisions["analyst_allowed"] is True


def test_missing_optional_model_dependency_not_crash(monkeypatch) -> None:
    monkeypatch.setattr(module.importlib.util, "find_spec", lambda name: None if name == "lightgbm" else object())

    row = module.skipped_model_row("base", "lightgbm_small", "dependency_not_installed")

    assert row["status"] == "dependency_not_installed"


def test_does_not_save_formal_model_or_touch_project_frontend() -> None:
    source = Path(module.__file__).read_text(encoding="utf-8")

    assert ".pickle" not in source
    assert ".pkl" not in source
    assert "front_end" not in source
    assert "project/" not in source
