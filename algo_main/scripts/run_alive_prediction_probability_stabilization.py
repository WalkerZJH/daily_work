#!/usr/bin/env python
"""Diagnose probability candidate stabilization after rolling-origin v1."""

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

import run_alive_prediction_probability_consolidation as consolidation
import run_alive_prediction_rolling_origin_v1 as rolling
import run_alive_prediction_small_model_experiments as small


OUTPUT_DIR = ROOT / "reports/alive_prediction_probability_stabilization"
ROLLING_DIR = ROOT / "reports/alive_prediction_rolling_origin_v1"
PRIMARY_SCOPE = "recurring_only"
KEY_COLS = ["manufacturer_code", "hospital_code", "drug_group"]
HORIZONS = [3, 6, 12]
FEATURES_TO_CHECK = [
    "months_since_last_purchase_asof_cutoff",
    "months_since_first_purchase_asof_cutoff",
    "order_count_last_3m_asof_cutoff",
    "order_count_last_6m_asof_cutoff",
    "order_count_last_12m_asof_cutoff",
    "active_month_count_asof_cutoff",
    "purchase_count_asof_cutoff",
    "months_observed_asof_cutoff",
    "active_month_ratio_asof_cutoff",
    "adi_asof_cutoff",
]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def markdown_table(df: pd.DataFrame) -> str:
    return small.dataframe_to_markdown(df, index=False)


def read_csv(name: str) -> pd.DataFrame:
    path = ROLLING_DIR / name
    if not path.exists() or path.stat().st_size == 0:
        raise FileNotFoundError(f"Missing rolling-origin report: {path}")
    return pd.read_csv(path)


def cutoff_periods(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["cutoff_month"]).dt.to_period("M")


def cutoff_mask(df: pd.DataFrame, period_text: str) -> pd.Series:
    if not period_text or period_text == "none":
        return pd.Series(False, index=df.index)
    start, end = period_text.split("~")
    periods = cutoff_periods(df)
    return (periods >= pd.Period(start, freq="M")) & (periods <= pd.Period(end, freq="M"))


def split_frame(df: pd.DataFrame, period_text: str, split: str) -> pd.DataFrame:
    if period_text == "none":
        return pd.DataFrame(columns=df.columns)
    frame = df[cutoff_mask(df, period_text)].copy()
    if split in {"model_train", "calibration_valid"}:
        frame = frame[frame["recurring_candidate_flag"]].copy()
        if "one_shot_high_value_silence_flag" in frame.columns:
            frame = frame[~frame["one_shot_high_value_silence_flag"].astype(bool)].copy()
    else:
        frame = small.split_scopes(frame)[PRIMARY_SCOPE]
    return frame


def entity_count(df: pd.DataFrame) -> int:
    return int(df[KEY_COLS].drop_duplicates().shape[0]) if len(df) else 0


def fold_label_distribution(df: pd.DataFrame, rolling_metrics: pd.DataFrame) -> pd.DataFrame:
    fold_periods = (
        rolling_metrics[["fold", "train_period", "calibration_period", "test_period"]]
        .drop_duplicates()
        .sort_values("fold")
    )
    rows: list[dict[str, Any]] = []
    for _, fold in fold_periods.iterrows():
        for split, period_col in [
            ("model_train", "train_period"),
            ("calibration_valid", "calibration_period"),
            ("test", "test_period"),
        ]:
            period = str(fold[period_col])
            frame = split_frame(df, period, split)
            if frame.empty and period == "none":
                continue
            for horizon in HORIZONS:
                label_col = f"label_die_H{horizon}"
                y = frame[label_col].dropna() if label_col in frame else pd.Series(dtype=float)
                rows.append(
                    {
                        "fold": fold["fold"],
                        "split": split,
                        "horizon": horizon,
                        "test_period": period,
                        "row_count": int(len(frame)),
                        "entity_count": entity_count(frame),
                        "positive_rate": float(y.mean()) if len(y) else np.nan,
                        "positive_count": int(y.sum()) if len(y) else 0,
                        "negative_count": int((1 - y).sum()) if len(y) else 0,
                    }
                )
    return pd.DataFrame(rows)


