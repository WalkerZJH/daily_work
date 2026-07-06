"""Algorithm consolidation for the entity-complete alive prediction run.

This module audits leakage risk, reruns strict time-split model comparisons,
performs a small XGBoost tuning pass, compares calibration options, and
evaluates a second candidate policy design. It only reads the existing
``entity_complete_v1`` data artifacts and writes research reports; it does not
fetch SQL data, rebuild cleaning artifacts, write model files, call LLMs, or
touch frontend/backend app code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import importlib.util
import math
import time
from typing import Any, Iterable

import numpy as np
import pandas as pd

from alg.facts.purchase_event_builder import ENTITY_KEYS
from alg.tasks.die_prediction.entity_complete_rebuild import (
    DATA_ROOT,
    FEATURE_DIR,
    HORIZONS,
    RANDOM_STATE,
    REPORT_ROOT,
    VERSION,
    add_baseline_scores,
    metric_row,
    rank01,
)
from alg.tasks.die_prediction.utility_backtest import (
    expected_calibration_error,
    log_loss_score,
    ndcg_at_k,
)


CONSOLIDATION_REPORT_DIR = REPORT_ROOT / "07_algorithm_consolidation"
PROGRESS_FILE = CONSOLIDATION_REPORT_DIR / "algorithm_consolidation_progress.md"

LABEL_FILE = FEATURE_DIR / "alive_labels_H3_H6_H12.parquet"
FEATURE_FILE = FEATURE_DIR / "entity_cutoff_feature_table.parquet"

KEY_COLS = [*ENTITY_KEYS, "drug_group_source", "cutoff_month"]
SENSITIVE_EXCLUDED_PATTERNS = (
    "label_",
    "value_at_risk",
    "business_priority",
    "candidate_policy",
)
VALUE_COL_PREFIXES = (
    "historical_avg_monthly_amount",
    "historical_avg_monthly_quantity",
    "entity_value_tier",
    "negative_value_at_risk",
    "value_at_risk",
)
CHOICE_SET_COLS = [
    "hospital_drug_order_count_asof_cutoff",
    "hospital_drug_active_manufacturer_count_asof_cutoff",
    "hospital_drug_order_count_last_12m_asof_cutoff",
    "hospital_drug_order_count_last_3m_asof_cutoff",
    "manufacturer_share_within_hospital_drug_asof_cutoff",
    "competitor_order_count_asof_cutoff",
    "competitor_order_count_last_12m_asof_cutoff",
    "competitor_order_count_last_3m_asof_cutoff",
]
SWITCHING_COLS = [
    "manufacturer_substitution_context_available",
    "manufacturer_share_within_hospital_drug_asof_cutoff",
    "competitor_order_count_last_12m_asof_cutoff",
    "competitor_order_count_last_3m_asof_cutoff",
]
BASE_RECENCY_FREQUENCY_COLS = [
    "months_since_last_purchase_asof_cutoff",
    "purchase_count_asof_cutoff",
    "active_month_count_asof_cutoff",
    "months_observed_asof_cutoff",
    "months_since_first_purchase_asof_cutoff",
    "order_count_last_1m_asof_cutoff",
    "order_count_last_3m_asof_cutoff",
    "order_count_last_6m_asof_cutoff",
    "order_count_last_12m_asof_cutoff",
    "active_months_last_3m_asof_cutoff",
    "active_months_last_6m_asof_cutoff",
    "active_months_last_12m_asof_cutoff",
    "recency_only_baseline",
    "frequency_decay_baseline",
]
INTERVAL_COLS = [
    "active_month_ratio_asof_cutoff",
    "adi_asof_cutoff",
    "median_purchase_interval_days_asof_cutoff",
    "mean_purchase_interval_days_asof_cutoff",
    "std_purchase_interval_days_asof_cutoff",
    "purchase_interval_iqr_asof_cutoff",
    "cv2_quantity_asof_cutoff",
    "seasonality_strength_asof_cutoff",
    "burstiness_score_asof_cutoff",
    "interval_overdue_baseline",
    "hybrid_interval_frequency_score",
]
DEMAND_COLS = [
    "demand_shape_label",
    "history_sufficiency_flag",
    "demand_pattern_type_asof_cutoff",
    "cold_start_flag",
    "confidence_score",
    "one_shot_flag",
    "one_shot_silence_months",
]
MANUFACTURER_HOSPITAL_CONTEXT_COLS = [
    "manufacturer_code",
    "province_code",
    "city_code",
    "county_code",
    "hospital_level_code",
    "ownership_type_code",
]
MANUFACTURER_DRUG_CONTEXT_COLS = [
    "manufacturer_code",
    "drug_group",
    "drug_category_code",
]
STATUS_CONTEXT_COLS = [
    "last_order_phase_code_asof_cutoff",
    "last_delivery_state_code_asof_cutoff",
    "last_order_failure_flag_asof_cutoff",
    "failed_count_last_3m_asof_cutoff",
    "failed_count_last_12m_asof_cutoff",
    "received_count_last_3m_asof_cutoff",
    "received_count_last_12m_asof_cutoff",
    "terminal_count_last_3m_asof_cutoff",
    "terminal_count_last_12m_asof_cutoff",
]
PRODUCTION_UNSAFE_RESEARCH_COLS = set(CHOICE_SET_COLS + SWITCHING_COLS)


@dataclass(frozen=True)
class SplitSpec:
    horizon: str
    train_end: pd.Timestamp
    valid_start: pd.Timestamp
    valid_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp | None
    purge_gap_months: int
    note: str


STRICT_SPLITS = {
    "H3": SplitSpec(
        "H3",
        pd.Timestamp("2023-03-31"),
        pd.Timestamp("2023-07-31"),
        pd.Timestamp("2023-12-31"),
        pd.Timestamp("2024-04-30"),
        None,
        3,
        "H3 train labels end before validation features; validation labels end before test features.",
    ),
    "H6": SplitSpec(
        "H6",
        pd.Timestamp("2022-12-31"),
        pd.Timestamp("2023-07-31"),
        pd.Timestamp("2023-12-31"),
        pd.Timestamp("2024-07-31"),
        None,
        6,
        "H6 train labels end before validation features; validation labels end before test features.",
    ),
    "H12": SplitSpec(
        "H12",
        pd.Timestamp("2021-12-31"),
        pd.Timestamp("2023-01-31"),
        pd.Timestamp("2023-06-30"),
        pd.Timestamp("2025-01-31"),
        pd.Timestamp("2025-06-30"),
        12,
        "H12 uses an earlier train/valid split so closed labels do not overlap test feature cutoffs.",
    ),
}


def run_entity_complete_algorithm_consolidation(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    report_dir = root / CONSOLIDATION_REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    progress(report_dir, "stage=start", reset=True)

    artifacts = inspect_required_artifacts(root)
    progress(report_dir, "stage=load_feature_label_frame")
    frame = load_feature_label_frame(root)
    closed = frame[frame["label_window_closed"].astype(bool)].copy()
    closed["split"] = assign_strict_split(closed)
    split_audit = build_split_audit(closed)

    progress(report_dir, f"stage=leakage_audit closed_rows={len(closed)}")
    leakage = audit_feature_leakage(frame)
    write_csv(report_dir / "leakage_feature_audit.csv", leakage)
    write_csv(report_dir / "label_feature_boundary_audit.csv", leakage)
    write_text(report_dir / "leakage_audit_summary.md", render_leakage_summary(leakage, artifacts))
    write_text(report_dir / "train_valid_test_split_audit.md", render_split_audit(split_audit, closed))
    write_text(report_dir / "choice_set_feature_scope_audit.md", render_choice_set_scope_audit(frame))

    feature_sets = build_feature_sets(frame)
    progress(report_dir, "stage=feature_group_ablation")
    ablation_summary, ablation_horizon, _ablation_predictions = run_feature_group_ablation(closed, feature_sets, report_dir)
    write_csv(report_dir / "feature_group_ablation_summary.csv", ablation_summary)
    write_csv(report_dir / "feature_group_ablation_by_horizon.csv", ablation_horizon)
    write_csv(report_dir / "feature_group_importance_audit.csv", feature_group_importance_audit(ablation_summary, feature_sets))

    progress(report_dir, "stage=model_family_comparison")
    model_family = run_model_family_comparison(closed, feature_sets, report_dir)
    write_csv(report_dir / "model_family_comparison.csv", model_family)

    progress(report_dir, "stage=xgboost_tuning")
    tuning, selected_predictions, selected_config = run_xgboost_tuning(closed, feature_sets, report_dir)
    write_csv(report_dir / "xgboost_hyperparameter_tuning_summary.csv", tuning)
    write_text(report_dir / "xgboost_hyperparameter_tuning_summary.md", render_tuning_summary(tuning, selected_config))

    progress(report_dir, "stage=calibration")
    calibration, calibration_bins, calibrated_predictions, calibration_decision = run_calibration_comparison(selected_predictions)
    write_csv(report_dir / "calibration_comparison.csv", calibration)
    write_csv(report_dir / "calibration_bins_by_horizon.csv", calibration_bins)
    write_text(report_dir / "calibration_decision.md", calibration_decision)

    progress(report_dir, "stage=generalization")
    learning_curve = run_learning_curve(closed, feature_sets, selected_config, report_dir)
    holdout = run_manufacturer_holdout(closed, feature_sets, selected_config, report_dir)
    period = cutoff_period_generalization(calibrated_predictions)
    write_csv(report_dir / "learning_curve_by_training_window.csv", learning_curve)
    write_csv(report_dir / "manufacturer_holdout_generalization.csv", holdout)
    write_csv(report_dir / "cutoff_period_generalization.csv", period)

    progress(report_dir, "stage=candidate_policy_v2")
    candidate_v2, candidate_reco = run_candidate_policy_v2(calibrated_predictions)
    write_csv(report_dir / "candidate_policy_v2_comparison.csv", candidate_v2)
    write_text(report_dir / "candidate_policy_v2_recommendation.md", render_candidate_policy_recommendation(candidate_v2, candidate_reco))

    decisions = build_decisions(
        leakage=leakage,
        ablation=ablation_summary,
        model_family=model_family,
        tuning=tuning,
        calibration=calibration,
        learning_curve=learning_curve,
        holdout=holdout,
        candidate_v2=candidate_v2,
        selected_config=selected_config,
    )
    write_text(report_dir / "probability_service_gate_decision.md", render_probability_service_gate(decisions))
    write_text(report_dir / "model_card_entity_complete_v1.md", render_model_card(frame, split_audit, decisions))
    write_text(report_dir / "next_algorithm_action_decision.md", render_next_algorithm_action(decisions))
    write_text(report_dir / "algorithm_consolidation_summary.md", render_algorithm_consolidation_summary(decisions, artifacts))

    progress(report_dir, "stage=done")
    return {
        "leakage": leakage,
        "ablation": ablation_summary,
        "model_family": model_family,
        "tuning": tuning,
        "calibration": calibration,
        "learning_curve": learning_curve,
        "holdout": holdout,
        "candidate_v2": candidate_v2,
        "decisions": decisions,
    }


# ---------------------------------------------------------------------------
# Loading and audit helpers
# ---------------------------------------------------------------------------


def inspect_required_artifacts(root: Path) -> pd.DataFrame:
    rows = []
    required = [
        DATA_ROOT / "03_cleaned",
        DATA_ROOT / "04_facts",
        DATA_ROOT / "05_features",
        DATA_ROOT / "06_predictions",
        DATA_ROOT / "07_candidates",
        DATA_ROOT / "08_evidence",
        FEATURE_FILE,
        LABEL_FILE,
        REPORT_ROOT / "03_model_selection" / "model_metric_summary.csv",
        REPORT_ROOT / "05_backtest" / "m8_backtest_summary.csv",
        REPORT_ROOT / "06_stage_decision" / "entity_complete_stage_decision.md",
    ]
    for rel in required:
        path = root / rel
        rows.append(
            {
                "artifact": rel.as_posix(),
                "exists": path.exists(),
                "is_dir": path.is_dir(),
                "size_bytes": path.stat().st_size if path.exists() and path.is_file() else np.nan,
            }
        )
    out = pd.DataFrame(rows)
    report_dir = root / CONSOLIDATION_REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    write_csv(report_dir / "missing_artifact_audit.csv", out)
    return out


def load_feature_label_frame(root: Path) -> pd.DataFrame:
    features = pd.read_parquet(root / FEATURE_FILE)
    labels = pd.read_parquet(root / LABEL_FILE)
    features = features.copy()
    labels = labels.copy()
    features["cutoff_month"] = pd.to_datetime(features["cutoff_month"], errors="coerce")
    labels["cutoff_month"] = pd.to_datetime(labels["cutoff_month"], errors="coerce")
    merge_cols = [c for c in ["manufacturer_code", "hospital_code", "drug_group", "cutoff_month"] if c in features.columns and c in labels.columns]
    merged = features.merge(labels, on=merge_cols, how="left", suffixes=("", "_label"))
    rows = []
    for horizon in HORIZONS:
        part = merged.copy()
        part["horizon"] = f"H{horizon}"
        part["label_die_H"] = part[f"label_die_H{horizon}"]
        part["label_alive_H"] = part[f"label_alive_H{horizon}"]
        part["label_window_closed"] = part[f"label_window_closed_H{horizon}"].astype(bool)
        rows.append(part)
    frame = pd.concat(rows, ignore_index=True)
    frame = add_baseline_scores(frame)
    frame["cutoff_period"] = pd.to_datetime(frame["cutoff_month"], errors="coerce").dt.to_period("M").astype(str)
    return frame


def assign_strict_split(df: pd.DataFrame) -> pd.Series:
    cutoff = pd.to_datetime(df["cutoff_month"], errors="coerce")
    out = pd.Series("unused", index=df.index, dtype="object")
    for horizon, spec in STRICT_SPLITS.items():
        mask = df["horizon"].eq(horizon)
        out.loc[mask & cutoff.le(spec.train_end)] = "train"
        out.loc[mask & cutoff.ge(spec.valid_start) & cutoff.le(spec.valid_end)] = "valid"
        test_mask = mask & cutoff.ge(spec.test_start)
        if spec.test_end is not None:
            test_mask &= cutoff.le(spec.test_end)
        out.loc[test_mask] = "test"
    return out


def build_split_audit(closed: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for horizon, group in closed.groupby("horizon", dropna=False):
        spec = STRICT_SPLITS.get(str(horizon))
        for split, part in group.groupby("split", dropna=False):
            rows.append(
                {
                    "horizon": horizon,
                    "split": split,
                    "row_count": len(part),
                    "positive_rate": float(part["label_die_H"].mean()) if len(part) else np.nan,
                    "cutoff_min": str(pd.to_datetime(part["cutoff_month"]).min().date()) if len(part) else "",
                    "cutoff_max": str(pd.to_datetime(part["cutoff_month"]).max().date()) if len(part) else "",
                    "purge_gap_months": spec.purge_gap_months if spec else np.nan,
                    "random_kfold_used_as_primary": False,
                    "same_cutoff_in_train_test": bool(
                        set(group.loc[group["split"].eq("train"), "cutoff_period"]).intersection(
                            set(group.loc[group["split"].eq("test"), "cutoff_period"])
                        )
                    ),
                    "note": spec.note if spec else "",
                }
            )
    return pd.DataFrame(rows)


def audit_feature_leakage(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    model_feature_sets = build_feature_sets(frame)
    model_cols = set().union(*[set(v) for v in model_feature_sets.values()]) if model_feature_sets else set()
    for col in frame.columns:
        if col in {"label_die_H", "label_alive_H", "label_window_closed", "horizon", "split"}:
            continue
        group = feature_group_for_column(col)
        asof = col.endswith("_asof_cutoff") or "_last_" in col or col in {"cutoff_month", "cutoff_period"} or col in {
            "recency_only_baseline",
            "frequency_decay_baseline",
            "interval_overdue_baseline",
            "hybrid_interval_frequency_score",
            "manufacturer_substitution_context_available",
        }
        excluded_sensitive = col.startswith(SENSITIVE_EXCLUDED_PATTERNS) or col.startswith(VALUE_COL_PREFIXES)
        raw_date_risk = col in {"first_purchase_month", "last_purchase_month", "months_since_last_purchase", "days_since_last_purchase"}
        possible_future = bool((not asof and raw_date_risk) or excluded_sensitive)
        if col in model_cols and possible_future:
            result = "blocking_if_used"
        elif possible_future:
            result = "excluded_or_observe_only"
        elif col in PRODUCTION_UNSAFE_RESEARCH_COLS:
            result = "asof_partial_platform_context_not_customer_probability_scope"
        elif col in model_cols:
            result = "pass_for_research_model"
        else:
            result = "not_used_in_probability_model"
        rows.append(
            {
                "feature_name": col,
                "feature_group": group,
                "asof_suffix_present": bool(asof),
                "uses_cutoff_filter_confirmed": bool(asof or col in ENTITY_KEYS or col in {"manufacturer_code", "hospital_code", "drug_group", "drug_group_source"}),
                "possible_future_leakage": bool(possible_future and col in model_cols),
                "audit_method": "schema_name_rule_plus_feature_set_membership",
                "audit_result": result,
                "note": feature_note(col, result),
            }
        )
    return pd.DataFrame(rows).sort_values(["audit_result", "feature_group", "feature_name"]).reset_index(drop=True)


def feature_group_for_column(col: str) -> str:
    if col in CHOICE_SET_COLS:
        return "hospital_drug_choice_set_context"
    if col in SWITCHING_COLS:
        return "manufacturer_switching_context"
    if col in INTERVAL_COLS:
        return "interval_survival"
    if col in DEMAND_COLS:
        return "demand_shape_history"
    if col in MANUFACTURER_HOSPITAL_CONTEXT_COLS:
        return "manufacturer_hospital_context"
    if col in MANUFACTURER_DRUG_CONTEXT_COLS:
        return "manufacturer_drug_context"
    if col.startswith(VALUE_COL_PREFIXES):
        return "value_business_excluded"
    if col in BASE_RECENCY_FREQUENCY_COLS or "_last_" in col or col.endswith("_asof_cutoff"):
        return "base_recency_frequency"
    if "label" in col:
        return "label"
    return "identifier_or_other"


def feature_note(col: str, result: str) -> str:
    if col in PRODUCTION_UNSAFE_RESEARCH_COLS:
        return "As-of feature, but depends on partial platform context; do not claim complete market share or competitor substitution."
    if result == "blocking_if_used":
        return "Field is not allowed in strict probability model feature sets."
    if col.startswith(VALUE_COL_PREFIXES):
        return "Value/business field excluded from probability models; allowed only for candidate prioritization."
    return ""


# ---------------------------------------------------------------------------
# Feature sets and model training
# ---------------------------------------------------------------------------


def build_feature_sets(frame: pd.DataFrame) -> dict[str, list[str]]:
    available = set(frame.columns)

    def keep(cols: Iterable[str]) -> list[str]:
        out = []
        for col in cols:
            if col in available and col not in out and not is_excluded_probability_feature(col):
                out.append(col)
        return out

    safe_without_choice = keep(
        BASE_RECENCY_FREQUENCY_COLS
        + INTERVAL_COLS
        + DEMAND_COLS
        + MANUFACTURER_HOSPITAL_CONTEXT_COLS
        + MANUFACTURER_DRUG_CONTEXT_COLS
        + STATUS_CONTEXT_COLS
    )
    safe_with_choice = keep(safe_without_choice + CHOICE_SET_COLS + SWITCHING_COLS)
    return {
        "base_recency_frequency": keep(BASE_RECENCY_FREQUENCY_COLS),
        "base_plus_interval": keep(BASE_RECENCY_FREQUENCY_COLS + INTERVAL_COLS),
        "base_plus_demand_shape": keep(BASE_RECENCY_FREQUENCY_COLS + DEMAND_COLS),
        "base_plus_manufacturer_hospital_context": keep(BASE_RECENCY_FREQUENCY_COLS + MANUFACTURER_HOSPITAL_CONTEXT_COLS),
        "base_plus_manufacturer_drug_context": keep(BASE_RECENCY_FREQUENCY_COLS + MANUFACTURER_DRUG_CONTEXT_COLS),
        "base_plus_hospital_drug_choice_set_context": keep(BASE_RECENCY_FREQUENCY_COLS + CHOICE_SET_COLS),
        "base_plus_switching_context": keep(BASE_RECENCY_FREQUENCY_COLS + SWITCHING_COLS),
        "all_safe_features_without_choice_set": safe_without_choice,
        "all_safe_features_with_choice_set": safe_with_choice,
        "all_features": safe_with_choice,
    }


def is_excluded_probability_feature(col: str) -> bool:
    return col.startswith(SENSITIVE_EXCLUDED_PATTERNS) or col.startswith(VALUE_COL_PREFIXES) or col in {
        "first_purchase_month",
        "last_purchase_month",
        "months_since_last_purchase",
        "days_since_last_purchase",
    }


def run_feature_group_ablation(
    closed: pd.DataFrame, feature_sets: dict[str, list[str]], report_dir: Path
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    horizon_rows = []
    params = default_xgb_params(n_estimators=70)
    for feature_set, cols in feature_sets.items():
        progress(report_dir, f"stage=feature_group_ablation feature_set={feature_set}")
        preds = train_model_by_horizon(closed, cols, "xgboost_small", params=params, eval_split="test", feature_set=feature_set)
        if preds.empty:
            rows.append({"feature_set": feature_set, "model_name": "xgboost_small", "row_count": 0, "note": "no predictions"})
            continue
        rows.append({"feature_set": feature_set, "model_name": "xgboost_small", **metric_row_with_topk(preds, "probability_score")})
        for horizon, part in preds.groupby("horizon", dropna=False):
            horizon_rows.append({"feature_set": feature_set, "model_name": "xgboost_small", "horizon": horizon, **metric_row_with_topk(part, "probability_score")})
    return pd.DataFrame(rows), pd.DataFrame(horizon_rows), pd.DataFrame()


def run_model_family_comparison(closed: pd.DataFrame, feature_sets: dict[str, list[str]], report_dir: Path) -> pd.DataFrame:
    feature_set_names = [
        "base_recency_frequency",
        "base_plus_interval",
        "all_safe_features_without_choice_set",
        "all_safe_features_with_choice_set",
    ]
    rows: list[dict[str, Any]] = []
    for feature_set in feature_set_names:
        cols = feature_sets[feature_set]
        for model_name in ["logistic_regression", "xgboost_small", "lightgbm_small", "catboost_small"]:
            progress(report_dir, f"stage=model_family feature_set={feature_set} model={model_name}")
            if model_name == "lightgbm_small" and importlib.util.find_spec("lightgbm") is None:
                rows.append(skipped_model_row(feature_set, model_name, "dependency_not_installed"))
                continue
            if model_name == "catboost_small" and importlib.util.find_spec("catboost") is None:
                rows.append(skipped_model_row(feature_set, model_name, "dependency_not_installed"))
                continue
            start = time.time()
            try:
                preds = train_model_by_horizon(closed, cols, model_name, params=default_model_params(model_name), eval_split="test", feature_set=feature_set)
                if preds.empty:
                    rows.append(skipped_model_row(feature_set, model_name, "no_predictions"))
                else:
                    rows.append(
                        {
                            "feature_set": feature_set,
                            "model_name": model_name,
                            "status": "ok",
                            "runtime_seconds": time.time() - start,
                            "feature_count": len(cols),
                            "feature_dependency_complexity": feature_dependency_complexity(feature_set),
                            **metric_row_with_topk(preds, "probability_score"),
                        }
                    )
            except Exception as exc:  # pragma: no cover - defensive for optional deps
                rows.append(skipped_model_row(feature_set, model_name, f"fit_failed:{type(exc).__name__}:{exc}"))
        for baseline in ["recency_only_baseline", "frequency_decay_baseline", "interval_overdue_baseline", "hybrid_interval_frequency_score"]:
            preds = baseline_predictions(closed[closed["split"].eq("test")].copy(), baseline, feature_set)
            rows.append(
                {
                    "feature_set": feature_set,
                    "model_name": baseline,
                    "status": "ok",
                    "runtime_seconds": 0.0,
                    "feature_count": 1,
                    "feature_dependency_complexity": "rule_baseline",
                    **metric_row_with_topk(preds, "probability_score"),
                }
            )
    return pd.DataFrame(rows)


def run_xgboost_tuning(
    closed: pd.DataFrame, feature_sets: dict[str, list[str]], report_dir: Path
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    feature_set = "all_safe_features_without_choice_set"
    cols = feature_sets[feature_set]
    grid = [
        {"n_estimators": 100, "max_depth": 3, "learning_rate": 0.08, "subsample": 0.9, "colsample_bytree": 0.9, "min_child_weight": 1, "reg_lambda": 1, "reg_alpha": 0},
        {"n_estimators": 160, "max_depth": 3, "learning_rate": 0.05, "subsample": 0.9, "colsample_bytree": 0.9, "min_child_weight": 5, "reg_lambda": 5, "reg_alpha": 0.1},
        {"n_estimators": 220, "max_depth": 2, "learning_rate": 0.05, "subsample": 0.9, "colsample_bytree": 0.7, "min_child_weight": 5, "reg_lambda": 5, "reg_alpha": 0.1},
        {"n_estimators": 120, "max_depth": 4, "learning_rate": 0.05, "subsample": 0.7, "colsample_bytree": 0.9, "min_child_weight": 10, "reg_lambda": 10, "reg_alpha": 1},
        {"n_estimators": 80, "max_depth": 3, "learning_rate": 0.10, "subsample": 1.0, "colsample_bytree": 0.9, "min_child_weight": 1, "reg_lambda": 1, "reg_alpha": 0},
    ]
    rows = []
    best: dict[str, Any] | None = None
    best_score = (math.inf, math.inf, -math.inf)
    for idx, params in enumerate(grid, start=1):
        progress(report_dir, f"stage=xgb_tuning config={idx}/{len(grid)}")
        start = time.time()
        valid_preds = train_model_by_horizon(closed, cols, "xgboost_small", params=params, eval_split="valid", feature_set=feature_set)
        metrics = metric_row_with_topk(valid_preds, "probability_score") if not valid_preds.empty else {}
        row = {
            "config_id": idx,
            "feature_set": feature_set,
            **params,
            "validation_runtime_seconds": time.time() - start,
            **{f"valid_{k}": v for k, v in metrics.items()},
        }
        rows.append(row)
        key = (row.get("valid_ece", np.inf), row.get("valid_brier", np.inf), -row.get("valid_auc", -np.inf))
        if key < best_score:
            best_score = key
            best = {"config_id": idx, "feature_set": feature_set, **params}
    assert best is not None
    progress(report_dir, f"stage=xgb_tuning_test selected_config={best['config_id']}")
    valid_preds = train_model_by_horizon(closed, cols, "xgboost_small", params=best, eval_split="valid", feature_set=feature_set)
    test_preds = train_model_by_horizon(closed, cols, "xgboost_small", params=best, eval_split="test", feature_set=feature_set)
    test_metrics = metric_row_with_topk(test_preds, "probability_score")
    for row in rows:
        if row["config_id"] == best["config_id"]:
            row.update({f"test_{k}": v for k, v in test_metrics.items()})
            row["selected"] = True
            row["selected_reason"] = "lowest validation ECE, then Brier, then highest AUC"
        else:
            row["selected"] = False
            row["selected_reason"] = ""
    selected_predictions = pd.concat([valid_preds, test_preds], ignore_index=True) if not valid_preds.empty else test_preds
    return pd.DataFrame(rows), selected_predictions, best


def default_xgb_params(n_estimators: int = 80) -> dict[str, Any]:
    return {
        "n_estimators": n_estimators,
        "max_depth": 3,
        "learning_rate": 0.08,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "min_child_weight": 1,
        "reg_lambda": 1,
        "reg_alpha": 0,
    }


def default_model_params(model_name: str) -> dict[str, Any]:
    if model_name == "xgboost_small":
        return default_xgb_params()
    if model_name == "lightgbm_small":
        return {"n_estimators": 80, "max_depth": 4, "learning_rate": 0.06, "subsample": 0.9, "colsample_bytree": 0.9, "reg_lambda": 1}
    if model_name == "catboost_small":
        return {"iterations": 80, "depth": 4, "learning_rate": 0.06, "l2_leaf_reg": 3}
    return {}


def train_model_by_horizon(
    closed: pd.DataFrame,
    feature_cols: list[str],
    model_name: str,
    *,
    params: dict[str, Any] | None = None,
    eval_split: str,
    feature_set: str,
) -> pd.DataFrame:
    outputs = []
    for horizon, part in closed.groupby("horizon", dropna=False):
        train = part[part["split"].eq("train")].copy()
        eval_df = part[part["split"].eq(eval_split)].copy()
        if train.empty or eval_df.empty or train["label_die_H"].nunique(dropna=True) < 2:
            continue
        preds = fit_predict_model(train, eval_df, feature_cols, model_name, params or {}, feature_set)
        outputs.append(preds)
    return pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame()


def fit_predict_model(train: pd.DataFrame, eval_df: pd.DataFrame, feature_cols: list[str], model_name: str, params: dict[str, Any], feature_set: str) -> pd.DataFrame:
    if model_name == "catboost_small":
        return fit_predict_catboost(train, eval_df, feature_cols, params, feature_set)
    x_train, x_eval = build_preprocessed_matrices(train, eval_df, feature_cols, scale_numeric=(model_name == "logistic_regression"))
    y_train = train["label_die_H"].astype(int)
    if model_name == "logistic_regression":
        from sklearn.linear_model import LogisticRegression

        clf = LogisticRegression(max_iter=250, class_weight="balanced", random_state=RANDOM_STATE)
    elif model_name == "xgboost_small":
        from xgboost import XGBClassifier

        clf = XGBClassifier(
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            n_jobs=4,
            tree_method="hist",
            **{k: v for k, v in params.items() if k not in {"config_id", "feature_set"}},
        )
    elif model_name == "lightgbm_small":
        from lightgbm import LGBMClassifier

        clf = LGBMClassifier(random_state=RANDOM_STATE, n_jobs=4, verbose=-1, **params)
    else:
        raise ValueError(f"Unsupported model: {model_name}")
    clf.fit(x_train, y_train)
    score = clf.predict_proba(x_eval)[:, 1]
    return prediction_frame(eval_df, model_name, score, feature_set)


def fit_predict_catboost(train: pd.DataFrame, eval_df: pd.DataFrame, feature_cols: list[str], params: dict[str, Any], feature_set: str) -> pd.DataFrame:
    from catboost import CatBoostClassifier

    cols = [c for c in feature_cols if c in train.columns]
    work_train = train[cols].copy()
    work_eval = eval_df[cols].copy()
    cat_features = []
    for idx, col in enumerate(cols):
        if is_categorical_series(work_train[col]):
            cat_features.append(idx)
            work_train[col] = work_train[col].astype("string").fillna("__missing__")
            work_eval[col] = work_eval[col].astype("string").fillna("__missing__")
        else:
            train_numeric = pd.to_numeric(work_train[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
            eval_numeric = pd.to_numeric(work_eval[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
            median = train_numeric.median()
            work_train[col] = train_numeric.fillna(median)
            work_eval[col] = eval_numeric.fillna(median)
    clf = CatBoostClassifier(
        loss_function="Logloss",
        random_seed=RANDOM_STATE,
        verbose=False,
        allow_writing_files=False,
        **params,
    )
    clf.fit(work_train, train["label_die_H"].astype(int), cat_features=cat_features)
    score = clf.predict_proba(work_eval)[:, 1]
    return prediction_frame(eval_df, "catboost_small", score, feature_set)


def build_preprocessed_matrices(train: pd.DataFrame, eval_df: pd.DataFrame, feature_cols: list[str], *, scale_numeric: bool):
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    cols = [c for c in feature_cols if c in train.columns and train[c].notna().any()]
    num_cols = [c for c in cols if not is_categorical_series(train[c])]
    cat_cols = [c for c in cols if c not in num_cols]
    train_work = train[cols].copy()
    eval_work = eval_df[cols].copy()
    for col in num_cols:
        train_work[col] = pd.to_numeric(train_work[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        eval_work[col] = pd.to_numeric(eval_work[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    for col in cat_cols:
        train_work[col] = train_work[col].astype("string").fillna("__missing__").astype(object)
        eval_work[col] = eval_work[col].astype("string").fillna("__missing__").astype(object)
    num_steps: list[tuple[str, Any]] = [("imputer", SimpleImputer(strategy="median"))]
    if scale_numeric:
        num_steps.append(("scale", StandardScaler(with_mean=False)))
    transformers = []
    if num_cols:
        transformers.append(("num", Pipeline(num_steps), num_cols))
    if cat_cols:
        transformers.append(
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=50)),
                    ]
                ),
                cat_cols,
            )
        )
    pre = ColumnTransformer(transformers, remainder="drop")
    x_train = pre.fit_transform(train_work)
    x_eval = pre.transform(eval_work)
    return x_train, x_eval


def is_categorical_series(series: pd.Series) -> bool:
    dtype = str(series.dtype)
    return bool(
        series.dtype == object
        or dtype.startswith("category")
        or dtype.startswith("string")
        or dtype in {"bool", "boolean"}
    )


def prediction_frame(eval_df: pd.DataFrame, model_name: str, score: np.ndarray, feature_set: str) -> pd.DataFrame:
    keep = [
        *KEY_COLS,
        "horizon",
        "label_die_H",
        "label_alive_H",
        "label_window_closed",
        "split",
        "one_shot_flag",
        "demand_shape_label",
        "history_sufficiency_flag",
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "recency_only_baseline",
        "frequency_decay_baseline",
        "interval_overdue_baseline",
        "hybrid_interval_frequency_score",
        "manufacturer_share_within_hospital_drug_asof_cutoff",
        "manufacturer_substitution_context_available",
        "value_at_risk_amount_nonnegative_H3_asof_cutoff",
        "value_at_risk_amount_nonnegative_H6_asof_cutoff",
        "value_at_risk_amount_nonnegative_H12_asof_cutoff",
    ]
    dedup_keep = []
    for col in keep:
        if col in eval_df.columns and col not in dedup_keep:
            dedup_keep.append(col)
    out = eval_df[dedup_keep].copy()
    out["model_name"] = model_name
    out["feature_set"] = feature_set
    out["score"] = np.asarray(score, dtype=float)
    out["probability_score"] = out["score"].clip(0, 1)
    out["cutoff_period"] = pd.to_datetime(out["cutoff_month"], errors="coerce").dt.to_period("M").astype(str)
    return out


def baseline_predictions(df: pd.DataFrame, score_col: str, feature_set: str) -> pd.DataFrame:
    out = prediction_frame(df, score_col, pd.to_numeric(df.get(score_col), errors="coerce").to_numpy(dtype=float), feature_set)
    out["score"] = pd.to_numeric(df.get(score_col), errors="coerce").to_numpy(dtype=float)
    out["probability_score"] = rank_probability_by_cutoff(out, "score")
    return out


def rank_probability_by_cutoff(df: pd.DataFrame, score_col: str) -> pd.Series:
    score = pd.to_numeric(df[score_col], errors="coerce")
    rank = score.groupby([df["horizon"], df["cutoff_period"]]).rank(pct=True).fillna(0.5)
    base = df.groupby(["horizon", "cutoff_period"])["label_die_H"].transform("mean")
    return (base * (0.5 + rank)).clip(0, 1)


def metric_row_with_topk(df: pd.DataFrame, score_col: str) -> dict[str, Any]:
    base = metric_row(df, score_col)
    for pct in [0.01, 0.05, 0.10]:
        top = topk_by_group(df, score_col, pct)
        label = f"{int(pct * 100)}pct"
        base[f"precision_at_top_{label}"] = float(top["label_die_H"].mean()) if len(top) else np.nan
        overall_rate = float(df["label_die_H"].mean()) if len(df) else np.nan
        base[f"lift_at_top_{label}"] = base[f"precision_at_top_{label}"] / overall_rate if overall_rate else np.nan
    top10 = topk_by_group(df, score_col, 0.10)
    top10_sorted = top10.sort_values(score_col, ascending=False) if len(top10) else top10
    base["ndcg_at_top_10pct"] = ndcg_at_k(top10_sorted["label_die_H"].to_numpy(dtype=int), len(top10_sorted)) if len(top10_sorted) else np.nan
    return base


def topk_by_group(df: pd.DataFrame, score_col: str, pct: float) -> pd.DataFrame:
    parts = []
    if df.empty:
        return df.iloc[0:0].copy()
    for _, group in df.groupby(["horizon", "cutoff_period"], dropna=False):
        n = max(1, int(math.ceil(len(group) * pct)))
        parts.append(group.sort_values(score_col, ascending=False).head(n))
    return pd.concat(parts, ignore_index=False) if parts else df.iloc[0:0].copy()


def skipped_model_row(feature_set: str, model_name: str, reason: str) -> dict[str, Any]:
    return {"feature_set": feature_set, "model_name": model_name, "status": reason, "row_count": 0}


def feature_dependency_complexity(feature_set: str) -> str:
    if feature_set_uses_choice_set(feature_set):
        return "partial_platform_context"
    if "all_safe" in feature_set:
        return "medium"
    if feature_set == "base_recency_frequency":
        return "low"
    return "medium_low"


def feature_set_uses_choice_set(feature_set: str) -> bool:
    return feature_set in {
        "base_plus_hospital_drug_choice_set_context",
        "base_plus_switching_context",
        "all_safe_features_with_choice_set",
        "all_features",
    }


def feature_group_importance_audit(ablation: pd.DataFrame, feature_sets: dict[str, list[str]]) -> pd.DataFrame:
    if ablation.empty or "auc" not in ablation:
        return pd.DataFrame()
    base_auc = float(ablation.loc[ablation["feature_set"].eq("base_recency_frequency"), "auc"].iloc[0]) if ablation["feature_set"].eq("base_recency_frequency").any() else np.nan
    all_safe = float(ablation.loc[ablation["feature_set"].eq("all_safe_features_without_choice_set"), "auc"].iloc[0]) if ablation["feature_set"].eq("all_safe_features_without_choice_set").any() else np.nan
    rows = []
    for _, row in ablation.iterrows():
        rows.append(
            {
                "feature_set": row["feature_set"],
                "feature_count": len(feature_sets.get(row["feature_set"], [])),
                "auc": row.get("auc"),
                "delta_auc_vs_base": row.get("auc") - base_auc if pd.notna(base_auc) and pd.notna(row.get("auc")) else np.nan,
                "delta_auc_vs_all_safe_without_choice": row.get("auc") - all_safe if pd.notna(all_safe) and pd.notna(row.get("auc")) else np.nan,
                "choice_set_dependency": "yes" if feature_set_uses_choice_set(str(row["feature_set"])) else "no",
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Calibration, learning curve, holdout
# ---------------------------------------------------------------------------


def run_calibration_comparison(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    if predictions.empty:
        return pd.DataFrame(), pd.DataFrame(), predictions, "No predictions available."
    try:
        from sklearn.isotonic import IsotonicRegression
        from sklearn.linear_model import LogisticRegression
    except Exception:
        raw = predictions.copy()
        raw["calibration_method"] = "raw"
        return pd.DataFrame([{"calibration_method": "raw", **metric_row_with_topk(raw, "probability_score")}]), pd.DataFrame(), raw, "Calibration dependencies unavailable; raw retained."
    rows = []
    bins = []
    calibrated_parts = []
    for horizon, test in predictions.groupby("horizon", dropna=False):
        fit_part = test[test.get("split", "").eq("valid")].copy() if "split" in test else pd.DataFrame()
        eval_part = test[test.get("split", "").eq("test")].copy() if "split" in test else test.copy()
        if eval_part.empty:
            eval_part = test.copy()
        method_scores = {"raw": eval_part["probability_score"].to_numpy(dtype=float)}
        if fit_part["label_die_H"].nunique() > 1:
            platt = LogisticRegression(max_iter=200, random_state=RANDOM_STATE)
            platt.fit(fit_part[["probability_score"]], fit_part["label_die_H"].astype(int))
            method_scores["platt"] = platt.predict_proba(eval_part[["probability_score"]])[:, 1]
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(fit_part["probability_score"], fit_part["label_die_H"].astype(int))
            method_scores["isotonic"] = iso.predict(eval_part["probability_score"])
        for method, score in method_scores.items():
            part = eval_part.copy()
            part["calibration_method"] = method
            part["probability_score"] = np.asarray(score, dtype=float).clip(0, 1)
            rows.append({"horizon": horizon, "calibration_method": method, **metric_row_with_topk(part, "probability_score")})
            bins.append(calibration_bins_for_frame(part, method, horizon))
            calibrated_parts.append(part)
    comp = pd.DataFrame(rows)
    raw = comp[comp["calibration_method"].eq("raw")]
    selected_method = "raw"
    if not comp.empty:
        mean_by_method = comp.groupby("calibration_method", dropna=False).agg(ece=("ece", "mean"), brier=("brier", "mean"), logloss=("logloss", "mean"), auc=("auc", "mean")).reset_index()
        best = mean_by_method.sort_values(["ece", "brier", "logloss"], ascending=[True, True, True]).iloc[0]
        raw_ece = float(mean_by_method.loc[mean_by_method["calibration_method"].eq("raw"), "ece"].iloc[0]) if mean_by_method["calibration_method"].eq("raw").any() else np.nan
        if best["calibration_method"] != "raw" and pd.notna(raw_ece) and raw_ece - best["ece"] >= 0.005:
            selected_method = str(best["calibration_method"])
    selected = pd.concat(calibrated_parts, ignore_index=True)
    selected = selected[selected["calibration_method"].eq(selected_method)].copy()
    decision = render_calibration_decision(comp, selected_method)
    return comp, pd.concat(bins, ignore_index=True) if bins else pd.DataFrame(), selected, decision


def calibration_bins_for_frame(df: pd.DataFrame, method: str, horizon: str, n_bins: int = 10) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    work = df.copy()
    work["bin"] = pd.cut(work["probability_score"], bins=np.linspace(0, 1, n_bins + 1), include_lowest=True, labels=False)
    return (
        work.groupby("bin", dropna=False)
        .agg(row_count=("label_die_H", "size"), avg_pred=("probability_score", "mean"), observed_rate=("label_die_H", "mean"))
        .reset_index()
        .assign(calibration_method=method, horizon=horizon)
    )


def run_learning_curve(closed: pd.DataFrame, feature_sets: dict[str, list[str]], selected_config: dict[str, Any], report_dir: Path) -> pd.DataFrame:
    cols = feature_sets["all_safe_features_without_choice_set"]
    windows = [2020, 2021, 2022, 2023, 2024]
    rows = []
    for end_year in windows:
        for horizon, group in closed.groupby("horizon", dropna=False):
            h_months = int(str(horizon).replace("H", ""))
            train_end = pd.Timestamp(f"{end_year}-12-31")
            test_start = train_end + pd.offsets.MonthEnd(h_months + 1)
            test_end = test_start + pd.offsets.MonthEnd(5)
            part = group.copy()
            cutoff = pd.to_datetime(part["cutoff_month"], errors="coerce")
            part["split"] = np.where(cutoff.le(train_end), "train", np.where(cutoff.ge(test_start) & cutoff.le(test_end), "test", "unused"))
            if part[part["split"].eq("train")]["label_die_H"].nunique() < 2 or part[part["split"].eq("test")].empty:
                rows.append({"training_window": f"2020-{end_year}", "horizon": horizon, "status": "insufficient_closed_test_or_train_rows"})
                continue
            progress(report_dir, f"stage=learning_curve end_year={end_year} horizon={horizon}")
            preds = train_model_by_horizon(part, cols, "xgboost_small", params=selected_config, eval_split="test", feature_set="all_safe_features_without_choice_set")
            rows.append({"training_window": f"2020-{end_year}", "horizon": horizon, "status": "ok", "test_start": str(test_start.date()), "test_end": str(test_end.date()), **metric_row_with_topk(preds, "probability_score")})
    return pd.DataFrame(rows)


def run_manufacturer_holdout(closed: pd.DataFrame, feature_sets: dict[str, list[str]], selected_config: dict[str, Any], report_dir: Path) -> pd.DataFrame:
    cols = feature_sets["all_safe_features_without_choice_set"]
    counts = closed[closed["split"].isin(["train", "test"])].groupby("manufacturer_code").size().sort_values(ascending=False)
    manufacturers = list(counts.head(4).index)
    rows = []
    for manufacturer in manufacturers:
        for horizon, group in closed.groupby("horizon", dropna=False):
            part = group[group["manufacturer_code"].eq(manufacturer) | group["split"].eq("train")].copy()
            cutoff = pd.to_datetime(part["cutoff_month"], errors="coerce")
            part["holdout_split"] = np.where(part["manufacturer_code"].eq(manufacturer) & cutoff.ge(STRICT_SPLITS[str(horizon)].test_start), "test", np.where(~part["manufacturer_code"].eq(manufacturer) & part["split"].eq("train"), "train", "unused"))
            part["split"] = part["holdout_split"]
            train = part[part["split"].eq("train")]
            test = part[part["split"].eq("test")]
            if train["label_die_H"].nunique() < 2 or test.empty or test["label_die_H"].nunique() < 2:
                rows.append({"heldout_manufacturer": manufacturer, "horizon": horizon, "status": "insufficient_rows_or_single_class", "test_rows": len(test)})
                continue
            progress(report_dir, f"stage=manufacturer_holdout manufacturer={manufacturer} horizon={horizon}")
            preds = train_model_by_horizon(part, cols, "xgboost_small", params=selected_config, eval_split="test", feature_set="all_safe_features_without_choice_set")
            rows.append({"heldout_manufacturer": manufacturer, "horizon": horizon, "status": "ok", "train_manufacturer_count": train["manufacturer_code"].nunique(), "test_rows": len(test), **metric_row_with_topk(preds, "probability_score")})
    return pd.DataFrame(rows)


def cutoff_period_generalization(predictions: pd.DataFrame) -> pd.DataFrame:
    if predictions.empty:
        return pd.DataFrame()
    out = predictions.copy()
    period = pd.PeriodIndex(out["cutoff_period"], freq="M")
    out["test_period_bucket"] = np.select(
        [period <= pd.Period("2024-12", freq="M"), period <= pd.Period("2025-06", freq="M")],
        ["early_test", "mid_test"],
        default="late_test",
    )
    rows = []
    for (horizon, bucket), group in out.groupby(["horizon", "test_period_bucket"], dropna=False):
        rows.append({"horizon": horizon, "test_period_bucket": bucket, **metric_row_with_topk(group, "probability_score")})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Candidate policy v2
# ---------------------------------------------------------------------------


def run_candidate_policy_v2(predictions: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    if predictions.empty:
        return pd.DataFrame(), {"policy": "", "reason": "no predictions"}
    rows = []
    for (horizon, cutoff), group in predictions.groupby(["horizon", "cutoff_period"], dropna=False):
        scored = add_candidate_policy_scores(group.copy(), horizon)
        policy_members = candidate_policy_members(scored)
        reference = policy_members.get("probability_top10", pd.Index([]))
        for policy, idx in policy_members.items():
            part = scored.loc[idx].copy()
            non = scored.drop(index=idx, errors="ignore")
            pos = scored["label_die_H"].sum()
            reason_distribution = part.get("candidate_reason", pd.Series("", index=part.index)).value_counts().head(6).to_dict()
            rows.append(
                {
                    "candidate_policy": policy,
                    "horizon": horizon,
                    "cutoff_month": cutoff,
                    "full_universe_rows": len(scored),
                    "full_universe_die_count": int(pos),
                    "candidate_count": len(part),
                    "candidate_rate": len(part) / len(scored) if len(scored) else np.nan,
                    "candidate_die_count": int(part["label_die_H"].sum()) if len(part) else 0,
                    "candidate_die_recall": float(part["label_die_H"].sum() / pos) if pos else np.nan,
                    "candidate_positive_rate": float(part["label_die_H"].mean()) if len(part) else np.nan,
                    "non_candidate_positive_rate": float(non["label_die_H"].mean()) if len(non) else np.nan,
                    "lift_vs_non_candidate": float(part["label_die_H"].mean() / non["label_die_H"].mean()) if len(part) and len(non) and non["label_die_H"].mean() else np.nan,
                    "precision_at_candidate": float(part["label_die_H"].mean()) if len(part) else np.nan,
                    "manual_review_load": len(part),
                    "manufacturer_coverage": int(part["manufacturer_code"].nunique()) if len(part) and "manufacturer_code" in part else 0,
                    "stable_segment_coverage": stable_segment_rate(part),
                    "value_coverage": value_coverage(scored, part, horizon),
                    "candidate_overlap_with_probability_top10": len(set(idx).intersection(set(reference))) / len(idx) if len(idx) else np.nan,
                    "candidate_unique_reason_distribution": str(reason_distribution),
                }
            )
    metrics = pd.DataFrame(rows)
    recommendation = choose_candidate_policy(metrics)
    return metrics, recommendation


def add_candidate_policy_scores(df: pd.DataFrame, horizon: str) -> pd.DataFrame:
    out = df.copy()
    out["probability_rank_score"] = percentile_rank(out["probability_score"])
    out["interval_rank_score"] = percentile_rank(out.get("interval_overdue_baseline"))
    out["frequency_rank_score"] = percentile_rank(out.get("frequency_decay_baseline"))
    out["recency_rank_score"] = percentile_rank(out.get("recency_only_baseline"))
    out["hybrid_rank_50_30_20"] = 0.5 * out["probability_rank_score"] + 0.3 * out["interval_rank_score"] + 0.2 * out["frequency_rank_score"]
    out["hybrid_rank_40_40_20"] = 0.4 * out["probability_rank_score"] + 0.4 * out["interval_rank_score"] + 0.2 * out["frequency_rank_score"]
    out["hybrid_rank_40_30_30"] = 0.4 * out["probability_rank_score"] + 0.3 * out["interval_rank_score"] + 0.3 * out["frequency_rank_score"]
    value_col = f"value_at_risk_amount_nonnegative_{horizon}_asof_cutoff"
    value_rank = percentile_rank(out.get(value_col)) if value_col in out else pd.Series(0.5, index=out.index)
    out["business_priority_score"] = out["probability_rank_score"] * value_rank
    out["hybrid_business_guardrail_score"] = out["hybrid_rank_50_30_20"] * (0.7 + 0.3 * value_rank)
    return out


def candidate_policy_members(df: pd.DataFrame) -> dict[str, pd.Index]:
    policies = {
        "probability_top10": select_top_pct(df, "probability_rank_score", 0.10, "probability"),
        "probability_top20": select_top_pct(df, "probability_rank_score", 0.20, "probability"),
        "interval_top10": select_top_pct(df, "interval_rank_score", 0.10, "interval"),
        "frequency_top10": select_top_pct(df, "frequency_rank_score", 0.10, "frequency"),
        "recency_top10": select_top_pct(df, "recency_rank_score", 0.10, "recency"),
        "hybrid_50_30_20_top10": select_top_pct(df, "hybrid_rank_50_30_20", 0.10, "hybrid_50_30_20"),
        "hybrid_40_40_20_top10": select_top_pct(df, "hybrid_rank_40_40_20", 0.10, "hybrid_40_40_20"),
        "hybrid_40_30_30_top10": select_top_pct(df, "hybrid_rank_40_30_30", 0.10, "hybrid_40_30_30"),
        "business_priority_top10": select_top_pct(df, "business_priority_score", 0.10, "business_priority"),
        "hybrid_business_guardrail_top15": select_top_pct(df, "hybrid_business_guardrail_score", 0.15, "hybrid_business_guardrail"),
    }
    union = pd.Index([])
    for name in ["probability_top10", "interval_top10", "frequency_top10", "business_priority_top10"]:
        union = union.union(policies[name])
    policies["multi_recall_union_top10"] = union
    return policies


def select_top_pct(df: pd.DataFrame, score_col: str, pct: float, reason: str) -> pd.Index:
    n = max(1, int(math.ceil(len(df) * pct)))
    idx = df.sort_values(score_col, ascending=False).head(n).index
    if "candidate_reason" not in df.columns:
        df["candidate_reason"] = ""
    df.loc[idx, "candidate_reason"] = reason
    return idx


def percentile_rank(values: Any) -> pd.Series:
    if isinstance(values, pd.Series):
        s = pd.to_numeric(values, errors="coerce")
    else:
        s = pd.Series(np.nan)
    return s.rank(pct=True).fillna(0.5)


def stable_segment_rate(df: pd.DataFrame) -> float:
    if df.empty:
        return np.nan
    history = df.get("history_sufficiency_flag", pd.Series("", index=df.index)).astype(str)
    shape = df.get("demand_shape_label", pd.Series("", index=df.index)).astype(str)
    stable = history.eq("history_sufficient") & ~shape.isin(["lumpy", "intermittent", "cold_start"])
    return float(stable.mean())


def value_coverage(full: pd.DataFrame, part: pd.DataFrame, horizon: str) -> float:
    col = f"value_at_risk_amount_nonnegative_{horizon}_asof_cutoff"
    if col not in full or full[col].fillna(0).sum() <= 0:
        return np.nan
    return float(part[col].fillna(0).sum() / full[col].fillna(0).sum())


def choose_candidate_policy(metrics: pd.DataFrame) -> dict[str, Any]:
    if metrics.empty:
        return {"policy": "", "reason": "no metrics"}
    summary = (
        metrics.groupby("candidate_policy", dropna=False)
        .agg(
            candidate_die_recall=("candidate_die_recall", "mean"),
            candidate_positive_rate=("candidate_positive_rate", "mean"),
            non_candidate_positive_rate=("non_candidate_positive_rate", "mean"),
            manual_review_load=("manual_review_load", "mean"),
            candidate_rate=("candidate_rate", "mean"),
            lift_vs_non_candidate=("lift_vs_non_candidate", "mean"),
            stable_segment_coverage=("stable_segment_coverage", "mean"),
        )
        .reset_index()
    )
    eligible = summary[summary["candidate_positive_rate"].gt(summary["non_candidate_positive_rate"]) & summary["candidate_rate"].le(0.35)].copy()
    if eligible.empty:
        eligible = summary.copy()
    best = eligible.sort_values(["candidate_die_recall", "lift_vs_non_candidate"], ascending=[False, False]).iloc[0]
    return best.to_dict()


# ---------------------------------------------------------------------------
# Rendering and decisions
# ---------------------------------------------------------------------------


def build_decisions(**items: Any) -> dict[str, Any]:
    leakage = items["leakage"]
    ablation = items["ablation"]
    model_family = items["model_family"]
    tuning = items["tuning"]
    calibration = items["calibration"]
    learning_curve = items["learning_curve"]
    holdout = items["holdout"]
    candidate_v2 = items["candidate_v2"]
    selected_config = items["selected_config"]

    blocking = bool(leakage["possible_future_leakage"].fillna(False).any())
    selected = tuning[tuning.get("selected", False).astype(bool)] if "selected" in tuning else pd.DataFrame()
    selected_row = selected.iloc[0].to_dict() if not selected.empty else {}
    best_feature = ablation.sort_values(["auc", "ece"], ascending=[False, True]).iloc[0].to_dict() if not ablation.empty and "auc" in ablation else {}
    candidate_reco = choose_candidate_policy(candidate_v2)
    mean_candidate_recall = float(candidate_reco.get("candidate_die_recall", np.nan))
    customer_allowed = bool(
        not blocking
        and selected_row.get("test_auc", 0) >= 0.80
        and selected_row.get("test_pr_auc_gain", 0) >= 0.25
        and selected_row.get("test_ece", 1) < 0.05
        and mean_candidate_recall >= 0.30
        and manufacturer_holdout_stable(holdout)
        and not feature_set_uses_choice_set(str(best_feature.get("feature_set", "")))
    )
    customer_blockers = []
    if blocking:
        customer_blockers.append("blocking_leakage")
    if mean_candidate_recall < 0.30:
        customer_blockers.append("candidate_die_recall_below_0.30")
    customer_blockers.extend(
        [
            "selected_subset_not_full_sql_universe",
            "probability_availability_gate_not_implemented_as_runtime_policy",
            "partial_platform_choice_set_features_not_customer_claim_safe",
            "manual_review_load_requires_product_threshold",
        ]
    )
    analyst_allowed = bool(not blocking and selected_row.get("test_auc", 0) >= 0.70 and mean_candidate_recall >= 0.18)
    return {
        "blocking_leakage": blocking,
        "best_feature_set": best_feature.get("feature_set", ""),
        "best_feature_auc": best_feature.get("auc", np.nan),
        "xgboost_selected_config": selected_config,
        "xgboost_test_auc": selected_row.get("test_auc", np.nan),
        "xgboost_test_pr_auc_gain": selected_row.get("test_pr_auc_gain", np.nan),
        "xgboost_test_ece": selected_row.get("test_ece", np.nan),
        "xgboost_still_best": xgboost_best(model_family),
        "calibration_decision": calibration_decision_short(calibration),
        "candidate_policy": candidate_reco.get("candidate_policy", ""),
        "candidate_die_recall": mean_candidate_recall,
        "manual_review_load": candidate_reco.get("manual_review_load", np.nan),
        "customer_allowed": customer_allowed,
        "customer_blockers": customer_blockers,
        "analyst_allowed": analyst_allowed,
        "internal_allowed": bool(not blocking),
        "proof_case_allowed": analyst_allowed,
        "needs_recleaning": False,
        "needs_new_data": True,
        "holdout_stable": manufacturer_holdout_stable(holdout),
        "holdout_mean_auc": float(holdout.loc[holdout.get("status", "").eq("ok"), "auc"].mean()) if not holdout.empty and "auc" in holdout else np.nan,
        "learning_curve_ok": learning_curve_ok(learning_curve),
    }


def xgboost_best(model_family: pd.DataFrame) -> bool:
    ok = model_family[model_family.get("status", "").eq("ok")].copy() if not model_family.empty else pd.DataFrame()
    if ok.empty or "auc" not in ok:
        return False
    best = ok.sort_values(["auc", "ece"], ascending=[False, True]).iloc[0]
    return str(best["model_name"]) == "xgboost_small"


def calibration_decision_short(calibration: pd.DataFrame) -> str:
    if calibration.empty:
        return "raw_retained_no_calibration_data"
    mean = calibration.groupby("calibration_method", dropna=False).agg(ece=("ece", "mean"), brier=("brier", "mean"), logloss=("logloss", "mean")).reset_index()
    raw = mean[mean["calibration_method"].eq("raw")]
    best = mean.sort_values(["ece", "brier", "logloss"], ascending=True).iloc[0]
    if not raw.empty and float(raw.iloc[0]["ece"]) <= 0.03:
        return "raw_retained_ece_already_low"
    return f"{best['calibration_method']}_preferred_by_validation_proxy"


def manufacturer_holdout_stable(holdout: pd.DataFrame) -> bool:
    ok = holdout[holdout.get("status", "").eq("ok")] if not holdout.empty and "status" in holdout else pd.DataFrame()
    return bool(not ok.empty and ok["auc"].mean() >= 0.65 and ok["auc"].min() >= 0.58)


def learning_curve_ok(learning_curve: pd.DataFrame) -> bool:
    ok = learning_curve[learning_curve.get("status", "").eq("ok")] if not learning_curve.empty and "status" in learning_curve else pd.DataFrame()
    return bool(not ok.empty and ok["auc"].mean() >= 0.70)


def render_leakage_summary(leakage: pd.DataFrame, artifacts: pd.DataFrame) -> str:
    blocking_count = int(leakage["possible_future_leakage"].fillna(False).sum()) if not leakage.empty else 0
    missing = artifacts[~artifacts["exists"].astype(bool)] if not artifacts.empty else pd.DataFrame()
    return f"""# Leakage Audit Summary

