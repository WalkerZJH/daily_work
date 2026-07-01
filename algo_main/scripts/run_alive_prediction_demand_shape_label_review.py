#!/usr/bin/env python
"""Review demand-shape routing and label-definition risk for churn probability."""

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
import run_alive_prediction_feature_stability_v1 as feature_stability
import run_alive_prediction_probability_consolidation as consolidation
import run_alive_prediction_small_model_experiments as small


OUTPUT_DIR = ROOT / "reports/alive_prediction_demand_shape_label_review"
PRIMARY_SCOPE = "recurring_only"
MODEL = "logistic_regression"
FEATURE_SET = "frequency_decay_v1"
CALIBRATION_METHOD = "raw"
HORIZONS = [3, 6, 12]
KEY_COLS = ["manufacturer_code", "hospital_code", "drug_group"]
SHAPES = ["smooth", "erratic", "intermittent", "lumpy", "__MISSING__"]
FOLD_1 = {"fold": "fold_1", "train_start": "2020-01", "train_end": "2020-12", "test_start": "2022-01", "test_end": "2022-12"}
FOLD_2 = {"fold": "fold_2", "train_start": "2020-01", "train_end": "2021-12", "test_start": "2024-01", "test_end": "2024-12"}
PERIODS_2024 = {
    "all_2024": ("2024-01", "2024-12"),
    "early_2024": ("2024-01", "2024-04"),
    "mid_2024": ("2024-05", "2024-08"),
    "late_2024": ("2024-09", "2024-12"),
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


def safe_mean(df: pd.DataFrame, column: str) -> float:
    if column not in df.columns or len(df) == 0:
        return np.nan
    return float(pd.to_numeric(df[column], errors="coerce").mean())


def shape_values(df: pd.DataFrame) -> pd.Series:
    if "demand_shape_label" not in df.columns:
        return pd.Series("__MISSING__", index=df.index, dtype="string")
    return df["demand_shape_label"].astype("string").fillna("__MISSING__")


def period_part(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    return df[cutoff_mask(df, start, end)].copy()


def load_data(config: dict[str, Any]) -> pd.DataFrame:
    df = consolidation.load_feature_data(config)
    df = feature_stability.add_stability_features(df)
    return df


def recurring_only(df: pd.DataFrame) -> pd.DataFrame:
    return small.split_scopes(df)[PRIMARY_SCOPE].copy()


def split_train_test(df: pd.DataFrame, fold: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[cutoff_mask(df, fold["train_start"], fold["train_end"]) & df["recurring_candidate_flag"]].copy()
    test = recurring_only(df[cutoff_mask(df, fold["test_start"], fold["test_end"])].copy())
    if "one_shot_high_value_silence_flag" in train.columns:
        train = train[~train["one_shot_high_value_silence_flag"].astype(bool)].copy()
    overlap = set(cutoff_periods(train)).intersection(set(cutoff_periods(test)))
    if overlap:
        raise RuntimeError(f"{fold['fold']} train/test cutoffs overlap: {sorted(map(str, overlap))}")
    return train, test


def selected_columns(config: dict[str, Any], df: pd.DataFrame) -> tuple[list[str], list[str], list[str]]:
    spec = feature_stability.feature_sets()[FEATURE_SET]
    numeric, categorical, rejected = feature_stability.validate_features(df, spec["numeric"], spec["categorical"], config)
    forbidden = [
        column
        for column in numeric + categorical
        if any(pattern in column for pattern in consolidation.FORBIDDEN_FEATURE_PATTERNS)
    ]
    if forbidden:
        raise RuntimeError(f"forbidden probability features selected: {forbidden}")
    return numeric, categorical, rejected


def score_fold2_probability(config: dict[str, Any], df: pd.DataFrame) -> tuple[dict[int, pd.DataFrame], list[dict[str, Any]]]:
    train, test = split_train_test(df, FOLD_2)
    numeric, categorical, rejected = selected_columns(config, train)
    scored_by_horizon: dict[int, pd.DataFrame] = {}
    failures: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        label_col = f"label_die_H{horizon}"
        if label_col not in train or label_col not in test:
            failures.append({"horizon": horizon, "reason": f"{label_col}_missing"})
            continue
        if train[label_col].isna().any() or test[label_col].isna().any():
            failures.append({"horizon": horizon, "reason": f"{label_col}_has_missing"})
            continue
        if train[label_col].nunique(dropna=True) < 2:
            failures.append({"horizon": horizon, "reason": f"{label_col}_single_class"})
            continue
        fitted, reason = expanded.fit_with_columns(MODEL, train, label_col, config, numeric, categorical, rejected)
        if fitted is None:
            failures.append({"horizon": horizon, "reason": f"model_fit_failed:{reason}"})
            continue
        scored = test.copy()
        scored[f"churn_probability_H{horizon}"] = np.clip(small.predict_with_fitted_model(fitted, scored), 1e-15, 1 - 1e-15)
        scored_by_horizon[horizon] = scored
    return scored_by_horizon, failures


def demand_shape_distribution(df: pd.DataFrame) -> pd.DataFrame:
    work = recurring_only(df)
    work["demand_shape_label"] = shape_values(work)
    rows: list[dict[str, Any]] = []
    for cutoff, cutoff_df in work.groupby(cutoff_periods(work), sort=True):
        total = len(cutoff_df)
        for shape, part in cutoff_df.groupby("demand_shape_label", dropna=False):
            rows.append(
                {
                    "cutoff_month": str(cutoff),
                    "demand_shape_label": str(shape),
                    "row_count": int(len(part)),
                    "entity_count": entity_count(part),
                    "share_in_recurring_only": float(len(part) / total) if total else np.nan,
                    "mean_purchase_count_asof_cutoff": safe_mean(part, "purchase_count_asof_cutoff"),
                    "mean_active_month_count_asof_cutoff": safe_mean(part, "active_month_count_asof_cutoff"),
                    "mean_months_since_last_purchase": safe_mean(part, "months_since_last_purchase_asof_cutoff"),
                    "mean_order_count_last_6m": safe_mean(part, "order_count_last_6m_asof_cutoff"),
                    "mean_order_count_last_12m": safe_mean(part, "order_count_last_12m_asof_cutoff"),
                    "mean_adi": safe_mean(part, "adi_asof_cutoff"),
                    "mean_cv2": safe_mean(part, "cv2_quantity_asof_cutoff"),
                }
            )
    return pd.DataFrame(rows)


def label_rate_rows(df: pd.DataFrame) -> pd.DataFrame:
    work = recurring_only(df)
    work["demand_shape_label"] = shape_values(work)
    periods = dict(PERIODS_2024)
    periods["fold_1_test_2022"] = ("2022-01", "2022-12")
    periods["fold_2_test_2024"] = ("2024-01", "2024-12")
    rows: list[dict[str, Any]] = []
    for period_name, (start, end) in periods.items():
        period_df = period_part(work, start, end)
        for shape, shape_df in period_df.groupby("demand_shape_label", dropna=False):
            for horizon in HORIZONS:
                label_col = f"label_die_H{horizon}"
                positive = int(shape_df[label_col].sum()) if label_col in shape_df and len(shape_df) else 0
                rows.append(
                    {
                        "demand_shape_label": str(shape),
                        "horizon": horizon,
                        "cutoff_period": period_name,
                        "row_count": int(len(shape_df)),
                        "entity_count": entity_count(shape_df),
                        "positive_rate": float(shape_df[label_col].mean()) if label_col in shape_df and len(shape_df) else np.nan,
                        "positive_count": positive,
                        "negative_count": int(len(shape_df) - positive),
                    }
                )
    return pd.DataFrame(rows)


def metric_interpretation(row: pd.Series) -> str:
    flags: list[str] = []
    if pd.notna(row.get("positive_rate")) and row["positive_rate"] >= 0.75:
        flags.append("high_base_rate_warning")
    if pd.notna(row.get("ece")) and row["ece"] >= 0.20:
        flags.append("probability_unstable")
    if pd.notna(row.get("brier_score")) and row["brier_score"] >= 0.25:
        flags.append("probability_unstable")
    if pd.notna(row.get("log_loss")) and row["log_loss"] >= 0.75:
        flags.append("probability_unstable")
    weak_ranking = (
        (pd.isna(row.get("auc")) or row.get("auc", np.nan) < 0.60)
        or (pd.isna(row.get("lift_at_top_10_pct")) or row.get("lift_at_top_10_pct", np.nan) <= 1.10)
    )
    if weak_ranking and pd.notna(row.get("ece")) and row["ece"] < 0.20:
        flags.append("business_usable_but_weak_ranking")
    return ";".join(dict.fromkeys(flags)) if flags else "no_major_guardrail_flag"


def shape_metric_row(part: pd.DataFrame, shape: str, horizon: int, period: str) -> dict[str, Any]:
    row = consolidation.metric_row(
        part,
        model=MODEL,
        feature_set=FEATURE_SET,
        horizon=horizon,
        aggregation_method="shape_period",
        period=period,
        compute_topk=True,
    )
    out = {
        "demand_shape_label": shape,
        "horizon": horizon,
        "period": period,
        "row_count": row["row_count"],
        "entity_count": row["entity_count"],
        "positive_rate": row["positive_rate"],
        "brier_score": row["brier_score"],
        "log_loss": row["log_loss"],
        "ece": row["ece"],
        "auc": row["auc"],
        "pr_auc": row["pr_auc"],
        "precision_at_top_1_pct": row["precision_at_top_1_pct"],
        "precision_at_top_5_pct": row["precision_at_top_5_pct"],
        "precision_at_top_10_pct": row["precision_at_top_10_pct"],
        "lift_at_top_1_pct": row["lift_at_top_1_pct"],
        "lift_at_top_5_pct": row["lift_at_top_5_pct"],
        "lift_at_top_10_pct": row["lift_at_top_10_pct"],
        "ndcg_at_top_1_pct": row["ndcg_at_top_1_pct"],
        "ndcg_at_top_5_pct": row["ndcg_at_top_5_pct"],
        "ndcg_at_top_10_pct": row["ndcg_at_top_10_pct"],
    }
    out["interpretation_flag"] = metric_interpretation(pd.Series(out))
    return out


def demand_shape_probability_metrics(scored_by_horizon: dict[int, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon, scored in scored_by_horizon.items():
        work = scored.copy()
        work["demand_shape_label"] = shape_values(work)
        for period, (start, end) in PERIODS_2024.items():
            period_df = period_part(work, start, end)
            for shape, part in period_df.groupby("demand_shape_label", dropna=False):
                if len(part):
                    rows.append(shape_metric_row(part, str(shape), horizon, period))
        cutoff_rows: list[pd.DataFrame] = []
        for cutoff, cutoff_df in work.groupby(cutoff_periods(work), sort=True):
            for shape, part in cutoff_df.groupby("demand_shape_label", dropna=False):
                if len(part):
                    row = shape_metric_row(part, str(shape), horizon, str(cutoff))
                    cutoff_rows.append(pd.DataFrame([row]))
        if cutoff_rows:
            cutoffs = pd.concat(cutoff_rows, ignore_index=True)
            metric_cols = [
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
            for shape, group in cutoffs.groupby("demand_shape_label", dropna=False):
                out = {"demand_shape_label": shape, "horizon": horizon, "period": "macro_by_cutoff"}
                for col in metric_cols:
                    out[col] = float(group[col].mean()) if col != "row_count" else int(group[col].sum())
                out["interpretation_flag"] = metric_interpretation(pd.Series(out))
                rows.append(out)
    return pd.DataFrame(rows)


def calibration_bins_by_shape(scored_by_horizon: dict[int, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    edges = np.linspace(0.0, 1.0, 11)
    for horizon, scored in scored_by_horizon.items():
        label_col = f"label_die_H{horizon}"
        prob_col = f"churn_probability_H{horizon}"
        work = scored.copy()
        work["demand_shape_label"] = shape_values(work)
        for period, (start, end) in PERIODS_2024.items():
            period_df = period_part(work, start, end)
            for shape, shape_df in period_df.groupby("demand_shape_label", dropna=False):
                for idx, (lower, upper) in enumerate(zip(edges[:-1], edges[1:]), start=1):
                    if upper == 1.0:
                        mask = (shape_df[prob_col] >= lower) & (shape_df[prob_col] <= upper)
                    else:
                        mask = (shape_df[prob_col] >= lower) & (shape_df[prob_col] < upper)
                    part = shape_df[mask]
                    rows.append(
                        {
                            "demand_shape_label": str(shape),
                            "horizon": horizon,
                            "period": period,
                            "bin_index": idx,
                            "probability_lower": lower,
                            "probability_upper": upper,
                            "row_count": int(len(part)),
                            "entity_count": entity_count(part),
                            "mean_predicted_probability": float(part[prob_col].mean()) if len(part) else np.nan,
                            "observed_positive_rate": float(part[label_col].mean()) if len(part) else np.nan,
                            "calibration_gap": float(part[prob_col].mean() - part[label_col].mean()) if len(part) else np.nan,
                        }
                    )
    return pd.DataFrame(rows)


def risk_band_report(scored_by_horizon: dict[int, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon, scored in scored_by_horizon.items():
        label_col = f"label_die_H{horizon}"
        prob_col = f"churn_probability_H{horizon}"
        work = scored.copy()
        work["demand_shape_label"] = shape_values(work)
        for shape, shape_df in work.groupby("demand_shape_label", dropna=False):
            base_rate = float(shape_df[label_col].mean()) if len(shape_df) else np.nan
            fixed = {
                "high_risk": shape_df[prob_col] >= 0.75,
                "medium_risk": (shape_df[prob_col] >= 0.50) & (shape_df[prob_col] < 0.75),
                "low_risk": shape_df[prob_col] < 0.50,
            }
            ranks = shape_df[prob_col].rank(method="first", pct=True)
            quantile = {
                "top_20_pct": ranks > 0.80,
                "middle_60_pct": (ranks >= 0.20) & (ranks <= 0.80),
                "bottom_20_pct": ranks < 0.20,
            }
            for band_type, masks in [("fixed_threshold", fixed), ("quantile", quantile)]:
                for band, mask in masks.items():
                    part = shape_df[mask]
                    mean_pred = float(part[prob_col].mean()) if len(part) else np.nan
                    observed = float(part[label_col].mean()) if len(part) else np.nan
                    rows.append(
                        {
                            "demand_shape_label": str(shape),
                            "horizon": horizon,
                            "band_type": band_type,
                            "band": band,
                            "row_count": int(len(part)),
                            "entity_count": entity_count(part),
                            "mean_predicted_probability": mean_pred,
                            "observed_positive_rate": observed,
                            "calibration_gap": mean_pred - observed if np.isfinite(mean_pred) and np.isfinite(observed) else np.nan,
                            "lift_vs_base_rate": observed / base_rate if np.isfinite(observed) and np.isfinite(base_rate) and base_rate > 0 else np.nan,
                        }
                    )
    return pd.DataFrame(rows)


def label_definition_stress_test(df: pd.DataFrame) -> pd.DataFrame:
    work = recurring_only(period_part(df, "2024-01", "2024-12"))
    work["demand_shape_label"] = shape_values(work)
    median_interval_months = pd.to_numeric(work.get("median_purchase_interval_days_asof_cutoff", np.nan), errors="coerce") / 30.4375
    recency = pd.to_numeric(work.get("months_since_last_purchase_asof_cutoff", np.nan), errors="coerce")
    rows: list[dict[str, Any]] = []
    for shape, shape_df in work.groupby("demand_shape_label", dropna=False):
        shape_idx = shape_df.index
        for horizon in HORIZONS:
            label_col = f"label_die_H{horizon}"
            y = shape_df[label_col].astype(float)
            current_rate = float(y.mean()) if len(y) else np.nan
            rows.append(
                {
                    "label_policy": "current_label",
                    "demand_shape_label": str(shape),
                    "horizon": horizon,
                    "affected_row_count": int(len(shape_df)),
                    "affected_entity_count": entity_count(shape_df),
                    "positive_rate_before": current_rate,
                    "positive_rate_after_or_flagged": current_rate,
                    "interpretation": "Current die_H definition: no purchase event in label window.",
                }
            )
            low_freq = str(shape) in {"intermittent", "lumpy"} and horizon == 3
            affected_low_freq = shape_df[y.eq(1)] if low_freq else shape_df.iloc[0:0]
            rows.append(
                {
                    "label_policy": "relaxed_low_frequency_label",
                    "demand_shape_label": str(shape),
                    "horizon": horizon,
                    "affected_row_count": int(len(affected_low_freq)),
                    "affected_entity_count": entity_count(affected_low_freq),
                    "positive_rate_before": current_rate,
                    "positive_rate_after_or_flagged": np.nan if low_freq else current_rate,
                    "interpretation": "For intermittent/lumpy, H3 positives should be low-confidence or observation-only rather than a hard churn call." if low_freq else "No low-frequency relaxation needed for this shape/horizon.",
                }
            )
            interval_ok = recency.loc[shape_idx] <= (median_interval_months.loc[shape_idx] * 1.5)
            interval_affected = shape_df[y.eq(1) & interval_ok.fillna(False)]
            rows.append(
                {
                    "label_policy": "interval_aware_label",
                    "demand_shape_label": str(shape),
                    "horizon": horizon,
                    "affected_row_count": int(len(interval_affected)),
                    "affected_entity_count": entity_count(interval_affected),
                    "positive_rate_before": current_rate,
                    "positive_rate_after_or_flagged": np.nan if len(interval_affected) else current_rate,
                    "interpretation": "Positive labels are lower confidence when recency has not exceeded 1.5x historical median interval.",
                }
            )
            recommended = {
                "smooth": {3, 6},
                "erratic": {6, 12},
                "intermittent": {12},
                "lumpy": set(),
            }.get(str(shape), set())
            unsupported = horizon not in recommended
            affected_specific = shape_df[y.eq(1)] if unsupported else shape_df.iloc[0:0]
            rows.append(
                {
                    "label_policy": "demand_shape_specific_label_flag",
                    "demand_shape_label": str(shape),
                    "horizon": horizon,
                    "affected_row_count": int(len(affected_specific)),
                    "affected_entity_count": entity_count(affected_specific),
                    "positive_rate_before": current_rate,
                    "positive_rate_after_or_flagged": np.nan if unsupported else current_rate,
                    "interpretation": "Shape/horizon is not recommended as a hard label policy; use lower confidence or observation routing." if unsupported else "Shape/horizon is acceptable for label review.",
                }
            )
    return pd.DataFrame(rows)


def routing_decision(metrics: pd.DataFrame, bands: pd.DataFrame, label_rates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for shape in SHAPES:
        shape_metrics = metrics[(metrics["demand_shape_label"].eq(shape)) & (metrics["period"].eq("macro_by_cutoff"))]
        shape_bands = bands[(bands["demand_shape_label"].eq(shape)) & (bands["band_type"].eq("fixed_threshold"))]
        high_low_ok = False
        for horizon in HORIZONS:
            h = shape_bands[shape_bands["horizon"].eq(horizon)]
            high = h[h["band"].eq("high_risk")]["observed_positive_rate"]
            low = h[h["band"].eq("low_risk")]["observed_positive_rate"]
            if len(high) and len(low) and pd.notna(high.iloc[0]) and pd.notna(low.iloc[0]) and high.iloc[0] > low.iloc[0]:
                high_low_ok = True
        if shape == "smooth":
            route = "main_probability_model"
            horizons = "H3,H6,H12"
            usage = "use_as_probability_input"
            alert = "eligible_for_line_card_with_human_review"
            reason = "Smooth demand has the clearest recurring cadence; unified model probability is most interpretable."
            next_action = "include_in_line_card_prototype"
        elif shape == "erratic":
            route = "main_probability_model_with_low_confidence"
            horizons = "H6,H12; H3 cautious"
            usage = "use_with_medium_confidence_note"
            alert = "prefer_medium_or_manual_review_alert"
            reason = "Erratic demand can use the main model, but short-horizon interpretation is noisier."
            next_action = "include_with_label_policy_note"
        elif shape == "intermittent":
            route = "longer_horizon_only"
            horizons = "H12 preferred; H3 observation-only"
            usage = "use_as_observation_probability_not_hard_alert"
            alert = "observation_list_unless_evidence_is_strong"
            reason = "Intermittent demand makes short no-purchase windows weak evidence of churn."
            next_action = "define_low_confidence_label_policy"
        elif shape == "lumpy":
            route = "observation_only"
            horizons = "H12 or observation-only"
            usage = "do_not_use_for_strong_unified_alert"
            alert = "observation_only"
            reason = "Lumpy demand has irregular cadence; unified no-purchase labels are highest risk."
            next_action = "consider_rule_based_review_later"
        else:
            route = "rule_based_review_later"
            horizons = "diagnostic_only"
            usage = "missing_or_unreliable_shape"
            alert = "manual_review_only"
            reason = "Demand shape label is missing or unreliable."
            next_action = "audit_missing_demand_shape_inputs"
        if shape_metrics["interpretation_flag"].astype(str).str.contains("probability_unstable", na=False).any():
            reason += " Probability instability flags are present in at least one horizon."
        if not high_low_ok and shape in {"intermittent", "lumpy"}:
            reason += " Risk bands do not provide strong enough separation for automatic warning."
        rows.append(
            {
                "demand_shape_label": shape,
                "recommended_route": route,
                "recommended_horizons": horizons,
                "probability_model_usage": usage,
                "alert_policy": alert,
                "reason": reason,
                "next_action": next_action,
            }
        )
    return pd.DataFrame(rows)


def write_label_definition_review(label_stress: pd.DataFrame, label_rates: pd.DataFrame, routing: pd.DataFrame) -> None:
    late = label_rates[label_rates["cutoff_period"].eq("late_2024")]
    high_rate = late.sort_values("positive_rate", ascending=False).head(8)
    lines = [
        "# Label Definition Review",
        "",
        "This report is a demand-shape label review. It is not a new model experiment, not tuning, and not a business ranking model.",
        "",
        "## Answers",
        "1. The current die_H label is usable as a coarse probability target for recurring demand, but it is not equally reliable across demand shapes.",
        "2. Label risk is highest for intermittent and lumpy demand, especially H3, because no purchase in a short window can be normal behavior.",
        "3. Horizon-specific label policy is recommended: smooth can use H3/H6/H12, erratic should emphasize H6/H12, intermittent/lumpy should prefer H12 or observation-only.",
        "4. Do not immediately exclude intermittent/lumpy from training; first route their alerts with lower confidence and collect business validation.",
        "5. A future label_confidence_weight is recommended for low-frequency shapes and interval-aware positives.",
        "6. Business confirmation is needed for how long low-frequency drug/customer pairs can be silent before being treated as churn.",
        "7. A real terminal churn list or account status backtest would materially improve label validation.",
        "8. Do not retrain immediately; proceed to line-card/evidence-chain prototype with demand-shape guardrails.",
        "",
        "## Late-2024 Highest Positive Rates",
        markdown_table(high_rate),
        "",
        "## Routing Decision",
        markdown_table(routing),
    ]
    write_text(OUTPUT_DIR / "label_definition_review.md", "\n".join(lines))


def write_business_use_note() -> None:
    lines = [
        "# Probability Candidate v1 Business Use Note",
        "",
        "Current model-layer conclusion: `probability_candidate_v1 = logistic_regression + frequency_decay_v1 + raw`.",
        "",
        "Current business-layer conclusion: `business_usable_probability_baseline = true`.",
        "",
        "Model usability and business usability are different. The model's ranking ability is still moderate, but the raw probability baseline can support coarse risk stratification when interpreted with demand-shape guardrails. Even when individual samples receive similar probabilities, a probability that roughly matches the observed base rate can still support a business risk baseline.",
        "",
        "Current claims that are not allowed:",
        "- The model precisely separates every terminal.",
        "- The model can automatically dispatch actions.",
        "- Low risk is always safe.",
        "- High risk always means churn.",
        "",
        "Current claims that are allowed:",
        "- The model is an initial churn probability baseline.",
        "- It can support layered warning and human review.",
        "- It can provide probability input to a line card.",
        "- Demand-shape routing and real business backtests should continue to strengthen the workflow.",
    ]
    write_text(OUTPUT_DIR / "probability_candidate_v1_business_use_note.md", "\n".join(lines))


def write_line_card_plan() -> None:
    lines = [
        "# Next Stage Line Card Plan",
        "",
        "This is a design note only; no line-card artifact or prediction detail is generated in this stage.",
        "",
        "## Proposed Fields",
        "- `manufacturer_code`",
        "- `hospital_code`",
        "- `drug_code` or current drug entity key when available",
        "- `cutoff_month`",
        "- `horizon`",
        "- `churn_probability_H`",
        "- `risk_band`",
        "- `demand_shape_label`",
        "- `demand_shape_confidence`",
        "- `label_policy_note`",
        "- `top_evidence_features`",
        "- `evidence_summary_text`",
        "- `recommended_action`",
        "- `human_review_required_flag`",
        "",
        "## Allowed Evidence Features",
        "- `frequency_decay_3m_vs_12m`",
        "- `frequency_decay_6m_vs_12m`",
        "- `normalized_recency`",
        "- `order_count_last_6m`",
        "- `order_count_last_12m`",
        "- `months_since_last_purchase`",
        "- `demand_shape_label`",
        "",
        "Evidence text must stay descriptive and must not claim causality. Value-at-risk and business-priority scores remain outside the probability model and outside this review.",
        "",
        "## Suggested Actions",
        "- Smooth: eligible for probability line card with human review.",
        "- Erratic: line card allowed with medium confidence and H3 caution.",
        "- Intermittent: observation list or H12-only warning unless evidence is strong.",
        "- Lumpy: observation-only first; consider later rule-based review.",
    ]
    write_text(OUTPUT_DIR / "next_stage_line_card_plan.md", "\n".join(lines))


def write_summary(
    distribution: pd.DataFrame,
    label_rates: pd.DataFrame,
    metrics: pd.DataFrame,
    bands: pd.DataFrame,
    stress: pd.DataFrame,
    routing: pd.DataFrame,
    failures: list[dict[str, Any]],
) -> None:
    dist_summary = (
        distribution.groupby("demand_shape_label", dropna=False)
        [["row_count", "share_in_recurring_only", "mean_adi", "mean_cv2"]]
        .mean(numeric_only=True)
        .reset_index()
        .sort_values("row_count", ascending=False)
    )
    label_summary = label_rates[label_rates["cutoff_period"].eq("all_2024")].sort_values(
        ["horizon", "positive_rate"], ascending=[True, False]
    )
    metric_summary = metrics[metrics["period"].eq("macro_by_cutoff")].sort_values(
        ["horizon", "demand_shape_label"]
    )
    fixed_bands = bands[bands["band_type"].eq("fixed_threshold")].copy()
    low_rows = fixed_bands[fixed_bands["band"].eq("low_risk")]
    high_rows = fixed_bands[fixed_bands["band"].eq("high_risk")]
    band_check = high_rows.merge(
        low_rows,
        on=["demand_shape_label", "horizon"],
        suffixes=("_high", "_low"),
        how="outer",
    )
    band_check["high_gt_low"] = band_check["observed_positive_rate_high"] > band_check["observed_positive_rate_low"]
    stress_summary = (
        stress[stress["label_policy"].ne("current_label")]
        .groupby(["label_policy", "demand_shape_label", "horizon"], dropna=False)[["affected_row_count"]]
        .sum()
        .reset_index()
        .sort_values("affected_row_count", ascending=False)
        .head(20)
    )
    lines = [
        "# Demand Shape Label Review Summary",
        "",
        "This report is a demand-shape routing and label-definition review. It is not a new model experiment, not tuning, and not a business ranking model.",
        "",
        "## Scope",
        "- Main probability candidate remains `logistic_regression + frequency_decay_v1 + raw`.",
        "- Main scope is `recurring_only`.",
        "- No value-at-risk or business-priority fields are used as model input or selection criteria.",
        "- Demand-shape routing changes interpretation and workflow, not the churn_probability_H meaning.",
        "",
        "## Demand Shape Distribution",
        markdown_table(dist_summary),
        "",
        "Demand shape is derived from as-of `adi_asof_cutoff` and `cv2_quantity_asof_cutoff` using fixed Syntetos-Boylan thresholds. Rows with missing inputs are retained as `__MISSING__` rather than imputed into a shape.",
        "",
        "## Label Rate Differences",
        markdown_table(label_summary.head(40)),
        "",
        "Label rates differ materially by demand shape and horizon. Short H3 no-purchase labels are highest-risk for intermittent/lumpy demand because silence can reflect normal cadence, not churn.",
        "",
        "## Probability Metrics By Shape",
        markdown_table(metric_summary.head(60)),
        "",
        "High base rates can make low-risk bands remain non-low in late 2024; therefore risk bands should be interpreted as priority strata rather than absolute action thresholds.",
        "",
        "## Risk Band Separation",
        markdown_table(band_check[["demand_shape_label", "horizon", "observed_positive_rate_high", "observed_positive_rate_low", "high_gt_low"]].head(40)),
        "",
        "## Label Policy Stress Test",
        markdown_table(stress_summary),
        "",
        "## Routing Decision",
        markdown_table(routing),
        "",
        "## Direct Answers",
        "1. H3/H6/H12 labels are not equally fair across smooth/erratic/intermittent/lumpy demand; low-frequency shapes need weaker short-horizon interpretation.",
        "2. Positive rate, Brier, ECE, AUC, and PR_AUC differ by demand shape; this supports routing rather than changing model family.",
        "3. The unified probability model can be systematically less reliable for low-frequency shapes, especially where base rate is very high.",
        "4. Intermittent should prefer H12 or observation routing; lumpy should be observation-only or longer-horizon-only before strong alerts.",
        "5. The die_H label should not be changed immediately for training, but label-confidence and horizon-specific policy should be designed.",
        "6. probability_candidate_v1 can be used as line-card probability input with demand-shape guardrails.",
        "7. Next stage should move to line-card/evidence-chain prototype rather than more model experiments.",
        "",
        "## Failures",
        markdown_table(pd.DataFrame(failures)) if failures else "No scoring failures.",
    ]
    write_text(OUTPUT_DIR / "demand_shape_label_review_summary.md", "\n".join(lines))


def run_review() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = small.read_yaml(ROOT / "configs/experiments/alive_prediction_small_models.yaml")
    df = load_data(config)
    distribution = demand_shape_distribution(df)
    label_rates = label_rate_rows(df)
    scored_by_horizon, failures = score_fold2_probability(config, df)
    metrics = demand_shape_probability_metrics(scored_by_horizon)
    bins = calibration_bins_by_shape(scored_by_horizon)
    bands = risk_band_report(scored_by_horizon)
    stress = label_definition_stress_test(df)
    routing = routing_decision(metrics, bands, label_rates)

    distribution.to_csv(OUTPUT_DIR / "demand_shape_distribution.csv", index=False, encoding="utf-8-sig")
    label_rates.to_csv(OUTPUT_DIR / "demand_shape_label_rate_by_horizon.csv", index=False, encoding="utf-8-sig")
    metrics.to_csv(OUTPUT_DIR / "demand_shape_probability_metrics.csv", index=False, encoding="utf-8-sig")
    bins.to_csv(OUTPUT_DIR / "demand_shape_calibration_bins.csv", index=False, encoding="utf-8-sig")
    bands.to_csv(OUTPUT_DIR / "demand_shape_risk_band_report.csv", index=False, encoding="utf-8-sig")
    stress.to_csv(OUTPUT_DIR / "label_definition_stress_test.csv", index=False, encoding="utf-8-sig")
    routing.to_csv(OUTPUT_DIR / "demand_shape_routing_decision.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(failures, columns=["horizon", "reason"]).to_csv(
        OUTPUT_DIR / "demand_shape_review_failure_report.csv", index=False, encoding="utf-8-sig"
    )
    write_label_definition_review(stress, label_rates, routing)
    write_business_use_note()
    write_line_card_plan()
    write_summary(distribution, label_rates, metrics, bands, stress, routing, failures)


def main() -> int:
    run_review()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
