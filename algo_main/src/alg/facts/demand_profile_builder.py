"""Build as-of-cutoff demand profile features."""

from __future__ import annotations

import numpy as np
import pandas as pd

from alg.facts.purchase_event_builder import ENTITY_KEYS
from alg.utils.months import month_diff, to_month_end


DEFAULT_COLD_START = {
    "min_purchase_count_asof_cutoff": 3,
    "min_active_month_count_asof_cutoff": 2,
    "min_months_observed_asof_cutoff": 3,
}


def classify_demand_pattern(adi: float, cv2: float, cold_start: bool) -> str:
    if cold_start:
        return "cold_start"
    if pd.isna(adi) or pd.isna(cv2):
        return "unknown"
    if adi <= 1.32 and cv2 <= 0.49:
        return "smooth"
    if adi <= 1.32 and cv2 > 0.49:
        return "erratic"
    if adi > 1.32 and cv2 <= 0.49:
        return "intermittent"
    return "lumpy"


def build_entity_demand_profile(
    entity_month: pd.DataFrame,
    cutoff_months: list[pd.Timestamp] | None = None,
    cold_start: dict | None = None,
) -> pd.DataFrame:
    """Build demand profile by entity and cutoff using only months <= cutoff."""

    config = {**DEFAULT_COLD_START, **(cold_start or {})}
    if cutoff_months is None:
        cutoff_months = sorted(entity_month["purchase_month"].dropna().unique())
    cutoff_months = [to_month_end(month) for month in cutoff_months]
    rows: list[dict] = []
    for keys, group in entity_month.groupby(ENTITY_KEYS, dropna=False):
        group = group.sort_values("purchase_month")
        for cutoff in cutoff_months:
            hist = group[group["purchase_month"] <= cutoff]
            if hist.empty:
                continue
            first_month = hist["purchase_month"].min()
            months_observed = month_diff(cutoff, first_month) + 1
            active_month_count = int(hist["purchase_month"].nunique())
            purchase_count = int(hist["order_count"].sum())
            active_month_ratio = active_month_count / months_observed if months_observed else np.nan
            active_months = list(hist["purchase_month"].sort_values())
            gaps = [month_diff(later, earlier) * 30.4375 for earlier, later in zip(active_months, active_months[1:])]
            quantity = pd.to_numeric(hist.get("purchase_quantity_sum", pd.Series(dtype=float)), errors="coerce")
            mean_quantity = quantity.mean()
            cv2 = float((quantity.std(ddof=0) / mean_quantity) ** 2) if mean_quantity and not pd.isna(mean_quantity) else np.nan
            adi = months_observed / active_month_count if active_month_count else np.nan
            cold = (
                purchase_count < config["min_purchase_count_asof_cutoff"]
                or active_month_count < config["min_active_month_count_asof_cutoff"]
                or months_observed < config["min_months_observed_asof_cutoff"]
            )
            row = dict(zip(ENTITY_KEYS, keys if isinstance(keys, tuple) else (keys,)))
            row.update(
                {
                    "cutoff_month": cutoff,
                    "purchase_count_asof_cutoff": purchase_count,
                    "active_month_count_asof_cutoff": active_month_count,
                    "months_observed_asof_cutoff": months_observed,
                    "active_month_ratio_asof_cutoff": active_month_ratio,
                    "median_purchase_interval_days_asof_cutoff": float(np.median(gaps)) if gaps else np.nan,
                    "mean_purchase_interval_days_asof_cutoff": float(np.mean(gaps)) if gaps else np.nan,
                    "std_purchase_interval_days_asof_cutoff": float(np.std(gaps)) if gaps else np.nan,
                    "purchase_interval_iqr_asof_cutoff": float(np.percentile(gaps, 75) - np.percentile(gaps, 25)) if gaps else np.nan,
                    "adi_asof_cutoff": adi,
                    "cv2_quantity_asof_cutoff": cv2,
                    "seasonality_strength_asof_cutoff": np.nan,
                    "burstiness_score_asof_cutoff": np.nan,
                    "cold_start_flag": bool(cold),
                    "confidence_score": min(1.0, purchase_count / 12),
                }
            )
            row["demand_pattern_type_asof_cutoff"] = classify_demand_pattern(adi, cv2, bool(cold))
            rows.append(row)
    return pd.DataFrame(rows)