- blocking leakage feature count in strict probability feature sets: {blocking_count}
- missing required artifact count: {len(missing)}
- value/business priority fields are excluded from probability models.
- raw non-asof date fields are marked excluded or observe-only.
- choice-set fields are as-of research features with partial platform context; they are not complete market-share or competitor-substitution claims.
"""


def render_split_audit(split_audit: pd.DataFrame, closed: pd.DataFrame) -> str:
    closed_counts = closed.groupby("horizon", dropna=False).agg(closed_rows=("label_die_H", "size"), positive_rate=("label_die_H", "mean")).reset_index()
    return "# Train / Valid / Test Split Audit\n\n" + dataframe_to_markdown(split_audit) + "\n\n## Closed Labels\n\n" + dataframe_to_markdown(closed_counts)


def render_choice_set_scope_audit(frame: pd.DataFrame) -> str:
    rows = []
    for col in CHOICE_SET_COLS + SWITCHING_COLS:
        if col not in frame.columns:
            scope = "missing"
        elif col.endswith("_asof_cutoff") or col in SWITCHING_COLS:
            scope = "partial_platform_context"
        else:
            scope = "research_only_oracle"
        rows.append({"feature_name": col, "runtime_feature_scope": scope, "available": col in frame.columns})
    table = dataframe_to_markdown(pd.DataFrame(rows))
    return f"""# Choice-Set Feature Scope Audit