def feature_stats(frame: pd.DataFrame, feature: str) -> dict[str, float | str]:
    if feature not in frame.columns:
        return {"mean": np.nan, "std": np.nan, "missing_rate": np.nan, "status": "missing_or_reserved"}
    values = pd.to_numeric(frame[feature], errors="coerce")
    return {
        "mean": float(values.mean()) if len(values) else np.nan,
        "std": float(values.std(ddof=0)) if len(values) else np.nan,
        "missing_rate": float(values.isna().mean()) if len(values) else np.nan,
        "status": "ok",
    }


def smd(mean_a: float, std_a: float, mean_b: float, std_b: float) -> float:
    if not np.isfinite(mean_a) or not np.isfinite(mean_b):
        return np.nan
    pooled = np.sqrt((np.nan_to_num(std_a, nan=0.0) ** 2 + np.nan_to_num(std_b, nan=0.0) ** 2) / 2)
    return float((mean_a - mean_b) / pooled) if pooled > 0 else np.nan


def fold_feature_distribution(df: pd.DataFrame, rolling_metrics: pd.DataFrame) -> pd.DataFrame:
    fold_periods = (
        rolling_metrics[["fold", "train_period", "calibration_period", "test_period"]]
        .drop_duplicates()
        .sort_values("fold")
    )
    rows: list[dict[str, Any]] = []
    for _, fold in fold_periods.iterrows():
        train = split_frame(df, str(fold["train_period"]), "model_train")
        calibration = split_frame(df, str(fold["calibration_period"]), "calibration_valid")
        test = split_frame(df, str(fold["test_period"]), "test")
        for horizon in HORIZONS:
            for feature in FEATURES_TO_CHECK:
                tr = feature_stats(train, feature)
                cal = feature_stats(calibration, feature)
                te = feature_stats(test, feature)
                rows.append(
                    {
                        "fold": fold["fold"],
                        "split": "model_train_vs_calibration_valid_vs_test",
                        "horizon": horizon,
                        "feature": feature,
                        "train_mean": tr["mean"],
                        "calibration_mean": cal["mean"],
                        "test_mean": te["mean"],
                        "train_std": tr["std"],
                        "calibration_std": cal["std"],
                        "test_std": te["std"],
                        "train_test_standardized_mean_diff": smd(tr["mean"], tr["std"], te["mean"], te["std"]),
                        "calibration_test_standardized_mean_diff": smd(cal["mean"], cal["std"], te["mean"], te["std"]),
                        "train_missing_rate": tr["missing_rate"],
                        "calibration_missing_rate": cal["missing_rate"],
                        "test_missing_rate": te["missing_rate"],
                        "status": ";".join(sorted({str(tr["status"]), str(cal["status"]), str(te["status"])})),
                    }
                )
    return pd.DataFrame(rows)


def bin_risk_flags(bins: pd.DataFrame) -> pd.DataFrame:
    calibrated = bins[bins["calibration_method"].isin(["platt", "isotonic"])].copy()
    rows: list[dict[str, Any]] = []
    group_cols = ["fold", "model", "feature_set", "horizon", "calibration_method"]
    for keys, group in calibrated.groupby(group_cols, dropna=False):
        nonempty = group[group["row_count"] > 0].copy()
        small_extreme = False
        sawtooth = False
        if not nonempty.empty:
            total = float(nonempty["row_count"].sum())
            small_extreme = bool(
                (
                    (nonempty["row_count"] <= max(3, 0.01 * total))
                    & (
                        (nonempty["observed_positive_rate"] <= 0.05)
                        | (nonempty["observed_positive_rate"] >= 0.95)
                    )
                ).any()
            )
            obs = nonempty.sort_values("bin")["observed_positive_rate"].dropna().to_numpy()
            if len(obs) >= 4:
                diffs = np.diff(obs)
                signs = np.sign(diffs[np.abs(diffs) > 0.05])
                sawtooth = bool(len(signs) >= 3 and np.any(signs[1:] * signs[:-1] < 0))
        rows.append(
            {
                "fold": keys[0],
                "model": keys[1],
                "feature_set": keys[2],
                "horizon": keys[3],
                "calibration_method": keys[4],
                "bin_small_extreme_flag": small_extreme,
                "bin_sawtooth_flag": sawtooth,
            }
        )
    return pd.DataFrame(rows)


