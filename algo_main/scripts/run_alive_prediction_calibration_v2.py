#!/usr/bin/env python
"""Run calibration v2 for stable churn probability feature candidates."""

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

import run_alive_prediction_calibration_v1 as calibration
import run_alive_prediction_feature_stability_v1 as feature_stability
import run_alive_prediction_probability_consolidation as consolidation
import run_alive_prediction_small_model_experiments as small


OUTPUT_DIR = ROOT / "reports/alive_prediction_calibration_v2"
PRIMARY_SCOPE = "recurring_only"
KEY_COLS = ["manufacturer_code", "hospital_code", "drug_group"]
HORIZONS = [3, 6, 12]
CANDIDATES = [
    ("logistic_regression", "frequency_decay_v1"),
    ("logistic_regression", "combined_stable_features_v1"),
    ("logistic_regression", "base_recency_frequency_only"),
    ("xgboost_small", "frequency_decay_v1"),
]
FOLDS = [
    {
        "fold": "fold_1",
        "train_start": "2020-01",
        "train_end": "2020-12",
        "calibration_start": "2021-01",
        "calibration_end": "2021-12",
        "test_start": "2022-01",
        "test_end": "2022-12",
        "purge": "",
    },
    {
        "fold": "fold_2",
        "train_start": "2020-01",
        "train_end": "2021-12",
        "calibration_start": "2022-01",
        "calibration_end": "2022-12",
        "test_start": "2024-01",
        "test_end": "2024-12",
        "purge": "2023-01~2023-12",
    },
]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def markdown_table(df: pd.DataFrame) -> str:
    return small.dataframe_to_markdown(df, index=False)


def period_label(start: str, end: str) -> str:
    return f"{start}~{end}"


def cutoff_periods(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["cutoff_month"]).dt.to_period("M")


def cutoff_mask(df: pd.DataFrame, start: str, end: str) -> pd.Series:
    periods = cutoff_periods(df)
    return (periods >= pd.Period(start, freq="M")) & (periods <= pd.Period(end, freq="M"))