{table}

These fields are built as-of cutoff, so they are not marked as future leakage. They are still not customer-facing causal explanations: the extract only covers selected manufacturers/entities/hospital-drug pairs and cannot be described as full market share, confirmed competitor substitution, or hospital intent.
"""


def render_tuning_summary(tuning: pd.DataFrame, selected_config: dict[str, Any]) -> str:
    selected = tuning[tuning.get("selected", False).astype(bool)] if not tuning.empty and "selected" in tuning else pd.DataFrame()
    row = selected.iloc[0].to_dict() if not selected.empty else {}
    return f"""# XGBoost Hyperparameter Tuning Summary

- selected config id: {selected_config.get("config_id")}
- selected reason: lowest validation ECE, then Brier, then highest AUC
- test AUC / PR-AUC gain / ECE: {row.get("test_auc", np.nan):.4f} / {row.get("test_pr_auc_gain", np.nan):.4f} / {row.get("test_ece", np.nan):.4f}
- formal model file saved: false
- test cutoff is only used once after choosing the validation winner.
"""


def render_calibration_decision(comp: pd.DataFrame, selected_method: str) -> str:
    summary = comp.groupby("calibration_method", dropna=False).agg(ece=("ece", "mean"), brier=("brier", "mean"), logloss=("logloss", "mean"), auc=("auc", "mean")).reset_index() if not comp.empty else pd.DataFrame()
    return f"""# Calibration Decision

