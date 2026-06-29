"""Build cutoff feature tables for alive prediction."""

from __future__ import annotations

import numpy as np
import pandas as pd

from alg.facts.purchase_event_builder import ENTITY_KEYS
from alg.utils.months import add_months, month_diff, to_month_end


def _candidate_key_cols() -> list[str]:
    return ENTITY_KEYS + ["cutoff_month"]


def _history_join(entity_month: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    monthly = entity_month.copy()
    monthly["purchase_month"] = to_month_end(monthly["purchase_month"])
    base = candidates[_candidate_key_cols()].copy()
    base["cutoff_month"] = to_month_end(base["cutoff_month"])
    hist = base.merge(monthly, on=ENTITY_KEYS, how="left")
    return hist[hist["purchase_month"].notna() & (hist["purchase_month"] <= hist["cutoff_month"])].copy()


def _merge_agg(features: pd.DataFrame, agg: pd.DataFrame) -> pd.DataFrame:
    if agg.empty:
        return features
    return features.merge(agg, on=_candidate_key_cols(), how="left")


def _latest_asof(hist: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    existing = [column for column in columns if column in hist.columns]
    if not existing or hist.empty:
        return pd.DataFrame(columns=_candidate_key_cols())
    latest = hist.sort_values("purchase_month").groupby(_candidate_key_cols(), dropna=False).tail(1)
    return latest[_candidate_key_cols() + existing]


def _qcut_value_tier(values: pd.Series) -> pd.Series:
    if values.nunique(dropna=True) >= 3:
        return pd.qcut(values.rank(method="first"), q=3, labels=["low", "mid", "high"]).astype("string")
    return pd.Series(np.where(values > 0, "known_value", "no_recent_value"), index=values.index, dtype="string")


def build_alive_prediction_feature_table(
    entity_month: pd.DataFrame,
    candidates: pd.DataFrame,
    demand_profile: pd.DataFrame | None = None,
    include_status_history: bool = False,
    horizons: tuple[int, ...] = (3, 6, 12),
) -> pd.DataFrame:
    """Build a leakage-safe cutoff feature table skeleton.

    All aggregations use `purchase_month <= cutoff_month`; label-window data is
    never joined into this table.
    """

    base = candidates.copy()
    base["cutoff_month"] = to_month_end(base["cutoff_month"])
    features = base[_candidate_key_cols()].drop_duplicates().copy()
    if "months_since_last_purchase" in base.columns:
        features = features.merge(
            base[_candidate_key_cols() + ["months_since_last_purchase"]],
            on=_candidate_key_cols(),
            how="left",
        )
    for column in ["first_purchase_month", "last_purchase_month_asof_cutoff"]:
        if column in base.columns:
            features = features.merge(base[_candidate_key_cols() + [column]], on=_candidate_key_cols(), how="left")
    features["days_since_last_purchase"] = features.get("months_since_last_purchase", pd.Series(np.nan, index=features.index)) * 30.4375

    hist = _history_join(entity_month, features)
    group_cols = _candidate_key_cols()
    if hist.empty:
        return features

    grouped = hist.groupby(group_cols, dropna=False)
    asof = grouped.agg(
        purchase_count_asof_cutoff=("order_count", "sum"),
        active_month_count_asof_cutoff=("purchase_month", "nunique"),
        first_purchase_month_asof_cutoff=("purchase_month", "min"),
    ).reset_index()
    asof["months_observed_asof_cutoff"] = [
        month_diff(cutoff, first_month) + 1
        for cutoff, first_month in zip(asof["cutoff_month"], asof["first_purchase_month_asof_cutoff"])
    ]
    asof = asof.drop(columns=["first_purchase_month_asof_cutoff"])
    features = _merge_agg(features, asof)
    if "first_purchase_month" in features.columns:
        features["first_purchase_month_asof_cutoff"] = features["first_purchase_month"]
        features["months_since_first_purchase_asof_cutoff"] = [
            month_diff(cutoff, first_month) if pd.notna(first_month) else np.nan
            for cutoff, first_month in zip(features["cutoff_month"], features["first_purchase_month_asof_cutoff"])
        ]
    if "last_purchase_month_asof_cutoff" in features.columns:
        features["months_since_last_purchase_asof_cutoff"] = [
            month_diff(cutoff, last_month) if pd.notna(last_month) else np.nan
            for cutoff, last_month in zip(features["cutoff_month"], features["last_purchase_month_asof_cutoff"])
        ]

    for months in [1, 3, 6, 12]:
        start = hist["cutoff_month"].map(lambda cutoff, m=months: add_months(cutoff, -(m - 1)))
        win = hist[hist["purchase_month"] >= start]
        grouped_win = win.groupby(group_cols, dropna=False)
        named_aggs = {
            f"order_count_last_{months}m_asof_cutoff": ("order_count", "sum"),
            f"active_months_last_{months}m_asof_cutoff": ("purchase_month", "nunique"),
        }
        if "purchase_quantity_sum" in win.columns:
            named_aggs[f"purchase_quantity_sum_last_{months}m_asof_cutoff"] = ("purchase_quantity_sum", "sum")
        if "purchase_amount_sum" in win.columns:
            named_aggs[f"purchase_amount_sum_last_{months}m_asof_cutoff"] = ("purchase_amount_sum", "sum")
        agg = grouped_win.agg(**named_aggs).reset_index()
        features = _merge_agg(features, agg)

    value_cols = [
        "purchase_amount_sum_last_12m_asof_cutoff",
        "purchase_quantity_sum_last_12m_asof_cutoff",
    ]
    for column in value_cols:
        if column not in features:
            features[column] = 0.0
    features["historical_avg_monthly_amount_asof_cutoff"] = features["purchase_amount_sum_last_12m_asof_cutoff"].fillna(0) / 12
    features["historical_avg_monthly_quantity_asof_cutoff"] = features["purchase_quantity_sum_last_12m_asof_cutoff"].fillna(0) / 12
    features["entity_value_tier_asof_cutoff"] = _qcut_value_tier(features["historical_avg_monthly_amount_asof_cutoff"])
    features["negative_value_at_risk_amount_flag"] = features["historical_avg_monthly_amount_asof_cutoff"] < 0
    features["negative_value_at_risk_quantity_flag"] = features["historical_avg_monthly_quantity_asof_cutoff"] < 0
    for horizon in horizons:
        amount_raw = features["historical_avg_monthly_amount_asof_cutoff"] * horizon
        quantity_raw = features["historical_avg_monthly_quantity_asof_cutoff"] * horizon
        features[f"value_at_risk_amount_raw_H{horizon}_asof_cutoff"] = amount_raw
        features[f"value_at_risk_quantity_raw_H{horizon}_asof_cutoff"] = quantity_raw
        features[f"value_at_risk_amount_nonnegative_H{horizon}_asof_cutoff"] = amount_raw.clip(lower=0)
        features[f"value_at_risk_quantity_nonnegative_H{horizon}_asof_cutoff"] = quantity_raw.clip(lower=0)

    features["one_shot_flag"] = features["purchase_count_asof_cutoff"] == 1
    features["one_shot_silence_months"] = features["months_since_last_purchase_asof_cutoff"]

    if include_status_history:
        for months in [3, 6]:
            start = hist["cutoff_month"].map(lambda cutoff, m=months: add_months(cutoff, -(m - 1)))
            win = hist[hist["purchase_month"] >= start]
            grouped_win = win.groupby(group_cols, dropna=False)
            status_aggs = {}
            if "failed_count" in win:
                status_aggs[f"failed_count_last_{months}m_asof_cutoff"] = ("failed_count", "sum")
            if "received_count" in win:
                status_aggs[f"received_count_last_{months}m_asof_cutoff"] = ("received_count", "sum")
            if months == 6 and "terminal_count" in win:
                status_aggs["terminal_count_last_6m_asof_cutoff"] = ("terminal_count", "sum")
            if status_aggs:
                agg = grouped_win.agg(**status_aggs, order_count_for_rate=("order_count", "sum")).reset_index()
                if months == 6:
                    if "failed_count_last_6m_asof_cutoff" in agg:
                        agg["failed_rate_last_6m_asof_cutoff"] = agg["failed_count_last_6m_asof_cutoff"] / agg["order_count_for_rate"].replace(0, np.nan)
                    if "received_count_last_6m_asof_cutoff" in agg:
                        agg["received_rate_last_6m_asof_cutoff"] = agg["received_count_last_6m_asof_cutoff"] / agg["order_count_for_rate"].replace(0, np.nan)
                agg = agg.drop(columns=["order_count_for_rate"])
                features = _merge_agg(features, agg)
        latest = _latest_asof(
            hist,
            ["last_order_phase_code_in_month", "last_delivery_state_code_in_month", "last_order_failure_flag_in_month"],
        ).rename(
            columns={
                "last_order_phase_code_in_month": "last_order_phase_code_asof_cutoff",
                "last_delivery_state_code_in_month": "last_delivery_state_code_asof_cutoff",
                "last_order_failure_flag_in_month": "last_order_failure_flag_asof_cutoff",
            }
        )
        features = _merge_agg(features, latest)

    static_cols = [
        "province_code",
        "city_code",
        "county_code",
        "hospital_level_code",
        "ownership_type_code",
        "drug_category_code",
    ]
    static_latest = _latest_asof(hist, static_cols)
    features = _merge_agg(features, static_latest)

    if demand_profile is not None and not demand_profile.empty:
        demand = demand_profile.copy()
        demand["cutoff_month"] = to_month_end(demand["cutoff_month"])
        features = features.merge(demand, on=group_cols, how="left", suffixes=("", "_demand"))

    zero_fill_prefixes = (
        "order_count_last_",
        "active_months_last_",
        "purchase_quantity_sum_last_",
        "purchase_amount_sum_last_",
        "failed_count_last_",
        "received_count_last_",
        "terminal_count_last_",
    )
    for column in features.columns:
        if column.startswith(zero_fill_prefixes):
            features[column] = features[column].fillna(0)
    return features.reset_index(drop=True)
