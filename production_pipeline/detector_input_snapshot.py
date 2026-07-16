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
    return build_detector_input_snapshot_from_prepared(
        prepare_detector_orders(orders),
        observation_date,
    )


def prepare_detector_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Normalize and sort the minimal raw-fact frame once for many run dates."""
    missing = REQUIRED_ORDER_COLUMNS.difference(orders.columns)
    if missing:
        raise ValueError(f"Detector snapshot is missing required order columns: {sorted(missing)}")
    work = orders.loc[:, list(REQUIRED_ORDER_COLUMNS)].copy()
    work["order_date"] = pd.to_datetime(work["order_date"], errors="coerce").dt.normalize()
    work["order_quantity"] = pd.to_numeric(work["order_quantity"], errors="coerce").fillna(0.0)
    work = work.loc[work["order_date"].notna()].copy()
    work["entity_id"] = (
        work["manufacturer_code"].astype(str)
        + "|"
        + work["hospital_code"].astype(str)
        + "|"
        + work["drug_code"].astype(str)
    )
    return work.sort_values(["entity_id", "order_date"], kind="mergesort").reset_index(drop=True)


def build_detector_input_snapshot_from_prepared(
    prepared_orders: pd.DataFrame,
    observation_date: str,
) -> pd.DataFrame:
    """Build one date's rule inputs without per-entity Python loops."""
    as_of = pd.Timestamp(observation_date).normalize()
    work = prepared_orders.loc[prepared_orders["order_date"].le(as_of)].copy()
    if work.empty:
        return pd.DataFrame(columns=_SNAPSHOT_COLUMNS)
    recent_start = as_of - pd.DateOffset(months=3)
    baseline_start = as_of - pd.DateOffset(months=12)
    dimensions = (
        work.groupby("entity_id", sort=False)[["manufacturer_code", "hospital_code", "drug_code"]]
        .first()
        .rename(columns={"drug_code": "drug_group"})
    )
    aggregate = work.groupby("entity_id", sort=False).agg(
        last_purchase=("order_date", "max"),
        purchase_count_total=("order_date", "size"),
    )
    gaps = work.groupby("entity_id", sort=False)["order_date"].diff().dt.days
    gap_frame = pd.DataFrame({"entity_id": work["entity_id"].to_numpy(), "gap": gaps.to_numpy()}).dropna()
    if gap_frame.empty:
        aggregate["historical_interval_median"] = 0.0
        aggregate["historical_interval_mad"] = 0.0
    else:
        median = gap_frame.groupby("entity_id", sort=False)["gap"].median().rename("historical_interval_median")
        gap_frame = gap_frame.join(median, on="entity_id")
        mad = (
            (gap_frame["gap"] - gap_frame["historical_interval_median"]).abs()
            .groupby(gap_frame["entity_id"], sort=False)
            .median()
            .rename("historical_interval_mad")
        )
        aggregate = aggregate.join(median).join(mad).fillna(
            {"historical_interval_median": 0.0, "historical_interval_mad": 0.0}
        )
    recent = _window_aggregate(work.loc[work["order_date"].gt(recent_start)], "recent")
    baseline = _window_aggregate(
        work.loc[work["order_date"].gt(baseline_start) & work["order_date"].le(recent_start)],
        "baseline",
    )
    out = dimensions.join(aggregate).join(recent).join(baseline).fillna(
        {
            "recent_quantity": 0.0,
            "baseline_quantity": 0.0,
            "recent_purchase_count": 0,
            "baseline_purchase_count": 0,
        }
    )
    out["tenant_id"] = "default_tenant"
    out["observation_date"] = as_of.date().isoformat()
    out["days_since_last_purchase"] = (as_of - out["last_purchase"]).dt.days.astype(int)
    out["recent_frequency"] = out["recent_purchase_count"].astype(float) / 3.0
    out["purchase_frequency_baseline"] = out["baseline_purchase_count"].astype(float) / 9.0
    out["quantity_ratio"] = out["recent_quantity"] / out["baseline_quantity"].where(out["baseline_quantity"].gt(0))
    out["frequency_ratio"] = out["recent_frequency"] / out["purchase_frequency_baseline"].where(
        out["purchase_frequency_baseline"].gt(0)
    )
    return out.reset_index().loc[:, _SNAPSHOT_COLUMNS]


def _window_aggregate(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=[f"{prefix}_quantity", f"{prefix}_purchase_count"])
    return frame.groupby("entity_id", sort=False).agg(
        **{
            f"{prefix}_quantity": ("order_quantity", "sum"),
            f"{prefix}_purchase_count": ("order_date", "size"),
        }
    )


def _ratio(numerator: float, denominator: float) -> float:
    return math.nan if denominator <= 0 else numerator / denominator


_SNAPSHOT_COLUMNS = [
    "entity_id", "tenant_id", "manufacturer_code", "hospital_code", "drug_group", "observation_date",
    "days_since_last_purchase", "historical_interval_median", "historical_interval_mad", "purchase_count_total",
    "recent_quantity", "baseline_quantity", "quantity_ratio", "recent_purchase_count", "baseline_purchase_count",
    "recent_frequency", "purchase_frequency_baseline", "frequency_ratio",
]