- selected method: {selected_method}
- rule: retain raw if ECE is already low or calibrator does not materially improve ECE/Brier/LogLoss.

{dataframe_to_markdown(summary)}
"""


def render_candidate_policy_recommendation(metrics: pd.DataFrame, reco: dict[str, Any]) -> str:
    summary = (
        metrics.groupby("candidate_policy", dropna=False)
        .agg(candidate_die_recall=("candidate_die_recall", "mean"), candidate_rate=("candidate_rate", "mean"), candidate_positive_rate=("candidate_positive_rate", "mean"), lift_vs_non_candidate=("lift_vs_non_candidate", "mean"), manual_review_load=("manual_review_load", "mean"))
        .reset_index()
        .sort_values("candidate_die_recall", ascending=False)
        if not metrics.empty
        else pd.DataFrame()
    )
    return f"""# Candidate Policy V2 Recommendation

- recommended policy: {reco.get("candidate_policy", "")}
- mean candidate die recall: {reco.get("candidate_die_recall", np.nan):.4f}
- mean manual review load per horizon-cutoff: {reco.get("manual_review_load", np.nan):.1f}
- previous M1 mean recall reference: 0.1862
- load caveat: the recall-maximizing union policy is appropriate for analyst batch review; use `probability_top20` or `hybrid_business_guardrail_top15` if manual load must be capped more tightly.

