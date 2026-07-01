#!/usr/bin/env python
"""Review calibration v1 results and prepare rolling-origin validation v1."""

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

import run_alive_prediction_small_model_experiments as small


CALIBRATION_DIR = ROOT / "reports/alive_prediction_calibration_v1"
OUTPUT_DIR = ROOT / "reports/alive_prediction_calibration_review"
PRIMARY_SCOPE = "recurring_only"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def markdown_table(df: pd.DataFrame) -> str:
    return small.dataframe_to_markdown(df, index=False)


def read_required_csv(name: str) -> pd.DataFrame:
    path = CALIBRATION_DIR / name
    if not path.exists() or path.stat().st_size == 0:
        raise FileNotFoundError(f"Missing or empty calibration v1 file: {path}")
    return pd.read_csv(path)


def topk_stability_status(row: pd.Series) -> str:
    deltas = [
        abs(float(row.get("lift_at_top_10_pct_delta_after_minus_before", np.nan))),
        abs(float(row.get("ndcg_at_top_10_pct_delta_after_minus_before", np.nan))),
        abs(float(row.get("precision_at_top_10_pct_delta_after_minus_before", np.nan))),
    ]
    finite = [value for value in deltas if np.isfinite(value)]
    if not finite:
        return "not_applicable_raw_overall"
    if max(finite) <= 0.02:
        return "stable"
    if max(finite) <= 0.05:
        return "minor_change"
    return "material_degradation_or_shift"


def method_comparison(before_after: pd.DataFrame) -> pd.DataFrame:
    macro = before_after[
        (before_after["scope"].eq(PRIMARY_SCOPE)) & (before_after["aggregation_method"].eq("macro_by_cutoff"))
    ].copy()
    grouped = (
        macro.groupby("calibration_method", dropna=False)
        [[
            "brier_score_before",
            "brier_score_after",
            "brier_score_delta_after_minus_before",
            "log_loss_before",
            "log_loss_after",
            "log_loss_delta_after_minus_before",
            "ece_before",
            "ece_after",
            "ece_delta_after_minus_before",
            "auc_before",
            "auc_after",
            "auc_delta_after_minus_before",
            "pr_auc_before",
            "pr_auc_after",
            "pr_auc_delta_after_minus_before",
        ]]
        .mean(numeric_only=True)
        .reset_index()
    )
    grouped["stability_note"] = np.where(
        (grouped["brier_score_delta_after_minus_before"] <= 0)
        & (grouped["log_loss_delta_after_minus_before"] <= 0)
        & (grouped["ece_delta_after_minus_before"] <= 0),
        "probability_quality_improves_on_average",
        "not_consistently_improving",
    )
    return grouped.sort_values(["brier_score_after", "log_loss_after", "ece_after"])


def calibrated_candidate_decision(before_after: pd.DataFrame, topk: pd.DataFrame) -> pd.DataFrame:
    macro = before_after[
        (before_after["scope"].eq(PRIMARY_SCOPE)) & (before_after["aggregation_method"].eq("macro_by_cutoff"))
    ].copy()
    topk_macro = topk[
        (topk["scope"].eq(PRIMARY_SCOPE)) & (topk["aggregation_method"].eq("macro_by_cutoff"))
    ].copy()
    if not topk_macro.empty:
        topk_macro["topk_stability_status"] = topk_macro.apply(topk_stability_status, axis=1)
        macro = macro.merge(
            topk_macro[["model", "feature_set", "horizon", "calibration_method", "topk_stability_status"]],
            on=["model", "feature_set", "horizon", "calibration_method"],
            how="left",
        )
    else:
        macro["topk_stability_status"] = "not_available"
    rows: list[dict[str, Any]] = []
    for _, row in macro.iterrows():
        model = str(row["model"])
        feature_set = str(row["feature_set"])
        method = str(row["calibration_method"])
        status = str(row.get("calibration_status", ""))
        brier_delta = float(row["brier_score_delta_after_minus_before"])
        logloss_delta = float(row["log_loss_delta_after_minus_before"])
        ece_delta = float(row["ece_delta_after_minus_before"])
        if model == "logistic_regression" and feature_set == "base_recency_frequency_only" and method == "isotonic":
            decision = "needs_rolling_origin_validation"
            reason = "Best calibrated aggregate probability metrics, but improvements are not consistent across H3/H6/H12."
        elif model == "logistic_regression" and feature_set == "base_recency_frequency_only":
            decision = "keep_as_sanity_baseline"
            reason = "Transparent baseline; Platt does not improve probability quality enough to promote."
        elif model == "xgboost_small" and feature_set == "base_recency_frequency_only":
            decision = "keep_as_backup"
            reason = "Nonlinear challenger remains useful, but calibrated probability metrics trail Logistic."
        elif model == "xgboost_small" and feature_set == "base_plus_interval_features":
            decision = "keep_as_backup" if status != "overfit_risk" and logloss_delta <= 0.02 else "reject_for_probability_mainline"
            reason = "Interval feature set needs rolling-origin proof; reject rows with overfit/logloss risk."
        elif model == "catboost_small" and feature_set == "base_recency_frequency_only":
            decision = "keep_as_backup" if (brier_delta <= 0 and logloss_delta <= 0 and ece_delta <= 0) else "reject_for_probability_mainline"
            reason = "CatBoost shows calibration risk and is not the main probability candidate."
        else:
            decision = "reject_for_probability_mainline"
            reason = "Not part of the main probability short list."
        rows.append(
            {
                "horizon": int(row["horizon"]),
                "candidate_model": model,
                "feature_set": feature_set,
                "calibration_method": method,
                "brier_before": row["brier_score_before"],
                "brier_after": row["brier_score_after"],
                "logloss_before": row["log_loss_before"],
                "logloss_after": row["log_loss_after"],
                "ece_before": row["ece_before"],
                "ece_after": row["ece_after"],
                "auc_before": row["auc_before"],
                "auc_after": row["auc_after"],
                "pr_auc_before": row["pr_auc_before"],
                "pr_auc_after": row["pr_auc_after"],
                "topk_stability_status": row.get("topk_stability_status", "not_available"),
                "decision": decision,
                "reason": reason,
            }
        )
    return pd.DataFrame(rows).sort_values(["horizon", "brier_after", "logloss_after", "ece_after"])


