"""Presentation helpers for the alive prediction model-selection story notebook.

The helpers in this module are intentionally report-only: they read existing
CSV/Markdown outputs under ``reports/`` and never train models, materialize
features, or read full parquet artifacts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


STAGE_REPORTS: dict[str, list[str]] = {
    "small_models": [
        "reports/alive_prediction_small_models/model_metrics_by_scope.csv",
        "reports/alive_prediction_small_models/model_metrics_by_cutoff.csv",
        "reports/alive_prediction_small_models/trainability_report_by_horizon.csv",
        "reports/alive_prediction_small_models/model_experiment_summary.md",
    ],
    "expanded_train": [
        "reports/alive_prediction_small_models_expanded_train/model_metrics_by_scope.csv",
        "reports/alive_prediction_small_models_expanded_train/training_window_comparison.csv",
        "reports/alive_prediction_small_models_expanded_train/model_family_comparison_by_horizon.csv",
        "reports/alive_prediction_small_models_expanded_train/model_experiment_summary.md",
    ],
    "temporal_drift": [
        "reports/alive_prediction_temporal_drift/cutoff_entity_count_trend.csv",
        "reports/alive_prediction_temporal_drift/cutoff_label_rate_trend.csv",
        "reports/alive_prediction_temporal_drift/feature_distribution_shift.csv",
        "reports/alive_prediction_temporal_drift/drift_aware_metric_summary.csv",
        "reports/alive_prediction_temporal_drift/metric_interpretation_guardrails.md",
    ],
    "data_regime_shift": [
        "reports/alive_prediction_data_regime_shift_review/data_regime_shift_summary.md",
        "reports/alive_prediction_data_regime_shift_review/cutoff_entity_inflow_decomposition.csv",
        "reports/alive_prediction_data_regime_shift_review/cutoff_label_rate_by_entity_age.csv",
        "reports/alive_prediction_data_regime_shift_review/cutoff_label_rate_by_first_seen_period.csv",
        "reports/alive_prediction_data_regime_shift_review/demand_shape_by_regime.csv",
        "reports/alive_prediction_data_regime_shift_review/label_window_closure_check.csv",
        "reports/alive_prediction_data_regime_shift_review/regime_split_recommendation.md",
    ],
    "feature_ablation": [
        "reports/alive_prediction_feature_ablation/feature_ablation_metrics.csv",
        "reports/alive_prediction_feature_ablation/feature_ablation_summary.md",
        "reports/alive_prediction_feature_ablation/feature_ablation_value_impact.md",
    ],
    "probability_consolidation": [
        "reports/alive_prediction_probability_consolidation/probability_candidate_metrics.csv",
        "reports/alive_prediction_probability_consolidation/probability_final_shortlist_v2.csv",
        "reports/alive_prediction_probability_consolidation/probability_consolidation_summary_v2.md",
    ],
    "calibration_v1": [
        "reports/alive_prediction_calibration_v1/calibration_metrics_before_after.csv",
        "reports/alive_prediction_calibration_v1/calibration_experiment_summary.md",
    ],
    "calibration_review": [
        "reports/alive_prediction_calibration_review/calibrated_candidate_decision.csv",
        "reports/alive_prediction_calibration_review/calibration_result_review.md",
    ],
    "rolling_origin": [
        "reports/alive_prediction_rolling_origin_v1/rolling_origin_metrics.csv",
        "reports/alive_prediction_rolling_origin_v1/probability_candidate_v1_decision.md",
    ],
    "probability_stabilization": [
        "reports/alive_prediction_probability_stabilization/probability_stabilization_summary.md",
        "reports/alive_prediction_probability_stabilization/candidate_decision_update.csv",
    ],
    "feature_stability": [
        "reports/alive_prediction_feature_stability_v1/feature_distribution_shift_before_after.csv",
        "reports/alive_prediction_feature_stability_v1/feature_set_comparison_by_fold.csv",
        "reports/alive_prediction_feature_stability_v1/probability_candidate_v1_reassessment.md",
    ],
    "calibration_v2": [
        "reports/alive_prediction_calibration_v2/calibration_v2_metrics_by_fold.csv",
        "reports/alive_prediction_calibration_v2/probability_candidate_v1_decision_v2.csv",
        "reports/alive_prediction_calibration_v2/calibration_v2_summary.md",
    ],
    "demand_shape_review": [
        "reports/alive_prediction_demand_shape_label_review/demand_shape_distribution.csv",
        "reports/alive_prediction_demand_shape_label_review/demand_shape_label_rate_by_horizon.csv",
        "reports/alive_prediction_demand_shape_label_review/demand_shape_probability_metrics.csv",
        "reports/alive_prediction_demand_shape_label_review/demand_shape_routing_decision.csv",
        "reports/alive_prediction_demand_shape_label_review/probability_candidate_v1_business_use_note.md",
        "reports/alive_prediction_demand_shape_label_review/next_stage_line_card_plan.md",
    ],
}


def _warning_frame(message: str, *, path: Path | None = None) -> pd.DataFrame:
    row: dict[str, Any] = {"warning": message}
    if path is not None:
        row["path"] = str(path)
    return pd.DataFrame([row])


def load_csv_if_exists(path: Path) -> pd.DataFrame | None:
    """Return a CSV as a DataFrame, or ``None`` when it is absent/unreadable."""

    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception as exc:  # pragma: no cover - defensive notebook path.
        return _warning_frame(f"failed_to_read_csv:{exc!r}", path=path)


def read_md_head(path: Path, max_chars: int = 3000) -> str:
    """Read a short Markdown excerpt without failing the notebook."""

    if not path.exists():
        return f"[missing] {path}"
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except Exception as exc:  # pragma: no cover - defensive notebook path.
        return f"[failed_to_read_markdown] {path}: {exc!r}"


def load_stage_reports(project_root: Path) -> dict[str, dict[str, Any]]:
    """Load known report assets by stage.

    Values are keyed by relative path and contain either a DataFrame, Markdown
    excerpt, or warning text.
    """

    loaded: dict[str, dict[str, Any]] = {}
    for stage, rel_paths in STAGE_REPORTS.items():
        stage_items: dict[str, Any] = {}
        for rel in rel_paths:
            path = project_root / rel
            if path.suffix.lower() == ".csv":
                stage_items[rel] = load_csv_if_exists(path)
            elif path.suffix.lower() == ".md":
                stage_items[rel] = read_md_head(path)
            else:
                stage_items[rel] = path if path.exists() else None
        loaded[stage] = stage_items
    return loaded


def render_missing_files_report(project_root: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for stage, rel_paths in STAGE_REPORTS.items():
        for rel in rel_paths:
            path = project_root / rel
            rows.append(
                {
                    "stage": stage,
                    "path": rel,
                    "exists": path.exists(),
                    "file_size": path.stat().st_size if path.exists() else 0,
                }
            )
    return pd.DataFrame(rows)


def build_stage_summary_table(project_root: Path) -> pd.DataFrame:
    missing = render_missing_files_report(project_root)
    rows: list[dict[str, Any]] = []
    for stage, group in missing.groupby("stage", sort=False):
        rows.append(
            {
                "stage": stage,
                "available_files": int(group["exists"].sum()),
                "expected_files": int(len(group)),
                "missing_files": ", ".join(group.loc[~group["exists"], "path"].tolist()),
            }
        )
    return pd.DataFrame(rows)


def build_final_decision_table(project_root: Path) -> pd.DataFrame:
    decision_path = project_root / "reports/alive_prediction_calibration_v2/probability_candidate_v1_decision_v2.csv"
    decision = load_csv_if_exists(decision_path)
    if decision is None or decision.empty or "decision" not in decision.columns:
        return pd.DataFrame(
            [
                {
                    "decision_item": "probability_candidate_v1",
                    "value": "logistic_regression + frequency_decay_v1 + raw",
                    "source": "fallback_from_stage_decision",
                },
                {
                    "decision_item": "business_usable_probability_baseline",
                    "value": "true",
                    "source": "fallback_from_stage_decision",
                },
            ]
        )
    promoted = decision[decision["decision"].eq("promote_to_probability_candidate_v1")].head(1)
    if promoted.empty:
        candidate = "not_promoted"
        source = str(decision_path)
    else:
        row = promoted.iloc[0]
        candidate = f"{row['model']} + {row['feature_set']} + {row['calibration_method']}"
        source = str(decision_path)
    return pd.DataFrame(
        [
            {
                "decision_item": "probability_candidate_v1",
                "value": candidate,
                "source": source,
            },
            {
                "decision_item": "business_usable_probability_baseline",
                "value": "true",
                "source": "reports/alive_prediction_calibration_v2/calibration_v2_summary.md",
            },
            {
                "decision_item": "main_scope",
                "value": "recurring_only",
                "source": "experiment contract",
            },
        ]
    )


def _new_figure(title: str):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.set_title(title)
    return fig, ax


def plot_model_probability_metrics(df: pd.DataFrame | None, *, title: str = "Model Probability Metrics"):
    fig, ax = _new_figure(title)
    if df is None or df.empty:
        ax.text(0.5, 0.5, "missing metrics", ha="center", va="center")
        ax.axis("off")
        return fig
    work = df.copy()
    if "aggregation_method" in work.columns:
        work = work[work["aggregation_method"].isin(["macro_by_cutoff", "raw_overall"])]
    group_cols = [col for col in ["model", "feature_set", "calibration_method"] if col in work.columns]
    if not group_cols:
        ax.text(0.5, 0.5, "metrics table lacks model columns", ha="center", va="center")
        ax.axis("off")
        return fig
    metrics = [col for col in ["brier_score", "log_loss", "ece"] if col in work.columns]
    if not metrics:
        ax.text(0.5, 0.5, "metrics table lacks probability columns", ha="center", va="center")
        ax.axis("off")
        return fig
    summary = work.groupby(group_cols, dropna=False)[metrics].mean(numeric_only=True).reset_index()
    summary["candidate"] = summary[group_cols].astype(str).agg(" / ".join, axis=1)
    summary = summary.sort_values(metrics[0]).head(10)
    summary.plot.barh(x="candidate", y=metrics, ax=ax)
    ax.invert_yaxis()
    ax.set_xlabel("lower is better")
    return fig


def plot_cutoff_label_rate_trend(label_rates: pd.DataFrame | None):
    fig, ax = _new_figure("Cutoff Label Positive Rate Trend")
    if label_rates is None or label_rates.empty:
        ax.text(0.5, 0.5, "missing cutoff_label_rate_trend.csv", ha="center", va="center")
        ax.axis("off")
        return fig
    work = label_rates.copy()
    work["cutoff_month"] = pd.to_datetime(work["cutoff_month"].astype(str))
    for col in ["label_die_H3_positive_rate", "label_die_H6_positive_rate", "label_die_H12_positive_rate"]:
        if col in work.columns:
            ax.plot(work["cutoff_month"], work[col], marker="o", label=col.replace("_positive_rate", ""))
    ax.set_ylabel("positive rate")
    ax.legend()
    return fig


def plot_cutoff_entity_count_trend(entity_counts: pd.DataFrame | None):
    fig, ax = _new_figure("Recurring Entity Count by Cutoff")
    if entity_counts is None or entity_counts.empty or "recurring_entity_count" not in entity_counts.columns:
        ax.text(0.5, 0.5, "missing cutoff_entity_count_trend.csv", ha="center", va="center")
        ax.axis("off")
        return fig
    work = entity_counts.copy()
    work["cutoff_month"] = pd.to_datetime(work["cutoff_month"].astype(str))
    ax.plot(work["cutoff_month"], work["recurring_entity_count"], marker="o")
    ax.set_ylabel("recurring entity count")
    return fig


def plot_feature_smd_top(shift: pd.DataFrame | None, *, top_n: int = 10):
    fig, ax = _new_figure(f"Top {top_n} Feature Standardized Mean Differences")
    if shift is None or shift.empty or "standardized_mean_diff" not in shift.columns:
        ax.text(0.5, 0.5, "missing feature distribution shift", ha="center", va="center")
        ax.axis("off")
        return fig
    work = shift.copy()
    work["abs_smd"] = pd.to_numeric(work["standardized_mean_diff"], errors="coerce").abs()
    work = work.sort_values("abs_smd", ascending=False).head(top_n)
    label_col = "feature" if "feature" in work.columns else work.columns[0]
    ax.barh(work[label_col].astype(str), work["abs_smd"])
    ax.invert_yaxis()
    ax.set_xlabel("abs standardized mean difference")
    return fig


def plot_feature_stability_before_after(shift: pd.DataFrame | None):
    fig, ax = _new_figure("Feature Stability Before/After")
    if shift is None or shift.empty or "feature_set" not in shift.columns:
        ax.text(0.5, 0.5, "missing feature stability shift table", ha="center", va="center")
        ax.axis("off")
        return fig
    work = shift.copy()
    if "standardized_mean_diff" not in work.columns:
        ax.text(0.5, 0.5, "missing standardized_mean_diff", ha="center", va="center")
        ax.axis("off")
        return fig
    work["abs_smd"] = pd.to_numeric(work["standardized_mean_diff"], errors="coerce").abs()
    summary = work.groupby("feature_set", dropna=False)["abs_smd"].mean().sort_values()
    summary.plot.barh(ax=ax)
    ax.set_xlabel("mean abs SMD")
    return fig


def plot_calibration_v2_before_after(metrics: pd.DataFrame | None):
    fig, ax = _new_figure("Calibration v2 Candidate Metrics")
    if metrics is None or metrics.empty:
        ax.text(0.5, 0.5, "missing calibration v2 metrics", ha="center", va="center")
        ax.axis("off")
        return fig
    work = metrics.copy()
    group_cols = [col for col in ["model", "feature_set", "calibration_method"] if col in work.columns]
    metric_cols = [col for col in ["brier_score", "log_loss", "ece"] if col in work.columns]
    if not group_cols or not metric_cols:
        ax.text(0.5, 0.5, "missing required calibration columns", ha="center", va="center")
        ax.axis("off")
        return fig
    summary = work.groupby(group_cols, dropna=False)[metric_cols].mean(numeric_only=True).reset_index()
    summary["candidate"] = summary[group_cols].astype(str).agg(" / ".join, axis=1)
    summary = summary.sort_values("brier_score").head(8)
    summary.plot.barh(x="candidate", y=metric_cols, ax=ax)
    ax.invert_yaxis()
    ax.set_xlabel("lower is better")
    return fig


def plot_demand_shape_label_rate(label_rates: pd.DataFrame | None):
    fig, ax = _new_figure("Demand Shape Label Rate by Horizon")
    if label_rates is None or label_rates.empty:
        ax.text(0.5, 0.5, "missing demand_shape_label_rate_by_horizon.csv", ha="center", va="center")
        ax.axis("off")
        return fig
    work = label_rates[label_rates["cutoff_period"].eq("all_2024")].copy() if "cutoff_period" in label_rates.columns else label_rates.copy()
    if work.empty or not {"demand_shape_label", "horizon", "positive_rate"}.issubset(work.columns):
        ax.text(0.5, 0.5, "missing demand-shape label columns", ha="center", va="center")
        ax.axis("off")
        return fig
    pivot = work.pivot_table(index="demand_shape_label", columns="horizon", values="positive_rate", aggfunc="mean")
    pivot.plot.bar(ax=ax)
    ax.set_ylabel("positive rate")
    return fig
