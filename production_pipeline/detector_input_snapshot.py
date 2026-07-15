"""Build lightweight, fact-only inputs for the independent daily detector stage."""

from __future__ import annotations

import math

import pandas as pd


REQUIRED_ORDER_COLUMNS = {
    "order_date",
    "manufacturer_code",
    "hospital_code",
    "drug_code",
    "order_quantity",
}


def build_detector_input_snapshot(orders: pd.DataFrame, observation_date: str) -> pd.DataFrame:
    """Return per-entity rule inputs using only orders available on ``observation_date``.

    This intentionally does not import model scoring, monthly feature engineering,
    candidate selection, or monthly result batches.
    """
    missing = REQUIRED_ORDER_COLUMNS.difference(orders.columns)
    if missing:
        raise ValueError(f"Detector snapshot is missing required order columns: {sorted(missing)}")
    as_of = pd.Timestamp(observation_date).normalize()
    work = orders.loc[:, list(REQUIRED_ORDER_COLUMNS)].copy()
    work["order_date"] = pd.to_datetime(work["order_date"], errors="coerce").dt.normalize()
    work["order_quantity"] = pd.to_numeric(work["order_quantity"], errors="coerce").fillna(0.0)
    work = work.loc[work["order_date"].notna() & work["order_date"].le(as_of)].copy()
    if work.empty:
        return pd.DataFrame(columns=_SNAPSHOT_COLUMNS)
    work["entity_id"] = (
        work["manufacturer_code"].astype(str)
        + "|"
        + work["hospital_code"].astype(str)
        + "|"
        + work["drug_code"].astype(str)
    )
    recent_start = as_of - pd.DateOffset(months=3)
    baseline_start = as_of - pd.DateOffset(months=12)
    rows: list[dict[str, object]] = []
    for entity_id, group in work.groupby("entity_id", sort=False):
        group = group.sort_values("order_date", kind="mergesort")
        dates = group["order_date"]
        gaps = dates.diff().dt.days.dropna()
        median_gap = float(gaps.median()) if not gaps.empty else 0.0
        mad_gap = float((gaps - median_gap).abs().median()) if not gaps.empty else 0.0
        recent = group.loc[dates.gt(recent_start)]
        baseline = group.loc[dates.gt(baseline_start) & dates.le(recent_start)]
        recent_frequency = float(len(recent) / 3.0)
        baseline_frequency = float(len(baseline) / 9.0)
        rows.append(
            {
                "entity_id": entity_id,
                "tenant_id": "default_tenant",
                "manufacturer_code": str(group.iloc[0]["manufacturer_code"]),
                "hospital_code": str(group.iloc[0]["hospital_code"]),
                "drug_group": str(group.iloc[0]["drug_code"]),
                "observation_date": as_of.date().isoformat(),
                "days_since_last_purchase": int((as_of - dates.iloc[-1]).days),
                "historical_interval_median": median_gap,
                "historical_interval_mad": mad_gap,
                "purchase_count_total": int(len(group)),
                "recent_quantity": float(recent["order_quantity"].sum()),
                "baseline_quantity": float(baseline["order_quantity"].sum()),
                "quantity_ratio": _ratio(float(recent["order_quantity"].sum()), float(baseline["order_quantity"].sum())),
                "recent_purchase_count": int(len(recent)),
                "baseline_purchase_count": int(len(baseline)),
                "recent_frequency": recent_frequency,
                "purchase_frequency_baseline": baseline_frequency,
                "frequency_ratio": _ratio(recent_frequency, baseline_frequency),
            }
        )
    return pd.DataFrame(rows, columns=_SNAPSHOT_COLUMNS)


def _ratio(numerator: float, denominator: float) -> float:
    return math.nan if denominator <= 0 else numerator / denominator


_SNAPSHOT_COLUMNS = [
    "entity_id", "tenant_id", "manufacturer_code", "hospital_code", "drug_group", "observation_date",
    "days_since_last_purchase", "historical_interval_median", "historical_interval_mad", "purchase_count_total",
    "recent_quantity", "baseline_quantity", "quantity_ratio", "recent_purchase_count", "baseline_purchase_count",
    "recent_frequency", "purchase_frequency_baseline", "frequency_ratio",
]
