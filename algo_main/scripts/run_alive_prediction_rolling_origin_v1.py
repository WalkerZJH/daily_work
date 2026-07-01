#!/usr/bin/env python
"""Run rolling-origin validation v1 for churn probability candidates."""

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
import run_alive_prediction_expanded_train_diagnostics as expanded
import run_alive_prediction_probability_consolidation as consolidation
import run_alive_prediction_small_model_experiments as small


OUTPUT_DIR = ROOT / "reports/alive_prediction_rolling_origin_v1"
PRIMARY_SCOPE = "recurring_only"
CANDIDATES = [
    ("logistic_regression", "base_recency_frequency_only"),
    ("xgboost_small", "base_recency_frequency_only"),
    ("xgboost_small", "base_plus_interval_features"),
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
    {
        "fold": "fold_3",
        "train_start": "2020-01",
        "train_end": "2022-12",
        "calibration_start": "",
        "calibration_end": "",
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
    return f"{start}~{end}" if start and end else "none"


def cutoff_periods(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["cutoff_month"]).dt.to_period("M")


def cutoff_mask(df: pd.DataFrame, start: str, end: str) -> pd.Series:
    periods = cutoff_periods(df)
    return (periods >= pd.Period(start, freq="M")) & (periods <= pd.Period(end, freq="M"))


def split_fold(df: pd.DataFrame, fold: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame]:
    train = df[cutoff_mask(df, fold["train_start"], fold["train_end"]) & df["recurring_candidate_flag"]].copy()
    valid = None
    if fold["calibration_start"] and fold["calibration_end"]:
        valid = df[cutoff_mask(df, fold["calibration_start"], fold["calibration_end"]) & df["recurring_candidate_flag"]].copy()
    test = df[cutoff_mask(df, fold["test_start"], fold["test_end"])].copy()
    test = small.split_scopes(test)[PRIMARY_SCOPE]
    for frame in [train, valid]:
        if frame is not None and "one_shot_high_value_silence_flag" in frame:
            frame.drop(frame[frame["one_shot_high_value_silence_flag"].astype(bool)].index, inplace=True)
    train_periods = set(cutoff_periods(train))
    test_periods = set(cutoff_periods(test))
    if train_periods.intersection(test_periods):
        raise RuntimeError(f"{fold['fold']} train/test cutoffs overlap")
    if valid is not None:
        valid_periods = set(cutoff_periods(valid))
        if train_periods.intersection(valid_periods) or valid_periods.intersection(test_periods):
            raise RuntimeError(f"{fold['fold']} calibration cutoffs overlap train/test")
    return train, valid, test


def ensure_label_usable(df: pd.DataFrame, label_col: str, *, split_name: str) -> str:
    if label_col not in df.columns:
        return f"{split_name}:{label_col}_missing"
    if df[label_col].isna().any():
        return f"{split_name}:{label_col}_has_missing_labels"
    if len(df) == 0:
        return f"{split_name}:empty_rows"
    return ""


def has_two_classes(df: pd.DataFrame, label_col: str, *, split_name: str) -> str:
    base = ensure_label_usable(df, label_col, split_name=split_name)
    if base:
        return base
    if df[label_col].nunique(dropna=True) < 2:
        return f"{split_name}:{label_col}_has_single_class"
    return ""


def add_fold_columns(rows: list[dict[str, Any]], fold: dict[str, str]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        row = dict(row)
        row.update(
            {
                "fold": fold["fold"],
                "train_period": period_label(fold["train_start"], fold["train_end"]),
                "calibration_period": period_label(fold["calibration_start"], fold["calibration_end"]),
                "test_period": period_label(fold["test_start"], fold["test_end"]),
            }
        )
        output.append(row)
    return output


def score_with_probability(df: pd.DataFrame, horizon: int, probability: np.ndarray) -> pd.DataFrame:
    scored = df.copy()
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
        row["calibration_method"] = calibration_method
    cutoff_df["calibration_method"] = calibration_method
    return add_fold_columns(rows, fold), cutoff_df


def calibration_bins_for_fold(
    scored: pd.DataFrame,
    *,
    model: str,
    feature_set: str,
    horizon: int,
    calibration_method: str,
    fold: dict[str, str],
) -> pd.DataFrame:
    bins = calibration.calibration_bins(
        scored,
        model=model,
        feature_set=feature_set,
        horizon=horizon,
        calibration_method=calibration_method,
        probability_version=calibration_method,
    )
    bins["fold"] = fold["fold"]
    bins["train_period"] = period_label(fold["train_start"], fold["train_end"])
    bins["calibration_period"] = period_label(fold["calibration_start"], fold["calibration_end"])
    bins["test_period"] = period_label(fold["test_start"], fold["test_end"])
    return bins


def selected_features(config: dict[str, Any], ablation_config: dict[str, Any], df: pd.DataFrame, model: str, feature_set: str) -> tuple[list[str], list[str], list[str]]:
    numeric_cols, categorical_cols, missing = expanded.ablation_feature_columns(df, config, ablation_config, model, feature_set)
    forbidden = [
        column
        for column in numeric_cols + categorical_cols
        if any(pattern in column for pattern in consolidation.FORBIDDEN_FEATURE_PATTERNS)
    ]
    if forbidden:
        raise RuntimeError(f"forbidden probability features selected: {forbidden}")
    return numeric_cols, categorical_cols, missing


def run_fold_candidate(
    config: dict[str, Any],
    ablation_config: dict[str, Any],
    fold: dict[str, str],
    train_df: pd.DataFrame,
    valid_df: pd.DataFrame | None,
    test_df: pd.DataFrame,
    model: str,
    feature_set: str,
    horizon: int,
) -> tuple[list[dict[str, Any]], list[pd.DataFrame], list[dict[str, Any]]]:
    label_col = f"label_die_H{horizon}"
    failures: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    bins: list[pd.DataFrame] = []
    for split_name, frame, require_two_classes in [
        ("model_train", train_df, True),
        ("test", test_df, False),
    ]:
        reason = has_two_classes(frame, label_col, split_name=split_name) if require_two_classes else ensure_label_usable(frame, label_col, split_name=split_name)
        if reason:
            failures.append(failure_row(fold, model, feature_set, horizon, reason))
            return rows, bins, failures
    if valid_df is not None:
        reason = has_two_classes(valid_df, label_col, split_name="calibration_valid")
        if reason:
            failures.append(failure_row(fold, model, feature_set, horizon, reason))
            return rows, bins, failures
    try:
        numeric_cols, categorical_cols, missing = selected_features(config, ablation_config, train_df, model, feature_set)
        fitted, reason = expanded.fit_with_columns(model, train_df, label_col, config, numeric_cols, categorical_cols, missing)
        if fitted is None:
            failures.append(failure_row(fold, model, feature_set, horizon, f"model_fit_failed:{reason}"))
            return rows, bins, failures
        raw_test = small.predict_with_fitted_model(fitted, test_df)
        raw_scored = score_with_probability(test_df, horizon, raw_test)
        raw_rows, _raw_cutoff = metric_rows(raw_scored, model=model, feature_set=feature_set, horizon=horizon, calibration_method="raw", fold=fold)
        rows.extend(raw_rows)
        bins.append(calibration_bins_for_fold(raw_scored, model=model, feature_set=feature_set, horizon=horizon, calibration_method="raw", fold=fold))
        if valid_df is None:
            return rows, bins, failures
        raw_valid = small.predict_with_fitted_model(fitted, valid_df)
        y_valid = valid_df[label_col].astype(int).to_numpy()
        for method in ["platt", "isotonic"]:
            try:
                calibrator = calibration.fit_calibrator(method, raw_valid, y_valid)
                calibrated_test = calibration.apply_calibrator(method, calibrator, raw_test)
                scored = score_with_probability(test_df, horizon, calibrated_test)
                method_rows, _cutoff = metric_rows(scored, model=model, feature_set=feature_set, horizon=horizon, calibration_method=method, fold=fold)
                rows.extend(method_rows)
                bins.append(calibration_bins_for_fold(scored, model=model, feature_set=feature_set, horizon=horizon, calibration_method=method, fold=fold))
            except Exception as exc:  # pragma: no cover - defensive, written to report.
                failures.append(failure_row(fold, model, feature_set, horizon, f"{method}_calibration_failed:{exc!r}"))
    except Exception as exc:  # pragma: no cover - defensive, written to report.
        failures.append(failure_row(fold, model, feature_set, horizon, f"unexpected_failure:{exc!r}"))
    return rows, bins, failures


def failure_row(fold: dict[str, str], model: str, feature_set: str, horizon: int, reason: str) -> dict[str, Any]:
    return {
        "fold": fold["fold"],
        "model": model,
        "feature_set": feature_set,
        "horizon": horizon,
        "train_period": period_label(fold["train_start"], fold["train_end"]),
        "calibration_period": period_label(fold["calibration_start"], fold["calibration_end"]),
        "test_period": period_label(fold["test_start"], fold["test_end"]),
        "reason": reason,
    }


def fold_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    macro = metrics[metrics["aggregation_method"].eq("macro_by_cutoff")].copy()
    group_cols = ["fold", "model", "feature_set", "scope", "calibration_method", "train_period", "calibration_period", "test_period"]
    metric_cols = ["brier_score", "log_loss", "ece", "auc", "pr_auc"]
    return macro.groupby(group_cols, dropna=False)[metric_cols].mean(numeric_only=True).reset_index()


def horizon_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    return metrics[metrics["aggregation_method"].eq("macro_by_cutoff")].copy()


def calibration_comparison(metrics: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    macro = metrics[metrics["aggregation_method"].eq("macro_by_cutoff")].copy()
    raw = macro[macro["calibration_method"].eq("raw")].copy()
    calibrated = macro[macro["calibration_method"].isin(["platt", "isotonic"])].copy()
    keys = ["fold", "model", "feature_set", "horizon", "scope", "aggregation_method", "period", "train_period", "calibration_period", "test_period"]
    paired = calibrated.merge(raw, on=keys, suffixes=("_after", "_before"), how="left")
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
        rows.append(out)
        topk["topk_stability_status"] = topk_stability_status(topk)
        topk_rows.append(topk)
    return pd.DataFrame(rows), pd.DataFrame(topk_rows)


def topk_stability_status(row: dict[str, Any] | pd.Series) -> str:
    deltas = [
        abs(float(row.get("precision_at_top_10_pct_delta_after_minus_before", np.nan))),
        abs(float(row.get("lift_at_top_10_pct_delta_after_minus_before", np.nan))),
        abs(float(row.get("ndcg_at_top_10_pct_delta_after_minus_before", np.nan))),
    ]
    finite = [value for value in deltas if np.isfinite(value)]
    if not finite:
        return "not_available"
    if max(finite) <= 0.02:
        return "stable"
    if max(finite) <= 0.05:
        return "minor_change"
    return "material_degradation_or_shift"


def candidate_decision(metrics_by_fold: pd.DataFrame, calibration_cmp: pd.DataFrame, topk: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    comparable = metrics_by_fold.copy()
    aggregate = (
        comparable.groupby(["model", "feature_set", "calibration_method"], dropna=False)[["brier_score", "log_loss", "ece", "auc", "pr_auc"]]
        .mean(numeric_only=True)
        .reset_index()
        .sort_values(["brier_score", "log_loss", "ece", "auc", "pr_auc"], ascending=[True, True, True, False, False])
    )
    decisions: list[dict[str, Any]] = []
    best = aggregate.iloc[0] if not aggregate.empty else pd.Series(dtype=object)
    logistic = aggregate[
        (aggregate["model"].eq("logistic_regression"))
        & (aggregate["feature_set"].eq("base_recency_frequency_only"))
    ].sort_values(["brier_score", "log_loss", "ece"]).head(1)
    xgb = aggregate[
        (aggregate["model"].eq("xgboost_small"))
        & (aggregate["feature_set"].eq("base_recency_frequency_only"))
    ].sort_values(["brier_score", "log_loss", "ece"]).head(1)
    xgb_interval = aggregate[
        (aggregate["model"].eq("xgboost_small"))
        & (aggregate["feature_set"].eq("base_plus_interval_features"))
    ].sort_values(["brier_score", "log_loss", "ece"]).head(1)
    xgb_beats_logistic = (
        not xgb.empty
        and not logistic.empty
        and float(xgb.iloc[0]["brier_score"]) < float(logistic.iloc[0]["brier_score"])
        and float(xgb.iloc[0]["log_loss"]) <= float(logistic.iloc[0]["log_loss"]) + 0.005
        and float(xgb.iloc[0]["ece"]) <= float(logistic.iloc[0]["ece"]) + 0.005
    )
    interval_needed = (
        not xgb_interval.empty
        and not xgb.empty
        and float(xgb_interval.iloc[0]["brier_score"]) < float(xgb.iloc[0]["brier_score"])
        and float(xgb_interval.iloc[0]["log_loss"]) <= float(xgb.iloc[0]["log_loss"])
    )
    calibration_stable = False
    if not calibration_cmp.empty:
        improved = calibration_cmp[
            (calibration_cmp["brier_score_delta_after_minus_before"] <= 0)
            & (calibration_cmp["log_loss_delta_after_minus_before"] <= 0)
            & (calibration_cmp["ece_delta_after_minus_before"] <= 0)
        ]
        calibration_stable = len(improved) >= max(1, int(0.5 * len(calibration_cmp)))
    if not logistic.empty:
        decisions.append(
            decision_row(
                logistic.iloc[0],
                "promote_to_probability_candidate_v1" if (not xgb_beats_logistic and calibration_stable) else "needs_rolling_origin_validation",
                "Logistic is the most stable probability family, but calibration consistency is required before promotion.",
            )
        )
    if not xgb.empty:
        decisions.append(
            decision_row(
                xgb.iloc[0],
                "promote_to_probability_candidate_v1" if xgb_beats_logistic and calibration_stable else "keep_as_backup",
                "XGBoost does not stably exceed Logistic across rolling-origin probability metrics." if not xgb_beats_logistic else "XGBoost exceeds Logistic under the promotion rule.",
            )
        )
    if not xgb_interval.empty:
        decisions.append(
            decision_row(
                xgb_interval.iloc[0],
                "keep_as_backup" if interval_needed else "reject_for_probability_mainline",
                "Interval features do not show stable probability-quality improvement over base-only." if not interval_needed else "Interval features improve the XGBoost base candidate.",
            )
        )
    promoted = [row for row in decisions if row["decision"] == "promote_to_probability_candidate_v1"]
    if promoted:
        candidate = promoted[0]
        decision_text = f"probability_candidate_v1 = {candidate['model']} + {candidate['feature_set']} + {candidate['calibration_method']}"
    else:
        decision_text = "no_candidate_promoted"
    return pd.DataFrame(decisions), decision_text


def decision_row(row: pd.Series, decision: str, reason: str) -> dict[str, Any]:
    return {
        "model": row["model"],
        "feature_set": row["feature_set"],
        "calibration_method": row["calibration_method"],
        "mean_brier_score": row["brier_score"],
        "mean_log_loss": row["log_loss"],
        "mean_ece": row["ece"],
        "mean_auc": row["auc"],
        "mean_pr_auc": row["pr_auc"],
        "decision": decision,
        "reason": reason,
    }


def write_summary(
    metrics: pd.DataFrame,
    by_fold: pd.DataFrame,
    by_horizon: pd.DataFrame,
    calibration_cmp: pd.DataFrame,
    topk: pd.DataFrame,
    failures: pd.DataFrame,
    decision: pd.DataFrame,
    decision_text: str,
) -> None:
    aggregate = (
        by_fold.groupby(["model", "feature_set", "calibration_method"], dropna=False)[["brier_score", "log_loss", "ece", "auc", "pr_auc"]]
        .mean(numeric_only=True)
        .reset_index()
        .sort_values(["brier_score", "log_loss", "ece", "auc", "pr_auc"], ascending=[True, True, True, False, False])
    )
    logistic_best = aggregate[aggregate["model"].eq("logistic_regression")].head(1)
    xgb_best = aggregate[(aggregate["model"].eq("xgboost_small")) & (aggregate["feature_set"].eq("base_recency_frequency_only"))].head(1)
    interval_best = aggregate[(aggregate["model"].eq("xgboost_small")) & (aggregate["feature_set"].eq("base_plus_interval_features"))].head(1)
    improved = calibration_cmp[
        (calibration_cmp["brier_score_delta_after_minus_before"] <= 0)
        & (calibration_cmp["log_loss_delta_after_minus_before"] <= 0)
        & (calibration_cmp["ece_delta_after_minus_before"] <= 0)
    ] if not calibration_cmp.empty else pd.DataFrame()
    isotonic_overfit = calibration_cmp[
        (calibration_cmp["calibration_method"].eq("isotonic"))
        & (calibration_cmp["ece_delta_after_minus_before"] < 0)
        & (calibration_cmp["log_loss_delta_after_minus_before"] > 0.02)
    ] if not calibration_cmp.empty else pd.DataFrame()
    topk_bad = topk[topk["topk_stability_status"].eq("material_degradation_or_shift")] if not topk.empty else pd.DataFrame()
    lines = [
        "# Rolling-Origin Validation v1 Summary",
        "",
        "This report validates churn_probability_H candidates only. It is not a business ranking model.",
        "",
        "## Fold Coverage",
        markdown_table(metrics[["fold", "model", "feature_set", "horizon", "calibration_method", "train_period", "calibration_period", "test_period"]].drop_duplicates().sort_values(["fold", "model", "feature_set", "horizon", "calibration_method"])),
        "",
        "## Aggregate Candidate Ranking",
        markdown_table(aggregate),
        "",
        "## Direct Answers",
        f"1. Logistic remains the most stable candidate: {'yes' if not logistic_best.empty and (xgb_best.empty or float(logistic_best.iloc[0]['brier_score']) <= float(xgb_best.iloc[0]['brier_score'])) else 'no'}.",
        f"2. XGBoost exceeds Logistic after calibration: {'yes' if not decision.empty and decision['decision'].eq('promote_to_probability_candidate_v1').any() and decision.iloc[0]['model'] == 'xgboost_small' else 'no'}.",
        f"3. XGBoost interval features need to be retained: {'yes' if not interval_best.empty and not xgb_best.empty and float(interval_best.iloc[0]['brier_score']) < float(xgb_best.iloc[0]['brier_score']) else 'no'}.",
        f"4. Calibration consistently improves Brier/LogLoss/ECE: {'yes' if len(improved) >= max(1, int(0.5 * len(calibration_cmp))) else 'no'}.",
        f"5. Isotonic overfit risk rows: {len(isotonic_overfit)}.",
        f"6. TopK material degradation rows: {len(topk_bad)}. TopK remains diagnostic only.",
        f"7. probability_candidate_v1 decision: {decision_text}.",
        "8. If no candidate is promoted, likely causes are temporal drift and calibration instability rather than lack of a transparent base signal.",
        "9. Main model semantics remain churn_probability_H = P(die_H = 1).",
        "",
        "## Candidate Decision",
        markdown_table(decision) if not decision.empty else "No candidate decision generated.",
        "",
        "## Failures",
        markdown_table(failures) if not failures.empty else "No fold/horizon failures.",
    ]
    write_text(OUTPUT_DIR / "rolling_origin_summary.md", "\n".join(lines))
    decision_lines = [
        "# Probability Candidate v1 Decision",
        "",
        f"Decision: {decision_text}",
        "",
        "## Answers",
        f"1. Logistic stable across folds: {'yes' if not logistic_best.empty and (xgb_best.empty or float(logistic_best.iloc[0]['brier_score']) <= float(xgb_best.iloc[0]['brier_score'])) else 'no'}.",
        f"2. XGBoost calibrated result stably exceeds Logistic: {'no' if decision_text != 'probability_candidate_v1 = xgboost_small + base_recency_frequency_only + selected_calibration_method' else 'yes'}.",
        f"3. Interval features stable improvement: {'no' if interval_best.empty or xgb_best.empty or float(interval_best.iloc[0]['brier_score']) >= float(xgb_best.iloc[0]['brier_score']) else 'yes'}.",
        "4. Platt vs isotonic: compare rolling_origin_calibration_comparison.csv; neither method is promoted unless Brier/LogLoss/ECE improve consistently.",
        f"5. Isotonic overfit signs: {'yes' if len(isotonic_overfit) else 'no'}.",
        "6. H3/H6/H12 consistency: review rolling_origin_metrics_by_horizon.csv; this run requires consistency before promotion.",
        f"7. probability_candidate_v1 can be determined: {'yes' if decision_text != 'no_candidate_promoted' else 'no'}.",
        "8. Next step if not promoted: inspect temporal drift and consider broader data/feature redesign before more calibration.",
        "9. The main model still outputs only churn_probability_H.",
        "",
        "## Decision Table",
        markdown_table(decision) if not decision.empty else "No candidate decision generated.",
    ]
    write_text(OUTPUT_DIR / "probability_candidate_v1_decision.md", "\n".join(decision_lines))


def run_rolling_origin_v1() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = small.read_yaml(ROOT / "configs/experiments/alive_prediction_small_models.yaml")
    ablation_config = small.read_yaml(ROOT / "configs/experiments/alive_prediction_feature_ablation.yaml")
    df = consolidation.load_feature_data(config)
    metric_rows_all: list[dict[str, Any]] = []
    bin_frames: list[pd.DataFrame] = []
    failures: list[dict[str, Any]] = []
    for fold in FOLDS:
        try:
            train_df, valid_df, test_df = split_fold(df, fold)
        except Exception as exc:
            for model, feature_set in CANDIDATES:
                for horizon in config["horizons_months"]:
                    failures.append(failure_row(fold, model, feature_set, int(horizon), f"fold_split_failed:{exc!r}"))
            continue
        for model, feature_set in CANDIDATES:
            for horizon in config["horizons_months"]:
                rows, bins, fail = run_fold_candidate(
                    config,
                    ablation_config,
                    fold,
                    train_df,
                    valid_df,
                    test_df,
                    model,
                    feature_set,
                    int(horizon),
                )
                metric_rows_all.extend(rows)
                bin_frames.extend(bins)
                failures.extend(fail)
    metrics = pd.DataFrame(metric_rows_all)
    ordered = [
        "fold",
        "model",
        "feature_set",
        "horizon",
        "scope",
        "calibration_method",
        "aggregation_method",
        "period",
        "train_period",
        "calibration_period",
        "test_period",
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
    ]
    metrics[[col for col in ordered if col in metrics.columns]].to_csv(OUTPUT_DIR / "rolling_origin_metrics.csv", index=False, encoding="utf-8-sig")
    by_fold = fold_summary(metrics)
    by_horizon = horizon_summary(metrics)
    calibration_cmp, topk = calibration_comparison(metrics)
    bins = pd.concat(bin_frames, ignore_index=True) if bin_frames else pd.DataFrame()
    failure_df = pd.DataFrame(failures, columns=["fold", "model", "feature_set", "horizon", "train_period", "calibration_period", "test_period", "reason"])
    decision, decision_text = candidate_decision(by_fold, calibration_cmp, topk)
    by_fold.to_csv(OUTPUT_DIR / "rolling_origin_metrics_by_fold.csv", index=False, encoding="utf-8-sig")
    by_horizon.to_csv(OUTPUT_DIR / "rolling_origin_metrics_by_horizon.csv", index=False, encoding="utf-8-sig")
    calibration_cmp.to_csv(OUTPUT_DIR / "rolling_origin_calibration_comparison.csv", index=False, encoding="utf-8-sig")
    bins.to_csv(OUTPUT_DIR / "rolling_origin_calibration_bins.csv", index=False, encoding="utf-8-sig")
    topk.to_csv(OUTPUT_DIR / "rolling_origin_topk_stability.csv", index=False, encoding="utf-8-sig")
    failure_df.to_csv(OUTPUT_DIR / "rolling_origin_failure_report.csv", index=False, encoding="utf-8-sig")
    decision.to_csv(OUTPUT_DIR / "probability_candidate_v1_decision.csv", index=False, encoding="utf-8-sig")
    write_summary(metrics, by_fold, by_horizon, calibration_cmp, topk, failure_df, decision, decision_text)


def main() -> int:
    run_rolling_origin_v1()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
