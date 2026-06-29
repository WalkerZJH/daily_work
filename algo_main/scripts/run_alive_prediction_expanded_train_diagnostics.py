#!/usr/bin/env python
"""Run expanded alive prediction diagnostics without saving model artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import traceback
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_alive_prediction_small_model_experiments as small


TOPK = "top_10_pct"
PRIMARY_SCOPE = "recurring_only"
KEY_COLS = ["manufacturer_code", "hospital_code", "drug_group"]


def entity_count(df: pd.DataFrame) -> int:
    return int(df[KEY_COLS].drop_duplicates().shape[0]) if len(df) else 0


def dataframe_to_markdown(df: pd.DataFrame, *, index: bool = False) -> str:
    return small.dataframe_to_markdown(df, index=index)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def split_train_test(df: pd.DataFrame, split: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    small.assert_temporal_split_valid(split)
    train = df[small.cutoff_mask(df, split["train_cutoff_start"], split["train_cutoff_end"]) & df["recurring_candidate_flag"]].copy()
    if "one_shot_high_value_silence_flag" in train:
        train = train[~train["one_shot_high_value_silence_flag"].astype(bool)].copy()
    test = df[small.cutoff_mask(df, split["test_cutoff_start"], split["test_cutoff_end"])].copy()
    train_periods = set(pd.to_datetime(train["cutoff_month"]).dt.to_period("M"))
    test_periods = set(pd.to_datetime(test["cutoff_month"]).dt.to_period("M"))
    if train_periods.intersection(test_periods):
        raise RuntimeError("Train and test cutoffs overlap")
    return train, test


def score_frame(fitted: dict[str, Any], df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    scored = df.copy()
    scored[f"churn_probability_H{horizon}"] = small.predict_with_fitted_model(fitted, scored)
    return scored


def evaluate_scored(
    scored: pd.DataFrame,
    *,
    config: dict[str, Any],
    model_name: str,
    horizon: int,
    scope: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    label_col = f"label_die_H{horizon}"
    prob_col = f"churn_probability_H{horizon}"
    value_col = config["value_at_risk"]["amount_columns"][f"H{horizon}"]
    prob, ranking, value, bins = small.evaluate_predictions(
        scored,
        label_col,
        prob_col,
        value_col,
        horizon,
        model_name,
        scope,
        config,
    )
    _cutoff, _manufacturer, scope_metrics = small.aggregate_metric_tables(ranking, value, prob)
    top = scope_metrics[scope_metrics["k"].astype(str) == TOPK].iloc[0].to_dict() if not scope_metrics.empty else {}
    summary = {
        "model": model_name,
        "horizon": horizon,
        "scope": scope,
        "row_count": int(len(scored)),
        "entity_count": entity_count(scored),
        "positive_rate": float(scored[label_col].mean()) if len(scored) else np.nan,
        "brier_score": top.get("brier_score", prob.iloc[0].get("brier_score", np.nan) if not prob.empty else np.nan),
        "log_loss": top.get("log_loss", prob.iloc[0].get("log_loss", np.nan) if not prob.empty else np.nan),
        "ece": top.get("ece", prob.iloc[0].get("ece", np.nan) if not prob.empty else np.nan),
        "auc": top.get("auc", prob.iloc[0].get("auc", np.nan) if not prob.empty else np.nan),
        "pr_auc": top.get("pr_auc", prob.iloc[0].get("pr_auc", np.nan) if not prob.empty else np.nan),
        "precision_at_top_10_pct": top.get("precision_at_k", np.nan),
        "ndcg_at_top_10_pct": top.get("ndcg_at_k", np.nan),
        "lift_at_top_10_pct": top.get("lift_at_k", np.nan),
        "value_weighted_ndcg_at_top_10_pct": top.get("value_weighted_ndcg_at_k", np.nan),
        "captured_value_at_top_10_pct": top.get("captured_value_at_k", np.nan),
    }
    return prob, ranking, value, bins, summary


def diagnosis_for_train_test(row: pd.Series) -> str:
    diagnoses: list[str] = []
    if pd.notna(row.get("train_auc")) and pd.notna(row.get("test_auc")):
        if row["train_auc"] < 0.60 and row["test_auc"] < 0.60:
            diagnoses.append("possible_underfit_or_weak_features")
        if row["train_auc"] >= 0.75 and (row["train_auc"] - row["test_auc"]) >= 0.15:
            diagnoses.append("possible_overfit_or_temporal_shift")
    if pd.notna(row.get("train_ndcg_at_top_10_pct")) and row["train_ndcg_at_top_10_pct"] >= 0.50:
        if (pd.notna(row.get("test_log_loss")) and row["test_log_loss"] > 0.70) or (
            pd.notna(row.get("test_brier_score")) and row["test_brier_score"] > 0.25
        ):
            diagnoses.append("ranking_signal_exists_but_probability_needs_calibration")
    if pd.notna(row.get("previous_2022_only_auc")) and pd.notna(row.get("test_auc")):
        if row["test_auc"] > row["previous_2022_only_auc"] + 0.01:
            diagnoses.append("previous_12_month_train_was_too_small")
    return ";".join(diagnoses) if diagnoses else "no_clear_train_test_pathology"


def train_test_table(rows: list[dict[str, Any]], previous_scope_metrics: pd.DataFrame | None) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    train = frame[frame["dataset"] == "train"].copy()
    test = frame[frame["dataset"] == "test"].copy()
    merged = train.merge(test, on=["model", "horizon", "scope"], suffixes=("_train", "_test"), how="outer")
    rename = {
        "brier_score_train": "train_brier_score",
        "brier_score_test": "test_brier_score",
        "log_loss_train": "train_log_loss",
        "log_loss_test": "test_log_loss",
        "auc_train": "train_auc",
        "auc_test": "test_auc",
        "pr_auc_train": "train_pr_auc",
        "pr_auc_test": "test_pr_auc",
        "precision_at_top_10_pct_train": "train_precision_at_top_10_pct",
        "precision_at_top_10_pct_test": "test_precision_at_top_10_pct",
        "ndcg_at_top_10_pct_train": "train_ndcg_at_top_10_pct",
        "ndcg_at_top_10_pct_test": "test_ndcg_at_top_10_pct",
        "lift_at_top_10_pct_train": "train_lift_at_top_10_pct",
        "lift_at_top_10_pct_test": "test_lift_at_top_10_pct",
    }
    merged = merged.rename(columns=rename)
    if previous_scope_metrics is not None and not previous_scope_metrics.empty:
        prev = previous_scope_metrics[
            (previous_scope_metrics["scope"] == PRIMARY_SCOPE) & (previous_scope_metrics["k"].astype(str) == TOPK)
        ][["model", "horizon", "auc"]].rename(columns={"auc": "previous_2022_only_auc"})
        merged = merged.merge(prev, on=["model", "horizon"], how="left")
    merged["diagnosis"] = merged.apply(diagnosis_for_train_test, axis=1)
    keep = [
        "model",
        "horizon",
        "scope",
        "train_brier_score",
        "test_brier_score",
        "train_log_loss",
        "test_log_loss",
        "train_auc",
        "test_auc",
        "train_pr_auc",
        "test_pr_auc",
        "train_precision_at_top_10_pct",
        "test_precision_at_top_10_pct",
        "train_ndcg_at_top_10_pct",
        "test_ndcg_at_top_10_pct",
        "train_lift_at_top_10_pct",
        "test_lift_at_top_10_pct",
        "diagnosis",
    ]
    return merged[[column for column in keep if column in merged.columns]]


def write_train_test_reports(output_dir: Path, metrics: pd.DataFrame) -> None:
    metrics.to_csv(output_dir / "train_vs_test_metrics.csv", index=False, encoding="utf-8-sig")
    recurring = metrics[metrics["scope"] == PRIMARY_SCOPE] if not metrics.empty else pd.DataFrame()
    write_text(
        output_dir / "train_vs_test_diagnostics.md",
        "\n".join(
            [
                "# Train vs Test Diagnostics",
                "",
                "This report follows reports/alive_prediction_temporal_drift metric guardrails. Model selection should use recurring_only and cutoff-aware summaries.",
                "",
                dataframe_to_markdown(recurring, index=False) if not recurring.empty else "No recurring_only train/test metrics were generated.",
                "",
                "one_shot_only rows, if present, are diagnostic only and must not drive model selection.",
            ]
        ),
    )


def run_expanded_experiment(config: dict[str, Any], df: pd.DataFrame, output_dir: Path, model_names: list[str]) -> pd.DataFrame:
    split = dict(config["time_splits"]["expanded_train_2020_2022"])
    trainability = small.build_trainability_report(df, config, split, list(config["horizons_months"]))
    all_probability: list[pd.DataFrame] = []
    all_ranking: list[pd.DataFrame] = []
    all_value: list[pd.DataFrame] = []
    all_bins: list[pd.DataFrame] = []
    all_coverage: list[pd.DataFrame] = []
    model_status: list[dict[str, Any]] = []
    tt_rows: list[dict[str, Any]] = []
    train_df, test_df = split_train_test(df, split)
    for horizon in config["horizons_months"]:
        label_col = f"label_die_H{horizon}"
        gate = trainability[trainability["horizon"] == horizon].iloc[0]
        if not bool(gate["can_train"]):
            for model_name in model_names:
                model_status.append({"model": model_name, "horizon": horizon, "status": "skipped", "reason": gate["skip_reason"]})
            continue
        for model_name in model_names:
            fitted, reason = small.fit_model_in_memory(model_name, train_df, label_col, config)
            if fitted is None:
                failure = reason if isinstance(reason, dict) else {"status": "skipped", "reason": str(reason), "traceback": ""}
                model_status.append({"model": model_name, "horizon": horizon, "scope": PRIMARY_SCOPE, "train_rows": len(train_df), "eval_rows": 0, **failure})
                continue
            try:
                train_scored = score_frame(fitted, train_df, horizon)
                _p, _r, _v, _b, train_summary = evaluate_scored(train_scored, config=config, model_name=model_name, horizon=horizon, scope=PRIMARY_SCOPE)
                train_summary["dataset"] = "train"
            except Exception:
                train_summary = {"model": model_name, "horizon": horizon, "scope": PRIMARY_SCOPE, "dataset": "train", "diagnostic_error": traceback.format_exc()}
            for scope, scope_df in small.split_scopes(test_df).items():
                status = {"model": model_name, "horizon": horizon, "scope": scope, "train_rows": len(train_df), "eval_rows": len(scope_df)}
                if scope_df.empty or scope_df[label_col].nunique(dropna=False) < 2:
                    status.update({"status": "skipped", "reason": "label_has_single_class_or_empty", "traceback": ""})
                    model_status.append(status)
                    continue
                try:
                    scored = score_frame(fitted, scope_df, horizon)
                    prob, ranking, value, bins, test_summary = evaluate_scored(scored, config=config, model_name=model_name, horizon=horizon, scope=scope)
                    all_probability.append(prob)
                    all_ranking.append(ranking)
                    all_value.append(value)
                    all_bins.append(bins)
                    coverage = small.metric_group_coverage(
                        scored,
                        label_col,
                        horizon,
                        scope,
                        config["metrics"]["ranking_group"],
                        int(config["metrics"].get("min_group_rows_for_topk", 5)),
                    )
                    coverage["model"] = model_name
                    all_coverage.append(coverage)
                    train_for_scope = dict(train_summary)
                    train_for_scope["scope"] = scope
                    tt_rows.append(train_for_scope)
                    test_summary["dataset"] = "test"
                    tt_rows.append(test_summary)
                    status.update({"status": "trained_in_memory", "reason": "", "traceback": ""})
                except Exception:
                    status.update({"status": "model_predict_failed", "reason": "model_predict_failed", "traceback": traceback.format_exc()})
                model_status.append(status)
    probability = pd.concat(all_probability, ignore_index=True) if all_probability else pd.DataFrame()
    ranking = pd.concat(all_ranking, ignore_index=True) if all_ranking else pd.DataFrame()
    value = pd.concat(all_value, ignore_index=True) if all_value else pd.DataFrame()
    bins = pd.concat(all_bins, ignore_index=True) if all_bins else pd.DataFrame()
    coverage = pd.concat(all_coverage, ignore_index=True) if all_coverage else pd.DataFrame()
    ranking_cutoff, ranking_manufacturer, scope_metrics = small.aggregate_metric_tables(ranking, value, probability)
    small.write_reports(output_dir, trainability, coverage, ranking_cutoff, ranking_manufacturer, scope_metrics, bins, model_status, split["purge_gap_note"], config)
    previous_path = Path("reports/alive_prediction_small_models/model_metrics_by_scope.csv")
    previous = pd.read_csv(previous_path) if previous_path.exists() else pd.DataFrame()
    tt = train_test_table(tt_rows, previous)
    write_train_test_reports(output_dir, tt)
    return scope_metrics


def run_window_comparison(config: dict[str, Any], df: pd.DataFrame, output_dir: Path, model_names: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    window_display_names = {
        "train_2022_only": "train_2022_only",
        "train_2021_2022": "train_2021_2022",
        "expanded_train_2020_2022": "train_2020_2022",
    }
    for window_name, display_name in window_display_names.items():
        split = dict(config["time_splits"][window_name])
        trainability = small.build_trainability_report(df, config, split, list(config["horizons_months"]))
        train_df, test_df_all = split_train_test(df, split)
        test_df = small.split_scopes(test_df_all)[PRIMARY_SCOPE]
        for horizon in config["horizons_months"]:
            label_col = f"label_die_H{horizon}"
            gate = trainability[trainability["horizon"] == horizon].iloc[0]
            for model_name in model_names:
                base = {
                    "model": model_name,
                    "horizon": horizon,
                    "train_window_name": display_name,
                    "train_cutoff_start": split["train_cutoff_start"],
                    "train_cutoff_end": split["train_cutoff_end"],
                    "test_cutoff_start": split["test_cutoff_start"],
                    "test_cutoff_end": split["test_cutoff_end"],
                    "train_row_count": int(len(train_df)),
                    "test_row_count": int(len(test_df)),
                    "train_entity_count": entity_count(train_df),
                    "test_entity_count": entity_count(test_df),
                    "train_positive_rate": float(train_df[label_col].mean()) if len(train_df) else np.nan,
                    "test_positive_rate": float(test_df[label_col].mean()) if len(test_df) else np.nan,
                    "status": "skipped" if not bool(gate["can_train"]) else "attempted",
                    "reason": gate["skip_reason"] if not bool(gate["can_train"]) else "",
                }
                if not bool(gate["can_train"]):
                    rows.append(base)
                    continue
                fitted, reason = small.fit_model_in_memory(model_name, train_df, label_col, config)
                if fitted is None:
                    failure = reason if isinstance(reason, dict) else {"status": "skipped", "reason": str(reason)}
                    base.update({"status": failure["status"], "reason": failure["reason"]})
                    rows.append(base)
                    continue
                try:
                    scored = score_frame(fitted, test_df, horizon)
                    _p, _r, _v, _b, summary = evaluate_scored(scored, config=config, model_name=model_name, horizon=horizon, scope=PRIMARY_SCOPE)
                    base.update(summary)
                    base["status"] = "trained_in_memory"
                except Exception:
                    base.update({"status": "model_predict_failed", "reason": traceback.format_exc()})
                rows.append(base)
    out = pd.DataFrame(rows)
    out.to_csv(output_dir / "training_window_comparison.csv", index=False, encoding="utf-8-sig")
    write_text(
        output_dir / "training_window_comparison.md",
        "# Training Window Comparison\n\n"
        "This report follows temporal drift guardrails: compare macro/cutoff-aware ranking and Lift, not raw Precision alone.\n\n"
        + dataframe_to_markdown(out, index=False),
    )
    return out


def ablation_feature_columns(df: pd.DataFrame, config: dict[str, Any], ablation_config: dict[str, Any], model_name: str, ablation: str) -> tuple[list[str], list[str], list[str]]:
    df = small.add_missing_flags(df)
    requested: list[str] = []
    for group in ablation_config["ablations"][ablation]["include_groups"]:
        requested.extend(ablation_config["feature_groups"][group])
    requested = list(dict.fromkeys(requested))
    categorical_all = set(
        config["features"].get("allowed_categorical_columns", [])
        + config["features"].get("low_cardinality_categorical_for_logistic", [])
        + config["features"].get("high_cardinality_categorical", [])
    )
    categorical_allowed = set(config["features"].get("low_cardinality_categorical_for_logistic", []))
    if model_name != "logistic_regression":
        categorical_allowed |= set(config["features"].get("allowed_categorical_columns", []))
        categorical_allowed |= set(config["features"].get("high_cardinality_categorical", []))
    numeric: list[str] = []
    categorical: list[str] = []
    missing: list[str] = []
    for column in requested:
        if column not in df.columns:
            missing.append(column)
        elif small.is_forbidden_column(column, config):
            missing.append(f"{column}:forbidden")
        elif column in categorical_all:
            if column in categorical_allowed:
                categorical.append(column)
            else:
                missing.append(f"{column}:not_used_by_model")
        else:
            numeric.append(column)
    small.assert_no_forbidden_columns(numeric + categorical, config)
    return numeric, categorical, missing


def fit_with_columns(model_name: str, train_df: pd.DataFrame, label_col: str, config: dict[str, Any], numeric_cols: list[str], categorical_cols: list[str], missing: list[str]) -> tuple[dict[str, Any] | None, dict[str, str] | str]:
    train_df = small.add_missing_flags(train_df)
    if model_name == "catboost_small":
        dependency = small.check_optional_dependency("catboost")
        if not dependency["ok"]:
            return None, {"status": "skipped_optional_dependency", "reason": "dependency_not_installed:catboost", "traceback": dependency["traceback"]}
        try:
            CatBoostClassifier = small.import_class(config["models"][model_name]["class_path"])
            train_x = train_df[numeric_cols + categorical_cols].copy()
            medians = {}
            for column in numeric_cols:
                medians[column] = train_x[column].median()
                train_x[column] = train_x[column].fillna(medians[column])
            for column in categorical_cols:
                train_x[column] = train_x[column].astype("string").fillna("__MISSING__")
            params = dict(config["models"][model_name]["params"])
            params["allow_writing_files"] = False
            model = CatBoostClassifier(**params)
            model.fit(train_x, train_df[label_col], cat_features=[train_x.columns.get_loc(c) for c in categorical_cols])
            return {"kind": "catboost", "model": model, "feature_cols": numeric_cols + categorical_cols, "numeric_cols": numeric_cols, "categorical_cols": categorical_cols, "missing_or_reserved_features": missing, "medians": medians}, ""
        except Exception as exc:
            return None, small._failure("model_fit_failed", model_name, exc)
    estimator, reason = small.build_sklearn_estimator(model_name, config, numeric_cols, categorical_cols)
    if estimator is None:
        return None, reason
    try:
        estimator.fit(train_df[numeric_cols + categorical_cols], train_df[label_col])
        return {"kind": "sklearn", "model": estimator, "feature_cols": numeric_cols + categorical_cols, "numeric_cols": numeric_cols, "categorical_cols": categorical_cols, "missing_or_reserved_features": missing}, ""
    except Exception as exc:
        return None, small._failure("model_fit_failed", model_name, exc)


def run_feature_ablation(config: dict[str, Any], df: pd.DataFrame, model_names: list[str]) -> pd.DataFrame:
    root = Path.cwd()
    ablation_config = small.read_yaml(root / "configs/experiments/alive_prediction_feature_ablation.yaml")
    output_dir = root / ablation_config["reports_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    split = dict(config["time_splits"]["expanded_train_2020_2022"])
    trainability = small.build_trainability_report(df, config, split, list(config["horizons_months"]))
    train_df, test_all = split_train_test(df, split)
    test_df = small.split_scopes(test_all)[PRIMARY_SCOPE]
    rows: list[dict[str, Any]] = []
    status_rows: list[dict[str, Any]] = []
    for ablation in ablation_config["ablations"]:
        for horizon in config["horizons_months"]:
            label_col = f"label_die_H{horizon}"
            gate = trainability[trainability["horizon"] == horizon].iloc[0]
            for model_name in model_names:
                if not bool(gate["can_train"]):
                    status_rows.append({"ablation": ablation, "model": model_name, "horizon": horizon, "status": "skipped", "reason": gate["skip_reason"]})
                    continue
                numeric, categorical, missing = ablation_feature_columns(train_df, config, ablation_config, model_name, ablation)
                fitted, reason = fit_with_columns(model_name, train_df, label_col, config, numeric, categorical, missing)
                if fitted is None:
                    failure = reason if isinstance(reason, dict) else {"status": "skipped", "reason": str(reason)}
                    status_rows.append({"ablation": ablation, "model": model_name, "horizon": horizon, "status": failure["status"], "reason": failure["reason"]})
                    continue
                try:
                    scored = score_frame(fitted, test_df, horizon)
                    _p, _r, _v, _b, summary = evaluate_scored(scored, config=config, model_name=model_name, horizon=horizon, scope=PRIMARY_SCOPE)
                    summary.update({"ablation": ablation, "numeric_feature_count": len(numeric), "categorical_feature_count": len(categorical), "missing_or_reserved_features": ",".join(missing[:20])})
                    rows.append(summary)
                    status_rows.append({"ablation": ablation, "model": model_name, "horizon": horizon, "status": "trained_in_memory", "reason": ""})
                except Exception:
                    status_rows.append({"ablation": ablation, "model": model_name, "horizon": horizon, "status": "model_predict_failed", "reason": traceback.format_exc()})
    metrics = pd.DataFrame(rows)
    metrics.to_csv(output_dir / "feature_ablation_metrics.csv", index=False, encoding="utf-8-sig")
    by_horizon = metrics.groupby(["model", "horizon", "ablation"], dropna=False).mean(numeric_only=True).reset_index() if not metrics.empty else pd.DataFrame()
    by_horizon.to_csv(output_dir / "feature_ablation_by_horizon.csv", index=False, encoding="utf-8-sig")
    write_ablation_reports(output_dir, metrics, by_horizon, pd.DataFrame(status_rows))
    return metrics


def write_ablation_reports(output_dir: Path, metrics: pd.DataFrame, by_horizon: pd.DataFrame, status: pd.DataFrame) -> None:
    lines = ["# Feature Ablation Summary", "", "Scope: recurring_only. Split: expanded_train_2020_2022. Temporal drift guardrails apply.", ""]
    for metric in ["ndcg_at_top_10_pct", "lift_at_top_10_pct", "value_weighted_ndcg_at_top_10_pct"]:
        if metric in by_horizon and not by_horizon.empty:
            best = by_horizon.sort_values(metric, ascending=False).iloc[0]
            lines.append(f"- best_{metric}: {best['ablation']} ({best['model']} H{best['horizon']}) = {best[metric]}")
    lines.extend(["", "## Metrics", dataframe_to_markdown(by_horizon, index=False), "", "## Status", dataframe_to_markdown(status, index=False)])
    write_text(output_dir / "feature_ablation_summary.md", "\n".join(lines))
    if not by_horizon.empty:
        all_features = by_horizon[by_horizon["ablation"] == "all_features"]
        no_value = by_horizon[by_horizon["ablation"] == "all_features_without_value"]
        comparison = all_features.merge(no_value, on=["model", "horizon"], suffixes=("_all", "_without_value"), how="inner")
        for metric in ["value_weighted_ndcg_at_top_10_pct", "brier_score", "log_loss", "ece"]:
            if f"{metric}_all" in comparison and f"{metric}_without_value" in comparison:
                comparison[f"{metric}_delta_all_minus_without_value"] = comparison[f"{metric}_all"] - comparison[f"{metric}_without_value"]
    else:
        comparison = pd.DataFrame()
    write_text(output_dir / "feature_ablation_value_impact.md", "# Feature Ablation Value Impact\n\n" + (dataframe_to_markdown(comparison, index=False) if not comparison.empty else "No value impact comparison was generated."))


def rule_baseline_family_rows(root: Path) -> pd.DataFrame:
    metric_path = root / "reports/alive_prediction_2024/rule_baseline_metrics_by_cutoff.csv"
    value_path = root / "reports/alive_prediction_2024/rule_baseline_value_metrics_by_cutoff.csv"
    if not metric_path.exists():
        return pd.DataFrame()
    metrics = pd.read_csv(metric_path)
    metrics["model"] = "rule_baseline"
    metrics["scope"] = PRIMARY_SCOPE
    if value_path.exists():
        values = pd.read_csv(value_path)
        metrics = metrics.merge(values, on=["cutoff_month", "horizon", "k"], how="left", suffixes=("", "_value"))
    grouped = metrics.groupby(["model", "horizon", "scope", "k"], dropna=False).mean(numeric_only=True).reset_index()
    for column in ["brier_score", "log_loss", "ece", "auc", "pr_auc"]:
        grouped[column] = np.nan
    return grouped


def write_family_summary(output_dir: Path, scope_metrics: pd.DataFrame, window_metrics: pd.DataFrame) -> None:
    recurring = scope_metrics[(scope_metrics["scope"] == PRIMARY_SCOPE)].copy() if not scope_metrics.empty else pd.DataFrame()
    rule_rows = rule_baseline_family_rows(Path.cwd())
    by_k = pd.concat([recurring, rule_rows], ignore_index=True, sort=False) if not rule_rows.empty else recurring.copy()
    by_k.to_csv(output_dir / "model_family_comparison_by_k.csv", index=False, encoding="utf-8-sig")
    by_horizon = by_k[by_k["k"].astype(str) == TOPK].copy() if not by_k.empty else pd.DataFrame()
    by_horizon.to_csv(output_dir / "model_family_comparison_by_horizon.csv", index=False, encoding="utf-8-sig")
    candidate = "not_available"
    backup = "not_available"
    model_ranking = pd.DataFrame()
    if not by_horizon.empty:
        candidate_rows = by_horizon[by_horizon["model"] != "rule_baseline"].copy()
        if not candidate_rows.empty:
            rank_columns = [column for column in ["lift_at_k", "ndcg_at_k", "auc", "brier_score", "ece"] if column in candidate_rows.columns]
            model_ranking = candidate_rows.groupby("model", dropna=False)[rank_columns].mean(numeric_only=True).reset_index()
            sort_columns = [column for column in ["lift_at_k", "ndcg_at_k", "auc", "brier_score", "ece"] if column in model_ranking.columns]
            ascending = [False if column in {"lift_at_k", "ndcg_at_k", "auc"} else True for column in sort_columns]
            model_ranking = model_ranking.sort_values(sort_columns, ascending=ascending).reset_index(drop=True)
            candidate = str(model_ranking.iloc[0]["model"])
            backup = str(model_ranking.iloc[1]["model"]) if len(model_ranking) > 1 else candidate
    needs_cal = bool((by_horizon.get("ece", pd.Series(dtype=float)) > 0.05).any()) if not by_horizon.empty else False
    needs_more_windows = "yes" if window_metrics.empty or window_metrics["train_window_name"].nunique() < 3 else "review_window_comparison"
    lines = [
        "# Model Family Comparison Summary",
        "",
        "Temporal drift guardrails apply: do not select models from raw Precision/NDCG alone, especially late-2024.",
        "",
        f"- current_first_candidate_model: {candidate}",
        f"- current_backup_model: {backup}",
        f"- calibration_recommended: {needs_cal}",
        f"- more_training_windows_needed: {needs_more_windows}",
        "- enter_hyperparameter_tuning_now: false",
        "- calibration_next_step: keep churn_probability_raw_H and fit Platt/isotonic on validation cutoffs, not test cutoffs.",
        "",
        "## Model Ranking Aggregate",
        dataframe_to_markdown(model_ranking, index=False) if not model_ranking.empty else "No model ranking was generated.",
        "",
        "## Recurring Only Top 10 Percent",
        dataframe_to_markdown(by_horizon, index=False) if not by_horizon.empty else "No recurring_only metrics.",
    ]
    write_text(output_dir / "model_family_comparison_summary.md", "\n".join(lines))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/experiments/alive_prediction_small_models.yaml")
    parser.add_argument("--reports-dir", default="reports/alive_prediction_small_models_expanded_train")
    parser.add_argument("--models", nargs="*", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    config = small.read_yaml(root / args.config)
    config["outputs"]["reports_dir"] = args.reports_dir
    config["input"]["reports_dir"] = args.reports_dir
    model_names = args.models or [name for name, cfg in config["models"].items() if cfg.get("enabled", False)]
    output_dir = root / args.reports_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    diagnostics = small.collect_environment_diagnostics()
    small.write_environment_diagnostics(output_dir, diagnostics)
    expanded_split = dict(config["time_splits"]["expanded_train_2020_2022"])
    include_status_history = bool(config["features"].get("status_history_features", {}).get("enabled", False))
    df = small.build_or_load_feature_label_table(config, expanded_split, refresh_cache=False, include_status_history=include_status_history)
    df = small.add_scope_flags(df, config, small.read_yaml(root / "configs/experiments/alive_prediction_rule_baseline.yaml"))
    scope_metrics = run_expanded_experiment(config, df, output_dir, model_names)
    window_metrics = run_window_comparison(config, df, output_dir, model_names)
    run_feature_ablation(config, df, model_names)
    write_family_summary(output_dir, scope_metrics, window_metrics)
    print({"output_dir": str(output_dir), "models": model_names}, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
