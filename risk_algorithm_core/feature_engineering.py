"""Production as-of feature engineering for monthly risk scoring."""

from __future__ import annotations

import numpy as np
import pandas as pd


def engineer_features(entity_base: pd.DataFrame, orders: pd.DataFrame, cutoff_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    if entity_base.empty:
        return entity_base.copy(), pd.DataFrame()
    cutoff = pd.Timestamp(cutoff_date)
    features = entity_base.copy()
    group_cols = ["manufacturer_code", "hospital_code", "drug_group"]
    order_df = orders.copy()
    order_df["order_date"] = pd.to_datetime(order_df["order_date"], errors="coerce")
    order_df["drug_group"] = order_df["drug_code"].astype(str)
    order_df["order_month"] = order_df["order_date"].dt.to_period("M").astype(str)

    intervals = _interval_metrics(order_df, group_cols)
    features = features.merge(intervals, on=group_cols, how="left")
    all_time = order_df.groupby(group_cols, dropna=False).agg(
        active_month_count_asof_cutoff=("order_month", "nunique"),
    ).reset_index()
    features = features.merge(all_time, on=group_cols, how="left")
    for months in [1, 3, 6, 12]:
        features = features.merge(_window_metrics(order_df, group_cols, cutoff, months), on=group_cols, how="left")
    for col in features.columns:
        if col.startswith(("order_count_last_", "active_months_last_", "purchase_quantity_sum_last_", "purchase_amount_sum_last_", "failed_count_last_", "received_count_last_", "terminal_count_last_")):
            features[col] = features[col].fillna(0)
    features["days_since_last_purchase"] = (cutoff - pd.to_datetime(features["last_purchase_date"])).dt.days.clip(lower=0)
    features["months_since_last_purchase"] = features["days_since_last_purchase"] / 30.4375
    features["months_since_last_purchase_asof_cutoff"] = features["months_since_last_purchase"]
    features["purchase_count_asof_cutoff"] = features["purchase_count_total"]
    features["active_month_count_asof_cutoff"] = features["active_month_count_asof_cutoff"].fillna(1)
    features["months_observed_asof_cutoff"] = np.ceil(features["history_months"]).clip(lower=1)
    features["months_since_first_purchase_asof_cutoff"] = features["history_months"]
    features["recency_bucket"] = pd.cut(
        features["months_since_last_purchase"],
        bins=[-0.01, 1, 3, 6, 12, 10_000],
        labels=["m0_1", "m1_3", "m3_6", "m6_12", "m12_plus"],
    ).astype(str)

    features["purchase_frequency_recent"] = features["purchase_count_recent"] / 3.0
    baseline_months = features["history_months"].clip(lower=1.0)
    features["purchase_frequency_baseline"] = features["purchase_count_total"] / baseline_months
    features["frequency_ratio"] = safe_ratio(features["purchase_frequency_recent"], features["purchase_frequency_baseline"])
    features["frequency_drop_flag"] = features["frequency_ratio"] < 0.5
    features["recency_only_baseline"] = features["months_since_last_purchase_asof_cutoff"]
    features["frequency_decay_baseline"] = (1.0 - features["frequency_ratio"].clip(0, 1)).fillna(0.0)

    features["historical_interval_median"] = features["historical_interval_median"].fillna(999.0)
    features["historical_interval_mad"] = features["historical_interval_mad"].fillna(0.0)
    features["current_interval_over_median"] = safe_ratio(features["days_since_last_purchase"], features["historical_interval_median"])
    features["interval_overdue_flag"] = features["current_interval_over_median"] > 1.5
    features["active_month_ratio_asof_cutoff"] = safe_ratio(features["active_month_count_asof_cutoff"], features["months_observed_asof_cutoff"])
    features["adi_asof_cutoff"] = safe_ratio(features["months_observed_asof_cutoff"], features["active_month_count_asof_cutoff"])
    features["median_purchase_interval_days_asof_cutoff"] = features["historical_interval_median"]
    features["mean_purchase_interval_days_asof_cutoff"] = features["historical_interval_mean"].fillna(features["historical_interval_median"])
    features["std_purchase_interval_days_asof_cutoff"] = features["historical_interval_std"].fillna(0.0)
    features["purchase_interval_iqr_asof_cutoff"] = features["historical_interval_iqr"].fillna(0.0)
    features["interval_overdue_baseline"] = features["current_interval_over_median"]

    features["purchase_quantity_recent"] = features["purchase_quantity_recent"].fillna(0.0)
    features["purchase_quantity_baseline"] = safe_ratio(features["purchase_quantity_total"], baseline_months) * 3.0
    features["quantity_ratio"] = safe_ratio(features["purchase_quantity_recent"], features["purchase_quantity_baseline"])
    features["quantity_drop_flag"] = features["quantity_ratio"] < 0.5
    features["cv2_quantity_asof_cutoff"] = features["quantity_cv2"].fillna(0.0)
    features["seasonality_strength_asof_cutoff"] = 0.0
    features["burstiness_score_asof_cutoff"] = features["historical_interval_mad"].fillna(0.0)
    features["hybrid_interval_frequency_score"] = (
        0.5 * features["current_interval_over_median"].clip(0, 4) / 4
        + 0.5 * features["frequency_decay_baseline"].clip(0, 1)
    )

    features["avg_order_amount"] = safe_ratio(features["order_amount_total"], features["purchase_count_total"])
    features["recent_order_amount"] = features["order_amount_recent"].fillna(0.0)
    features["value_at_risk_proxy"] = features["avg_order_amount"] * 3.0
    features["potential_value_level"] = pd.cut(
        features["value_at_risk_proxy"].rank(method="average", pct=True),
        bins=[-0.01, 0.5, 0.8, 1.0],
        labels=["low", "medium", "high"],
    ).astype(str)
    features["demand_shape_label"] = features.apply(_demand_shape, axis=1)
    features["demand_pattern_type_asof_cutoff"] = features["demand_shape_label"]
    features["cold_start_flag"] = features["history_sufficiency_flag"].eq("history_insufficient")
    features["confidence_score"] = features["history_sufficiency_flag"].map({"history_sufficient": 1.0, "history_medium": 0.65}).fillna(0.25)
    features["probability_display_level"] = np.where(
        features["history_sufficiency_flag"].eq("history_sufficient"),
        "probability_allowed",
        "risk_band_only",
    )
    features["display_mode"] = np.where(
        features["probability_display_level"].eq("probability_allowed"),
        "show_probability",
        "show_risk_band",
    )
    features["first_purchase_month"] = pd.to_datetime(features["first_purchase_date"]).dt.to_period("M").astype(str)
    features["one_shot_attention_score"] = np.where(features["is_one_shot"], features["value_at_risk_proxy"].rank(pct=True), 0.0)
    features["one_shot_flag"] = features["is_one_shot"]
    features["one_shot_silence_months"] = np.where(features["is_one_shot"], features["months_since_last_purchase_asof_cutoff"], 0.0)
    province_source = "province_code" if "province_code" in features.columns else "region_code"
    features["province_code"] = _series_or_default(features, province_source, "").fillna("").astype(str)
    features["city_code"] = _series_or_default(features, "city_code", "").fillna("").astype(str)
    features["county_code"] = _series_or_default(features, "county_code", "").fillna("").astype(str)
    features["hospital_level_code"] = _series_or_default(features, "hospital_level", "").fillna("").astype(str)
    features["ownership_type_code"] = _series_or_default(features, "ownership_type_code", "unknown").fillna("unknown").astype(str)
    features["drug_category_code"] = _series_or_default(features, "drug_category", "").fillna("").astype(str)
    features["last_order_phase_code_asof_cutoff"] = "unknown"
    features["last_delivery_state_code_asof_cutoff"] = "unknown"
    features["last_order_failure_flag_asof_cutoff"] = 0

    quality = pd.DataFrame(
        [
            {"metric": "feature_rows", "value": len(features)},
            {"metric": "history_sufficient_rows", "value": int(features["history_sufficiency_flag"].eq("history_sufficient").sum())},
            {"metric": "one_shot_rows", "value": int(features["is_one_shot"].sum())},
        ]
    )
    return features, quality


def safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    den2 = den.replace(0, np.nan)
    return (num / den2).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _series_or_default(df: pd.DataFrame, column: str, default: object) -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series(default, index=df.index)


def _interval_metrics(orders: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows = []
    for keys, part in orders.sort_values("order_date").groupby(group_cols, dropna=False):
        dates = pd.to_datetime(part["order_date"]).dropna().sort_values()
        intervals = dates.diff().dt.days.dropna()
        quantities = pd.to_numeric(part.get("order_quantity"), errors="coerce").dropna()
        if intervals.empty:
            median = np.nan
            mad = np.nan
            mean = np.nan
            std = np.nan
            iqr = np.nan
        else:
            median = float(intervals.median())
            mad = float((intervals - median).abs().median())
            mean = float(intervals.mean())
            std = float(intervals.std(ddof=0))
            iqr = float(intervals.quantile(0.75) - intervals.quantile(0.25))
        if quantities.empty or quantities.mean() == 0:
            cv2 = np.nan
        else:
            cv2 = float((quantities.std(ddof=0) / quantities.mean()) ** 2)
        key_values = keys if isinstance(keys, tuple) else (keys,)
        rows.append(
            {
                **dict(zip(group_cols, key_values)),
                "historical_interval_median": median,
                "historical_interval_mad": mad,
                "historical_interval_mean": mean,
                "historical_interval_std": std,
                "historical_interval_iqr": iqr,
                "quantity_cv2": cv2,
            }
        )
    return pd.DataFrame(rows)


def _window_metrics(orders: pd.DataFrame, group_cols: list[str], cutoff: pd.Timestamp, months: int) -> pd.DataFrame:
    start = cutoff - pd.DateOffset(months=months)
    part = orders[(orders["order_date"] > start) & (orders["order_date"] <= cutoff)].copy()
    if part.empty:
        return pd.DataFrame(columns=group_cols)
    status = part.get("order_status", pd.Series("", index=part.index)).astype(str).str.lower()
    delivery = part.get("delivery_status", pd.Series("", index=part.index)).astype(str).str.lower()
    part["_failed_flag"] = status.str.contains("fail|reject|cancel|退|拒", regex=True, na=False).astype(int)
    part["_received_flag"] = delivery.str.contains("receive|arrive|delivered|到|收", regex=True, na=False).astype(int)
    part["_terminal_flag"] = 1
    return part.groupby(group_cols, dropna=False).agg(
        **{
            f"order_count_last_{months}m_asof_cutoff": ("order_id", "count"),
            f"active_months_last_{months}m_asof_cutoff": ("order_month", "nunique"),
            f"purchase_quantity_sum_last_{months}m_asof_cutoff": ("order_quantity", "sum"),
            f"purchase_amount_sum_last_{months}m_asof_cutoff": ("order_amount", "sum"),
            f"failed_count_last_{months}m_asof_cutoff": ("_failed_flag", "sum"),
            f"received_count_last_{months}m_asof_cutoff": ("_received_flag", "sum"),
            f"terminal_count_last_{months}m_asof_cutoff": ("_terminal_flag", "sum"),
        }
    ).reset_index()


def _demand_shape(row: pd.Series) -> str:
    count = int(row.get("purchase_count_total", 0))
    history = float(row.get("history_months", 0))
    if count <= 1:
        return "one_shot"
    if history >= 12 and count >= 8 and float(row.get("frequency_ratio", 1.0)) >= 0.7:
        return "recurring"
    if count < 4:
        return "intermittent"
    return "lumpy"
