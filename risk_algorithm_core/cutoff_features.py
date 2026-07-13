"""Source-of-truth cutoff feature construction.

The core logic is migrated from the verified exploration rebuild flow and kept
free of exploration-workspace imports. Choice-set context is deliberately
optional; the current production artifact excludes choice-set features from the
main model.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .facts import ENTITY_KEYS


HORIZONS = [3, 6, 12]


def add_months(ts: pd.Timestamp, months: int) -> pd.Timestamp:
    return pd.Timestamp(ts) + pd.DateOffset(months=months)


def to_month_end(value: Any) -> pd.Timestamp:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return pd.NaT
    return parsed.to_period("M").to_timestamp("M")


def build_source_cutoff_features(
    entity_month: pd.DataFrame,
    cutoff_months: list[pd.Timestamp],
    *,
    max_monitor_gap_months: int = 12,
    include_choice_context: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if entity_month.empty or not cutoff_months:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    monthly = entity_month.copy()
    monthly["purchase_month"] = pd.to_datetime(monthly["purchase_month"], errors="coerce")
    monthly = monthly.sort_values(ENTITY_KEYS + ["purchase_month"]).reset_index(drop=True)
    monthly["previous_purchase_month"] = monthly.groupby(ENTITY_KEYS, dropna=False)["purchase_month"].shift(1)
    monthly["gap_days"] = (monthly["purchase_month"] - monthly["previous_purchase_month"]).dt.days

    parts: list[pd.DataFrame] = []
    unmonitorable_parts: list[pd.DataFrame] = []
    report_rows: list[dict[str, Any]] = []
    for cutoff in cutoff_months:
        cutoff_ts = to_month_end(cutoff)
        part = build_features_for_cutoff(
            monthly,
            cutoff_ts,
            max_monitor_gap_months=max_monitor_gap_months,
            include_choice_context=include_choice_context,
        )
        audit = part.attrs.get("unmonitorable_purchase_relationships")
        if isinstance(audit, pd.DataFrame) and not audit.empty:
            unmonitorable_parts.append(audit)
        part.attrs.pop("unmonitorable_purchase_relationships", None)
        report_rows.append(
            {
                "cutoff_month": cutoff_ts,
                "all_seen_entity_count": int(part.attrs.get("all_seen_entity_count", len(part))),
                "monitorable_entity_count": int(len(part)),
                "excluded_by_monitor_gap_count": int(part.attrs.get("excluded_by_monitor_gap_count", 0)),
                "unmonitorable_entity_count": int(part.attrs.get("unmonitorable_entity_count", 0)),
                "one_shot_entity_count": int(part.attrs.get("one_shot_entity_count", 0)),
                "recurring_entity_count": int(part.attrs.get("recurring_entity_count", 0)),
            }
        )
        if not part.empty:
            parts.append(part)
    features = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    for attr_name in [
        "all_seen_entity_count",
        "monitorable_entity_count",
        "excluded_by_monitor_gap_count",
        "unmonitorable_entity_count",
        "one_shot_entity_count",
        "recurring_entity_count",
    ]:
        features.attrs[attr_name] = int(pd.to_numeric(pd.DataFrame(report_rows).get(attr_name, pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    demand_cols = [
        *ENTITY_KEYS,
        "cutoff_month",
        "purchase_count_asof_cutoff",
        "active_month_count_asof_cutoff",
        "months_observed_asof_cutoff",
        "active_month_ratio_asof_cutoff",
        "median_purchase_interval_days_asof_cutoff",
        "mean_purchase_interval_days_asof_cutoff",
        "std_purchase_interval_days_asof_cutoff",
        "purchase_interval_iqr_asof_cutoff",
        "adi_asof_cutoff",
        "cv2_quantity_asof_cutoff",
        "seasonality_strength_asof_cutoff",
        "burstiness_score_asof_cutoff",
        "cold_start_flag",
        "confidence_score",
        "demand_pattern_type_asof_cutoff",
    ]
    demand_profile = features[[c for c in demand_cols if c in features.columns]].copy() if not features.empty else pd.DataFrame(columns=demand_cols)
    cutoff_report = pd.DataFrame(report_rows)
    if unmonitorable_parts:
        cutoff_report.attrs["unmonitorable_purchase_relationships"] = pd.concat(unmonitorable_parts, ignore_index=True)
    return features, demand_profile, cutoff_report


def build_features_for_cutoff(
    monthly: pd.DataFrame,
    cutoff_ts: pd.Timestamp,
    *,
    max_monitor_gap_months: int = 12,
    include_choice_context: bool = False,
) -> pd.DataFrame:
    hist = monthly[monthly["purchase_month"].le(cutoff_ts)].copy()
    if hist.empty:
        return pd.DataFrame()
    grouped = hist.groupby(ENTITY_KEYS, dropna=False)
    base = grouped.agg(
        purchase_count_asof_cutoff=("order_count", "sum"),
        active_month_count_asof_cutoff=("purchase_month", "nunique"),
        first_purchase_month_asof_cutoff=("purchase_month", "min"),
        last_purchase_month_asof_cutoff=("purchase_month", "max"),
    ).reset_index()
    base["cutoff_month"] = cutoff_ts
    base["first_purchase_month"] = base["first_purchase_month_asof_cutoff"]
    base["last_purchase_month_asof_cutoff"] = pd.to_datetime(base["last_purchase_month_asof_cutoff"], errors="coerce")
    base["months_since_last_purchase"] = month_diff_series(cutoff_ts, base["last_purchase_month_asof_cutoff"])
    base["months_since_last_purchase_asof_cutoff"] = base["months_since_last_purchase"]
    base["months_observed_asof_cutoff"] = month_diff_series(cutoff_ts, base["first_purchase_month_asof_cutoff"]) + 1
    base["months_since_first_purchase_asof_cutoff"] = month_diff_series(cutoff_ts, base["first_purchase_month_asof_cutoff"])
    if pd.to_numeric(base["active_month_count_asof_cutoff"], errors="coerce").lt(1).any():
        raise ValueError("active_month_count_asof_cutoff must be >= 1 for all seen purchase relationships.")
    base["sample_class"] = classify_monthly_sample_scope(
        base["months_since_last_purchase_asof_cutoff"],
        base["active_month_count_asof_cutoff"],
        max_monitor_gap_months=max_monitor_gap_months,
    )
    all_seen = len(base)
    unmonitorable_audit = _unmonitorable_audit_rows(base)
    features = base[base["sample_class"].ne("unmonitorable")].copy()
    features.attrs["all_seen_entity_count"] = all_seen
    features.attrs["monitorable_entity_count"] = int(len(features))
    features.attrs["excluded_by_monitor_gap_count"] = all_seen - len(features)
    features.attrs["unmonitorable_entity_count"] = int(base["sample_class"].eq("unmonitorable").sum())
    features.attrs["one_shot_entity_count"] = int(base["sample_class"].eq("one_shot").sum())
    features.attrs["recurring_entity_count"] = int(base["sample_class"].eq("recurring").sum())
    features.attrs["unmonitorable_purchase_relationships"] = unmonitorable_audit
    features["candidate_policy"] = "monitorable"
    features["days_since_last_purchase"] = features["months_since_last_purchase"] * 30.4375
    for months in [1, 3, 6, 12]:
        win = hist[hist["purchase_month"].ge(add_months(cutoff_ts, -(months - 1)))]
        features = features.merge(window_aggregate(win, months), on=ENTITY_KEYS, how="left")
    features = merge_latest_static_status(features, hist)
    features = merge_interval_demand(features, hist)
    if include_choice_context:
        features = merge_choice_context_for_cutoff(features, hist)
    features = finalize_feature_columns(features).reset_index(drop=True)
    features.attrs["all_seen_entity_count"] = all_seen
    features.attrs["monitorable_entity_count"] = int(len(features))
    features.attrs["excluded_by_monitor_gap_count"] = all_seen - len(features)
    features.attrs["unmonitorable_entity_count"] = int(base["sample_class"].eq("unmonitorable").sum())
    features.attrs["one_shot_entity_count"] = int(base["sample_class"].eq("one_shot").sum())
    features.attrs["recurring_entity_count"] = int(base["sample_class"].eq("recurring").sum())
    features.attrs["unmonitorable_purchase_relationships"] = unmonitorable_audit
    return features


def _unmonitorable_audit_rows(base: pd.DataFrame) -> pd.DataFrame:
    cols = [
        *ENTITY_KEYS,
        "cutoff_month",
        "first_purchase_month_asof_cutoff",
        "last_purchase_month_asof_cutoff",
        "purchase_count_asof_cutoff",
        "active_month_count_asof_cutoff",
        "months_since_last_purchase_asof_cutoff",
        "months_observed_asof_cutoff",
        "sample_class",
    ]
    available = [col for col in cols if col in base.columns]
    return base[base["sample_class"].eq("unmonitorable")][available].copy()


def classify_monthly_sample_scope(
    months_since_last_purchase: pd.Series,
    active_month_count: pd.Series,
    *,
    max_monitor_gap_months: int = 12,
) -> pd.Series:
    gap = pd.to_numeric(months_since_last_purchase, errors="coerce")
    active = pd.to_numeric(active_month_count, errors="coerce")
    if active.lt(1).any():
        raise ValueError("active_month_count_asof_cutoff must be >= 1 for all seen purchase relationships.")
    return pd.Series(
        np.select(
            [
                gap.gt(max_monitor_gap_months),
                active.eq(1),
                active.ge(2),
            ],
            ["unmonitorable", "one_shot", "recurring"],
            default="data_integrity_error",
        ),
        index=active.index,
    )


def month_diff_series(cutoff_ts: pd.Timestamp, values: pd.Series) -> pd.Series:
    vals = pd.to_datetime(values, errors="coerce")
    return (cutoff_ts.year - vals.dt.year) * 12 + (cutoff_ts.month - vals.dt.month)


def window_aggregate(win: pd.DataFrame, months: int) -> pd.DataFrame:
    if win.empty:
        return pd.DataFrame(columns=ENTITY_KEYS)
    grouped = win.groupby(ENTITY_KEYS, dropna=False)
    named_aggs: dict[str, tuple[str, str]] = {
        f"order_count_last_{months}m_asof_cutoff": ("order_count", "sum"),
        f"active_months_last_{months}m_asof_cutoff": ("purchase_month", "nunique"),
    }
    for source, target_prefix in [
        ("purchase_quantity_sum", "purchase_quantity_sum"),
        ("purchase_amount_sum", "purchase_amount_sum"),
        ("failed_count", "failed_count"),
        ("received_count", "received_count"),
        ("terminal_count", "terminal_count"),
    ]:
        if source in win.columns:
            named_aggs[f"{target_prefix}_last_{months}m_asof_cutoff"] = (source, "sum")
    return grouped.agg(**named_aggs).reset_index()


def merge_latest_static_status(features: pd.DataFrame, hist: pd.DataFrame) -> pd.DataFrame:
    latest = hist.sort_values("purchase_month").groupby(ENTITY_KEYS, dropna=False).tail(1)
    static_cols = [
        "province_code",
        "city_code",
        "county_code",
        "hospital_level_code",
        "ownership_type_code",
        "drug_category_code",
        "last_order_phase_code_in_month",
        "last_delivery_state_code_in_month",
        "last_order_failure_flag_in_month",
    ]
    existing = [c for c in static_cols if c in latest.columns]
    if not existing:
        return features
    latest = latest[ENTITY_KEYS + existing].rename(
        columns={
            "last_order_phase_code_in_month": "last_order_phase_code_asof_cutoff",
            "last_delivery_state_code_in_month": "last_delivery_state_code_asof_cutoff",
            "last_order_failure_flag_in_month": "last_order_failure_flag_asof_cutoff",
        }
    )
    return features.merge(latest, on=ENTITY_KEYS, how="left")


def merge_interval_demand(features: pd.DataFrame, hist: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    out["active_month_ratio_asof_cutoff"] = out["active_month_count_asof_cutoff"] / out["months_observed_asof_cutoff"].replace(0, np.nan)
    out["adi_asof_cutoff"] = out["months_observed_asof_cutoff"] / out["active_month_count_asof_cutoff"].replace(0, np.nan)
    gaps = hist[hist["gap_days"].notna()]
    if not gaps.empty:
        interval = (
            gaps.groupby(ENTITY_KEYS, dropna=False)["gap_days"]
            .agg(
                median_purchase_interval_days_asof_cutoff="median",
                mean_purchase_interval_days_asof_cutoff="mean",
                std_purchase_interval_days_asof_cutoff="std",
                q25=lambda s: s.quantile(0.25),
                q75=lambda s: s.quantile(0.75),
            )
            .reset_index()
        )
        interval["purchase_interval_iqr_asof_cutoff"] = interval["q75"] - interval["q25"]
        interval = interval.drop(columns=["q25", "q75"])
        out = out.merge(interval, on=ENTITY_KEYS, how="left")
    else:
        for col in [
            "median_purchase_interval_days_asof_cutoff",
            "mean_purchase_interval_days_asof_cutoff",
            "std_purchase_interval_days_asof_cutoff",
            "purchase_interval_iqr_asof_cutoff",
        ]:
            out[col] = np.nan
    if "purchase_quantity_sum" in hist.columns:
        q = hist.groupby(ENTITY_KEYS, dropna=False)["purchase_quantity_sum"].agg(["mean", "std"]).reset_index()
        q["cv2_quantity_asof_cutoff"] = (q["std"] / q["mean"].replace(0, np.nan)) ** 2
        out = out.merge(q[ENTITY_KEYS + ["cv2_quantity_asof_cutoff"]], on=ENTITY_KEYS, how="left")
    else:
        out["cv2_quantity_asof_cutoff"] = np.nan
    out["seasonality_strength_asof_cutoff"] = np.nan
    out["burstiness_score_asof_cutoff"] = np.nan
    out["cold_start_flag"] = (
        out["purchase_count_asof_cutoff"].lt(3)
        | out["active_month_count_asof_cutoff"].lt(2)
        | out["months_observed_asof_cutoff"].lt(3)
    )
    out["confidence_score"] = (out["purchase_count_asof_cutoff"] / 12).clip(upper=1.0)
    out["demand_pattern_type_asof_cutoff"] = np.select(
        [
            out["cold_start_flag"],
            out["adi_asof_cutoff"].le(1.32) & out["cv2_quantity_asof_cutoff"].le(0.49),
            out["adi_asof_cutoff"].le(1.32) & out["cv2_quantity_asof_cutoff"].gt(0.49),
            out["adi_asof_cutoff"].gt(1.32) & out["cv2_quantity_asof_cutoff"].le(0.49),
            out["adi_asof_cutoff"].gt(1.32) & out["cv2_quantity_asof_cutoff"].gt(0.49),
        ],
        ["cold_start", "smooth", "erratic", "intermittent", "lumpy"],
        default="unknown",
    )
    out["demand_shape_label"] = out["demand_pattern_type_asof_cutoff"]
    out["history_sufficiency_flag"] = np.select(
        [
            out["purchase_count_asof_cutoff"].lt(3)
            | out["active_month_count_asof_cutoff"].lt(2)
            | out["months_observed_asof_cutoff"].lt(3),
            out["purchase_count_asof_cutoff"].ge(6)
            & out["active_month_count_asof_cutoff"].ge(4)
            & out["months_observed_asof_cutoff"].ge(12),
        ],
        ["history_insufficient", "history_sufficient"],
        default="history_medium",
    )
    return out


def merge_choice_context_for_cutoff(features: pd.DataFrame, hist: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    pair_cols = ["hospital_code", "drug_group"]
    pair_total = (
        hist.groupby(pair_cols, dropna=False)
        .agg(
            hospital_drug_order_count_asof_cutoff=("order_count", "sum"),
            hospital_drug_active_manufacturer_count_asof_cutoff=("manufacturer_code", "nunique"),
        )
        .reset_index()
    )
    cutoff = out["cutoff_month"].iloc[0]
    pair_12 = (
        hist[hist["purchase_month"].ge(add_months(cutoff, -11))]
        .groupby(pair_cols, dropna=False)["order_count"]
        .sum()
        .reset_index(name="hospital_drug_order_count_last_12m_asof_cutoff")
    )
    pair_3 = (
        hist[hist["purchase_month"].ge(add_months(cutoff, -2))]
        .groupby(pair_cols, dropna=False)["order_count"]
        .sum()
        .reset_index(name="hospital_drug_order_count_last_3m_asof_cutoff")
    )
    out = out.merge(pair_total, on=pair_cols, how="left").merge(pair_12, on=pair_cols, how="left").merge(pair_3, on=pair_cols, how="left")
    entity_orders = pd.to_numeric(out["purchase_count_asof_cutoff"], errors="coerce")
    total_orders = pd.to_numeric(out["hospital_drug_order_count_asof_cutoff"], errors="coerce")
    out["manufacturer_share_within_hospital_drug_asof_cutoff"] = entity_orders / total_orders.replace(0, np.nan)
    out["competitor_order_count_asof_cutoff"] = (total_orders - entity_orders).clip(lower=0)
    out["competitor_order_count_last_12m_asof_cutoff"] = (
        pd.to_numeric(out["hospital_drug_order_count_last_12m_asof_cutoff"], errors="coerce")
        - pd.to_numeric(out.get("order_count_last_12m_asof_cutoff"), errors="coerce")
    ).clip(lower=0)
    out["competitor_order_count_last_3m_asof_cutoff"] = (
        pd.to_numeric(out["hospital_drug_order_count_last_3m_asof_cutoff"], errors="coerce")
        - pd.to_numeric(out.get("order_count_last_3m_asof_cutoff"), errors="coerce")
    ).clip(lower=0)
    out["manufacturer_substitution_context_available"] = pd.to_numeric(out["hospital_drug_active_manufacturer_count_asof_cutoff"], errors="coerce").gt(1)
    return out


def finalize_feature_columns(features: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    for col in out.columns:
        if col.startswith(
            (
                "order_count_last_",
                "active_months_last_",
                "purchase_quantity_sum_last_",
                "purchase_amount_sum_last_",
                "failed_count_last_",
                "received_count_last_",
                "terminal_count_last_",
            )
        ):
            out[col] = out[col].fillna(0)
    for col in ["purchase_amount_sum_last_12m_asof_cutoff", "purchase_quantity_sum_last_12m_asof_cutoff"]:
        if col not in out.columns:
            out[col] = 0.0
    out["historical_avg_monthly_amount_asof_cutoff"] = pd.to_numeric(out["purchase_amount_sum_last_12m_asof_cutoff"], errors="coerce").fillna(0) / 12
    out["historical_avg_monthly_quantity_asof_cutoff"] = pd.to_numeric(out["purchase_quantity_sum_last_12m_asof_cutoff"], errors="coerce").fillna(0) / 12
    if out["historical_avg_monthly_amount_asof_cutoff"].nunique(dropna=True) >= 3:
        out["entity_value_tier_asof_cutoff"] = pd.qcut(
            out["historical_avg_monthly_amount_asof_cutoff"].rank(method="first"),
            q=3,
            labels=["low", "mid", "high"],
            duplicates="drop",
        ).astype("string")
    else:
        out["entity_value_tier_asof_cutoff"] = "known_value"
    out["negative_value_at_risk_amount_flag"] = out["historical_avg_monthly_amount_asof_cutoff"] < 0
    out["negative_value_at_risk_quantity_flag"] = out["historical_avg_monthly_quantity_asof_cutoff"] < 0
    for horizon in HORIZONS:
        out[f"value_at_risk_amount_raw_H{horizon}_asof_cutoff"] = out["historical_avg_monthly_amount_asof_cutoff"] * horizon
        out[f"value_at_risk_quantity_raw_H{horizon}_asof_cutoff"] = out["historical_avg_monthly_quantity_asof_cutoff"] * horizon
        out[f"value_at_risk_amount_nonnegative_H{horizon}_asof_cutoff"] = out[f"value_at_risk_amount_raw_H{horizon}_asof_cutoff"].clip(lower=0)
        out[f"value_at_risk_quantity_nonnegative_H{horizon}_asof_cutoff"] = out[f"value_at_risk_quantity_raw_H{horizon}_asof_cutoff"].clip(lower=0)
    out["one_shot_flag"] = out["active_month_count_asof_cutoff"].eq(1)
    out["one_shot_silence_months"] = out["months_since_last_purchase_asof_cutoff"]
    out["drug_group_source"] = "drug_code"
    return out


def add_baseline_scores(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["recency_only_baseline"] = pd.to_numeric(out.get("months_since_last_purchase_asof_cutoff"), errors="coerce")
    recent_3 = pd.to_numeric(out.get("order_count_last_3m_asof_cutoff"), errors="coerce") / 3.0
    recent_12 = pd.to_numeric(out.get("order_count_last_12m_asof_cutoff"), errors="coerce") / 12.0
    out["frequency_decay_baseline"] = 1.0 - (recent_3 / recent_12.replace(0, np.nan))
    expected_interval = pd.to_numeric(out.get("median_purchase_interval_days_asof_cutoff"), errors="coerce") / 30.4375
    months_since = pd.to_numeric(out.get("months_since_last_purchase_asof_cutoff"), errors="coerce")
    out["interval_overdue_baseline"] = months_since / expected_interval.where(expected_interval > 0)
    out["hybrid_interval_frequency_score"] = (
        rank01(out["interval_overdue_baseline"]) * 0.6
        + rank01(out["frequency_decay_baseline"]) * 0.25
        + rank01(out["recency_only_baseline"]) * 0.15
    )
    out["current_interval_over_median"] = out["interval_overdue_baseline"]
    return out


def rank01(values: pd.Series) -> pd.Series:
    vals = pd.to_numeric(values, errors="coerce")
    if vals.notna().sum() == 0:
        return pd.Series(np.nan, index=values.index)
    return vals.rank(pct=True)
