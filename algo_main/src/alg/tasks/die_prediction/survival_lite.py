"""M3 survival-lite / interval-aware refinement helpers.

M3 refines only recurring business-priority candidates. It does not train a
survival model, does not process one-shot candidates, and does not change
churn_probability or business-priority scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


KEY_COLS = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month"]
ENTITY_COLS = ["manufacturer_code", "hospital_code", "drug_group"]
EPSILON = 1e-6
DAYS_PER_MONTH = 30.4375


GROUP_PRIOR_DEFINITIONS: list[tuple[str, list[str]]] = [
    ("manufacturer_drug_category", ["manufacturer_code", "drug_category_code"]),
    ("hospital_level_drug_category", ["hospital_level_code", "drug_category_code"]),
    ("province_drug_category", ["province_code", "drug_category_code"]),
    ("demand_shape_drug_category", ["demand_shape_label", "drug_category_code"]),
    ("global_by_drug_category", ["drug_category_code"]),
    ("global", []),
]


@dataclass(frozen=True)
class SurvivalLiteConfig:
    interval_variance_threshold: float = 1.0
    cv2_high_threshold: float = 1.0


def normalize_cutoff_month(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "cutoff_month" in out.columns:
        out["cutoff_month"] = pd.to_datetime(out["cutoff_month"], errors="coerce").dt.to_period("M").astype(str)
    return out


def ensure_drug_group_source(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "drug_group_source" not in out.columns:
        out["drug_group_source"] = "drug_code"
    return out


def candidate_id(df: pd.DataFrame) -> pd.Series:
    cols = [c for c in KEY_COLS if c in df.columns]
    return df[cols].astype(str).agg("|".join, axis=1)


def parse_primary_horizon(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.replace("H", "", regex=False).replace("", np.nan).astype("float").astype("Int64")


def add_history_sufficiency(df: pd.DataFrame, config: SurvivalLiteConfig | None = None) -> pd.DataFrame:
    cfg = config or SurvivalLiteConfig()
    out = df.copy()
    for col in [
        "purchase_count_asof_cutoff",
        "active_month_count_asof_cutoff",
        "median_purchase_interval_days_asof_cutoff",
        "std_purchase_interval_days_asof_cutoff",
        "purchase_interval_iqr_asof_cutoff",
        "cv2_quantity_asof_cutoff",
    ]:
        if col not in out.columns:
            out[col] = np.nan
    purchase = pd.to_numeric(out["purchase_count_asof_cutoff"], errors="coerce")
    active = pd.to_numeric(out["active_month_count_asof_cutoff"], errors="coerce")
    median = pd.to_numeric(out["median_purchase_interval_days_asof_cutoff"], errors="coerce")
    std = pd.to_numeric(out["std_purchase_interval_days_asof_cutoff"], errors="coerce")
    iqr = pd.to_numeric(out["purchase_interval_iqr_asof_cutoff"], errors="coerce")
    cv2 = pd.to_numeric(out["cv2_quantity_asof_cutoff"], errors="coerce")
    sufficient_base = purchase.ge(3) & active.ge(2) & median.notna()
    high_variance = (
        (std.notna() & median.gt(0) & (std / median).gt(cfg.interval_variance_threshold))
        | (iqr.notna() & median.gt(0) & (iqr / median).gt(cfg.interval_variance_threshold))
        | cv2.gt(cfg.cv2_high_threshold)
    )
    flag = pd.Series("history_sufficient", index=out.index, dtype="object")
    reason = pd.Series("entity_interval_available", index=out.index, dtype="object")
    medium = sufficient_base & high_variance
    flag.loc[medium] = "history_medium"
    reason.loc[medium] = "interval_variance_or_cv2_high"
    insufficient = purchase.lt(3) | active.lt(2) | median.isna()
    flag.loc[insufficient] = "history_insufficient"
    reason.loc[purchase.lt(3)] = "purchase_count_asof_cutoff_lt_3"
    reason.loc[active.lt(2)] = "active_month_count_asof_cutoff_lt_2"
    reason.loc[median.isna()] = "median_purchase_interval_missing"
    one_shot = out.get("one_shot_flag", pd.Series(False, index=out.index)).fillna(False).astype(bool)
    flag.loc[one_shot] = "one_shot"
    reason.loc[one_shot] = "one_shot_not_applicable_for_m3"
    out["history_sufficiency_flag"] = flag
    out["history_sufficiency_reason"] = reason
    return out


def demand_shape_route_fields(shape: str | float | None) -> dict[str, object]:
    label = "__MISSING__" if pd.isna(shape) else str(shape)
    mapping = {
        "smooth": {
            "survival_method": "entity_interval",
            "confidence_multiplier": 1.0,
            "allowed_horizons": "H3,H6,H12",
            "alert_policy": "normal_probability_alert",
            "demand_shape_route": "main_probability_model",
        },
        "erratic": {
            "survival_method": "entity_interval_with_lower_confidence",
            "confidence_multiplier": 0.75,
            "allowed_horizons": "H6,H12_preferred_H3_cautious",
            "alert_policy": "review_required",
            "demand_shape_route": "main_probability_model_with_low_confidence",
        },
        "intermittent": {
            "survival_method": "group_prior_or_long_horizon",
            "confidence_multiplier": 0.6,
            "allowed_horizons": "H12_preferred_H3_observation_only",
            "alert_policy": "observation_or_manual_review",
            "demand_shape_route": "longer_horizon_only",
        },
        "lumpy": {
            "survival_method": "observation_only",
            "confidence_multiplier": 0.4,
            "allowed_horizons": "H12_or_later",
            "alert_policy": "no_strong_alert_without_extra_evidence",
            "demand_shape_route": "observation_only",
        },
    }
    return mapping.get(
        label,
        {
            "survival_method": "unknown",
            "confidence_multiplier": 0.5,
            "allowed_horizons": "manual_review",
            "alert_policy": "manual_review_required",
            "demand_shape_route": "unknown",
        },
    )


def add_demand_shape_route(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "demand_shape_label" not in out.columns:
        out["demand_shape_label"] = "__MISSING__"
    routes = [demand_shape_route_fields(x) for x in out["demand_shape_label"]]
    route_df = pd.DataFrame(routes, index=out.index)
    for col in route_df.columns:
        out[col] = route_df[col]
    out["demand_shape_adjustment"] = out["demand_shape_label"].astype(str) + ":" + out["alert_policy"].astype(str)
    return out


def compute_group_prior_intervals(feature_df: pd.DataFrame) -> pd.DataFrame:
    if feature_df is None or feature_df.empty:
        return pd.DataFrame(
            columns=[
                "cutoff_month",
                "group_name",
                "group_key",
                "group_count",
                "median_interval_days",
                "mean_interval_days",
                "prior_source",
                "data_quality_note",
            ]
        )
    feat = normalize_cutoff_month(ensure_drug_group_source(feature_df))
    interval_col = "median_purchase_interval_days_asof_cutoff"
    if interval_col not in feat.columns:
        return pd.DataFrame()
    rows: list[pd.DataFrame] = []
    for group_name, cols in GROUP_PRIOR_DEFINITIONS:
        if cols and not set(cols).issubset(feat.columns):
            continue
        group_cols = ["cutoff_month"] + cols
        work = feat[feat[interval_col].notna()].copy()
        if work.empty:
            continue
        grouped = (
            work.groupby(group_cols, dropna=False)[interval_col]
            .agg(group_count="count", median_interval_days="median", mean_interval_days="mean")
            .reset_index()
        )
        grouped["group_name"] = group_name
        if cols:
            grouped["group_key"] = grouped[cols].astype(str).agg("|".join, axis=1)
        else:
            grouped["group_key"] = "global"
        grouped["prior_source"] = group_name
        grouped["data_quality_note"] = "asof_cutoff_feature_aggregate"
        rows.append(
            grouped[
                [
                    "cutoff_month",
                    "group_name",
                    "group_key",
                    "group_count",
                    "median_interval_days",
                    "mean_interval_days",
                    "prior_source",
                    "data_quality_note",
                ]
            ]
        )
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def attach_best_group_prior(candidates: pd.DataFrame, prior_report: pd.DataFrame) -> pd.DataFrame:
    out = candidates.copy()
    out["group_prior_interval_days"] = np.nan
    out["group_prior_source"] = ""
    out["group_prior_group_count"] = np.nan
    if prior_report.empty:
        return out
    for group_name, cols in GROUP_PRIOR_DEFINITIONS:
        if not set(["cutoff_month", *cols]).issubset(out.columns):
            continue
        pri = prior_report[prior_report["group_name"].eq(group_name)].copy()
        if pri.empty:
            continue
        if cols:
            temp = out[["cutoff_month", *cols]].copy()
            temp["group_key"] = temp[cols].astype(str).agg("|".join, axis=1)
        else:
            temp = out[["cutoff_month"]].copy()
            temp["group_key"] = "global"
        temp["_idx"] = out.index
        merged = temp.merge(
            pri[["cutoff_month", "group_key", "median_interval_days", "group_count", "prior_source"]],
            on=["cutoff_month", "group_key"],
            how="left",
        ).set_index("_idx")
        mask = out["group_prior_interval_days"].isna() & merged["median_interval_days"].notna()
        out.loc[mask.index[mask], "group_prior_interval_days"] = merged.loc[mask, "median_interval_days"]
        out.loc[mask.index[mask], "group_prior_source"] = group_name
        out.loc[mask.index[mask], "group_prior_group_count"] = merged.loc[mask, "group_count"]
    return out


def expected_interval_days(row: pd.Series) -> tuple[float, str, str]:
    flag = row.get("history_sufficiency_flag")
    median = pd.to_numeric(pd.Series([row.get("median_purchase_interval_days_asof_cutoff")]), errors="coerce").iloc[0]
    prior = pd.to_numeric(pd.Series([row.get("group_prior_interval_days")]), errors="coerce").iloc[0]
    purchase = pd.to_numeric(pd.Series([row.get("purchase_count_asof_cutoff")]), errors="coerce").iloc[0]
    if flag == "history_sufficient":
        return float(median), "entity_median_interval", ""
    if flag == "history_medium":
        if pd.notna(median) and pd.notna(prior):
            w_entity = min(1.0, float(purchase) / 6.0) if pd.notna(purchase) else 0.5
            return float(w_entity * median + (1 - w_entity) * prior), "entity_group_mixed_interval", "mixed_entity_group_prior"
        if pd.notna(median):
            return float(median), "entity_median_interval_low_confidence", "entity_interval_only_no_prior"
        if pd.notna(prior):
            return float(prior), "group_prior_only", "group_prior_interval"
    if pd.notna(prior):
        return float(prior), "group_prior_only", "group_prior_interval"
    return np.nan, "unavailable", "insufficient_history_no_prior"


def compute_expected_interval(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    values = out.apply(expected_interval_days, axis=1, result_type="expand")
    values.columns = ["expected_interval_days", "expected_interval_source", "fallback_method"]
    out = pd.concat([out, values], axis=1)
    out["expected_interval_months"] = pd.to_numeric(out["expected_interval_days"], errors="coerce") / DAYS_PER_MONTH
    return out


def compute_survival_metrics(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    months = pd.to_numeric(
        out.get("months_since_last_purchase_asof_cutoff", out.get("months_since_last_purchase", pd.Series(np.nan, index=out.index))),
        errors="coerce",
    )
    out["months_since_last_purchase"] = months
    expected = pd.to_numeric(out["expected_interval_months"], errors="coerce")
    out["overdue_ratio"] = months / np.maximum(expected, EPSILON)
    out.loc[expected.isna() | months.isna(), "overdue_ratio"] = np.nan
    out["overdue_gap_months"] = months - expected
    out["interval_percentile"] = np.nan
    return out


def assign_survival_state(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    state = pd.Series("insufficient_interval_data", index=out.index, dtype="object")
    ratio = pd.to_numeric(out["overdue_ratio"], errors="coerce")
    state.loc[ratio.lt(0.8)] = "normal_interval"
    state.loc[ratio.ge(0.8) & ratio.lt(1.2)] = "near_expected_interval"
    state.loc[ratio.ge(1.2) & ratio.lt(2.0)] = "slightly_overdue"
    state.loc[ratio.ge(2.0) & ratio.lt(3.0)] = "materially_overdue"
    state.loc[ratio.ge(3.0)] = "likely_churn_interval"
    state.loc[ratio.isna()] = "insufficient_interval_data"
    state.loc[out["demand_shape_label"].astype(str).eq("lumpy")] = "low_confidence_lumpy"
    state.loc[out["history_sufficiency_flag"].astype(str).eq("history_insufficient")] = "insufficient_history"
    state.loc[out["history_sufficiency_flag"].astype(str).eq("one_shot")] = "not_applicable_one_shot"
    out["survival_state"] = state
    return out


def compute_survival_confidence(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    purchase = pd.to_numeric(out.get("purchase_count_asof_cutoff", pd.Series(np.nan, index=out.index)), errors="coerce")
    base = (purchase / 6.0).clip(lower=0, upper=1).fillna(0)
    multiplier = pd.to_numeric(out.get("confidence_multiplier", pd.Series(0.5, index=out.index)), errors="coerce").fillna(0.5)
    confidence = base * multiplier
    max_conf = pd.Series(1.0, index=out.index)
    max_conf.loc[out["history_sufficiency_flag"].ne("history_sufficient")] = 0.4
    max_conf.loc[out["expected_interval_source"].eq("group_prior_only")] = np.minimum(
        max_conf.loc[out["expected_interval_source"].eq("group_prior_only")], 0.5
    )
    out["survival_confidence"] = np.minimum(confidence, max_conf)
    return out


def human_review_required(df: pd.DataFrame) -> pd.Series:
    warnings = df.get("data_quality_note", pd.Series("", index=df.index)).fillna("").astype(str).ne("")
    return (
        df["survival_state"].isin(["materially_overdue", "likely_churn_interval"])
        | df["demand_shape_label"].astype(str).isin(["erratic", "intermittent", "lumpy"])
        | df["history_sufficiency_flag"].ne("history_sufficient")
        | warnings
        | pd.to_numeric(df["survival_confidence"], errors="coerce").lt(0.7)
    )


def refine_survival(candidates: pd.DataFrame, features: pd.DataFrame | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = normalize_cutoff_month(ensure_drug_group_source(candidates))
    base = base.copy()
    base["horizon"] = parse_primary_horizon(base.get("primary_horizon", pd.Series("", index=base.index)))
    base["churn_probability_H"] = base.get("primary_churn_probability", np.nan)
    base["relative_business_priority_score_H"] = base.get("primary_relative_business_priority_score", np.nan)
    base["relative_value_at_risk_H"] = base.get("primary_relative_value_at_risk", np.nan)
    if "candidate_id" not in base.columns:
        base["candidate_id"] = candidate_id(base)
    if features is not None and not features.empty:
        feat = normalize_cutoff_month(ensure_drug_group_source(features))
        join_cols = [c for c in KEY_COLS if c in feat.columns and c in base.columns]
        keep_cols = join_cols + [
            c
            for c in [
                "months_since_last_purchase_asof_cutoff",
                "purchase_count_asof_cutoff",
                "active_month_count_asof_cutoff",
                "months_observed_asof_cutoff",
                "adi_asof_cutoff",
                "cv2_quantity_asof_cutoff",
                "median_purchase_interval_days_asof_cutoff",
                "mean_purchase_interval_days_asof_cutoff",
                "std_purchase_interval_days_asof_cutoff",
                "purchase_interval_iqr_asof_cutoff",
                "order_count_last_3m_asof_cutoff",
                "order_count_last_6m_asof_cutoff",
                "order_count_last_12m_asof_cutoff",
                "drug_category_code",
                "province_code",
                "hospital_level_code",
                "one_shot_flag",
                "demand_pattern_type_asof_cutoff",
            ]
            if c in feat.columns
        ]
        base = base.merge(feat[keep_cols].drop_duplicates(join_cols), on=join_cols, how="left")
    if "demand_shape_label" not in base.columns or base["demand_shape_label"].isna().all():
        base["demand_shape_label"] = base.get("demand_pattern_type_asof_cutoff", "__MISSING__")
    prior_report = compute_group_prior_intervals(features if features is not None else pd.DataFrame())
    out = add_demand_shape_route(add_history_sufficiency(base))
    out = attach_best_group_prior(out, prior_report)
    out = compute_expected_interval(out)
    out = compute_survival_metrics(out)
    out = assign_survival_state(out)
    out = compute_survival_confidence(out)
    out["data_quality_note"] = ""
    missing_interval = out["expected_interval_source"].eq("unavailable")
    out.loc[missing_interval, "data_quality_note"] = "expected_interval_unavailable"
    one_shot = out["history_sufficiency_flag"].eq("one_shot")
    out.loc[one_shot, "data_quality_note"] = "one_shot_input_excluded_from_m3"
    out["human_review_required"] = human_review_required(out)
    out["survival_note"] = (
        "survival_state_is_interval_refinement_not_final_churn; probability_and_business_priority_unchanged"
    )
    return out[~one_shot].reset_index(drop=True), prior_report


def format_survival_results(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "candidate_id",
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "drug_group_source",
        "cutoff_month",
        "horizon",
        "churn_probability_H",
        "relative_business_priority_score_H",
        "relative_value_at_risk_H",
        "survival_method",
        "expected_interval_months",
        "expected_interval_source",
        "months_since_last_purchase",
        "overdue_ratio",
        "overdue_gap_months",
        "interval_percentile",
        "survival_state",
        "survival_confidence",
        "demand_shape_label",
        "demand_shape_route",
        "demand_shape_adjustment",
        "history_sufficiency_flag",
        "fallback_method",
        "survival_note",
        "human_review_required",
        "data_quality_note",
    ]
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = np.nan
    return out[columns]