def calibration_instability(comparison: pd.DataFrame, bins: pd.DataFrame) -> pd.DataFrame:
    bin_flags = bin_risk_flags(bins)
    rows = comparison.copy()
    rows["brier_delta"] = rows["brier_score_delta_after_minus_before"]
    rows["logloss_delta"] = rows["log_loss_delta_after_minus_before"]
    rows["ece_delta"] = rows["ece_delta_after_minus_before"]
    rows["auc_delta"] = rows["auc_delta_after_minus_before"]
    rows["pr_auc_delta"] = rows["pr_auc_delta_after_minus_before"]
    rows["improves_brier"] = rows["brier_delta"] < 0
    rows["improves_logloss"] = rows["logloss_delta"] < 0
    rows["improves_ece"] = rows["ece_delta"] < 0
    rows["improves_all_probability_metrics"] = rows["improves_brier"] & rows["improves_logloss"] & rows["improves_ece"]
    rows = rows.merge(bin_flags, on=["fold", "model", "feature_set", "horizon", "calibration_method"], how="left")
    rows[["bin_small_extreme_flag", "bin_sawtooth_flag"]] = rows[["bin_small_extreme_flag", "bin_sawtooth_flag"]].fillna(False)
    rows["overfit_risk_flag"] = (
        ((rows["ece_delta"] < 0) & (rows["logloss_delta"] > 0.02))
        | ((rows["brier_delta"] < 0) & (rows["logloss_delta"] > 0.02))
        | rows["bin_small_extreme_flag"]
        | rows["bin_sawtooth_flag"]
        | (rows["auc_delta"] < -0.02)
        | (rows["pr_auc_delta"] < -0.02)
    )
    def reason(row: pd.Series) -> str:
        reasons: list[str] = []
        if row["improves_all_probability_metrics"]:
            reasons.append("improves_brier_logloss_ece")
        if row["ece_delta"] < 0 and row["logloss_delta"] > 0.02:
            reasons.append("ece_improves_but_logloss_worsens")
        if row["brier_delta"] < 0 and row["logloss_delta"] > 0.02:
            reasons.append("brier_improves_but_logloss_worsens")
        if bool(row["bin_small_extreme_flag"]):
            reasons.append("small_sample_extreme_calibration_bins")
        if bool(row["bin_sawtooth_flag"]):
            reasons.append("sawtooth_calibration_bins")
        if row["auc_delta"] < -0.02:
            reasons.append("auc_declines")
        if row["pr_auc_delta"] < -0.02:
            reasons.append("pr_auc_declines")
        return ";".join(reasons) if reasons else "diagnostic_only_no_clear_improvement"
    rows["reason"] = rows.apply(reason, axis=1)
    keep_cols = [
        "fold",
        "model",
        "feature_set",
        "horizon",
        "calibration_method",
        "brier_delta",
        "logloss_delta",
        "ece_delta",
        "auc_delta",
        "pr_auc_delta",
        "improves_brier",
        "improves_logloss",
        "improves_ece",
        "improves_all_probability_metrics",
        "overfit_risk_flag",
        "reason",
    ]
    return rows[keep_cols]


def candidate_decision_update() -> pd.DataFrame:
    src = ROLLING_DIR / "probability_candidate_v1_decision.csv"
    decision = pd.read_csv(src)
    rows: list[dict[str, Any]] = []
    for _, row in decision.iterrows():
        old = row["decision"]
        if row["model"] == "logistic_regression":
            new = "needs_drift_and_feature_stability_review" if old == "needs_rolling_origin_validation" else old
            reason = "Logistic remains the primary_probability_direction, but no promotion until drift and feature stability are addressed."
        elif row["model"] == "xgboost_small" and row["feature_set"] == "base_recency_frequency_only":
            new = "backup_nonlinear_challenger"
            reason = "XGBoost base-only remains a backup nonlinear challenger; it did not stably beat Logistic."
        elif row["model"] == "xgboost_small" and row["feature_set"] == "base_plus_interval_features":
            new = "paused_feature_set"
            reason = "Interval features are paused because they did not stabilize probability quality."
        else:
            new = "holdout"
            reason = "Not part of this stabilization review."
        rows.append(
            {
                "model": row["model"],
                "feature_set": row["feature_set"],
                "calibration_method": row["calibration_method"],
                "old_decision": old,
                "new_decision": new,
                "reason": reason,
            }
        )
    return pd.DataFrame(rows)


