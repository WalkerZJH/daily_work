#!/usr/bin/env python
"""Run lightweight calibration v1 for churn probability candidates."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_alive_prediction_expanded_train_diagnostics as expanded
import run_alive_prediction_probability_consolidation as consolidation
import run_alive_prediction_small_model_experiments as small


OUTPUT_DIR = ROOT / "reports/alive_prediction_calibration_v1"
PRIMARY_SCOPE = "recurring_only"
MODEL_TRAIN = {"train_cutoff_start": "2020-01", "train_cutoff_end": "2021-12"}
CALIBRATION_VALID = {"valid_cutoff_start": "2022-01", "valid_cutoff_end": "2022-12"}
FINAL_TEST = {"test_cutoff_start": "2024-01", "test_cutoff_end": "2024-12"}
PERIODS = consolidation.PERIODS
CALIBRATION_CANDIDATES = [
    ("logistic_regression", "base_recency_frequency_only"),
    ("xgboost_small", "base_recency_frequency_only"),
    ("xgboost_small", "base_plus_interval_features"),
    ("catboost_small", "base_recency_frequency_only"),
]


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


def split_calibration_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = df[cutoff_mask(df, MODEL_TRAIN["train_cutoff_start"], MODEL_TRAIN["train_cutoff_end"]) & df["recurring_candidate_flag"]].copy()
    valid = df[cutoff_mask(df, CALIBRATION_VALID["valid_cutoff_start"], CALIBRATION_VALID["valid_cutoff_end"]) & df["recurring_candidate_flag"]].copy()
    test = df[cutoff_mask(df, FINAL_TEST["test_cutoff_start"], FINAL_TEST["test_cutoff_end"])].copy()
    test = small.split_scopes(test)[PRIMARY_SCOPE]
    if "one_shot_high_value_silence_flag" in train:
        train = train[~train["one_shot_high_value_silence_flag"].astype(bool)].copy()
    if "one_shot_high_value_silence_flag" in valid:
        valid = valid[~valid["one_shot_high_value_silence_flag"].astype(bool)].copy()
    if set(cutoff_periods(train)).intersection(set(cutoff_periods(valid))) or set(cutoff_periods(valid)).intersection(set(cutoff_periods(test))):
        raise RuntimeError("Calibration split cutoffs overlap")
    return train, valid, test


def fit_calibrator(method: str, raw_valid: np.ndarray, y_valid: np.ndarray):
    raw_valid = np.clip(raw_valid.astype(float), 1e-15, 1 - 1e-15)
    if method == "platt":
        calibrator = LogisticRegression(solver="lbfgs", max_iter=1000)
        calibrator.fit(raw_valid.reshape(-1, 1), y_valid.astype(int))
        return calibrator
    if method == "isotonic":
        calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        calibrator.fit(raw_valid, y_valid.astype(float))
        return calibrator
    raise ValueError(f"Unknown calibration method: {method}")


def apply_calibrator(method: str, calibrator: Any, raw: np.ndarray) -> np.ndarray:
    raw = np.clip(raw.astype(float), 1e-15, 1 - 1e-15)
    if method == "platt":
        return calibrator.predict_proba(raw.reshape(-1, 1))[:, 1]
    if method == "isotonic":
        return calibrator.predict(raw)
    raise ValueError(f"Unknown calibration method: {method}")


def scored_with_probability(df: pd.DataFrame, horizon: int, probability: np.ndarray, version: str) -> pd.DataFrame:
    scored = df.copy()
    scored[f"churn_probability_H{horizon}"] = np.clip(probability.astype(float), 1e-15, 1 - 1e-15)
    scored["probability_version"] = version
    return scored


def metric_rows_for_version(scored: pd.DataFrame, *, model: str, feature_set: str, horizon: int, calibration_method: str, probability_version: str) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    cutoff_rows: list[dict[str, Any]] = []
    for cutoff, part in scored.groupby(cutoff_periods(scored), sort=True):
        row = consolidation.metric_row(
            part,
            model=model,
            feature_set=feature_set,
            horizon=horizon,
            aggregation_method="by_cutoff",
            period=str(cutoff),
            cutoff_month=str(cutoff),
            compute_topk=True,
        )
        cutoff_rows.append(row)
    cutoff_df = pd.DataFrame(cutoff_rows)
    raw_overall = consolidation.metric_row(
        scored,
        model=model,
        feature_set=feature_set,
        horizon=horizon,
        aggregation_method="raw_overall",
        period="all_2024",
        compute_topk=False,
    )
    rows.append(raw_overall)
    if not cutoff_df.empty:
        rows.append(consolidation.macro_from_cutoffs(cutoff_df, period="all_2024", aggregation_method="macro_by_cutoff"))
        for period, (start, end) in PERIODS.items():
            part_cutoffs = cutoff_df[cutoff_df["period"].between(start, end)]
            if not part_cutoffs.empty:
                rows.append(consolidation.macro_from_cutoffs(part_cutoffs, period=period, aggregation_method="early_mid_late"))
    for row in rows:
        row["calibration_method"] = calibration_method
        row["probability_version"] = probability_version
    cutoff_df["calibration_method"] = calibration_method
    cutoff_df["probability_version"] = probability_version
    return rows, cutoff_df


def calibration_bins(scored: pd.DataFrame, *, model: str, feature_set: str, horizon: int, calibration_method: str, probability_version: str, bins: int = 10) -> pd.DataFrame:
    label_col = f"label_die_H{horizon}"
    prob_col = f"churn_probability_H{horizon}"
    y = scored[label_col].astype(float)
    p = scored[prob_col].astype(float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows: list[dict[str, Any]] = []
    for idx, (lower, upper) in enumerate(zip(edges[:-1], edges[1:]), start=1):
        mask = (p >= lower) & (p <= upper) if upper == 1.0 else (p >= lower) & (p < upper)
        part_y = y[mask]
        part_p = p[mask]
        rows.append(
            {
                "model": model,
                "feature_set": feature_set,
                "horizon": horizon,
                "scope": PRIMARY_SCOPE,
                "calibration_method": calibration_method,
                "probability_version": probability_version,
                "period": "all_2024",
                "bin": idx,
                "bin_lower": lower,
                "bin_upper": upper,
                "row_count": int(mask.sum()),
                "mean_predicted_probability": float(part_p.mean()) if len(part_p) else np.nan,
                "observed_positive_rate": float(part_y.mean()) if len(part_y) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def before_after_rows(metrics: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    probability_cols = ["brier_score", "log_loss", "ece", "auc", "pr_auc"]
    topk_cols = [
        "precision_at_top_1_pct",
        "precision_at_top_5_pct",
        "precision_at_top_10_pct",
        "lift_at_top_1_pct",
        "lift_at_top_5_pct",
        "lift_at_top_10_pct",
        "ndcg_at_top_1_pct",
        "ndcg_at_top_5_pct",
        "ndcg_at_top_10_pct",
    ]
    calibrated = metrics[metrics["probability_version"].eq("calibrated")].copy()
    raw = metrics[metrics["probability_version"].eq("raw")].copy()
    keys = ["model", "feature_set", "horizon", "scope", "aggregation_method", "period", "calibration_method"]
    paired = calibrated.merge(raw, on=keys, suffixes=("_after", "_before"), how="left")
    rows: list[dict[str, Any]] = []
    topk_rows: list[dict[str, Any]] = []
    for _, row in paired.iterrows():
        out = {key: row[key] for key in keys}
        for col in probability_cols:
            out[f"{col}_before"] = row.get(f"{col}_before", np.nan)
            out[f"{col}_after"] = row.get(f"{col}_after", np.nan)
            out[f"{col}_delta_after_minus_before"] = out[f"{col}_after"] - out[f"{col}_before"]
        rows.append(out)
        topk = {key: row[key] for key in keys}
        for col in topk_cols:
            topk[f"{col}_before"] = row.get(f"{col}_before", np.nan)
            topk[f"{col}_after"] = row.get(f"{col}_after", np.nan)
            topk[f"{col}_delta_after_minus_before"] = topk[f"{col}_after"] - topk[f"{col}_before"]
        topk_rows.append(topk)
    before_after = pd.DataFrame(rows)
    topk = pd.DataFrame(topk_rows)
    by_horizon = (
        before_after[before_after["aggregation_method"].eq("macro_by_cutoff")]
        .sort_values(["brier_score_after", "log_loss_after", "ece_after", "auc_after", "pr_auc_after"], ascending=[True, True, True, False, False])
        .copy()
    )
    return before_after, by_horizon, topk


def method_status(before_after: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    macro = before_after[before_after["aggregation_method"].eq("macro_by_cutoff")]
    for _, row in macro.iterrows():
        brier_delta = row["brier_score_delta_after_minus_before"]
        logloss_delta = row["log_loss_delta_after_minus_before"]
        ece_delta = row["ece_delta_after_minus_before"]
        if pd.notna(ece_delta) and ece_delta < 0 and pd.notna(brier_delta) and brier_delta <= 0 and pd.notna(logloss_delta) and logloss_delta <= 0:
            status = "keep_calibration_method"
        elif pd.notna(ece_delta) and ece_delta < 0 and pd.notna(logloss_delta) and logloss_delta > 0.02:
            status = "overfit_risk"
        else:
            status = "diagnostic_only"
        rows.append({**{key: row[key] for key in ["model", "feature_set", "horizon", "calibration_method"]}, "calibration_status": status})
    return pd.DataFrame(rows)


def run_calibration_v1() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = small.read_yaml(ROOT / "configs/experiments/alive_prediction_small_models.yaml")
    ablation_config = small.read_yaml(ROOT / "configs/experiments/alive_prediction_feature_ablation.yaml")
    df = consolidation.load_feature_data(config)
    train_df, valid_df, test_df = split_calibration_data(df)
    metric_frames: list[pd.DataFrame] = []
    cutoff_frames: list[pd.DataFrame] = []
    bin_frames: list[pd.DataFrame] = []
    failures: list[dict[str, Any]] = []
    for model, feature_set in CALIBRATION_CANDIDATES:
        for horizon in config["horizons_months"]:
            label_col = f"label_die_H{horizon}"
            try:
                numeric_cols, categorical_cols, missing = expanded.ablation_feature_columns(train_df, config, ablation_config, model, feature_set)
                forbidden = [
                    column
                    for column in numeric_cols + categorical_cols
                    if any(pattern in column for pattern in consolidation.FORBIDDEN_FEATURE_PATTERNS)
                ]
                if forbidden:
                    raise RuntimeError(f"forbidden probability features selected: {forbidden}")
                fitted, reason = expanded.fit_with_columns(model, train_df, label_col, config, numeric_cols, categorical_cols, missing)
                if fitted is None:
                    raise RuntimeError(str(reason))
                raw_valid = small.predict_with_fitted_model(fitted, valid_df)
                raw_test = small.predict_with_fitted_model(fitted, test_df)
                for method in ["platt", "isotonic"]:
                    calibrator = fit_calibrator(method, raw_valid, valid_df[label_col].astype(int).to_numpy())
                    calibrated_test = apply_calibrator(method, calibrator, raw_test)
                    for version, probs in [("raw", raw_test), ("calibrated", calibrated_test)]:
                        scored = scored_with_probability(test_df, int(horizon), probs, version)
                        rows, cutoff_df = metric_rows_for_version(
                            scored,
                            model=model,
                            feature_set=feature_set,
                            horizon=int(horizon),
                            calibration_method=method,
                            probability_version=version,
                        )
                        metric_frames.append(pd.DataFrame(rows))
                        cutoff_frames.append(cutoff_df)
                        bin_frames.append(
                            calibration_bins(
                                scored,
                                model=model,
                                feature_set=feature_set,
                                horizon=int(horizon),
                                calibration_method=method,
                                probability_version=version,
                            )
                        )
            except Exception as exc:
                failures.append({"model": model, "feature_set": feature_set, "horizon": horizon, "failure": repr(exc)})
    metrics = pd.concat(metric_frames, ignore_index=True) if metric_frames else pd.DataFrame()
    before_after, by_horizon, topk = before_after_rows(metrics) if not metrics.empty else (pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    period = before_after[before_after["aggregation_method"].isin(["raw_overall", "macro_by_cutoff", "early_mid_late"])].copy()
    bins = pd.concat(bin_frames, ignore_index=True) if bin_frames else pd.DataFrame()
    status = method_status(before_after) if not before_after.empty else pd.DataFrame()
    if not status.empty:
        before_after = before_after.merge(status, on=["model", "feature_set", "horizon", "calibration_method"], how="left")
        by_horizon = by_horizon.merge(status, on=["model", "feature_set", "horizon", "calibration_method"], how="left")
    before_after.to_csv(OUTPUT_DIR / "calibration_metrics_before_after.csv", index=False, encoding="utf-8-sig")
    by_horizon.to_csv(OUTPUT_DIR / "calibration_metrics_by_horizon.csv", index=False, encoding="utf-8-sig")
    period.to_csv(OUTPUT_DIR / "calibration_metrics_by_period.csv", index=False, encoding="utf-8-sig")
    bins.to_csv(OUTPUT_DIR / "calibration_bins_before_after.csv", index=False, encoding="utf-8-sig")
    topk.to_csv(OUTPUT_DIR / "calibration_topk_stability.csv", index=False, encoding="utf-8-sig")
    failure_df = pd.DataFrame(failures, columns=["model", "feature_set", "horizon", "failure"])
    failure_df.to_csv(OUTPUT_DIR / "calibration_failure_report.csv", index=False, encoding="utf-8-sig")
    write_summary(before_after, by_horizon, failures)


def write_summary(before_after: pd.DataFrame, by_horizon: pd.DataFrame, failures: list[dict[str, Any]]) -> None:
    macro = before_after[before_after["aggregation_method"].eq("macro_by_cutoff")].copy() if not before_after.empty else pd.DataFrame()
    best = (
        macro.sort_values(["brier_score_after", "log_loss_after", "ece_after", "auc_after", "pr_auc_after"], ascending=[True, True, True, False, False])
        .head(10)
        .copy()
    )
    lines = [
        "# Calibration Experiment v1 Summary",
        "",
        "This is a lightweight calibration experiment for churn_probability_H only. It is not a business ranking model.",
        "",
        "## Split",
        "- model_train: 2020-01 ~ 2021-12",
        "- calibration_valid: 2022-01 ~ 2022-12",
        "- purge: 2023",
        "- final_test: 2024-01 ~ 2024-12",
        "- Calibrators are fit only on 2022 validation cutoffs, never on 2024 test.",
        "",
        "## Candidates",
        "- logistic_regression + base_recency_frequency_only",
        "- xgboost_small + base_recency_frequency_only",
        "- xgboost_small + base_plus_interval_features",
        "- catboost_small + base_recency_frequency_only",
        "",
        "## Best Calibrated Rows By Probability Metrics",
        markdown_table(best) if not best.empty else "No calibrated metrics generated.",
        "",
        "## Selection Rules",
        "- Keep Platt/isotonic only when ECE and Brier improve and LogLoss does not worsen.",
        "- If isotonic lowers ECE but LogLoss clearly worsens, mark overfit_risk.",
        "- AUC/PR_AUC should be preserved; TopK changes are stability diagnostics only.",
        "- TopK is computed cutoff-aware and is not used to choose the probability calibrator.",
        "- value_at_risk and business_priority_score are not inputs or selection criteria.",
        "",
        "## Failures",
        markdown_table(pd.DataFrame(failures)) if failures else "No calibration failures.",
    ]
    write_text(OUTPUT_DIR / "calibration_experiment_summary.md", "\n".join(lines))


def main() -> int:
    run_calibration_v1()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
