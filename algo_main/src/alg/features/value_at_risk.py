"""As-of-cutoff value-at-risk feature construction."""

from __future__ import annotations

import numpy as np
import pandas as pd

from alg.facts.purchase_event_builder import ENTITY_KEYS
from alg.utils.months import add_months, to_month_end


def add_value_at_risk_features(
    candidates: pd.DataFrame,
    entity_month: pd.DataFrame,
    horizons: tuple[int, ...] = (3, 6, 12),
    lookback_months: int = 12,
) -> pd.DataFrame:
    """Estimate value at risk using only prior months up to cutoff."""

    out = candidates.copy()
    out["cutoff_month"] = to_month_end(out["cutoff_month"])
    monthly = entity_month.copy()
    monthly["purchase_month"] = to_month_end(monthly["purchase_month"])
    groups = {
        key if isinstance(key, tuple) else (key,): group.sort_values("purchase_month")
        for key, group in monthly.groupby(ENTITY_KEYS, dropna=False)
    }

    amount_col = "purchase_amount_sum"
    quantity_col = "purchase_quantity_sum"
    amount_avgs = []
    quantity_avgs = []
    for record in out.itertuples(index=False):
        key = tuple(getattr(record, column) for column in ENTITY_KEYS)
        cutoff = getattr(record, "cutoff_month")
        start = add_months(cutoff, -(lookback_months - 1))
        group = groups.get(key, monthly.iloc[0:0])
        hist = group.loc[(group["purchase_month"] >= start) & (group["purchase_month"] <= cutoff)]
        amount = pd.to_numeric(hist[amount_col], errors="coerce").sum() if amount_col in hist else 0.0
        quantity = pd.to_numeric(hist[quantity_col], errors="coerce").sum() if quantity_col in hist else 0.0
        amount_avgs.append(float(amount) / lookback_months)
        quantity_avgs.append(float(quantity) / lookback_months)

    out["historical_avg_monthly_amount_asof_cutoff"] = amount_avgs
    out["historical_avg_monthly_quantity_asof_cutoff"] = quantity_avgs
    amount_series = pd.Series(amount_avgs)
    if amount_series.nunique(dropna=True) >= 3:
        out["entity_value_tier_asof_cutoff"] = pd.qcut(amount_series.rank(method="first"), q=3, labels=["low", "mid", "high"]).astype("string")
    else:
        out["entity_value_tier_asof_cutoff"] = np.where(amount_series > 0, "known_value", "no_recent_value")
    out["negative_value_at_risk_amount_flag"] = out["historical_avg_monthly_amount_asof_cutoff"] < 0
    out["negative_value_at_risk_quantity_flag"] = out["historical_avg_monthly_quantity_asof_cutoff"] < 0
    for horizon in horizons:
        amount_raw = out["historical_avg_monthly_amount_asof_cutoff"] * horizon
        quantity_raw = out["historical_avg_monthly_quantity_asof_cutoff"] * horizon
        out[f"value_at_risk_amount_raw_H{horizon}_asof_cutoff"] = amount_raw
        out[f"value_at_risk_quantity_raw_H{horizon}_asof_cutoff"] = quantity_raw
        out[f"value_at_risk_amount_nonnegative_H{horizon}_asof_cutoff"] = amount_raw.clip(lower=0)
        out[f"value_at_risk_quantity_nonnegative_H{horizon}_asof_cutoff"] = quantity_raw.clip(lower=0)
    return out


def add_business_priority_scores(
    predictions: pd.DataFrame,
    horizons: tuple[int, ...] = (3, 6, 12),
) -> pd.DataFrame:
    """Post-process churn probabilities into business priority scores."""

    out = predictions.copy()
    for horizon in horizons:
        probability = f"churn_probability_H{horizon}"
        value = f"value_at_risk_amount_nonnegative_H{horizon}_asof_cutoff"
        if probability in out.columns and value in out.columns:
            out[f"business_priority_score_H{horizon}"] = out[probability] * out[value]
    return out