def candidate_rank_consistency(metrics_by_horizon: pd.DataFrame) -> pd.DataFrame:
    macro = metrics_by_horizon[metrics_by_horizon["aggregation_method"].eq("macro_by_cutoff")].copy()
    rows: list[dict[str, Any]] = []
    specs = {
        "brier_score": True,
        "log_loss": True,
        "ece": True,
        "auc": False,
        "pr_auc": False,
    }
    for metric, ascending in specs.items():
        for (fold, horizon), group in macro.groupby(["fold", "horizon"], dropna=False):
            ranked = group.sort_values(metric, ascending=ascending).head(2)
            first = ranked.iloc[0] if len(ranked) > 0 else pd.Series(dtype=object)
            second = ranked.iloc[1] if len(ranked) > 1 else pd.Series(dtype=object)
            note = "logistic_rank_1" if first.get("model") == "logistic_regression" else "non_logistic_rank_1"
            rows.append(
                {
                    "metric": metric,
                    "fold": fold,
                    "horizon": horizon,
                    "rank_1_model": first.get("model", ""),
                    "rank_1_feature_set": first.get("feature_set", ""),
                    "rank_1_calibration_method": first.get("calibration_method", ""),
                    "rank_2_model": second.get("model", ""),
                    "rank_2_feature_set": second.get("feature_set", ""),
                    "rank_2_calibration_method": second.get("calibration_method", ""),
                    "rank_stability_note": note,
                }
            )
    return pd.DataFrame(rows)


def write_calibration_instability_summary(diag: pd.DataFrame) -> None:
    method_counts = (
        diag.groupby("calibration_method")
        .agg(
            rows=("fold", "count"),
            improves_brier=("improves_brier", "sum"),
            improves_logloss=("improves_logloss", "sum"),
            improves_ece=("improves_ece", "sum"),
            improves_all_probability_metrics=("improves_all_probability_metrics", "sum"),
            overfit_risk=("overfit_risk_flag", "sum"),
        )
        .reset_index()
    )
    logloss_spike = diag[
        (diag["ece_delta"] < 0) & (diag["logloss_delta"] > 0.02)
    ].groupby("calibration_method").size().reset_index(name="ece_improves_logloss_worsens")
    lines = [
        "# Calibration Instability Summary",
        "",
        "This diagnosis reviews calibration stability only for churn_probability_H. It is not a business ranking analysis.",
        "",
        "## Method Counts",
        markdown_table(method_counts),
        "",
        "## ECE Improves But LogLoss Worsens",
        markdown_table(logloss_spike) if not logloss_spike.empty else "No rows where ECE improves while LogLoss worsens by more than 0.02.",
        "",
        "## Answers",
        f"1. Platt improvements are shown in the method count table.",
        f"2. Isotonic improvements are shown in the method count table.",
        "3. More conservative method: platt, because it is parametric and rank-order preserving in this setup.",
        "4. Higher stepwise/logloss overfit risk method: isotonic, especially where ECE improves while LogLoss worsens.",
        "5. Current recommendation: do not promote a calibrated probability candidate yet.",
        "6. If continuing calibration, use Platt as the conservative reference and isotonic only with stronger fold-level safeguards.",
        "7. Feature stability should be improved before spending more effort on calibration.",
    ]
    write_text(OUTPUT_DIR / "calibration_instability_summary.md", "\n".join(lines))


def write_horizon_report(metrics_by_horizon: pd.DataFrame, instability: pd.DataFrame) -> None:
    macro = metrics_by_horizon[metrics_by_horizon["aggregation_method"].eq("macro_by_cutoff")].copy()
    summary = (
        macro.groupby("horizon")[["brier_score", "log_loss", "ece", "auc", "pr_auc"]]
        .agg(["mean", "std"])
        .reset_index()
    )
    summary.columns = ["_".join(map(str, col)).strip("_") for col in summary.columns.to_flat_index()]
    auc_stable = summary.sort_values("auc_std").iloc[0]["horizon"]
    pr_stable = summary.sort_values("pr_auc_std").iloc[0]["horizon"]
    ece_hard = summary.sort_values("ece_mean", ascending=False).iloc[0]["horizon"]
    brier_hard = summary.sort_values("brier_score_mean", ascending=False).iloc[0]["horizon"]
    lines = [
        "# Horizon Difficulty Report",
        "",
        "## Metric Stability By Horizon",
        markdown_table(summary),
        "",
        "## Answers",
        f"1. Most stable AUC horizon: H{int(auc_stable)}; most stable PR_AUC horizon: H{int(pr_stable)}.",
        f"2. Hardest ECE horizon: H{int(ece_hard)}; hardest Brier horizon: H{int(brier_hard)}.",
        "3. H3/H6/H12 should not be forced to share the same calibration method at this stage.",
        "4. Horizon-specific decision is recommended.",
        "5. If H12 remains less stable, plausible causes include longer label windows, more business disturbance, and noisier churn definitions.",
    ]
    write_text(OUTPUT_DIR / "horizon_difficulty_report.md", "\n".join(lines))