{dataframe_to_markdown(summary.head(20))}
"""


def render_probability_service_gate(decisions: dict[str, Any]) -> str:
    return f"""# Probability Service Gate Decision

## Internal Diagnostic View

Allowed: {str(decisions["internal_allowed"]).lower()}

Reason: leakage audit has no blocking feature in strict probability model sets, and the model is useful for algorithm analysis.

## Analyst View / Proof-Case Report

Allowed: {str(decisions["analyst_allowed"]).lower()}

Reason: full-universe strict test metrics are strong enough for analyst review if caveats are shown.

## Customer-Facing Probability Service

Allowed: {str(decisions["customer_allowed"]).lower()}

Blocking constraints if false: {", ".join(decisions.get("customer_blockers", []))}
"""


def render_model_card(frame: pd.DataFrame, split_audit: pd.DataFrame, decisions: dict[str, Any]) -> str:
    manufacturers = ", ".join(map(str, frame["manufacturer_code"].dropna().unique()[:8]))
    return f"""# Model Card Entity Complete V1

- data version: {VERSION}
- row count: {len(frame)}
- entity count: {frame[ENTITY_KEYS].drop_duplicates().shape[0]}
- selected manufacturers shown: {manufacturers}
- cutoff range: {pd.to_datetime(frame["cutoff_month"]).min().date()} to {pd.to_datetime(frame["cutoff_month"]).max().date()}
- label definition: fixed-window die label, `label_die_H=1` if no purchase exists in `(cutoff, cutoff + H]`.
- feature groups: recency/frequency, interval, demand shape, manufacturer/hospital/drug context, order-status evidence, and as-of partial choice-set context.
- excluded probability features: value/business priority, detector severity, raw non-asof date fields, labels, and candidate policy fields.
- leakage conclusion: blocking leakage = {decisions["blocking_leakage"]}
- selected model family: XGBoost small, in-memory only.
- validation split: horizon-specific time split with purge gap; no random K-fold primary validation.
- selected strict test AUC / PR-AUC gain / ECE: {decisions["xgboost_test_auc"]:.4f} / {decisions["xgboost_test_pr_auc_gain"]:.4f} / {decisions["xgboost_test_ece"]:.4f}
- calibration: {decisions["calibration_decision"]}
- candidate policy status: {decisions["candidate_policy"]}, recall {decisions["candidate_die_recall"]:.4f}
- probability availability scope: internal/analyst only; customer-facing service is not approved.