def best_rows(before_after: pd.DataFrame) -> dict[str, pd.Series]:
    macro = before_after[
        (before_after["scope"].eq(PRIMARY_SCOPE)) & (before_after["aggregation_method"].eq("macro_by_cutoff"))
    ].copy()
    return {
        "brier": macro.sort_values("brier_score_after").iloc[0],
        "logloss": macro.sort_values("log_loss_after").iloc[0],
        "ece": macro.sort_values("ece_after").iloc[0],
    }


def aggregate_best(before_after: pd.DataFrame) -> pd.DataFrame:
    macro = before_after[
        (before_after["scope"].eq(PRIMARY_SCOPE)) & (before_after["aggregation_method"].eq("macro_by_cutoff"))
    ].copy()
    return (
        macro.groupby(["model", "feature_set", "calibration_method"], dropna=False)
        [[
            "brier_score_after",
            "log_loss_after",
            "ece_after",
            "auc_after",
            "pr_auc_after",
            "brier_score_delta_after_minus_before",
            "log_loss_delta_after_minus_before",
            "ece_delta_after_minus_before",
        ]]
        .mean(numeric_only=True)
        .reset_index()
        .sort_values(["brier_score_after", "log_loss_after", "ece_after", "auc_after", "pr_auc_after"], ascending=[True, True, True, False, False])
    )


def has_topk_degradation(topk: pd.DataFrame) -> bool:
    macro = topk[(topk["scope"].eq(PRIMARY_SCOPE)) & (topk["aggregation_method"].eq("macro_by_cutoff"))].copy()
    if macro.empty:
        return False
    macro["topk_stability_status"] = macro.apply(topk_stability_status, axis=1)
    return bool(macro["topk_stability_status"].eq("material_degradation_or_shift").any())


def write_review(before_after: pd.DataFrame, topk: pd.DataFrame, bins: pd.DataFrame, failures: pd.DataFrame) -> None:
    best = best_rows(before_after)
    aggregate = aggregate_best(before_after)
    method_cmp = method_comparison(before_after)
    overfit = before_after[
        (before_after["scope"].eq(PRIMARY_SCOPE))
        & (before_after["aggregation_method"].eq("macro_by_cutoff"))
        & (before_after["calibration_status"].eq("overfit_risk"))
    ].copy()
    topk_degraded = has_topk_degradation(topk)
    h3h6h12_consistent = bool(
        before_after[
            (before_after["scope"].eq(PRIMARY_SCOPE))
            & (before_after["aggregation_method"].eq("macro_by_cutoff"))
            & (before_after["model"].eq("logistic_regression"))
            & (before_after["feature_set"].eq("base_recency_frequency_only"))
            & (before_after["calibration_method"].eq("isotonic"))
            & (before_after["calibration_status"].eq("keep_calibration_method"))
        ]["horizon"].nunique()
        == 3
    )
    probability_candidate_v1_ready = False
    lines = [
        "# Calibration Result Review",
        "",
        "This review uses recurring_only only. It reviews churn_probability_H calibration and is not a business ranking model.",
        "",
        "## Direct Answers",
        f"1. Best calibrated Brier row: {describe_row(best['brier'], 'brier_score_after')}.",
        f"2. Best calibrated LogLoss row: {describe_row(best['logloss'], 'log_loss_after')}.",
        f"3. Best calibrated ECE row: {describe_row(best['ece'], 'ece_after')}.",
        "4. Platt vs isotonic: isotonic has the better calibrated aggregate Brier/LogLoss/ECE in this run, but it is not consistently improving all horizons; Platt is monotonic-order preserving but often worsens Brier/ECE here.",
        f"5. Isotonic overfit risk rows: {len(overfit)}. " + ("See method comparison and decision CSV." if len(overfit) else "No overfit_risk rows were flagged."),
        "6. AUC/PR_AUC are mostly preserved for Platt by construction; isotonic can slightly change ranking because ties/steps may alter order.",
        f"7. TopK Lift/NDCG/Precision material degradation: {'yes' if topk_degraded else 'no material degradation in macro_by_cutoff rows'}. TopK remains diagnostic only.",
        f"8. H3/H6/H12 conclusion consistent: {'yes' if h3h6h12_consistent else 'no; calibration benefits are horizon-specific and mixed'}.",
        f"9. probability_candidate_v1 can be determined now: {'yes' if probability_candidate_v1_ready else 'no'}.",
        "10. Reason: Logistic + base_recency_frequency_only remains the leading candidate, but calibration does not improve all H3/H6/H12 probability metrics consistently; rolling-origin validation is needed before promotion.",
        "",
        "## Aggregate Calibrated Probability Ranking",
        markdown_table(aggregate),
        "",
        "## Method Comparison",
        markdown_table(method_cmp),
        "",
        "## Failure Report",
        markdown_table(failures) if not failures.empty else "No calibration failures.",
    ]
    write_text(OUTPUT_DIR / "calibration_result_review.md", "\n".join(lines))
    method_cmp.to_csv(OUTPUT_DIR / "calibration_method_comparison.csv", index=False, encoding="utf-8-sig")