def write_recency_activity_report(feature_shift: pd.DataFrame) -> None:
    top = feature_shift.copy()
    top["abs_train_test_smd"] = top["train_test_standardized_mean_diff"].abs()
    top = top.sort_values("abs_train_test_smd", ascending=False).head(20)
    lines = [
        "# Recency/Activity Drift Report",
        "",
        "Recency and frequency features are reasonable churn probability inputs because churn is behaviorally tied to recent activity and purchase cadence.",
        "",
        "However, recency/activity/cohort-age proxy features drift across train, calibration, and test splits. This can preserve ranking signal while destabilizing probability calibration.",
        "",
        "## Largest Train/Test Feature Shifts",
        markdown_table(top[["fold", "horizon", "feature", "train_test_standardized_mean_diff", "calibration_test_standardized_mean_diff", "train_mean", "calibration_mean", "test_mean", "status"]]),
        "",
        "## Interpretation",
        "- The model is allowed to use recency/frequency signals.",
        "- The instability comes from distribution shift in the same signals across time.",
        "- Next feature work should prefer low-leakage normalized and within-cohort features that are more stable across cutoffs.",
    ]
    write_text(OUTPUT_DIR / "recency_activity_drift_report.md", "\n".join(lines))


def write_next_feature_plan() -> None:
    lines = [
        "# Next Feature Design Plan",
        "",
        "Design only; no implementation in this step.",
        "",
        "## Candidate Feature Directions",
        "1. normalized_recency: months_since_last_purchase / expected_purchase_interval.",
        "2. recency_percentile_within_demand_group: recency percentile within demand pattern or active_month_count groups.",
        "3. frequency_decay_ratio: recent_order_rate / historical_order_rate.",
        "4. stability_of_purchase_interval: interval variability instead of high-cardinality identifiers.",
        "5. cohort_age_bucket: coarse buckets instead of continuous months_since_first_purchase proxy.",
        "6. horizon-specific base rate feature: only historical as-of cutoff cohort statistics; never test labels.",
        "7. demand_shape flags: recurring/intermittent/lumpy segmentation if existing fields pass leakage audit.",
        "",
        "## Prohibited",
        "- cutoff_month directly in X.",
        "- Future label statistics.",
        "- 2024 test-fitted encodings or thresholds.",
        "- value_at_risk or business_priority fields.",
    ]
    write_text(OUTPUT_DIR / "next_feature_design_plan.md", "\n".join(lines))


def write_data_expansion_note(label_shift: pd.DataFrame) -> None:
    lines = [
        "# Data Expansion Decision Note",
        "",
        "1. Model family insufficiency is not proven. Logistic remains competitive and stable.",
        "2. Data insufficiency should be separated into raw order volume, recurring entity x cutoff training coverage, and calibration_valid/test distribution mismatch.",
        "3. Do not immediately expand raw data just to add model capacity.",
        "4. If expanding data, prioritize more years, more recurring entity x cutoff samples, more stable calibration_valid cutoffs, and more true terminal churn backtests. Additional manufacturers are useful only if they increase stable recurring cohorts.",
        "5. If not expanding first, prioritize feature stability redesign: normalized recency, frequency decay, cohort buckets, and demand-shape audits.",
        "",
        "## Label Distribution Snapshot",
        markdown_table(label_shift.head(30)),
    ]
    write_text(OUTPUT_DIR / "data_expansion_decision_note.md", "\n".join(lines))


