#!/usr/bin/env python
"""Evaluate stable probability features with raw rolling-origin validation."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_alive_prediction_expanded_train_diagnostics as expanded
import run_alive_prediction_probability_consolidation as consolidation
import run_alive_prediction_small_model_experiments as small


OUTPUT_DIR = ROOT / "reports/alive_prediction_feature_stability_v1"
PRIMARY_SCOPE = "recurring_only"
KEY_COLS = ["manufacturer_code", "hospital_code", "drug_group"]
HORIZONS = [3, 6, 12]
MODELS = ["logistic_regression", "xgboost_small"]
EPS = 1e-6
FOLDS = [
    {"fold": "fold_1", "train_start": "2020-01", "train_end": "2020-12", "test_start": "2022-01", "test_end": "2022-12", "purge": ""},
    {"fold": "fold_2", "train_start": "2020-01", "train_end": "2021-12", "test_start": "2024-01", "test_end": "2024-12", "purge": "2023-01~2023-12"},
    {"fold": "fold_3", "train_start": "2020-01", "train_end": "2022-12", "test_start": "2024-01", "test_end": "2024-12", "purge": "2023-01~2023-12"},
]
BASE_FEATURES = [
    "months_since_last_purchase_asof_cutoff",
    "months_since_first_purchase_asof_cutoff",
    "purchase_count_asof_cutoff",
    "active_month_count_asof_cutoff",
    "months_observed_asof_cutoff",
    "active_month_ratio_asof_cutoff",
]
NORMALIZED_RECENCY = [
    "normalized_recency_by_adi",
    "normalized_recency_by_median_interval",
    "recency_excess_over_median_interval",
    "recency_ratio_to_months_observed",
]
FREQUENCY_DECAY = [
    "recent_order_rate_3m",
    "recent_order_rate_6m",
    "historical_order_rate_12m",
    "frequency_decay_3m_vs_12m",
    "frequency_decay_6m_vs_12m",
    "prior_6m_order_count",
    "frequency_decay_6m_vs_prior_6m",
]
COHORT_BUCKET_NUMERIC = [
    "months_observed_bucket_code",
    "months_since_first_purchase_bucket_code",
    "cohort_maturity_flag",
]
COHORT_BUCKET_CATEGORICAL = [
    "months_observed_bucket",
    "months_since_first_purchase_bucket",
]
DEMAND_SHAPE_NUMERIC = ["adi_asof_cutoff", "cv2_quantity_asof_cutoff"]
DEMAND_SHAPE_CATEGORICAL = ["demand_shape_label"]
REFERENCE_FEATURE_SETS = {
    "raw_recency_reference": ["months_since_last_purchase_asof_cutoff"],
    "raw_frequency_reference": [
        "order_count_last_3m_asof_cutoff",
        "order_count_last_6m_asof_cutoff",
        "order_count_last_12m_asof_cutoff",
    ],
    "raw_cohort_age_reference": [
        "months_since_first_purchase_asof_cutoff",
        "months_observed_asof_cutoff",
    ],
}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def markdown_table(df: pd.DataFrame) -> str:
    return small.dataframe_to_markdown(df, index=False)


def cutoff_periods(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["cutoff_month"]).dt.to_period("M")


def cutoff_mask(df: pd.DataFrame, start: str, end: str) -> pd.Series:
    periods = cutoff_periods(df)
    return (periods >= pd.Period(start, freq="M")) & (periods <= pd.Period(end, freq="M"))


def entity_count(df: pd.DataFrame) -> int:
    return int(df[KEY_COLS].drop_duplicates().shape[0]) if len(df) else 0


def safe_divide(numerator: pd.Series, denominator: pd.Series, *, clip: tuple[float, float] | None = None) -> pd.Series:
    result = numerator.astype(float) / denominator.astype(float).clip(lower=EPS)
    if clip is not None:
        result = result.clip(lower=clip[0], upper=clip[1])
    return result


def fixed_bucket(values: pd.Series) -> pd.Series:
    bins = [-np.inf, 6, 12, 24, 60, np.inf]
    labels = ["0-6", "7-12", "13-24", "25-60", "60+"]
    return pd.cut(pd.to_numeric(values, errors="coerce"), bins=bins, labels=labels).astype("string").fillna("__MISSING__")


def bucket_code(labels: pd.Series) -> pd.Series:
    mapping = {"0-6": 0, "7-12": 1, "13-24": 2, "25-60": 3, "60+": 4, "__MISSING__": np.nan}
    return labels.map(mapping).astype(float)


def demand_shape_label(adi: pd.Series, cv2: pd.Series) -> pd.Series:
    adi = pd.to_numeric(adi, errors="coerce")
    cv2 = pd.to_numeric(cv2, errors="coerce")
    labels = np.full(len(adi), "__MISSING__", dtype=object)
    valid = adi.notna() & cv2.notna()
    labels[valid & (adi < 1.32) & (cv2 < 0.49)] = "smooth"
    labels[valid & (adi < 1.32) & (cv2 >= 0.49)] = "erratic"
    labels[valid & (adi >= 1.32) & (cv2 < 0.49)] = "intermittent"
    labels[valid & (adi >= 1.32) & (cv2 >= 0.49)] = "lumpy"
    return pd.Series(labels, index=adi.index, dtype="string")


def add_stability_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    recency = pd.to_numeric(out["months_since_last_purchase_asof_cutoff"], errors="coerce")
    adi = pd.to_numeric(out.get("adi_asof_cutoff", np.nan), errors="coerce")
    median_interval_days = pd.to_numeric(out.get("median_purchase_interval_days_asof_cutoff", np.nan), errors="coerce")
    median_interval_months = median_interval_days / 30.4375
    months_observed = pd.to_numeric(out.get("months_observed_asof_cutoff", np.nan), errors="coerce")
    out["normalized_recency_by_adi"] = safe_divide(recency, adi.fillna(1).clip(lower=1))
    out["normalized_recency_by_median_interval"] = safe_divide(recency, median_interval_months.fillna(1).clip(lower=1))
    out["recency_excess_over_median_interval"] = recency - median_interval_months
    out["recency_ratio_to_months_observed"] = safe_divide(recency, months_observed.fillna(1).clip(lower=1), clip=(0, 20))
    order_3m = pd.to_numeric(out.get("order_count_last_3m_asof_cutoff", np.nan), errors="coerce")
    order_6m = pd.to_numeric(out.get("order_count_last_6m_asof_cutoff", np.nan), errors="coerce")
    order_12m = pd.to_numeric(out.get("order_count_last_12m_asof_cutoff", np.nan), errors="coerce")
    out["recent_order_rate_3m"] = order_3m / 3.0
    out["recent_order_rate_6m"] = order_6m / 6.0
    out["historical_order_rate_12m"] = order_12m / 12.0
    out["frequency_decay_3m_vs_12m"] = safe_divide(out["recent_order_rate_3m"], out["historical_order_rate_12m"], clip=(0, 20))
    out["frequency_decay_6m_vs_12m"] = safe_divide(out["recent_order_rate_6m"], out["historical_order_rate_12m"], clip=(0, 20))
    out["prior_6m_order_count"] = (order_12m - order_6m).clip(lower=0)
    out["frequency_decay_6m_vs_prior_6m"] = safe_divide(order_6m / 6.0, out["prior_6m_order_count"] / 6.0, clip=(0, 20))
    out["months_observed_bucket"] = fixed_bucket(out["months_observed_asof_cutoff"])
    out["months_observed_bucket_code"] = bucket_code(out["months_observed_bucket"])
    out["months_since_first_purchase_bucket"] = fixed_bucket(out["months_since_first_purchase_asof_cutoff"])
    out["months_since_first_purchase_bucket_code"] = bucket_code(out["months_since_first_purchase_bucket"])
    out["cohort_maturity_flag"] = (pd.to_numeric(out["months_observed_asof_cutoff"], errors="coerce") >= 12).astype(float)
    out["demand_shape_label"] = demand_shape_label(out["adi_asof_cutoff"], out["cv2_quantity_asof_cutoff"])
    return out


def feature_sets() -> dict[str, dict[str, list[str]]]:
    return {
        "base_recency_frequency_only": {"numeric": BASE_FEATURES, "categorical": []},
        "normalized_recency_v1": {"numeric": NORMALIZED_RECENCY, "categorical": []},
        "frequency_decay_v1": {"numeric": FREQUENCY_DECAY, "categorical": []},
        "cohort_bucket_v1": {"numeric": COHORT_BUCKET_NUMERIC, "categorical": COHORT_BUCKET_CATEGORICAL},
        "demand_shape_v1": {"numeric": DEMAND_SHAPE_NUMERIC, "categorical": DEMAND_SHAPE_CATEGORICAL},
        "combined_stable_features_v1": {
            "numeric": BASE_FEATURES + NORMALIZED_RECENCY + FREQUENCY_DECAY + COHORT_BUCKET_NUMERIC + DEMAND_SHAPE_NUMERIC,
            "categorical": COHORT_BUCKET_CATEGORICAL + DEMAND_SHAPE_CATEGORICAL,
        },
    }


def split_fold(df: pd.DataFrame, fold: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[cutoff_mask(df, fold["train_start"], fold["train_end"]) & df["recurring_candidate_flag"]].copy()
    test = df[cutoff_mask(df, fold["test_start"], fold["test_end"])].copy()
    test = small.split_scopes(test)[PRIMARY_SCOPE]
    if "one_shot_high_value_silence_flag" in train:
        train = train[~train["one_shot_high_value_silence_flag"].astype(bool)].copy()
    if set(cutoff_periods(train)).intersection(set(cutoff_periods(test))):
        raise RuntimeError(f"{fold['fold']} train/test cutoffs overlap")
    return train, test


def validate_features(df: pd.DataFrame, numeric: list[str], categorical: list[str], config: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    usable_numeric: list[str] = []
    usable_categorical: list[str] = []
    rejected: list[str] = []
    for column in numeric:
        if column not in df.columns:
            rejected.append(f"{column}:missing_or_reserved")
        elif any(pattern in column for pattern in consolidation.FORBIDDEN_FEATURE_PATTERNS) or small.is_forbidden_column(column, config):
            rejected.append(f"{column}:forbidden")
        else:
            usable_numeric.append(column)
    for column in categorical:
        if column not in df.columns:
            rejected.append(f"{column}:missing_or_reserved")
        elif any(pattern in column for pattern in consolidation.FORBIDDEN_FEATURE_PATTERNS) or small.is_forbidden_column(column, config):
            rejected.append(f"{column}:forbidden")
        else:
            usable_categorical.append(column)
    return usable_numeric, usable_categorical, rejected


def label_ready(train: pd.DataFrame, test: pd.DataFrame, horizon: int) -> str:
    label_col = f"label_die_H{horizon}"
    for name, frame in [("train", train), ("test", test)]:
        if label_col not in frame.columns:
            return f"{name}:{label_col}_missing"
        if frame[label_col].isna().any():
            return f"{name}:{label_col}_has_missing"
        if len(frame) == 0:
            return f"{name}:empty"
    if train[label_col].nunique(dropna=True) < 2:
        return "train_label_has_single_class"
    return ""


def score_candidate(config: dict[str, Any], train: pd.DataFrame, test: pd.DataFrame, model: str, feature_set: str, numeric: list[str], categorical: list[str], horizon: int) -> tuple[dict[str, Any] | None, str]:
    label_col = f"label_die_H{horizon}"
    fitted, reason = expanded.fit_with_columns(model, train, label_col, config, numeric, categorical, [])
    if fitted is None:
        return None, f"model_fit_failed:{reason}"
    try:
        scored = test.copy()
        scored[f"churn_probability_H{horizon}"] = small.predict_with_fitted_model(fitted, scored)
        return scored, ""
    except Exception as exc:
        return None, f"model_predict_failed:{exc!r}"


def metrics_for_scored(scored: pd.DataFrame, model: str, feature_set: str, fold: str, horizon: int) -> dict[str, Any]:
    cutoff_rows: list[dict[str, Any]] = []
    for cutoff, part in scored.groupby(cutoff_periods(scored), sort=True):
        cutoff_rows.append(
            consolidation.metric_row(
                part,
                model=model,
                feature_set=feature_set,
                horizon=horizon,
                aggregation_method="by_cutoff",
                period=str(cutoff),
                cutoff_month=str(cutoff),
                compute_topk=True,
            )
        )
    macro = consolidation.macro_from_cutoffs(pd.DataFrame(cutoff_rows), period=fold, aggregation_method="macro_by_cutoff")
    row = {
        "model": model,
        "feature_set": feature_set,
        "fold": fold,
        "horizon": horizon,
        "scope": PRIMARY_SCOPE,
    }
    for key in [
        "row_count",
        "entity_count",
        "positive_rate",
        "brier_score",
        "log_loss",
        "ece",
        "auc",
        "pr_auc",
        "precision_at_top_1_pct",
        "precision_at_top_5_pct",
        "precision_at_top_10_pct",
        "lift_at_top_1_pct",
        "lift_at_top_5_pct",
        "lift_at_top_10_pct",
        "ndcg_at_top_1_pct",
        "ndcg_at_top_5_pct",
        "ndcg_at_top_10_pct",
    ]:
        row[key] = macro.get(key, np.nan)
    return row


def feature_stats(frame: pd.DataFrame, feature: str) -> tuple[float, float, float]:
    if feature not in frame.columns:
        return np.nan, np.nan, np.nan
    values = pd.to_numeric(frame[feature], errors="coerce")
    mean = values.mean()
    std = values.std(ddof=0)
    return (
        float(mean) if pd.notna(mean) else np.nan,
        float(std) if pd.notna(std) else np.nan,
        float(values.isna().mean()) if len(values) else np.nan,
    )


def drift_level(smd: float) -> str:
    if not np.isfinite(smd):
        return "missing"
    value = abs(smd)
    if value < 0.2:
        return "low"
    if value < 0.5:
        return "medium"
    return "high"


def feature_shift_rows(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for fold in FOLDS:
        train, test = split_fold(df, fold)
        drift_sets = {name: spec["numeric"] + spec["categorical"] for name, spec in feature_sets().items()}
        drift_sets.update(REFERENCE_FEATURE_SETS)
        for feature_set, requested_features in drift_sets.items():
            if feature_set in feature_sets():
                spec = feature_sets()[feature_set]
                numeric, categorical, _rejected = validate_features(df, spec["numeric"], spec["categorical"], config)
                features = numeric + categorical
            else:
                features = [feature for feature in requested_features if feature in df.columns]
            for feature in features:
                train_mean, train_std, train_missing = feature_stats(train, feature)
                test_mean, test_std, test_missing = feature_stats(test, feature)
                pooled = np.sqrt((np.nan_to_num(train_std, nan=0.0) ** 2 + np.nan_to_num(test_std, nan=0.0) ** 2) / 2)
                smd = float((train_mean - test_mean) / pooled) if pooled > 0 and np.isfinite(train_mean) and np.isfinite(test_mean) else np.nan
                rows.append(
                    {
                        "feature_set": feature_set,
                        "feature": feature,
                        "fold": fold["fold"],
                        "train_mean": train_mean,
                        "test_mean": test_mean,
                        "train_std": train_std,
                        "test_std": test_std,
                        "standardized_mean_diff": smd,
                        "train_missing_rate": train_missing,
                        "test_missing_rate": test_missing,
                        "drift_risk_level": drift_level(smd),
                    }
                )
    return pd.DataFrame(rows)


def demand_shape_audit(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for fold in FOLDS:
        train, test = split_fold(df, fold)
        for split, frame in [("train", train), ("test", test)]:
            for horizon in HORIZONS:
                label_col = f"label_die_H{horizon}"
                for shape, group in frame.groupby("demand_shape_label", dropna=False):
                    y = group[label_col].dropna()
                    rows.append(
                        {
                            "fold": fold["fold"],
                            "split": split,
                            "horizon": horizon,
                            "demand_shape_label": shape,
                            "row_count": int(len(group)),
                            "entity_count": entity_count(group),
                            "positive_rate": float(y.mean()) if len(y) else np.nan,
                            "mean_months_since_last_purchase": float(pd.to_numeric(group["months_since_last_purchase_asof_cutoff"], errors="coerce").mean()),
                            "mean_order_count_last_6m": float(pd.to_numeric(group["order_count_last_6m_asof_cutoff"], errors="coerce").mean()),
                            "mean_order_count_last_12m": float(pd.to_numeric(group["order_count_last_12m_asof_cutoff"], errors="coerce").mean()),
                            "mean_adi": float(pd.to_numeric(group["adi_asof_cutoff"], errors="coerce").mean()),
                            "mean_cv2": float(pd.to_numeric(group["cv2_quantity_asof_cutoff"], errors="coerce").mean()),
                        }
                    )
    return pd.DataFrame(rows)


def run_feature_comparison(df: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for fold in FOLDS:
        train, test = split_fold(df, fold)
        for feature_set, spec in feature_sets().items():
            numeric, categorical, rejected = validate_features(df, spec["numeric"], spec["categorical"], config)
            if not numeric and not categorical:
                for model in MODELS:
                    for horizon in HORIZONS:
                        failures.append(failure_row(fold["fold"], model, feature_set, horizon, f"no_usable_features:{';'.join(rejected)}"))
                continue
            for model in MODELS:
                for horizon in HORIZONS:
                    reason = label_ready(train, test, horizon)
                    if reason:
                        failures.append(failure_row(fold["fold"], model, feature_set, horizon, reason))
                        continue
                    scored, reason = score_candidate(config, train, test, model, feature_set, numeric, categorical, horizon)
                    if scored is None:
                        failures.append(failure_row(fold["fold"], model, feature_set, horizon, reason))
                        continue
                    rows.append(metrics_for_scored(scored, model, feature_set, fold["fold"], horizon))
    return pd.DataFrame(rows), pd.DataFrame(failures, columns=["fold", "model", "feature_set", "horizon", "reason"])


def failure_row(fold: str, model: str, feature_set: str, horizon: int, reason: str) -> dict[str, Any]:
    return {"fold": fold, "model": model, "feature_set": feature_set, "horizon": horizon, "reason": reason}


def summarize_by_fold(metrics: pd.DataFrame) -> pd.DataFrame:
    return (
        metrics.groupby(["model", "feature_set", "fold", "scope"], dropna=False)[["brier_score", "log_loss", "ece", "auc", "pr_auc"]]
        .mean(numeric_only=True)
        .reset_index()
    )


def summarize_by_horizon(metrics: pd.DataFrame) -> pd.DataFrame:
    return (
        metrics.groupby(["model", "feature_set", "horizon", "scope"], dropna=False)[["brier_score", "log_loss", "ece", "auc", "pr_auc"]]
        .mean(numeric_only=True)
        .reset_index()
    )


def candidate_decisions(metrics: pd.DataFrame, shift: pd.DataFrame, rejected: pd.DataFrame) -> pd.DataFrame:
    agg = (
        metrics.groupby(["feature_set", "model"], dropna=False)[["brier_score", "log_loss", "ece", "auc", "pr_auc"]]
        .agg(["mean", "std"])
        .reset_index()
    )
    agg.columns = ["_".join(map(str, col)).strip("_") for col in agg.columns.to_flat_index()]
    drift = shift.groupby("feature_set")["standardized_mean_diff"].apply(lambda s: float(s.abs().mean())).reset_index(name="mean_abs_smd")
    out = agg.merge(drift, on="feature_set", how="left")
    baseline = out[(out["feature_set"].eq("base_recency_frequency_only")) & (out["model"].eq("logistic_regression"))]
    baseline_brier = float(baseline.iloc[0]["brier_score_mean"]) if not baseline.empty else np.nan
    rows: list[dict[str, Any]] = []
    rejected_sets = set(rejected.loc[rejected["risk_level"].eq("high"), "feature_set"]) if not rejected.empty else set()
    for _, row in out.iterrows():
        feature_set = row["feature_set"]
        model = row["model"]
        if feature_set in rejected_sets:
            decision = "reject_due_to_leakage"
        elif feature_set == "base_recency_frequency_only" and model == "logistic_regression":
            decision = "keep_as_baseline"
        elif row["mean_abs_smd"] >= 0.5:
            decision = "reject_due_to_drift"
        elif np.isfinite(baseline_brier) and row["brier_score_mean"] <= baseline_brier * 0.99:
            decision = "promote_to_probability_feature_candidate"
        elif feature_set in {"combined_stable_features_v1", "normalized_recency_v1", "frequency_decay_v1"}:
            decision = "keep_as_backup"
        else:
            decision = "needs_more_data"
        rows.append(
            {
                "feature_set": feature_set,
                "model": model,
                "decision": decision,
                "reason": decision_reason(decision),
                "probability_metric_strength": f"Brier={row['brier_score_mean']:.4f}, LogLoss={row['log_loss_mean']:.4f}, ECE={row['ece_mean']:.4f}, AUC={row['auc_mean']:.4f}, PR_AUC={row['pr_auc_mean']:.4f}",
                "drift_stability": f"mean_abs_smd={row['mean_abs_smd']:.4f}",
                "leakage_risk": "low" if feature_set not in rejected_sets else "high",
                "recommended_next_action": recommended_action(decision),
            }
        )
    return pd.DataFrame(rows)


def decision_reason(decision: str) -> str:
    return {
        "promote_to_probability_feature_candidate": "Improves probability metrics without high drift/leakage risk.",
        "keep_as_baseline": "Current transparent baseline remains required for comparison.",
        "keep_as_backup": "Potentially useful but not clearly superior across folds/horizons.",
        "reject_due_to_drift": "Feature set has high train/test standardized mean drift.",
        "reject_due_to_leakage": "Feature set failed leakage audit.",
        "needs_more_data": "Signal is inconclusive under current fold coverage.",
    }[decision]


def recommended_action(decision: str) -> str:
    return {
        "promote_to_probability_feature_candidate": "Consider calibration v2 after stability review.",
        "keep_as_baseline": "Keep as primary baseline.",
        "keep_as_backup": "Retest after feature refinement.",
        "reject_due_to_drift": "Do not use in candidate v1.",
        "reject_due_to_leakage": "Remove from modeling set.",
        "needs_more_data": "Review data coverage and label stability.",
    }[decision]


def leakage_audit(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for feature_set, spec in feature_sets().items():
        for feature in spec["numeric"] + spec["categorical"]:
            missing = feature not in df.columns
            forbidden = any(pattern in feature for pattern in consolidation.FORBIDDEN_FEATURE_PATTERNS)
            if missing:
                status = "rejected"
                risk = "medium"
                reason = "missing_or_reserved"
            elif forbidden:
                status = "rejected"
                risk = "high"
                reason = "matches_forbidden_pattern"
            else:
                status = "accepted"
                risk = "low"
                reason = "as_of_cutoff_or_fixed_rule"
            rows.append({"feature_set": feature_set, "feature": feature, "status": status, "risk_level": risk, "reason": reason})
    return pd.DataFrame(rows)


def write_definition_and_audit(audit: pd.DataFrame) -> None:
    lines = [
        "# Feature Definition v1",
        "",
        "All features are derived from as-of cutoff artifacts and fixed transformations. No model family or hyperparameter changes are introduced.",
        "",
        "## Feature Sets",
    ]
    for name, spec in feature_sets().items():
        lines.extend([f"### {name}", "", "Numeric:", *[f"- {c}" for c in spec["numeric"]], "", "Categorical:", *[f"- {c}" for c in spec["categorical"]], ""])
    write_text(OUTPUT_DIR / "feature_definition_v1.md", "\n".join(lines))
    rejected = audit[audit["status"].eq("rejected")]
    audit_lines = [
        "# Feature Leakage Audit",
        "",
        "## Checks",
        "1. New features use purchase/activity state as of cutoff only.",
        "2. ADI, median interval, and CV2 are read from as-of cutoff fields.",
        "3. Buckets use fixed rules and are not fit on test.",
        "4. No label/future/next_purchase/cutoff-after-order fields are used.",
        "5. No value_at_risk or business_priority fields are used.",
        "6. No 2024 test-fitted encoding, threshold, or percentile is used.",
        "7. No high-cardinality identifiers are introduced.",
        "8. Main evaluation remains recurring_only.",
        "",
        "## Rejected Features",
        markdown_table(rejected) if not rejected.empty else "No high-risk features rejected; missing/reserved features would be listed here.",
        "",
        "## Full Audit",
        markdown_table(audit),
    ]
    write_text(OUTPUT_DIR / "feature_leakage_audit.md", "\n".join(audit_lines))


def write_demand_shape_report(audit: pd.DataFrame) -> None:
    label_rates = audit.pivot_table(index=["fold", "split", "horizon"], columns="demand_shape_label", values="positive_rate").reset_index()
    variability = audit.groupby("demand_shape_label")["positive_rate"].std().reset_index(name="positive_rate_std").sort_values("positive_rate_std", ascending=False)
    lines = [
        "# Demand Shape Label Rate Report",
        "",
        "## Label Rate By Demand Shape",
        markdown_table(label_rates.head(60)),
        "",
        "## Demand Shape Variability",
        markdown_table(variability),
        "",
        "## Answers",
        "1. Demand shape label rates differ across smooth/erratic/intermittent/lumpy groups when enough rows are present.",
        "2. The most unstable class is the one with the highest positive_rate_std in the table above.",
        "3. A unified H3/H6/H12 treatment for all demand shapes is probably too coarse.",
        "4. Intermittent/lumpy demand may need later routing or horizon-specific handling rather than one shared probability model.",
        "5. demand_shape should remain a diagnostic segmentation until leakage and stability are stronger.",
    ]
    write_text(OUTPUT_DIR / "demand_shape_label_rate_report.md", "\n".join(lines))


def write_reassessment(metrics: pd.DataFrame, decisions: pd.DataFrame, shift: pd.DataFrame) -> None:
    agg = (
        metrics.groupby(["model", "feature_set"], dropna=False)[["brier_score", "log_loss", "ece", "auc", "pr_auc"]]
        .mean(numeric_only=True)
        .reset_index()
        .sort_values(["brier_score", "log_loss", "ece", "auc", "pr_auc"], ascending=[True, True, True, False, False])
    )
    norm_drift = drift_compare_sets(shift, "normalized_recency_v1", "raw_recency_reference")
    freq_drift = drift_compare_sets(shift, "frequency_decay_v1", "raw_frequency_reference")
    cohort_drift = drift_compare_sets(shift, "cohort_bucket_v1", "raw_cohort_age_reference")
    logistic_best = agg[agg["model"].eq("logistic_regression")].head(1)
    xgb_best = agg[agg["model"].eq("xgboost_small")].head(1)
    feature_candidate_ready = decisions["decision"].eq("promote_to_probability_feature_candidate").any()
    lines = [
        "# Probability Candidate v1 Reassessment",
        "",
        "## Aggregate Metrics",
        markdown_table(agg),
        "",
        "## Answers",
        f"1. Logistic remains most stable: {'yes' if not logistic_best.empty and (xgb_best.empty or float(logistic_best.iloc[0]['brier_score']) <= float(xgb_best.iloc[0]['brier_score'])) else 'no'}.",
        f"2. normalized_recency improves drift vs raw recency: {'yes' if norm_drift < 0 else 'no'} (mean abs SMD delta={norm_drift:.4f}).",
        f"3. frequency_decay improves drift vs raw order count: {'yes' if freq_drift < 0 else 'no'} (mean abs SMD delta={freq_drift:.4f}).",
        f"4. cohort bucket lowers cohort-age drift: {'yes' if cohort_drift < 0 else 'no'} (mean abs SMD delta={cohort_drift:.4f}).",
        "5. demand_shape should remain a segmentation/audit feature for now, not a default model input.",
        "6. promote probability_candidate_v1 now: no. This raw-only run can only promote feature candidates for calibration v2.",
        f"7. Feature candidate ready for calibration v2: {'yes' if feature_candidate_ready else 'no'}. See candidate_feature_decision.csv.",
        "8. If calibration v2 does not stabilize the promoted feature candidate, next step should prioritize demand-shape routing and label/data coverage review before more model tuning.",
    ]
    write_text(OUTPUT_DIR / "probability_candidate_v1_reassessment.md", "\n".join(lines))


def drift_compare_sets(shift: pd.DataFrame, feature_set: str, baseline_feature_set: str) -> float:
    baseline = shift[shift["feature_set"].eq(baseline_feature_set)]["standardized_mean_diff"].abs().mean()
    candidate = shift[shift["feature_set"].eq(feature_set)]["standardized_mean_diff"].abs().mean()
    return float(candidate - baseline) if np.isfinite(candidate) and np.isfinite(baseline) else np.nan


def write_data_or_label_decision(metrics: pd.DataFrame, decisions: pd.DataFrame, shift: pd.DataFrame) -> None:
    improved = decisions["decision"].eq("promote_to_probability_feature_candidate").any()
    high_drift = (shift["drift_risk_level"].eq("high")).mean()
    lines = [
        "# Data Or Label Next Step Decision",
        "",
        "## Options",
        "A. Continue feature reconstruction.",
        "B. Expand data.",
        "C. Review label definition.",
        "D. Demand-shape routing.",
        "E. Return to model family/tuning.",
        "",
        "## Decision",
    ]
    if improved:
        lines.append("New features improved raw rolling-origin stability; next step can be calibration v2 on the promoted feature candidate.")
    elif high_drift > 0.25:
        lines.append("Priority: D then C/B. Demand-shape routing and label/data coverage review are more appropriate than model tuning.")
    else:
        lines.append("Priority: A then C. Continue feature reconstruction and label review before data expansion.")
    lines.extend(
        [
            "",
            "## Rationale",
            "- If new features lower drift but do not improve probability metrics, label definition or demand-shape routing is likely needed.",
            "- If features improve fold_1 but fail fold_2, time drift and closer calibration windows matter.",
            "- If Logistic remains stronger than XGBoost, do not return to model family expansion or tuning.",
            "- If label rates differ strongly across time, inspect label coverage and business meaning before tuning.",
        ]
    )
    write_text(OUTPUT_DIR / "data_or_label_next_step_decision.md", "\n".join(lines))


def write_summary(metrics: pd.DataFrame, shift: pd.DataFrame, audit: pd.DataFrame, demand_audit: pd.DataFrame, decisions: pd.DataFrame) -> None:
    agg = (
        metrics.groupby(["model", "feature_set"], dropna=False)[["brier_score", "log_loss", "ece", "auc", "pr_auc"]]
        .mean(numeric_only=True)
        .reset_index()
        .sort_values(["brier_score", "log_loss", "ece", "auc", "pr_auc"], ascending=[True, True, True, False, False])
    )
    drift_summary = shift.groupby("feature_set")["standardized_mean_diff"].apply(lambda s: float(s.abs().mean())).reset_index(name="mean_abs_smd").sort_values("mean_abs_smd")
    model_drift_summary = drift_summary[~drift_summary["feature_set"].str.startswith("raw_")].copy()
    rejected = audit[audit["status"].eq("rejected")]
    lines = [
        "# Feature Stability Summary v1",
        "",
        "This report evaluates low-leakage historical behavior features for churn_probability_H only. It does not run calibration, tuning, or new model families.",
        "",
        "## Added Feature Sets",
        "- normalized_recency_v1",
        "- frequency_decay_v1",
        "- cohort_bucket_v1",
        "- demand_shape_v1",
        "- combined_stable_features_v1",
        "",
        "## Rejected Features",
        markdown_table(rejected) if not rejected.empty else "No high-risk feature was rejected by the audit.",
        "",
        "## Aggregate Probability Metrics",
        markdown_table(agg),
        "",
        "## Drift Summary",
        markdown_table(model_drift_summary),
        "",
        "## Raw Reference Drift",
        markdown_table(drift_summary[drift_summary["feature_set"].str.startswith("raw_")]),
        "",
        "## Candidate Feature Decisions",
        markdown_table(decisions),
        "",
        "## Conclusion",
        "- Logistic remains the primary stable model direction unless candidate_feature_decision.csv promotes a new feature set.",
        "- XGBoost remains a challenger only if it beats Logistic on probability metrics without higher drift.",
        "- TopK diagnostics are not used for main probability selection.",
        "- No value_at_risk or business_priority fields are used.",
    ]
    write_text(OUTPUT_DIR / "feature_stability_summary.md", "\n".join(lines))


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = small.read_yaml(ROOT / "configs/experiments/alive_prediction_small_models.yaml")
    df = consolidation.load_feature_data(config)
    df = add_stability_features(df)
    audit = leakage_audit(df)
    metrics, failures = run_feature_comparison(df, config)
    shift = feature_shift_rows(df, config)
    by_fold = summarize_by_fold(metrics)
    by_horizon = summarize_by_horizon(metrics)
    demand_audit = demand_shape_audit(df)
    decisions = candidate_decisions(metrics, shift, audit)
    write_definition_and_audit(audit)
    metrics.to_csv(OUTPUT_DIR / "feature_set_comparison_metrics.csv", index=False, encoding="utf-8-sig")
    by_fold.to_csv(OUTPUT_DIR / "feature_set_comparison_by_fold.csv", index=False, encoding="utf-8-sig")
    by_horizon.to_csv(OUTPUT_DIR / "feature_set_comparison_by_horizon.csv", index=False, encoding="utf-8-sig")
    shift.to_csv(OUTPUT_DIR / "feature_distribution_shift_before_after.csv", index=False, encoding="utf-8-sig")
    demand_audit.to_csv(OUTPUT_DIR / "demand_shape_audit.csv", index=False, encoding="utf-8-sig")
    decisions.to_csv(OUTPUT_DIR / "candidate_feature_decision.csv", index=False, encoding="utf-8-sig")
    failures.to_csv(OUTPUT_DIR / "feature_stability_failure_report.csv", index=False, encoding="utf-8-sig")
    write_demand_shape_report(demand_audit)
    write_reassessment(metrics, decisions, shift)
    write_data_or_label_decision(metrics, decisions, shift)
    write_summary(metrics, shift, audit, demand_audit, decisions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
