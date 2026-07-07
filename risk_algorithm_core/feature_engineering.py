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
    order_df["drug_group"] = order_df["drug_code"].astype(str)

    intervals = _interval_metrics(order_df, group_cols)
    features = features.merge(intervals, on=group_cols, how="left")
    features["days_since_last_purchase"] = (cutoff - pd.to_datetime(features["last_purchase_date"])).dt.days.clip(lower=0)
    features["months_since_last_purchase"] = features["days_since_last_purchase"] / 30.4375
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

    features["historical_interval_median"] = features["historical_interval_median"].fillna(999.0)
    features["historical_interval_mad"] = features["historical_interval_mad"].fillna(0.0)
    features["current_interval_over_median"] = safe_ratio(features["days_since_last_purchase"], features["historical_interval_median"])
    features["interval_overdue_flag"] = features["current_interval_over_median"] > 1.5

    features["purchase_quantity_recent"] = features["purchase_quantity_recent"].fillna(0.0)
    features["purchase_quantity_baseline"] = safe_ratio(features["purchase_quantity_total"], baseline_months) * 3.0
    features["quantity_ratio"] = safe_ratio(features["purchase_quantity_recent"], features["purchase_quantity_baseline"])
    features["quantity_drop_flag"] = features["quantity_ratio"] < 0.5

    features["avg_order_amount"] = safe_ratio(features["order_amount_total"], features["purchase_count_total"])
    features["recent_order_amount"] = features["order_amount_recent"].fillna(0.0)
    features["value_at_risk_proxy"] = features["avg_order_amount"] * 3.0
    features["potential_value_level"] = pd.cut(
        features["value_at_risk_proxy"].rank(method="average", pct=True),
        bins=[-0.01, 0.5, 0.8, 1.0],
        labels=["low", "medium", "high"],
    ).astype(str)
    features["demand_shape_label"] = features.apply(_demand_shape, axis=1)
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


def _interval_metrics(orders: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows = []
    for keys, part in orders.sort_values("order_date").groupby(group_cols, dropna=False):
        dates = pd.to_datetime(part["order_date"]).dropna().sort_values()
        intervals = dates.diff().dt.days.dropna()
        if intervals.empty:
            median = np.nan
            mad = np.nan
        else:
            median = float(intervals.median())
            mad = float((intervals - median).abs().median())
        key_values = keys if isinstance(keys, tuple) else (keys,)
        rows.append({**dict(zip(group_cols, key_values)), "historical_interval_median": median, "historical_interval_mad": mad})
    return pd.DataFrame(rows)


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