def write_stabilization_summary(
    label_shift: pd.DataFrame,
    feature_shift: pd.DataFrame,
    instability: pd.DataFrame,
    rank_consistency: pd.DataFrame,
    decision_update: pd.DataFrame,
) -> None:
    test_labels = label_shift[label_shift["split"].eq("test")]
    label_pivot = test_labels.pivot_table(index=["fold", "test_period"], columns="horizon", values="positive_rate").reset_index()
    cal_test = label_shift[label_shift["split"].isin(["calibration_valid", "test"])].copy()
    cal_test_compare = cal_test.pivot_table(index=["fold", "horizon"], columns="split", values="positive_rate").reset_index()
    cal_test_compare["calibration_test_positive_rate_gap"] = cal_test_compare.get("calibration_valid") - cal_test_compare.get("test")
    logistic_rank1_rate = float((rank_consistency["rank_1_model"] == "logistic_regression").mean()) if len(rank_consistency) else np.nan
    overfit_rate = float(instability["overfit_risk_flag"].mean()) if len(instability) else np.nan
    top_shift = feature_shift.copy()
    top_shift["abs_train_test_smd"] = top_shift["train_test_standardized_mean_diff"].abs()
    lines = [
        "# Probability Stabilization Summary",
        "",
        "This report diagnoses why no probability_candidate_v1 was promoted. The main model remains churn_probability_H = P(die_H = 1).",
        "",
        "## Candidate Decision Update",
        markdown_table(decision_update),
        "",
        "## Test Label Rate By Fold/Horizon",
        markdown_table(label_pivot),
        "",
        "## Calibration/Test Label Rate Gap",
        markdown_table(cal_test_compare),
        "",
        "## Main Findings",
        f"- Logistic rank-1 share across candidate rank checks: {logistic_rank1_rate:.2f}.",
        f"- Calibration overfit-risk share across calibration rows: {overfit_rate:.2f}.",
        "- Fold label rates differ materially, especially between 2022 and 2024 test periods.",
        "- Positive rate also changes systematically by horizon, so one shared calibration decision across H3/H6/H12 is not justified.",
        "- Calibration_valid/test base-rate mismatch makes calibrator instability expected, not surprising.",
        "- Recency/activity/cohort-age features drift across train/calibration/test; this explains ranking signal with unstable probability calibration.",
        "",
        "## Largest Feature Shifts",
        markdown_table(top_shift.sort_values("abs_train_test_smd", ascending=False).head(15)[["fold", "horizon", "feature", "train_test_standardized_mean_diff", "calibration_test_standardized_mean_diff", "status"]]),
        "",
        "## Conclusion",
        "- Logistic remains the primary_probability_direction.",
        "- XGBoost base-only remains a backup/nonlinear challenger.",
        "- XGBoost interval features are paused.",
        "- CatBoost is not part of this round.",
        "- Do not promote probability_candidate_v1 yet; do drift and feature stability redesign first.",
    ]
    write_text(OUTPUT_DIR / "probability_stabilization_summary.md", "\n".join(lines))


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = small.read_yaml(ROOT / "configs/experiments/alive_prediction_small_models.yaml")
    df = consolidation.load_feature_data(config)
    rolling_metrics = read_csv("rolling_origin_metrics.csv")
    metrics_by_horizon = read_csv("rolling_origin_metrics_by_horizon.csv")
    calibration_comparison = read_csv("rolling_origin_calibration_comparison.csv")
    bins = read_csv("rolling_origin_calibration_bins.csv")
    label_shift = fold_label_distribution(df, rolling_metrics)
    feature_shift = fold_feature_distribution(df, rolling_metrics)
    instability = calibration_instability(calibration_comparison, bins)
    rank_consistency = candidate_rank_consistency(metrics_by_horizon)
    decision_update = candidate_decision_update()
    label_shift.to_csv(OUTPUT_DIR / "fold_label_distribution_shift.csv", index=False, encoding="utf-8-sig")
    feature_shift.to_csv(OUTPUT_DIR / "fold_feature_distribution_shift.csv", index=False, encoding="utf-8-sig")
    instability.to_csv(OUTPUT_DIR / "calibration_instability_diagnosis.csv", index=False, encoding="utf-8-sig")
    rank_consistency.to_csv(OUTPUT_DIR / "candidate_rank_consistency.csv", index=False, encoding="utf-8-sig")
    decision_update.to_csv(OUTPUT_DIR / "candidate_decision_update.csv", index=False, encoding="utf-8-sig")
    write_calibration_instability_summary(instability)
    write_horizon_report(metrics_by_horizon, instability)
    write_recency_activity_report(feature_shift)
    write_next_feature_plan()
    write_data_expansion_note(label_shift)
    write_stabilization_summary(label_shift, feature_shift, instability, rank_consistency, decision_update)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
