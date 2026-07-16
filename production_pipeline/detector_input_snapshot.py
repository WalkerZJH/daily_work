"""Build fact-only Daily Detector inputs from canonical cleaned orders."""

from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_ORDER_COLUMNS = {
    "order_date",
    "manufacturer_code",
    "hospital_code",
    "drug_code",
    "order_quantity",
}
OPTIONAL_ORDER_COLUMNS = [
    "row_uid",
    "order_id",
    "order_amount",
    "purchase_unit",
    "purchase_unit_price",
]


def build_detector_input_snapshot(orders: pd.DataFrame, observation_date: str) -> pd.DataFrame:
    """Return as-of rule inputs without monthly features or model outputs."""
    return build_detector_input_snapshot_from_prepared(prepare_detector_orders(orders), observation_date)


def prepare_detector_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Normalize the already-cleaned fact frame once for many run dates."""
    missing = REQUIRED_ORDER_COLUMNS.difference(orders.columns)
    if missing:
        raise ValueError(f"Detector snapshot is missing required order columns: {sorted(missing)}")
    columns = sorted(REQUIRED_ORDER_COLUMNS) + [column for column in OPTIONAL_ORDER_COLUMNS if column in orders]
    work = orders.loc[:, columns].copy()
    work["order_date"] = pd.to_datetime(work["order_date"], errors="coerce").dt.normalize()
    for column in ["order_quantity", "order_amount", "purchase_unit_price"]:
        if column not in work:
            work[column] = np.nan
        work[column] = pd.to_numeric(work[column], errors="coerce")
    if "purchase_unit" not in work:
        work["purchase_unit"] = pd.Series(pd.NA, index=work.index, dtype="string")
    work["purchase_unit"] = work["purchase_unit"].astype("string").str.strip()
    if "order_id" not in work:
        work["order_id"] = pd.Series(work.index.astype(str), index=work.index, dtype="string")
    work = work.loc[work["order_date"].notna()].copy()
    work["entity_id"] = (
        work["manufacturer_code"].astype(str)
        + "|"
        + work["hospital_code"].astype(str)
        + "|"
        + work["drug_code"].astype(str)
    )
    return work.sort_values(["entity_id", "order_date", "order_id"], kind="mergesort").reset_index(drop=True)


def build_detector_input_snapshot_from_prepared(
    prepared_orders: pd.DataFrame,
    observation_date: str,
) -> pd.DataFrame:
    """Build one date's rule inputs with grouped/vectorized operations."""
    as_of = pd.Timestamp(observation_date).normalize()
    work = prepared_orders.loc[prepared_orders["order_date"].le(as_of)].copy()
    if work.empty:
        return pd.DataFrame(columns=_SNAPSHOT_COLUMNS)
    recent_start = as_of - pd.Timedelta(days=90)
    baseline_start = as_of - pd.Timedelta(days=365)

    dimensions = (
        work.groupby("entity_id", sort=False)[
            ["manufacturer_code", "hospital_code", "drug_code", "purchase_unit"]
        ]
        .last()
        .rename(columns={"drug_code": "drug_group"})
    )
    unit_count = work.groupby("entity_id", sort=False)["purchase_unit"].nunique(dropna=True)
    purchase_days = work[["entity_id", "order_date"]].drop_duplicates()
    aggregate = purchase_days.groupby("entity_id", sort=False).agg(
        last_purchase=("order_date", "max"),
        first_purchase_date=("order_date", "min"),
        purchase_count_total=("order_date", "size"),
    )
    aggregate["entity_purchase_unit_count"] = unit_count
    gaps = purchase_days.groupby("entity_id", sort=False)["order_date"].diff().dt.days
    gap_frame = pd.DataFrame(
        {"entity_id": purchase_days["entity_id"].to_numpy(), "gap": gaps.to_numpy()}
    ).dropna()
    if gap_frame.empty:
        aggregate["historical_interval_median"] = 0.0
        aggregate["historical_interval_mad"] = 0.0
    else:
        median = gap_frame.groupby("entity_id", sort=False)["gap"].median().rename(
            "historical_interval_median"
        )
        gap_frame = gap_frame.join(median, on="entity_id")
        mad = (
            (gap_frame["gap"] - gap_frame["historical_interval_median"])
            .abs()
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
    current = _current_purchase_facts(work.loc[work["order_date"].eq(as_of)])
    first = _first_purchase_facts(work)
    previous = (
        work.loc[work["order_date"].lt(as_of)]
        .groupby("entity_id", sort=False)["order_date"]
        .max()
        .rename("previous_purchase_date")
    )
    demand = _demand_shape(work, as_of)

    out = dimensions.join(aggregate).join(recent).join(baseline).join(current).join(first).join(previous).join(demand)
    for column, default in {
        "recent_quantity": 0.0,
        "baseline_quantity": 0.0,
        "recent_amount": 0.0,
        "baseline_amount": 0.0,
        "recent_order_count": 0,
        "baseline_order_count": 0,
        "current_order_count": 0,
    }.items():
        out[column] = pd.to_numeric(out[column], errors="coerce").fillna(default)
    out["tenant_id"] = "default_tenant"
    out["observation_date"] = as_of.date().isoformat()
    out["days_since_last_purchase"] = (as_of - out["last_purchase"]).dt.days.astype(int)
    out["recent_window_start"] = recent_start.date().isoformat()
    out["recent_window_end"] = as_of.date().isoformat()
    out["baseline_window_start"] = baseline_start.date().isoformat()
    out["baseline_window_end"] = recent_start.date().isoformat()
    out["recent_frequency"] = out["recent_order_count"].astype(float) / 3.0
    out["purchase_frequency_baseline"] = out["baseline_order_count"].astype(float) / 9.0
    recent_quantity_rate = out["recent_quantity"].astype(float) / 3.0
    baseline_quantity_rate = out["baseline_quantity"].astype(float) / 9.0
    out["quantity_ratio"] = recent_quantity_rate / baseline_quantity_rate.where(baseline_quantity_rate.gt(0))
    recent_amount_rate = out["recent_amount"].astype(float) / 3.0
    baseline_amount_rate = out["baseline_amount"].astype(float) / 9.0
    out["amount_ratio"] = recent_amount_rate / baseline_amount_rate.where(baseline_amount_rate.gt(0))
    out["frequency_ratio"] = out["recent_frequency"] / out["purchase_frequency_baseline"].where(
        out["purchase_frequency_baseline"].gt(0)
    )
    out["current_purchase_flag"] = out["current_order_count"].gt(0)
    out["silence_days"] = (as_of - pd.to_datetime(out["previous_purchase_date"])).dt.days
    out["data_history_start"] = work["order_date"].min().date().isoformat()

    out = _join_price_evidence(out.reset_index(), work, as_of, recent_start, baseline_start)
    for column in _SNAPSHOT_COLUMNS:
        if column not in out:
            out[column] = pd.NA
    return out.loc[:, _SNAPSHOT_COLUMNS].reset_index(drop=True)


def _window_aggregate(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=[f"{prefix}_quantity", f"{prefix}_amount", f"{prefix}_order_count"]
        )
    grouped = frame.groupby("entity_id", sort=False)
    result = grouped.agg(
        **{
            f"{prefix}_quantity": ("order_quantity", "sum"),
            f"{prefix}_amount": ("order_amount", "sum"),
        }
    )
    counts = frame[["entity_id", "order_date"]].drop_duplicates().groupby("entity_id").size()
    result[f"{prefix}_order_count"] = counts
    return result


def _current_purchase_facts(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["current_order_count", "current_purchase_quantity", "current_purchase_amount"])
    return frame.groupby("entity_id", sort=False).agg(
        current_order_count=("order_id", "nunique"),
        current_purchase_quantity=("order_quantity", "sum"),
        current_purchase_amount=("order_amount", "sum"),
        current_order_id=("order_id", "first"),
        current_unit_price=("purchase_unit_price", "median"),
    )


def _first_purchase_facts(work: pd.DataFrame) -> pd.DataFrame:
    first = work.sort_values(["entity_id", "order_date", "order_id"], kind="mergesort").groupby(
        "entity_id", sort=False
    ).first()
    return first[["order_id", "order_quantity", "order_amount"]].rename(
        columns={
            "order_id": "first_order_id",
            "order_quantity": "first_purchase_quantity",
            "order_amount": "first_purchase_amount",
        }
    )


def _demand_shape(work: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    monthly = work.assign(purchase_month=work["order_date"].dt.to_period("M").dt.to_timestamp()).groupby(
        ["entity_id", "purchase_month"], sort=False
    ).agg(monthly_quantity=("order_quantity", "sum"))
    shape = monthly.reset_index().groupby("entity_id", sort=False).agg(
        active_month_count=("purchase_month", "nunique"),
        first_active_month=("purchase_month", "min"),
        monthly_quantity_mean=("monthly_quantity", "mean"),
        monthly_quantity_std=("monthly_quantity", "std"),
    )
    shape["months_observed"] = (
        (as_of.year - shape["first_active_month"].dt.year) * 12
        + as_of.month
        - shape["first_active_month"].dt.month
        + 1
    )
    shape["adi"] = shape["months_observed"] / shape["active_month_count"].where(
        shape["active_month_count"].gt(0)
    )
    coefficient = shape["monthly_quantity_std"].fillna(0) / shape["monthly_quantity_mean"].where(
        shape["monthly_quantity_mean"].gt(0)
    )
    shape["cv2_quantity"] = coefficient.pow(2).fillna(0)
    shape["demand_shape_label"] = np.select(
        [
            shape["adi"].lt(1.32) & shape["cv2_quantity"].lt(0.49),
            shape["adi"].lt(1.32) & shape["cv2_quantity"].ge(0.49),
            shape["adi"].ge(1.32) & shape["cv2_quantity"].lt(0.49),
        ],
        ["smooth", "erratic", "intermittent"],
        default="lumpy",
    )
    return shape[["active_month_count", "months_observed", "adi", "cv2_quantity", "demand_shape_label"]]


def _join_price_evidence(
    out: pd.DataFrame,
    work: pd.DataFrame,
    as_of: pd.Timestamp,
    recent_start: pd.Timestamp,
    baseline_start: pd.Timestamp,
) -> pd.DataFrame:
    valid_price = work.loc[work["purchase_unit_price"].gt(0) & work["purchase_unit"].notna()].copy()
    keys = ["entity_id", "purchase_unit"]
    recent = valid_price.loc[valid_price["order_date"].gt(recent_start)].groupby(keys, sort=False).agg(
        price_recent_order_count=("order_id", "nunique"),
        recent_price=("purchase_unit_price", "median"),
        min_price=("purchase_unit_price", "min"),
        max_price=("purchase_unit_price", "max"),
        median_price=("purchase_unit_price", "median"),
    )
    baseline = valid_price.loc[
        valid_price["order_date"].gt(baseline_start) & valid_price["order_date"].le(recent_start)
    ].groupby(keys, sort=False).agg(
        price_baseline_order_count=("order_id", "nunique"),
        baseline_price=("purchase_unit_price", "median"),
    )
    price = recent.join(baseline, how="outer").reset_index()
    price["price_spread_ratio"] = price["max_price"] / price["min_price"].where(price["min_price"].gt(0))
    price["price_ratio"] = price["recent_price"] / price["baseline_price"].where(price["baseline_price"].gt(0))
    out = out.merge(price, on=keys, how="left", validate="one_to_one")

    reference = valid_price.loc[valid_price["order_date"].lt(as_of)].groupby(
        ["drug_code", "purchase_unit"], sort=False
    ).agg(
        market_reference_price=("purchase_unit_price", lambda values: values.quantile(0.05)),
        reference_order_count=("order_id", "nunique"),
        reference_hospital_count=("hospital_code", "nunique"),
    ).reset_index().rename(columns={"drug_code": "drug_group"})
    return out.merge(reference, on=["drug_group", "purchase_unit"], how="left", validate="many_to_one")


_SNAPSHOT_COLUMNS = [
    "entity_id", "tenant_id", "manufacturer_code", "hospital_code", "drug_group", "purchase_unit",
    "observation_date", "days_since_last_purchase", "historical_interval_median", "historical_interval_mad",
    "purchase_count_total", "entity_purchase_unit_count", "recent_quantity", "baseline_quantity", "quantity_ratio",
    "recent_amount", "baseline_amount", "amount_ratio", "recent_order_count", "baseline_order_count",
    "recent_frequency", "purchase_frequency_baseline", "frequency_ratio", "recent_window_start", "recent_window_end",
    "baseline_window_start", "baseline_window_end", "demand_shape_label", "active_month_count", "months_observed",
    "adi", "cv2_quantity", "current_purchase_flag", "current_order_count", "current_order_id",
    "current_purchase_quantity", "current_purchase_amount", "current_unit_price", "first_purchase_date", "first_order_id",
    "first_purchase_quantity", "first_purchase_amount", "previous_purchase_date", "silence_days", "data_history_start",
    "price_recent_order_count", "price_baseline_order_count", "recent_price", "baseline_price", "price_ratio",
    "min_price", "max_price", "median_price", "price_spread_ratio", "market_reference_price",
    "reference_order_count", "reference_hospital_count",
]