def describe_row(row: pd.Series, metric_col: str) -> str:
    return (
        f"{row['model']} + {row['feature_set']} + {row['calibration_method']} "
        f"H{int(row['horizon'])}, {metric_col}={float(row[metric_col]):.4f}"
    )


def write_risk_notes(before_after: pd.DataFrame, topk: pd.DataFrame) -> None:
    lines = [
        "# Calibration Risk Notes",
        "",
        "- Calibration v1 does not fit on 2024 test; calibrators are fit on 2022 validation only.",
        "- 2023 remains a purge gap before the 2024 final test.",
        "- All selection rows use recurring_only only.",
        "- value_at_risk and business_priority_score are not model inputs or selection metrics.",
        "- Value-weighted metrics are not used for probability selection.",
        "- TopK metrics are cutoff-aware stability diagnostics and are not primary probability metrics.",
        "- raw_overall TopK remains blank because cross-cutoff TopK mixing is not allowed.",
        "- Isotonic can overfit when validation sample shape differs from 2024; rows with ECE improvement but LogLoss worsening are flagged overfit_risk.",
        "- The current calibration result is not strong enough to skip rolling-origin validation.",
    ]
    write_text(OUTPUT_DIR / "calibration_risk_notes.md", "\n".join(lines))


def write_rolling_plan() -> None:
    feature_path = ROOT / "data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/cutoff_2020-01_2024-12/feature_table__status0.parquet"
    label_path = ROOT / "data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/cutoff_2020-01_2024-12/alive_labels__H3_6_12.parquet"
    supported = feature_path.exists() and label_path.exists()
    lines = [
        "# Rolling-Origin Validation v1 Plan",
        "",
        "This is a design plan. It does not run large-scale validation in this step.",
        "",
        "## Artifact Availability",
        f"- feature_table__status0.parquet: {'available' if feature_path.exists() else 'missing'}",
        f"- alive_labels__H3_6_12.parquet: {'available' if label_path.exists() else 'missing'}",
        f"- lightweight implementation feasible from existing artifacts: {'yes' if supported else 'no'}",
        "",
        "## Candidate Set",
        "- logistic_regression + base_recency_frequency_only",
        "- xgboost_small + base_recency_frequency_only",
        "- xgboost_small + base_plus_interval_features only if needed after review",
        "",
        "## Folds",
        "### fold_1",
        "- train: 2020",
        "- valid/test: 2021",
        "",
        "### fold_2",
        "- train: 2020-2021",
        "- valid/test: 2022",
        "",
        "### fold_3",
        "- train: 2020-2022",
        "- purge: 2023",
        "- test: 2024",
        "",
        "## Evaluation",
        "- recurring_only is the main scope.",
        "- H3/H6/H12 are evaluated separately.",
        "- Primary metrics: Brier, LogLoss, ECE, AUC, PR_AUC.",
        "- Calibration bins are produced per horizon and fold.",
        "- TopK Lift/NDCG/Precision are cutoff-aware stability diagnostics only.",
        "- Do not use value-weighted metrics or business priority fields for probability selection.",
        "",
        "## Decision Gate",
        "- Promote probability_candidate_v1 only if Logistic/base or a challenger is stable across folds and calibration improves or preserves Brier/LogLoss/ECE without material ranking degradation.",
    ]
    write_text(OUTPUT_DIR / "rolling_origin_validation_v1_plan.md", "\n".join(lines))


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    before_after = read_required_csv("calibration_metrics_before_after.csv")
    topk = read_required_csv("calibration_topk_stability.csv")
    bins = read_required_csv("calibration_bins_before_after.csv")
    failures = read_required_csv("calibration_failure_report.csv")
    decision = calibrated_candidate_decision(before_after, topk)
    decision.to_csv(OUTPUT_DIR / "calibrated_candidate_decision.csv", index=False, encoding="utf-8-sig")
    write_review(before_after, topk, bins, failures)
    write_risk_notes(before_after, topk)
    write_rolling_plan()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