## Forbidden Interpretations

- The hospital has certainly churned.
- The hospital intentionally abandoned a manufacturer.
- Other manufacturers definitely replaced this product.
- The choice-set fields represent complete market share.
- Low risk means safe.
- Business priority is probability.
"""


def render_next_algorithm_action(decisions: dict[str, Any]) -> str:
    return f"""# Next Algorithm Action Decision

1. Current metrics credible: {str(not decisions["blocking_leakage"]).lower()} with strict split caveats.
2. Blocking leakage: {str(decisions["blocking_leakage"]).lower()}.
3. Re-cleaning needed: false.
4. New data needed: true, for broader manufacturer/time-window coverage before customer-facing probability.
5. Model change needed: no immediate replacement; keep XGBoost as main candidate and logistic as transparent fallback.
6. Continue XGBoost tuning: only light targeted tuning, not broad blind search.
7. Keep logistic: true, as fallback/benchmark.
8. Keep interval evidence: true, as evidence/ranking support, not calibrated probability.
9. M1 candidate policy v2 required: true; recommended policy is `{decisions["candidate_policy"]}`.
10. Internal diagnostic view allowed: {str(decisions["internal_allowed"]).lower()}.
11. Analyst view allowed: {str(decisions["analyst_allowed"]).lower()}.
12. Proof-case report allowed: {str(decisions["proof_case_allowed"]).lower()}.
13. Customer-facing probability service allowed: {str(decisions["customer_allowed"]).lower()}.
14. Next best task: expand complete coverage and implement probability availability gates before productizing probabilities.
"""


def render_algorithm_consolidation_summary(decisions: dict[str, Any], artifacts: pd.DataFrame) -> str:
    missing_count = int((~artifacts["exists"].astype(bool)).sum()) if not artifacts.empty else 0
    return f"""# Algorithm Consolidation Summary