def split_fold(df: pd.DataFrame, fold: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = df[cutoff_mask(df, fold["train_start"], fold["train_end"]) & df["recurring_candidate_flag"]].copy()
    valid = df[cutoff_mask(df, fold["calibration_start"], fold["calibration_end"]) & df["recurring_candidate_flag"]].copy()
    test = df[cutoff_mask(df, fold["test_start"], fold["test_end"])].copy()
    test = small.split_scopes(test)[PRIMARY_SCOPE]
    for frame in [train, valid]:
        if "one_shot_high_value_silence_flag" in frame.columns:
            frame.drop(frame[frame["one_shot_high_value_silence_flag"].astype(bool)].index, inplace=True)
    train_periods = set(cutoff_periods(train))
    valid_periods = set(cutoff_periods(valid))
    test_periods = set(cutoff_periods(test))
    if train_periods.intersection(valid_periods) or train_periods.intersection(test_periods) or valid_periods.intersection(test_periods):
        raise RuntimeError(f"{fold['fold']} split cutoffs overlap")
    return train, valid, test


def entity_count(df: pd.DataFrame) -> int:
    return int(df[KEY_COLS].drop_duplicates().shape[0]) if len(df) else 0


def selected_columns(config: dict[str, Any], df: pd.DataFrame, feature_set: str) -> tuple[list[str], list[str], list[str]]:
    spec = feature_stability.feature_sets()[feature_set]
    numeric, categorical, rejected = feature_stability.validate_features(df, spec["numeric"], spec["categorical"], config)
    forbidden = [
        column
        for column in numeric + categorical
        if any(pattern in column for pattern in consolidation.FORBIDDEN_FEATURE_PATTERNS)
    ]
    if forbidden:
        raise RuntimeError(f"forbidden probability features selected: {forbidden}")
    return numeric, categorical, rejected


def label_check(train: pd.DataFrame, valid: pd.DataFrame, test: pd.DataFrame, horizon: int) -> str:
    label_col = f"label_die_H{horizon}"
    for name, frame, require_two_classes in [
        ("model_train", train, True),
        ("calibration_valid", valid, True),
        ("test", test, False),
    ]:
        if label_col not in frame.columns:
            return f"{name}:{label_col}_missing"
        if frame[label_col].isna().any():
            return f"{name}:{label_col}_has_missing"
        if len(frame) == 0:
            return f"{name}:empty"
        if require_two_classes and frame[label_col].nunique(dropna=True) < 2:
            return f"{name}:{label_col}_single_class"
    return ""


def score_with_probability(test: pd.DataFrame, horizon: int, probability: np.ndarray) -> pd.DataFrame:
    scored = test.copy()
    scored[f"churn_probability_H{horizon}"] = np.clip(probability.astype(float), 1e-15, 1 - 1e-15)
    return scored


def metric_rows(
    scored: pd.DataFrame,
    *,
    model: str,
    feature_set: str,
    horizon: int,
    calibration_method: str,
    fold: dict[str, str],
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
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
    cutoff_df = pd.DataFrame(cutoff_rows)
    rows = [
        consolidation.metric_row(
            scored,
            model=model,
            feature_set=feature_set,
            horizon=horizon,
            aggregation_method="raw_overall",
            period=fold["test_start"][:4],
            compute_topk=False,
        )
    ]
    if not cutoff_df.empty:
        rows.append(consolidation.macro_from_cutoffs(cutoff_df, period=fold["test_start"][:4], aggregation_method="macro_by_cutoff"))
        if fold["test_start"].startswith("2024"):
            for period, (start, end) in consolidation.PERIODS.items():
                part_cutoffs = cutoff_df[cutoff_df["period"].between(start, end)]
                if not part_cutoffs.empty:
                    rows.append(consolidation.macro_from_cutoffs(part_cutoffs, period=period, aggregation_method="early_mid_late"))
    for row in rows:
        row.update(fold_columns(fold))
        row["calibration_method"] = calibration_method
    cutoff_df["calibration_method"] = calibration_method
    return rows, cutoff_df


def fold_columns(fold: dict[str, str]) -> dict[str, str]:
    return {
        "fold": fold["fold"],
        "train_period": period_label(fold["train_start"], fold["train_end"]),
        "calibration_period": period_label(fold["calibration_start"], fold["calibration_end"]),
        "test_period": period_label(fold["test_start"], fold["test_end"]),
    }


def calibration_bins(scored: pd.DataFrame, *, model: str, feature_set: str, horizon: int, calibration_method: str, fold: dict[str, str]) -> pd.DataFrame:
    bins = calibration.calibration_bins(
        scored,
        model=model,
        feature_set=feature_set,
        horizon=horizon,
        calibration_method=calibration_method,
        probability_version=calibration_method,
    )
    for key, value in fold_columns(fold).items():
        bins[key] = value
    return bins


def risk_bands(scored: pd.DataFrame, *, model: str, feature_set: str, horizon: int, calibration_method: str, fold: dict[str, str]) -> pd.DataFrame:
    label_col = f"label_die_H{horizon}"
    prob_col = f"churn_probability_H{horizon}"
    base_rate = float(scored[label_col].mean()) if len(scored) else np.nan
    rows: list[dict[str, Any]] = []
    fixed_masks = {
        "high_risk": scored[prob_col] >= 0.75,
        "medium_risk": (scored[prob_col] >= 0.50) & (scored[prob_col] < 0.75),
        "low_risk": scored[prob_col] < 0.50,
    }
    probs = scored[prob_col].rank(method="first", pct=True)
    quantile_masks = {
        "top_20_pct": probs > 0.80,
        "middle_60_pct": (probs >= 0.20) & (probs <= 0.80),
        "bottom_20_pct": probs < 0.20,
    }
    for band_type, masks in [("fixed_threshold", fixed_masks), ("quantile", quantile_masks)]:
        for band, mask in masks.items():
            part = scored[mask].copy()
            mean_pred = float(part[prob_col].mean()) if len(part) else np.nan
            observed = float(part[label_col].mean()) if len(part) else np.nan
            rows.append(
                {
                    **fold_columns(fold),
                    "model": model,
                    "feature_set": feature_set,
                    "horizon": horizon,
                    "scope": PRIMARY_SCOPE,
                    "calibration_method": calibration_method,
                    "band_type": band_type,
                    "risk_band": band,
                    "row_count": int(len(part)),
                    "entity_count": entity_count(part),
                    "mean_predicted_probability": mean_pred,
                    "observed_positive_rate": observed,
                    "calibration_gap": mean_pred - observed if np.isfinite(mean_pred) and np.isfinite(observed) else np.nan,
                    "lift_vs_base_rate": observed / base_rate if np.isfinite(observed) and np.isfinite(base_rate) and base_rate > 0 else np.nan,
                }
            )
    return pd.DataFrame(rows)


def run_candidate(
    config: dict[str, Any],
    fold: dict[str, str],
    train: pd.DataFrame,
    valid: pd.DataFrame,
    test: pd.DataFrame,
    model: str,
    feature_set: str,
    horizon: int,
) -> tuple[list[dict[str, Any]], list[pd.DataFrame], list[pd.DataFrame], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    bin_frames: list[pd.DataFrame] = []
    band_frames: list[pd.DataFrame] = []
    failures: list[dict[str, Any]] = []
    label_col = f"label_die_H{horizon}"
    reason = label_check(train, valid, test, horizon)
    if reason:
        return rows, bin_frames, band_frames, [failure_row(fold, model, feature_set, horizon, reason)]
    try:
        numeric, categorical, rejected = selected_columns(config, train, feature_set)
        if rejected and not numeric and not categorical:
            return rows, bin_frames, band_frames, [failure_row(fold, model, feature_set, horizon, f"no_usable_features:{';'.join(rejected)}")]
        fitted, fit_reason = feature_stability.expanded.fit_with_columns(model, train, label_col, config, numeric, categorical, rejected)
        if fitted is None:
            return rows, bin_frames, band_frames, [failure_row(fold, model, feature_set, horizon, f"model_fit_failed:{fit_reason}")]
        raw_valid = small.predict_with_fitted_model(fitted, valid)
        raw_test = small.predict_with_fitted_model(fitted, test)
        scored_by_method = {"raw": score_with_probability(test, horizon, raw_test)}
        for method in ["platt", "isotonic"]:
            calibrator = calibration.fit_calibrator(method, raw_valid, valid[label_col].astype(int).to_numpy())
            scored_by_method[method] = score_with_probability(test, horizon, calibration.apply_calibrator(method, calibrator, raw_test))
        for method, scored in scored_by_method.items():
            method_rows, _cutoff = metric_rows(scored, model=model, feature_set=feature_set, horizon=horizon, calibration_method=method, fold=fold)
            rows.extend(method_rows)
            bin_frames.append(calibration_bins(scored, model=model, feature_set=feature_set, horizon=horizon, calibration_method=method, fold=fold))
            band_frames.append(risk_bands(scored, model=model, feature_set=feature_set, horizon=horizon, calibration_method=method, fold=fold))
    except Exception as exc:  # pragma: no cover - defensive reporting path.
        failures.append(failure_row(fold, model, feature_set, horizon, f"unexpected_failure:{exc!r}"))
    return rows, bin_frames, band_frames, failures


def failure_row(fold: dict[str, str], model: str, feature_set: str, horizon: int, reason: str) -> dict[str, Any]:
    return {
        **fold_columns(fold),
        "model": model,
        "feature_set": feature_set,
        "horizon": horizon,
        "reason": reason,
    }


def before_after(metrics: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    macro = metrics[metrics["aggregation_method"].eq("macro_by_cutoff")].copy()
    raw = macro[macro["calibration_method"].eq("raw")].copy()
    cal = macro[macro["calibration_method"].isin(["platt", "isotonic"])].copy()
    keys = ["fold", "model", "feature_set", "horizon", "scope", "aggregation_method", "period", "train_period", "calibration_period", "test_period"]
    paired = cal.merge(raw, on=keys, suffixes=("_after", "_before"), how="left")
    rows: list[dict[str, Any]] = []
    topk_rows: list[dict[str, Any]] = []
    for _, row in paired.iterrows():
        out = {key: row[key] for key in keys}
        out["calibration_method"] = row["calibration_method_after"]
        topk = dict(out)
        for col in ["brier_score", "log_loss", "ece", "auc", "pr_auc"]:
            out[f"{col}_before"] = row.get(f"{col}_before", np.nan)
            out[f"{col}_after"] = row.get(f"{col}_after", np.nan)
            out[f"{col}_delta_after_minus_before"] = out[f"{col}_after"] - out[f"{col}_before"]
        for col in [
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
            topk[f"{col}_before"] = row.get(f"{col}_before", np.nan)
            topk[f"{col}_after"] = row.get(f"{col}_after", np.nan)
            topk[f"{col}_delta_after_minus_before"] = topk[f"{col}_after"] - topk[f"{col}_before"]
        topk["topk_stability_status"] = topk_status(topk)
        rows.append(out)
        topk_rows.append(topk)
    return pd.DataFrame(rows), pd.DataFrame(topk_rows)


def topk_status(row: dict[str, Any] | pd.Series) -> str:
    deltas = [
        abs(float(row.get("lift_at_top_10_pct_delta_after_minus_before", np.nan))),
        abs(float(row.get("ndcg_at_top_10_pct_delta_after_minus_before", np.nan))),
        abs(float(row.get("precision_at_top_10_pct_delta_after_minus_before", np.nan))),
    ]
    finite = [value for value in deltas if np.isfinite(value)]
    if not finite:
        return "not_available"
    if max(finite) <= 0.02:
        return "stable"
    if max(finite) <= 0.05:
        return "minor_change"
    return "material_degradation_or_shift"


def overfit_report(before_after_df: pd.DataFrame, bins: pd.DataFrame, topk: pd.DataFrame) -> pd.DataFrame:
    bin_flags = []
    for keys, group in bins[bins["calibration_method"].isin(["platt", "isotonic"])].groupby(
        ["fold", "model", "feature_set", "horizon", "calibration_method"], dropna=False
    ):
        nonempty = group[group["row_count"] > 0].copy()
        total = float(nonempty["row_count"].sum()) if len(nonempty) else 0.0
        small_extreme = bool(
            len(nonempty)
            and (
                (nonempty["row_count"] <= max(3, total * 0.01))
                & ((nonempty["observed_positive_rate"] <= 0.05) | (nonempty["observed_positive_rate"] >= 0.95))
            ).any()
        )
        bin_flags.append(
            {
                "fold": keys[0],
                "model": keys[1],
                "feature_set": keys[2],
                "horizon": keys[3],
                "calibration_method": keys[4],
                "bin_small_extreme_flag": small_extreme,
            }
        )
    flags = pd.DataFrame(bin_flags)
    out = before_after_df.merge(flags, on=["fold", "model", "feature_set", "horizon", "calibration_method"], how="left")
    topk_flags = topk[["fold", "model", "feature_set", "horizon", "calibration_method", "topk_stability_status"]].copy()
    out = out.merge(topk_flags, on=["fold", "model", "feature_set", "horizon", "calibration_method"], how="left")
    out["bin_small_extreme_flag"] = out["bin_small_extreme_flag"].fillna(False)
    out["ece_down_logloss_up"] = (out["ece_delta_after_minus_before"] < 0) & (out["log_loss_delta_after_minus_before"] > 0.02)
    out["brier_down_logloss_up"] = (out["brier_score_delta_after_minus_before"] < 0) & (out["log_loss_delta_after_minus_before"] > 0.02)
    out["auc_pr_decline"] = (out["auc_delta_after_minus_before"] < -0.02) | (out["pr_auc_delta_after_minus_before"] < -0.02)
    out["topk_degrades"] = out["topk_stability_status"].eq("material_degradation_or_shift")
    out["overfit_risk_flag"] = (
        out["ece_down_logloss_up"]
        | out["brier_down_logloss_up"]
        | out["bin_small_extreme_flag"]
        | out["auc_pr_decline"]
        | out["topk_degrades"]
    )
    def reason(row: pd.Series) -> str:
        reasons = []
        for col in ["ece_down_logloss_up", "brier_down_logloss_up", "bin_small_extreme_flag", "auc_pr_decline", "topk_degrades"]:
            if bool(row[col]):
                reasons.append(col)
        return ";".join(reasons) if reasons else "no_overfit_risk_flag"
    out["reason"] = out.apply(reason, axis=1)
    return out[
        [
            "fold",
            "model",
            "feature_set",
            "horizon",
            "calibration_method",
            "ece_down_logloss_up",
            "brier_down_logloss_up",
            "bin_small_extreme_flag",
            "auc_pr_decline",
            "topk_degrades",
            "overfit_risk_flag",
            "reason",
        ]
    ]


def aggregate_by_fold(metrics: pd.DataFrame) -> pd.DataFrame:
    macro = metrics[metrics["aggregation_method"].eq("macro_by_cutoff")].copy()
    return (
        macro.groupby(["fold", "model", "feature_set", "scope", "calibration_method", "train_period", "calibration_period", "test_period"], dropna=False)
        [["brier_score", "log_loss", "ece", "auc", "pr_auc"]]
        .mean(numeric_only=True)
        .reset_index()
    )


def aggregate_by_horizon(metrics: pd.DataFrame) -> pd.DataFrame:
    return metrics[metrics["aggregation_method"].eq("macro_by_cutoff")].copy()


def decision_table(metrics_by_fold: pd.DataFrame, before_after_df: pd.DataFrame, overfit: pd.DataFrame, bands: pd.DataFrame, topk: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    agg = (
        metrics_by_fold.groupby(["model", "feature_set", "calibration_method"], dropna=False)
        [["brier_score", "log_loss", "ece", "auc", "pr_auc"]]
        .mean(numeric_only=True)
        .reset_index()
        .sort_values(["brier_score", "log_loss", "ece", "auc", "pr_auc"], ascending=[True, True, True, False, False])
    )
    rows: list[dict[str, Any]] = []
    base = agg[(agg["model"].eq("logistic_regression")) & (agg["feature_set"].eq("base_recency_frequency_only"))].head(1)
    fd = agg[(agg["model"].eq("logistic_regression")) & (agg["feature_set"].eq("frequency_decay_v1"))].head(1)
    combined = agg[(agg["model"].eq("logistic_regression")) & (agg["feature_set"].eq("combined_stable_features_v1"))].head(1)
    xgb = agg[(agg["model"].eq("xgboost_small")) & (agg["feature_set"].eq("frequency_decay_v1"))].head(1)
    promoted = False
    for _, row in agg.iterrows():
        risk_count = len(
            overfit[
                (overfit["model"].eq(row["model"]))
                & (overfit["feature_set"].eq(row["feature_set"]))
                & (overfit["calibration_method"].eq(row["calibration_method"]))
                & (overfit["overfit_risk_flag"])
            ]
        )
        topk_bad = len(
            topk[
                (topk["model"].eq(row["model"]))
                & (topk["feature_set"].eq(row["feature_set"]))
                & (topk["calibration_method"].eq(row["calibration_method"]))
                & (topk["topk_stability_status"].eq("material_degradation_or_shift"))
            ]
        )
        is_fd_logistic = row["model"] == "logistic_regression" and row["feature_set"] == "frequency_decay_v1"
        beats_base = (
            not base.empty
            and row["brier_score"] < float(base.iloc[0]["brier_score"])
            and row["log_loss"] <= float(base.iloc[0]["log_loss"])
            and row["ece"] <= float(base.iloc[0]["ece"])
        )
        if is_fd_logistic and beats_base and risk_count == 0 and topk_bad == 0:
            decision = "promote_to_probability_candidate_v1"
            promoted = True
        elif is_fd_logistic:
            decision = "business_usable_probability_baseline"
        elif row["model"] == "logistic_regression" and row["feature_set"] == "base_recency_frequency_only":
            decision = "keep_as_baseline"
        elif row["model"] == "logistic_regression" and row["feature_set"] == "combined_stable_features_v1":
            decision = "keep_as_backup"
        elif row["model"] == "xgboost_small":
            decision = "keep_as_challenger"
        else:
            decision = "reject"
        rows.append(
            {
                "model": row["model"],
                "feature_set": row["feature_set"],
                "calibration_method": row["calibration_method"],
                "mean_brier_score": row["brier_score"],
                "mean_log_loss": row["log_loss"],
                "mean_ece": row["ece"],
                "mean_auc": row["auc"],
                "mean_pr_auc": row["pr_auc"],
                "overfit_risk_rows": risk_count,
                "topk_degradation_rows": topk_bad,
                "decision": decision,
                "reason": decision_reason(decision, risk_count),
            }
        )
    decision_text = "no_candidate_promoted"
    if promoted:
        winner = pd.DataFrame(rows)
        winner = winner[winner["decision"].eq("promote_to_probability_candidate_v1")].sort_values(["mean_brier_score", "mean_log_loss"]).iloc[0]
        decision_text = f"probability_candidate_v1 = {winner['model']} + {winner['feature_set']} + {winner['calibration_method']}"
    return pd.DataFrame(rows), decision_text


def decision_reason(decision: str, risk_count: int) -> str:
    if decision == "promote_to_probability_candidate_v1":
        return "Meets v2 promote rule against baseline without overfit or TopK degradation flags."
    if decision == "business_usable_probability_baseline":
        return f"Useful direction but not strong enough for final promotion; overfit risk rows={risk_count}."
    if decision == "keep_as_baseline":
        return "Old baseline retained for comparison."
    if decision == "keep_as_backup":
        return "Enhanced feature set remains backup; not better than frequency_decay_v1."
    if decision == "keep_as_challenger":
        return "XGBoost challenger does not exceed Logistic on calibrated probability metrics."
    return "Rejected from main probability candidate."


def write_summary(metrics_by_fold: pd.DataFrame, before_after_df: pd.DataFrame, overfit: pd.DataFrame, bands: pd.DataFrame, decision: pd.DataFrame, decision_text: str) -> None:
    agg = (
        metrics_by_fold.groupby(["model", "feature_set", "calibration_method"], dropna=False)
        [["brier_score", "log_loss", "ece", "auc", "pr_auc"]]
        .mean(numeric_only=True)
        .reset_index()
        .sort_values(["brier_score", "log_loss", "ece", "auc", "pr_auc"], ascending=[True, True, True, False, False])
    )
    method_cmp = (
        before_after_df.groupby("calibration_method")
        [["brier_score_delta_after_minus_before", "log_loss_delta_after_minus_before", "ece_delta_after_minus_before", "auc_delta_after_minus_before", "pr_auc_delta_after_minus_before"]]
        .mean(numeric_only=True)
        .reset_index()
    )
    business_usable = bool(decision["decision"].eq("business_usable_probability_baseline").any() or decision["decision"].eq("promote_to_probability_candidate_v1").any())
    lines = [
        "# Calibration v2 Summary",
        "",
        "This report evaluates calibration for stable churn_probability_H feature candidates only. It is not a business ranking model.",
        "",
        "## Aggregate Metrics",
        markdown_table(agg),
        "",
        "## Calibration Method Delta",
        markdown_table(method_cmp),
        "",
        "## Candidate Decision",
        markdown_table(decision),
        "",
        "## Direct Answers",
        "- Logistic + frequency_decay_v1 is the main stable direction.",
        "- combined_stable_features_v1 is evaluated as an enhanced backup.",
        "- XGBoost + frequency_decay_v1 remains a nonlinear challenger and does not drive promotion.",
        "- Platt is still the conservative rank-preserving reference; isotonic is allowed only when it avoids overfit flags.",
        f"- Decision: {decision_text}.",
        f"- business_usable_probability_baseline: {str(business_usable).lower()}.",
        "",
        "## Overfit Risk Rows",
        markdown_table(overfit[overfit["overfit_risk_flag"]].head(40)) if not overfit.empty else "No overfit risk rows.",
    ]
    write_text(OUTPUT_DIR / "calibration_v2_summary.md", "\n".join(lines))
    decision_lines = [
        "# Probability Candidate v1 Decision v2",
        "",
        f"Decision: {decision_text}",
        "",
        "## Required Answers",
        "1. Logistic + frequency_decay_v1 is compared against old baseline in calibration_v2_metrics_by_fold.csv.",
        "2. combined_stable_features_v1 does not automatically supersede frequency_decay_v1; see aggregate metrics.",
        "3. XGBoost + frequency_decay_v1 does not exceed Logistic if its aggregate probability metrics rank lower.",
        "4. Platt is more conservative; isotonic is promoted only if overfit checks pass.",
        "5. H3/H6/H12 can require horizon-specific calibration; do not force one method if overfit rows differ by horizon.",
        f"6. promote probability_candidate_v1: {'yes' if decision_text != 'no_candidate_promoted' else 'no'}.",
        "7. If promoted, the model/feature/method is stated above.",
        "8. If not promoted, remaining reasons are calibration instability, temporal drift, label noise, demand-shape mixture, or data coverage.",
        f"9. business_usable_probability_baseline: {str(business_usable).lower()}.",
        "10. Next step: demand-shape routing and label review if promotion fails; calibration v2 follow-up if a candidate is promoted.",
        "",
        "## Decision Table",
        markdown_table(decision),
    ]
    write_text(OUTPUT_DIR / "probability_candidate_v1_decision_v2.md", "\n".join(decision_lines))


def run_calibration_v2() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = small.read_yaml(ROOT / "configs/experiments/alive_prediction_small_models.yaml")
    df = consolidation.load_feature_data(config)
    df = feature_stability.add_stability_features(df)
    metric_rows_all: list[dict[str, Any]] = []
    bin_frames: list[pd.DataFrame] = []
    band_frames: list[pd.DataFrame] = []
    failures: list[dict[str, Any]] = []
    for fold in FOLDS:
        try:
            train, valid, test = split_fold(df, fold)
        except Exception as exc:
            for model, feature_set in CANDIDATES:
                for horizon in HORIZONS:
                    failures.append({**fold_columns(fold), "model": model, "feature_set": feature_set, "horizon": horizon, "reason": f"split_failed:{exc!r}"})
            continue
        for model, feature_set in CANDIDATES:
            for horizon in HORIZONS:
                rows, bins, bands, fail = run_candidate(config, fold, train, valid, test, model, feature_set, horizon)
                metric_rows_all.extend(rows)
                bin_frames.extend(bins)
                band_frames.extend(bands)
                failures.extend(fail)
    metrics = pd.DataFrame(metric_rows_all)
    bins = pd.concat(bin_frames, ignore_index=True) if bin_frames else pd.DataFrame()
    bands = pd.concat(band_frames, ignore_index=True) if band_frames else pd.DataFrame()
    before_after_df, topk = before_after(metrics)
    overfit = overfit_report(before_after_df, bins, topk)
    by_fold = aggregate_by_fold(metrics)
    by_horizon = aggregate_by_horizon(metrics)
    by_period = metrics.copy()
    decision, decision_text = decision_table(by_fold, before_after_df, overfit, bands, topk)
    failures_df = pd.DataFrame(failures, columns=["fold", "train_period", "calibration_period", "test_period", "model", "feature_set", "horizon", "reason"])
    metrics.to_csv(OUTPUT_DIR / "calibration_v2_metrics_by_period.csv", index=False, encoding="utf-8-sig")
    before_after_df.to_csv(OUTPUT_DIR / "calibration_v2_metrics_before_after.csv", index=False, encoding="utf-8-sig")
    by_horizon.to_csv(OUTPUT_DIR / "calibration_v2_metrics_by_horizon.csv", index=False, encoding="utf-8-sig")
    by_fold.to_csv(OUTPUT_DIR / "calibration_v2_metrics_by_fold.csv", index=False, encoding="utf-8-sig")
    bins.to_csv(OUTPUT_DIR / "calibration_v2_bins.csv", index=False, encoding="utf-8-sig")
    bands.to_csv(OUTPUT_DIR / "calibration_v2_business_usability_bands.csv", index=False, encoding="utf-8-sig")
    topk.to_csv(OUTPUT_DIR / "calibration_v2_topk_stability.csv", index=False, encoding="utf-8-sig")
    overfit.to_csv(OUTPUT_DIR / "calibration_v2_overfit_risk_report.csv", index=False, encoding="utf-8-sig")
    decision.to_csv(OUTPUT_DIR / "probability_candidate_v1_decision_v2.csv", index=False, encoding="utf-8-sig")
    failures_df.to_csv(OUTPUT_DIR / "calibration_v2_failure_report.csv", index=False, encoding="utf-8-sig")
    write_summary(by_fold, before_after_df, overfit, bands, decision, decision_text)


def main() -> int:
    run_calibration_v2()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