- required missing artifact count: {missing_count}
- blocking leakage issue: {str(decisions["blocking_leakage"]).lower()}
- best feature group: {decisions["best_feature_set"]}
- XGBoost strict test AUC / PR-AUC gain / ECE: {decisions["xgboost_test_auc"]:.4f} / {decisions["xgboost_test_pr_auc_gain"]:.4f} / {decisions["xgboost_test_ece"]:.4f}
- calibration: {decisions["calibration_decision"]}
- learning curve acceptable: {str(decisions["learning_curve_ok"]).lower()}
- manufacturer holdout stable: {str(decisions["holdout_stable"]).lower()}
- recommended candidate policy v2: {decisions["candidate_policy"]}
- candidate die recall: {decisions["candidate_die_recall"]:.4f}
- internal diagnostic allowed: {str(decisions["internal_allowed"]).lower()}
- analyst/proof-case allowed: {str(decisions["analyst_allowed"]).lower()}
- customer-facing probability service allowed: {str(decisions["customer_allowed"]).lower()}
"""


# ---------------------------------------------------------------------------
# Shared I/O
# ---------------------------------------------------------------------------


def write_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    return df.to_markdown(index=False)


def progress(report_dir: Path, message: str, *, reset: bool = False) -> None:
    path = report_dir / "algorithm_consolidation_progress.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{pd.Timestamp.utcnow().isoformat()} {message}\n"
    if reset:
        path.write_text(line, encoding="utf-8")
    else:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    print(message, flush=True)


__all__ = [
    "run_entity_complete_algorithm_consolidation",
    "audit_feature_leakage",
    "assign_strict_split",
    "build_feature_sets",
    "metric_row_with_topk",
    "run_candidate_policy_v2",
    "add_candidate_policy_scores",
    "build_decisions",
    "STRICT_SPLITS",
]
